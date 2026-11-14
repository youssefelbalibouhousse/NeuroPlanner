"""Plan d'apprentissage modifiable, persisté dans ``neuro_plan.json``.

Le plan est la **structure** (domaines, blocs, tâches) ; la progression (cases
cochées, sessions de focus) vit dans un fichier séparé (voir ``store.py``).

Document JSON ::

    {
      "version": 1,
      "updated_at": "2026-11-14T23:41:00",
      "domains": [{"name": "Dev & Archi", "color": "#7C9CFF"}],
      "days": {
        "lun": [
          {"start": "07:30", "end": "08:45", "title": "Dev & Archi",
           "intent": "Encodage profond",
           "tasks": [{"id": "lun-0-0", "label": "…", "domain": "Dev & Archi", "minutes": 45}]}
        ]
      }
    }

Ce format est volontairement simple et stable : un futur générateur (LLM ou
import) n'a qu'à produire ce document, ou appeler :meth:`PlanStore.replace_week`
avec des objets :class:`~neuroplanner.models.Block`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from neuroplanner.config import DAY_KEYS, DAY_LABELS
from neuroplanner.data.curriculum import DEFAULT_DOMAINS, RAW_WEEK
from neuroplanner.data.jsonfile import read_json, write_json_atomic
from neuroplanner.models import Block, BlockNode, DayPlan, Domain, TaskNode
from neuroplanner.theme import DOMAIN_PALETTE, FALLBACK_DOMAIN_COLOR

#: Bornes acceptées pour une tâche.
MIN_TASK_MINUTES = 1
MAX_TASK_MINUTES = 240
MAX_NAME_LENGTH = 40
MAX_LABEL_LENGTH = 120


@dataclass(frozen=True, slots=True)
class PlanSnapshot:
    """Vue immuable du plan, pratique pour les tests et l'export."""

    domains: tuple[Domain, ...]
    days: dict[str, DayPlan]


