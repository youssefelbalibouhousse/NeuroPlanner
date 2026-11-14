"""Génération d'un planning hebdomadaire à partir de chapitres.

Principe : **le LLM (ou l'utilisateur) fournit la structure — chapitres et durées
indicatives — et cet algorithme construit le planning**. Cette séparation rend le
résultat prévisible, testable et indépendant du modèle utilisé.

Modèle d'une journée (identique au plan d'origine, 5 h) :

* 07:30–08:45 · Encodage          « Lecture active — <chapitre> »
* 09:00–10:15 · Pratique          « Exercices — <chapitre> »
* 10:30–12:00 · Approfondissement « Synthèse — <chapitre> »
* 13:30–14:30 · Récupération active (rappel + feuille blanche)

Les 240 premières minutes sont remplies par les chapitres, au prorata de leur
durée ; les 60 dernières sont toujours consacrées au rappel actif.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from neuroplanner.config import DAY_KEYS, DAY_LABELS
from neuroplanner.models import Block, Chapter, Task

#: Durée minimale d'une tâche générée.
MIN_TASK_MINUTES = 5
#: Durée du bloc de récupération active (dernier bloc de la journée).
RECALL_MINUTES = 60
#: Répartition du bloc de récupération : rappel puis feuille blanche.
RECALL_SPLIT = (45, 15)


@dataclass(frozen=True, slots=True)
class Slot:
    """Emplacement d'une journée : horaire, thème et préfixe d'intitulé."""

    start: str
    end: str
    title: str
    intent: str
    prefix: str
    minutes: int


STUDY_SLOTS: tuple[Slot, ...] = (
    Slot("07:30", "08:45", "Encodage", "Encodage profond", "Lecture active", 75),
    Slot("09:00", "10:15", "Pratique", "Récupération guidée", "Exercices", 75),
    Slot("10:30", "12:00", "Approfondissement", "Production concrète", "Synthèse", 90),
)

RECALL_SLOT = Slot(
    "13:30", "14:30", "Récupération active", "Rappel & feuille blanche", "", RECALL_MINUTES
)

#: Contenu étudiable par jour (hors récupération active).
STUDY_MINUTES_PER_DAY: int = sum(slot.minutes for slot in STUDY_SLOTS)
MINUTES_PER_DAY: int = STUDY_MINUTES_PER_DAY + RECALL_MINUTES


def build_week(
    chapters: Sequence[Chapter],
    *,
    domain: str,
    revision_domain: str | None = None,
    day_keys: Sequence[str] = DAY_KEYS,
) -> dict[str, tuple[Block, ...]]:
    """Construit un planning complet (un :class:`Block` par emplacement).

    ``revision_domain`` par défaut : le pilier étudié. Un domaine distinct permet
    de garder le graphique de refocalisation lisible (ex. « Révision Active »).
    """
    if not chapters:
        raise ValueError("Il faut au moins un chapitre pour générer un planning.")
    if not domain.strip():
        raise ValueError("Le pilier d'apprentissage ne peut pas être vide.")

    revision = (revision_domain or domain).strip() or domain
    clean = [_normalise(chapter) for chapter in chapters]
    allocs = _allocate(clean, STUDY_MINUTES_PER_DAY * len(day_keys))
    queue = _Queue(clean, allocs)

    week: dict[str, tuple[Block, ...]] = {}
    for day_key in day_keys:
        blocks = []
        for slot in STUDY_SLOTS:
            tasks = queue.fill(slot, domain)
            blocks.append(
                Block(slot.start, slot.end, slot.title, slot.intent, tuple(tasks))
            )
        blocks.append(_recall_block(queue.day_titles(), revision))
        week[day_key] = tuple(blocks)

    return week


def describe_week(
    week: dict[str, tuple[Block, ...]],
    labels: dict[str, str] | None = None,
) -> str:
    """Résumé lisible du planning généré (aperçu avant application)."""
    names = DAY_LABELS if labels is None else labels
    lines: list[str] = []
    for day_key, blocks in week.items():
        label = names.get(day_key, day_key)
        total = sum(block.minutes for block in blocks)
        tasks = [task for block in blocks for task in block.tasks]
        lines.append(f"{label} · {len(blocks)} blocs · {total} min · {len(tasks)} tâches")
        for block in blocks:
            for task in block.tasks:
                lines.append(f"    {task.minutes:>3} min  {task.label}")
    return "\n".join(lines)


def chapter_titles(week: dict[str, tuple[Block, ...]]) -> list[str]:
    """Chapitres placés dans le planning, dans l'ordre d'apparition."""
    prefixes = tuple(f"{slot.prefix} — " for slot in STUDY_SLOTS)
    seen: list[str] = []
    for blocks in week.values():
        for block in blocks:
            for task in block.tasks:
                for prefix in prefixes:
                    if task.label.startswith(prefix):
                        title = task.label[len(prefix):]
                        if title not in seen:
                            seen.append(title)
                        break
    return seen


# --------------------------------------------------------------------------- #
# Répartition des minutes
# --------------------------------------------------------------------------- #
def _normalise(chapter: Chapter) -> Chapter:
    title = " ".join(chapter.title.split())[:120]
    if not title:
        raise ValueError("Un chapitre a un intitulé vide.")
    minutes = chapter.minutes
    if minutes is not None and minutes <= 0:
        minutes = None
    return Chapter(title=title, minutes=minutes)


def _allocate(chapters: Sequence[Chapter], total: int) -> list[int]:
    """Répartit ``total`` minutes : au prorata si toutes les durées sont connues.

    La somme des allocations vaut exactement ``total`` (méthode du plus fort
    reste), et chaque chapitre reçoit au moins :data:`MIN_TASK_MINUTES`.
    """
    count = len(chapters)
    estimated = [chapter.minutes for chapter in chapters]

    if count * MIN_TASK_MINUTES > total:  # trop de chapitres pour le volume
        raise ValueError(
            f"Trop de chapitres ({count}) pour {total} minutes de contenu : "
            "réduis la liste ou fournis des durées."
        )

    if all(minutes for minutes in estimated):
        weights = [float(minutes) for minutes in estimated]  # type: ignore[arg-type]
        raw = [total * weight / sum(weights) for weight in weights]
        allocs = [int(value) for value in raw]
        remainder = total - sum(allocs)
        order = sorted(range(count), key=lambda i: raw[i] - allocs[i], reverse=True)
        for index in order[:remainder]:
            allocs[index] += 1
    else:
        base, extra = divmod(total, count)
        allocs = [base + (1 if index < extra else 0) for index in range(count)]

    return _enforce_minimum(allocs, total)


def _enforce_minimum(allocs: list[int], total: int) -> list[int]:
    """Garantit ``MIN_TASK_MINUTES`` par chapitre sans changer le total."""
    for index, value in enumerate(allocs):
        if value >= MIN_TASK_MINUTES:
            continue
        missing = MIN_TASK_MINUTES - value
        donor = max(range(len(allocs)), key=lambda i: allocs[i])
        if allocs[donor] - missing < MIN_TASK_MINUTES:
            # Répartition égale : plus simple et toujours valide ici.
            base, extra = divmod(total, len(allocs))
            return [base + (1 if i < extra else 0) for i in range(len(allocs))]
        allocs[donor] -= missing
        allocs[index] += missing
    return allocs


# --------------------------------------------------------------------------- #
# Remplissage des emplacements
# --------------------------------------------------------------------------- #
class _Queue:
    """File de minutes à placer, chapitre par chapitre."""

    def __init__(self, chapters: Sequence[Chapter], allocs: Sequence[int]) -> None:
        self._items = [[chapter.title, minutes] for chapter, minutes in zip(chapters, allocs, strict=True)]
        self._cursor = 0
        self._day: list[str] = []

    def _current(self) -> list | None:
        while self._cursor < len(self._items) and self._items[self._cursor][1] <= 0:
            self._cursor += 1
        return self._items[self._cursor] if self._cursor < len(self._items) else None

    def fill(self, slot: Slot, domain: str) -> list[Task]:
        """Remplit un emplacement avec les chapitres en cours, au plus juste."""
        tasks: list[Task] = []
        remaining = slot.minutes
        while remaining > 0:
            item = self._current()
            if item is None:
                # Le contenu est épuisé (ne devrait pas arriver : la somme des
                # allocations égale la capacité) : on complète par du rappel.
                tasks.append(Task(f"{slot.prefix} — consolidation libre", domain, remaining))
                break
            title, left = item[0], item[1]
            take = min(left, remaining)
            item[1] -= take
            remaining -= take
            tasks.append(Task(f"{slot.prefix} — {title}", domain, take))
            if title not in self._day:
                self._day.append(title)

        return _merge_slivers(tasks, slot)

    def day_titles(self) -> list[str]:
        titles = list(self._day)
        self._day = []
        return titles


def _merge_slivers(tasks: list[Task], slot: Slot) -> list[Task]:
    """Fusionne les reliquats (< 5 min) dans la tâche voisine, à somme constante."""
    merged: list[Task] = []
    for task in tasks:
        if task.minutes >= MIN_TASK_MINUTES or not merged:
            merged.append(task)
            continue
        previous = merged[-1]
        merged[-1] = Task(previous.label, previous.domain, previous.minutes + task.minutes)

    if merged and merged[0].minutes < MIN_TASK_MINUTES and len(merged) > 1:
        first, second = merged[0], merged[1]
        merged[0:2] = [Task(second.label, second.domain, first.minutes + second.minutes)]

    total = sum(task.minutes for task in merged)
    if total != slot.minutes:  # garde-fou : la journée doit rester à 5 h
        raise AssertionError(f"emplacement {slot.title} : {total} min au lieu de {slot.minutes}")
    return merged


def _recall_block(titles: Iterable[str], revision_domain: str) -> Block:
    """Dernier bloc : rappel actif des chapitres du jour + feuille blanche."""
    studied = list(titles)
    if studied:
        head = studied[0] if len(studied) == 1 else f"{studied[0]} (+{len(studied) - 1})"
        recall_label = f"Rappel actif — {head}"
    else:
        recall_label = "Rappel actif — séance précédente"

    return Block(
        RECALL_SLOT.start,
        RECALL_SLOT.end,
        RECALL_SLOT.title,
        RECALL_SLOT.intent,
        (
            Task(recall_label, revision_domain, RECALL_SPLIT[0]),
            Task("Feuille blanche — restitution libre", revision_domain, RECALL_SPLIT[1]),
        ),
    )
