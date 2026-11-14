"""Modèles immuables du domaine (aucune dépendance à l'interface)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Task:
    """Tâche déclarée dans le plan brut (sans identifiant)."""

    label: str
    domain: str
    minutes: int


@dataclass(frozen=True, slots=True)
class Block:
    """Bloc horaire déclaré dans le plan brut."""

    start: str
    end: str
    title: str
    intent: str
    tasks: tuple[Task, ...]

    @property
    def minutes(self) -> int:
        return sum(task.minutes for task in self.tasks)


@dataclass(frozen=True, slots=True)
class TaskNode:
    """Tâche persistable : ``tid`` sert de clé dans le fichier de progression."""

    tid: str
    label: str
    domain: str
    minutes: int


@dataclass(frozen=True, slots=True)
class BlockNode:
    bid: str
    start: str
    end: str
    title: str
    intent: str
    tasks: tuple[TaskNode, ...]

    @property
    def minutes(self) -> int:
        return sum(task.minutes for task in self.tasks)


@dataclass(frozen=True, slots=True)
class DayPlan:
    """Une journée complète : 4 blocs, 5 piliers, 5 h."""

    key: str
    label: str
    blocks: tuple[BlockNode, ...]

    @property
    def tasks(self) -> tuple[TaskNode, ...]:
        return tuple(task for block in self.blocks for task in block.tasks)

    @property
    def total_minutes(self) -> int:
        return sum(block.minutes for block in self.blocks)


@dataclass(frozen=True, slots=True)
class TimerPreset:
    """Préréglage de minuteur neuroplastique."""

    key: str
    label: str
    seconds: int
    caption: str
    finished_hint: str
