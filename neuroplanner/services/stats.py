"""Agrégations de progression — fonctions pures, sans aucune dépendance UI."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

from neuroplanner.models import DayPlan, TaskNode

#: Bornes du code couleur de refocalisation (pourcentages).
REFOCUS_BELOW = 50.0
MASTERY_FROM = 80.0


@dataclass(frozen=True, slots=True)
class Progress:
    """Avancement d'un ensemble de tâches."""

    done: int
    total: int
    minutes_done: int
    minutes_total: int

    @property
    def percent(self) -> float:
        return percent(self.done, self.total)

    @property
    def complete(self) -> bool:
        return self.total > 0 and self.done == self.total

    @property
    def minutes_left(self) -> int:
        return max(0, self.minutes_total - self.minutes_done)


@dataclass(frozen=True, slots=True)
class DomainProgress:
    domain: str
    progress: Progress

    @property
    def percent(self) -> float:
        return self.progress.percent


def percent(done: int, total: int) -> float:
    """Pourcentage borné à ``[0, 100]`` ; ``0.0`` si l'ensemble est vide."""
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * done / total))


def progress_of(tasks: Iterable[TaskNode], completed: Collection[str]) -> Progress:
    """Nombre de tâches terminées et minutes associées."""
    count = minutes_total = minutes_done = done = 0
    for task in tasks:
        count += 1
        minutes_total += task.minutes
        if task.tid in completed:
            done += 1
            minutes_done += task.minutes
    return Progress(done=done, total=count, minutes_done=minutes_done, minutes_total=minutes_total)


def day_progress(day: DayPlan, completed: Collection[str]) -> Progress:
    return progress_of(day.tasks, completed)


def week_progress(days: Iterable[DayPlan], completed: Collection[str]) -> Progress:
    return progress_of((task for day in days for task in day.tasks), completed)


def domain_progress(
    days: Iterable[DayPlan],
    completed: Collection[str],
    *,
    order: Sequence[str] | None = None,
) -> list[DomainProgress]:
    """Progression par pilier.

    Sans ``order``, les piliers suivent leur ordre d'apparition dans le plan ;
    sinon, l'ordre fourni (les piliers non listés passent en dernier).
    """
    buckets: dict[str, list[TaskNode]] = {}
    for day in days:
        for task in day.tasks:
            buckets.setdefault(task.domain, []).append(task)

    if order is None:
        names = list(buckets)
    else:
        known = [name for name in order if name in buckets]
        names = known + [name for name in buckets if name not in known]

    return [
        DomainProgress(domain=name, progress=progress_of(buckets[name], completed))
        for name in names
    ]