class PlanStore:
    """Source de vérité du planning : domaines, blocs, tâches.

    Toute mutation est persistée immédiatement et invalide le cache des vues.
    Les identifiants de tâches sont stables : éditer le plan ne perd aucune
    coche, alors qu'un identifiant positionnel se décalerait.
    """

    VERSION = 1

    def __init__(self, path: Path | str, *, seed: Mapping[str, Iterable[Block]] | None = None) -> None:
        self.path = Path(path)
        self._domains: list[Domain] = []
        self._days: dict[str, list[dict[str, Any]]] = {}
        self._week: dict[str, DayPlan] | None = None

        raw = read_json(self.path)
        if raw is None:
            self._seed(seed if seed is not None else RAW_WEEK)
            self.save()
        else:
            self._load(raw)

    # -- chargement ------------------------------------------------------- #
    def _seed(self, seed: Mapping[str, Iterable[Block]]) -> None:
        """Construit le plan initial à partir d'une graine (par défaut : curriculum)."""
        self._domains = list(DEFAULT_DOMAINS)
        self._days = {}
        for day_key in DAY_KEYS:
            blocks = list(seed.get(day_key, ()))
            self._days[day_key] = [
                {
                    "start": block.start,
                    "end": block.end,
                    "title": block.title,
                    "intent": block.intent,
                    "tasks": [
                        {
                            # Convention historique : <jour>-<bloc>-<tâche>.
                            "id": f"{day_key}-{block_index}-{task_index}",
                            "label": task.label,
                            "domain": task.domain,
                            "minutes": int(task.minutes),
                        }
                        for task_index, task in enumerate(block.tasks)
                    ],
                }
                for block_index, block in enumerate(blocks)
            ]
        for day_key in DAY_KEYS:
            for block in self._days[day_key]:
                for task in block["tasks"]:
                    self._ensure_domain(task["domain"])
        self._week = None

    def _load(self, raw: dict[str, Any]) -> None:
        domains: list[Domain] = []
        for entry in raw.get("domains", []) if isinstance(raw.get("domains"), list) else []:
            if not isinstance(entry, dict):
                continue
            name = _clean_name(entry.get("name"))
            if not name or any(item.name.casefold() == name.casefold() for item in domains):
                continue
            color = entry.get("color")
            domains.append(Domain(name=name, color=color if _is_color(color) else _pick_color(domains)))
        self._domains = domains or list(DEFAULT_DOMAINS)

        days_raw = raw.get("days") if isinstance(raw.get("days"), dict) else {}
        self._days = {}
        for day_key in DAY_KEYS:
            self._days[day_key] = _load_blocks(days_raw.get(day_key))
            for block in self._days[day_key]:
                for task in block["tasks"]:
                    self._ensure_domain(task["domain"])
        self._week = None

    # -- lecture : domaines ------------------------------------------------ #
    @property
    def domains(self) -> tuple[Domain, ...]:
        return tuple(self._domains)

    @property
    def domain_names(self) -> tuple[str, ...]:
        return tuple(domain.name for domain in self._domains)

    def has_domain(self, name: str) -> bool:
        return self._find_domain(name) is not None

    def color_of(self, name: str) -> str:
        domain = self._find_domain(name)
        return domain.color if domain else FALLBACK_DOMAIN_COLOR

    def colors(self) -> dict[str, str]:
        """Couleur de chaque domaine (pratique pour les vues)."""
        return {domain.name: domain.color for domain in self._domains}

    def task_count(self, name: str) -> int:
        key = name.casefold()
        return sum(
            1
            for blocks in self._days.values()
            for block in blocks
            for task in block["tasks"]
            if task["domain"].casefold() == key
        )

    # -- lecture : plan ---------------------------------------------------- #
    def day(self, day_key: str) -> DayPlan:
        if day_key not in self._days:
            raise KeyError(f"jour inconnu : {day_key!r}")
        return self._week_cache()[day_key]

    def week(self) -> dict[str, DayPlan]:
        return dict(self._week_cache())

    def week_days(self) -> tuple[DayPlan, ...]:
        cache = self._week_cache()
        return tuple(cache[key] for key in DAY_KEYS)

    def tasks(self) -> dict[str, TaskNode]:
        return {task.tid: task for day in self.week_days() for task in day.tasks}

    def task_ids(self) -> set[str]:
        return {tid for day in self.week_days() for tid in (task.tid for task in day.tasks)}

    def find_task(self, tid: str) -> TaskNode | None:
        return self.tasks().get(tid)

    def total_minutes(self) -> int:
        return sum(day.total_minutes for day in self.week_days())

    def snapshot(self) -> PlanSnapshot:
        return PlanSnapshot(domains=self.domains, days=self.week())

    def _week_cache(self) -> dict[str, DayPlan]:
        if self._week is None:
            self._week = {
                day_key: DayPlan(
                    key=day_key,
                    label=DAY_LABELS[day_key],
                    blocks=tuple(
                        BlockNode(
                            bid=f"{day_key}-{block_index}",
                            start=block["start"],
                            end=block["end"],
                            title=block["title"],
                            intent=block["intent"],
                            tasks=tuple(
                                TaskNode(
                                    tid=task["id"],
                                    label=task["label"],
                                    domain=task["domain"],
                                    minutes=task["minutes"],
                                )
                                for task in block["tasks"]
                            ),
                        )
                        for block_index, block in enumerate(self._days[day_key])
                    ),
                )
                for day_key in DAY_KEYS
            }
        return self._week

    # -- écriture ---------------------------------------------------------- #
    def save(self) -> None:
        write_json_atomic(
            self.path,
            {
                "version": self.VERSION,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "domains": [{"name": d.name, "color": d.color} for d in self._domains],
                "days": self._days,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Copie sérialisable (tests, export, futur envoi à un LLM)."""
        return {
            "version": self.VERSION,
            "domains": [{"name": d.name, "color": d.color} for d in self._domains],
            "days": {key: blocks for key, blocks in self._days.items()},
        }

    # -- mutations : domaines ---------------------------------------------- #
    def add_domain(self, name: str, color: str | None = None) -> Domain:
        clean = _clean_name(name)
        if not clean:
            raise ValueError("Le nom du domaine ne peut pas être vide.")
        if self._find_domain(clean) is not None:
            raise ValueError(f"Le domaine « {clean} » existe déjà.")
        domain = Domain(name=clean, color=color if _is_color(color) else _pick_color(self._domains))
        self._domains.append(domain)
        self.save()
        return domain

    def rename_domain(self, old: str, new: str) -> str:
        domain = self._find_domain(old)
        if domain is None:
            raise ValueError(f"Domaine inconnu : « {old} ».")
        clean = _clean_name(new)
        if not clean:
            raise ValueError("Le nom du domaine ne peut pas être vide.")
        existing = self._find_domain(clean)
        if existing is not None and existing.name != domain.name:
            raise ValueError(f"Le domaine « {clean} » existe déjà.")

        index = self._domains.index(domain)
        self._domains[index] = Domain(name=clean, color=domain.color)
        for blocks in self._days.values():
            for block in blocks:
                for task in block["tasks"]:
                    if task["domain"] == domain.name:
                        task["domain"] = clean
        self._week = None
        self.save()
        return clean

    def set_domain_color(self, name: str, color: str) -> None:
        domain = self._find_domain(name)
        if domain is None:
            raise ValueError(f"Domaine inconnu : « {name} ».")
        if not _is_color(color):
            raise ValueError(f"Couleur invalide : {color!r}.")
        self._domains[self._domains.index(domain)] = Domain(name=domain.name, color=color)
        self._week = None
        self.save()

    def delete_domain(self, name: str) -> int:
        """Supprime un domaine **et toutes ses tâches** ; renvoie le nombre supprimé."""
        domain = self._find_domain(name)
        if domain is None:
            raise ValueError(f"Domaine inconnu : « {name} ».")
        if len(self._domains) == 1:
            raise ValueError("Impossible de supprimer le dernier domaine.")

        removed = 0
        for blocks in self._days.values():
            for block in blocks:
                kept = [task for task in block["tasks"] if task["domain"] != domain.name]
                removed += len(block["tasks"]) - len(kept)
                block["tasks"] = kept
        self._domains.remove(domain)
        self._week = None
        self.save()
        return removed

    # -- mutations : tâches ------------------------------------------------ #
    def add_task(
        self,
        day_key: str,
        block_index: int,
        *,
        label: str,
        domain: str,
        minutes: int,
    ) -> TaskNode:
        block = self._block_dict(day_key, block_index)
        clean_label = _clean_label(label)
        domain_name = self._require_domain(domain).name
        clean_minutes = _clean_minutes(minutes)

        tid = self._new_task_id()
        block["tasks"].append(
            {"id": tid, "label": clean_label, "domain": domain_name, "minutes": clean_minutes}
        )
        self._week = None
        self.save()
        return TaskNode(tid=tid, label=clean_label, domain=domain_name, minutes=clean_minutes)

    def update_task(
        self,
        tid: str,
        *,
        label: str | None = None,
        domain: str | None = None,
        minutes: int | None = None,
    ) -> TaskNode:
        task = self._find_task_dict(tid)
        if task is None:
            raise ValueError(f"Tâche inconnue : {tid!r}.")
        if label is not None:
            task["label"] = _clean_label(label)
        if domain is not None:
            task["domain"] = self._require_domain(domain).name
        if minutes is not None:
            task["minutes"] = _clean_minutes(minutes)
        self._week = None
        self.save()
        return TaskNode(
            tid=tid,
            label=task["label"],
            domain=task["domain"],
            minutes=task["minutes"],
        )

    def delete_task(self, tid: str) -> bool:
        for blocks in self._days.values():
            for block in blocks:
                for index, task in enumerate(block["tasks"]):
                    if task["id"] == tid:
                        del block["tasks"][index]
                        self._week = None
                        self.save()
                        return True
        return False

    # -- remplacement global (futur import LLM) ---------------------------- #
    def replace_week(
        self,
        week: Mapping[str, Iterable[Block]],
        *,
        prune_unused_domains: bool = False,
    ) -> None:
        """Remplace tout le planning ; les domaines inconnus sont enregistrés.

        Point d'entrée prévu pour un générateur externe (LLM, import de
        chapitres) : il suffit de fournir, par jour, la liste des blocs.
        Avec ``prune_unused_domains``, les piliers qui ne contiennent plus aucune
        tâche sont retirés (le dernier pilier est toujours conservé).
        """
        unknown_days = [key for key in week if key not in DAY_KEYS]
        if unknown_days:
            raise ValueError(f"jours inconnus : {', '.join(unknown_days)}")

        self._days = {}
        for day_key in DAY_KEYS:
            blocks = list(week.get(day_key, ()))
            self._days[day_key] = [
                {
                    "start": block.start,
                    "end": block.end,
                    "title": block.title,
                    "intent": block.intent,
                    "tasks": [
                        {
                            "id": self._new_task_id(),
                            "label": _clean_label(task.label),
                            "domain": self._ensure_domain(task.domain).name,
                            "minutes": _clean_minutes(task.minutes),
                        }
                        for task in block.tasks
                    ],
                }
                for block in blocks
            ]

        if prune_unused_domains:
            # On conserve l'ordre d'apparition dans le nouveau planning : le
            # pilier étudié arrive avant celui du rappel.
            order: list[str] = []
            for blocks in self._days.values():
                for block in blocks:
                    for task in block["tasks"]:
                        if task["domain"] not in order:
                            order.append(task["domain"])
            by_name = {domain.name: domain for domain in self._domains}
            kept = [by_name[name] for name in order if name in by_name]
            self._domains = kept or self._domains[:1]

        self._week = None
        self.save()

    def reset_to_default(self) -> None:
        """Revient au programme d'origine (les domaines personnalisés disparaissent)."""
        self._seed(RAW_WEEK)
        self.save()

    # -- utilitaires internes ---------------------------------------------- #
    def _find_domain(self, name: str) -> Domain | None:
        key = name.strip().casefold()
        return next((domain for domain in self._domains if domain.name.casefold() == key), None)

    def _require_domain(self, name: str) -> Domain:
        domain = self._find_domain(name)
        if domain is None:
            raise ValueError(f"Domaine inconnu : « {name} ».")
        return domain

    def _ensure_domain(self, name: str) -> Domain:
        """Enregistre un domaine découvert dans le plan (tolérance au rechargement)."""
        existing = self._find_domain(name)
        if existing is not None:
            return existing
        domain = Domain(name=_clean_name(name) or "Sans pilier", color=_pick_color(self._domains))
        self._domains.append(domain)
        return domain

    def _block_dict(self, day_key: str, block_index: int) -> dict[str, Any]:
        if day_key not in self._days:
            raise ValueError(f"Jour inconnu : « {day_key} ».")
        blocks = self._days[day_key]
        if not 0 <= block_index < len(blocks):
            raise ValueError(f"Bloc introuvable : {day_key} n° {block_index}.")
        return blocks[block_index]

    def _find_task_dict(self, tid: str) -> dict[str, Any] | None:
        for blocks in self._days.values():
            for block in blocks:
                for task in block["tasks"]:
                    if task["id"] == tid:
                        return task
        return None

    def _new_task_id(self) -> str:
        existing = {
            task["id"]
            for blocks in self._days.values()
            for block in blocks
            for task in block["tasks"]
        }
        while True:
            candidate = f"t{uuid4().hex[:8]}"
            if candidate not in existing:
                return candidate


# --------------------------------------------------------------------------- #
# Normalisation et validation
# --------------------------------------------------------------------------- #
def _clean_name(value: object) -> str:
    text = " ".join(str(value or "").split())
    return text[:MAX_NAME_LENGTH]


def _clean_label(value: object) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError("L'intitulé de la tâche ne peut pas être vide.")
    return text[:MAX_LABEL_LENGTH]


def _clean_minutes(value: object) -> int:
    try:
        minutes = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError("La durée doit être un nombre de minutes.") from None
    if not MIN_TASK_MINUTES <= minutes <= MAX_TASK_MINUTES:
        raise ValueError(
            f"La durée doit être comprise entre {MIN_TASK_MINUTES} et {MAX_TASK_MINUTES} minutes."
        )
    return minutes


def _is_color(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return False
    return all(char in "0123456789abcdefABCDEF" for char in value[1:])


def _pick_color(used: Collection[Domain]) -> str:
    """Première couleur de la palette non utilisée (sinon rotation)."""
    taken = {domain.color.upper() for domain in used}
    for color in DOMAIN_PALETTE:
        if color.upper() not in taken:
            return color
    return DOMAIN_PALETTE[len(used) % len(DOMAIN_PALETTE)]


def _load_blocks(raw_blocks: object) -> list[dict[str, Any]]:
    """Nettoie la liste de blocs d'un jour, en ignorant ce qui est invalide."""
    if not isinstance(raw_blocks, list):
        return []
    blocks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in raw_blocks:
        if not isinstance(raw, dict):
            continue
        tasks: list[dict[str, Any]] = []
        for raw_task in raw.get("tasks", []) if isinstance(raw.get("tasks"), list) else []:
            if not isinstance(raw_task, dict):
                continue
            tid = raw_task.get("id")
            if not isinstance(tid, str) or not tid or tid in seen_ids:
                continue
            label = _clean_name(raw_task.get("label"))
            domain = _clean_name(raw_task.get("domain"))
            if not label or not domain:
                continue
            try:
                minutes = _clean_minutes(raw_task.get("minutes"))
            except ValueError:
                continue
            seen_ids.add(tid)
            tasks.append({"id": tid, "label": label, "domain": domain, "minutes": minutes})
        blocks.append(
            {
                "start": _clean_name(raw.get("start")) or "--:--",
                "end": _clean_name(raw.get("end")) or "--:--",
                "title": _clean_name(raw.get("title")) or "Bloc",
                "intent": _clean_name(raw.get("intent")),
                "tasks": tasks,
            }
        )
    return blocks


__all__ = [
    "MAX_LABEL_LENGTH",
    "MAX_NAME_LENGTH",
    "MAX_TASK_MINUTES",
    "MIN_TASK_MINUTES",
    "PlanSnapshot",
    "PlanStore",
]
