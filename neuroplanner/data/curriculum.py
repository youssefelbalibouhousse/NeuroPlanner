"""Plan d'apprentissage de la semaine.

Tout le contenu pédagogique vit ici. Chaque journée est décrite par 4 blocs
(1 h 15 + 1 h 15 + 1 h 30 + 1 h = 5 h) couvrant les 5 piliers :

* Dev & Archi
* IA & World Models
* Projets (SilenceLess & LocalArabi_RAG)
* Arabe MSA
* Révision Active

Pour modifier le programme, il suffit d'éditer ``RAW_WEEK`` ci-dessous : les
identifiants, les statistiques et le graphique sont recalculés automatiquement.
"""

from __future__ import annotations

from collections.abc import Mapping

from neuroplanner.config import DAY_LABELS, DAYS
from neuroplanner.models import Block, BlockNode, DayPlan, Task, TaskNode


def _day(
    dev_core: str,
    dev_lab: str,
    ia_core: str,
    ia_lab: str,
    proj_silence: str,
    proj_rag: str,
    arabe: str,
) -> tuple[Block, ...]:
    """Construit les 4 blocs d'une journée (5 h au total)."""
    return (
        Block(
            start="07:30",
            end="08:45",
            title="Dev & Archi",
            intent="Encodage profond",
            tasks=(
                Task(dev_core, "Dev & Archi", 45),
                Task(dev_lab, "Dev & Archi", 20),
                Task("Rappel actif de la veille — sans notes", "Révision Active", 10),
            ),
        ),
        Block(
            start="09:00",
            end="10:15",
            title="IA & World Models",
            intent="Concepts & intuition",
            tasks=(
                Task(ia_core, "IA & World Models", 45),
                Task(ia_lab, "IA & World Models", 30),
            ),
        ),
        Block(
            start="10:30",
            end="12:00",
            title="Projets",
            intent="Production concrète",
            tasks=(
                Task(proj_silence, "Projets", 45),
                Task(proj_rag, "Projets", 45),
            ),
        ),
        Block(
            start="13:30",
            end="14:30",
            title="Arabe MSA & Révision",
            intent="Récupération active",
            tasks=(
                Task(arabe, "Arabe MSA", 30),
                Task("Dictée active + correction phonétique", "Arabe MSA", 15),
                Task("Feuille blanche — restitution libre", "Révision Active", 15),
            ),
        ),
    )


RAW_WEEK: dict[str, tuple[Block, ...]] = {
    "lun": _day(
        "Architecture hexagonale : frontières de modules",
        "Implémentation d'un cas d'usage isolé",
        "Transformers : attention & positional encoding",
        "Mini-implémentation d'un bloc d'attention",
        "SilenceLess — refonte du flux de capture",
        "LocalArabi_RAG — ingestion PDF & chunking",
        "MSA — 200 mots : racines et schèmes",
    ),
    "mar": _day(
        "Event sourcing & idempotence",
        "Projection d'événements + tests de rejeu",
        "World models : JEPA & représentations latentes",
        "Notes de synthèse + schéma comparatif",
        "SilenceLess — synchronisation offline-first",
        "LocalArabi_RAG — retrieval hybride (BM25 + dense)",
        "MSA — structures nominales (iḍāfa)",
    ),
    "mer": _day(
        "Concurrence : async, backpressure, annulation",
        "Refactor d'un pipeline asynchrone",
        "RL & planification dans l'espace latent",
        "Mini-expérience : politique tabulaire",
        "SilenceLess — écran de rappel quotidien",
        "LocalArabi_RAG — jeu d'évaluation du RAG",
        "MSA — formes verbales dérivées (II → X)",
    ),
    "jeu": _day(
        "Observabilité : tracing & corrélation",
        "Instrumentation d'un parcours critique",
        "Diffusion & modèles génératifs vidéo",
        "Notes : bruit, espace latent, échantillonnage",
        "SilenceLess — mode focus & notifications",
        "LocalArabi_RAG — réindexation incrémentale",
        "MSA — connecteurs & syntaxe de la phrase",
    ),
    "ven": _day(
        "Refactoring guidé par les tests",
        "Écriture de tests avant extraction",
        "Mémoire & fenêtre de contexte : compression",
        "Implémentation d'un résumé hiérarchique",
        "SilenceLess — analytics locales (zéro cloud)",
        "LocalArabi_RAG — reranking & citations",
        "MSA — lecture active d'un article de presse",
    ),
    "sam": _day(
        "Revue de code & dette technique",
        "Nettoyage ciblé du module le plus fragile",
        "Synthèse : cartographie des world models",
        "Schéma récapitulatif d'une page",
        "SilenceLess — bêta test & retours",
        "LocalArabi_RAG — benchmarks & latence",
        "MSA — production écrite (150 mots)",
    ),
}


def _materialise_day(day_key: str, blocks: tuple[Block, ...]) -> DayPlan:
    """Donne un identifiant stable à chaque tâche : ``<jour>-<bloc>-<tâche>``."""
    nodes = tuple(
        BlockNode(
            bid=f"{day_key}-{block_index}",
            start=block.start,
            end=block.end,
            title=block.title,
            intent=block.intent,
            tasks=tuple(
                TaskNode(
                    tid=f"{day_key}-{block_index}-{task_index}",
                    label=task.label,
                    domain=task.domain,
                    minutes=task.minutes,
                )
                for task_index, task in enumerate(block.tasks)
            ),
        )
        for block_index, block in enumerate(blocks)
    )
    return DayPlan(key=day_key, label=DAY_LABELS[day_key], blocks=nodes)


def build_week(raw: Mapping[str, tuple[Block, ...]]) -> dict[str, DayPlan]:
    """Matérialise le plan brut, dans l'ordre de ``config.DAYS``."""
    missing = [key for key in DAY_LABELS if key not in raw]
    if missing:
        raise ValueError(f"jours manquants dans le plan : {', '.join(missing)}")
    return {day_key: _materialise_day(day_key, raw[day_key]) for day_key, _ in DAYS}


WEEK: dict[str, DayPlan] = build_week(RAW_WEEK)

#: Jours dans l'ordre d'affichage.
WEEK_DAYS: tuple[DayPlan, ...] = tuple(WEEK[day_key] for day_key, _ in DAYS)

TASKS_BY_DAY: dict[str, tuple[TaskNode, ...]] = {day.key: day.tasks for day in WEEK_DAYS}
TASKS_BY_ID: dict[str, TaskNode] = {
    task.tid: task for day in WEEK_DAYS for task in day.tasks
}

TOTAL_TASKS: int = len(TASKS_BY_ID)

#: Piliers d'apprentissage, dans l'ordre d'affichage (graphique, légendes).
#: L'ordre du plan, lui, place la « Révision Active » dès le premier bloc.
DOMAINS: tuple[str, ...] = (
    "Dev & Archi",
    "IA & World Models",
    "Projets",
    "Arabe MSA",
    "Révision Active",
)


def get_day(day_key: str) -> DayPlan:
    """Journée demandée ; lève ``KeyError`` avec un message explicite."""
    try:
        return WEEK[day_key]
    except KeyError:
        raise KeyError(f"jour inconnu : {day_key!r}") from None


def find_task(tid: str) -> TaskNode | None:
    return TASKS_BY_ID.get(tid)


def day_total_minutes(day_key: str) -> int:
    return get_day(day_key).total_minutes
