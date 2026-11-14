"""Statistiques : agrégations et bornes du code couleur."""

from __future__ import annotations

import pytest

from neuroplanner.data.curriculum import DOMAINS, WEEK_DAYS
from neuroplanner.models import TaskNode
from neuroplanner.services.stats import (
    MASTERY_FROM,
    REFOCUS_BELOW,
    day_progress,
    domain_progress,
    percent,
    progress_of,
    week_progress,
)

TASKS = (
    TaskNode("a", "un", "Dev & Archi", 10),
    TaskNode("b", "deux", "Dev & Archi", 20),
    TaskNode("c", "trois", "Projets", 30),
)


def test_percent_handles_empty_sets() -> None:
    assert percent(0, 0) == 0.0


def test_percent_is_bounded() -> None:
    assert percent(1, 2) == 50.0
    assert percent(9, 3) == 100.0
    assert percent(-1, 3) == 0.0


def test_progress_of_counts_tasks_and_minutes() -> None:
    result = progress_of(TASKS, {"a", "c"})
    assert (result.done, result.total) == (2, 3)
    assert (result.minutes_done, result.minutes_total) == (40, 60)
    assert result.minutes_left == 20
    assert result.percent == pytest.approx(200 / 3)


def test_progress_of_ignores_unknown_ids() -> None:
    result = progress_of(TASKS, {"inconnu"})
    assert result.done == 0


def test_progress_complete_flag() -> None:
    assert progress_of(TASKS, {"a", "b", "c"}).complete is True
    assert progress_of(TASKS, {"a"}).complete is False
    assert progress_of((), set()).complete is False


def test_day_progress_totals() -> None:
    monday = WEEK_DAYS[0]
    result = day_progress(monday, set())
    assert (result.done, result.total) == (0, 10)
    assert result.minutes_total == 300
    assert result.percent == 0.0


def test_week_progress_totals() -> None:
    result = week_progress(WEEK_DAYS, set())
    assert (result.done, result.total) == (0, 60)
    assert result.minutes_total == 1800


def test_domain_progress_is_balanced() -> None:
    domains = domain_progress(WEEK_DAYS, set(), order=DOMAINS)
    assert [item.domain for item in domains] == list(DOMAINS)
    assert all(item.progress.total == 12 for item in domains)
    # Les minutes diffèrent par pilier, mais la somme fait bien 5 h × 6 jours.
    assert sum(item.progress.minutes_total for item in domains) == 1800


def test_domain_progress_without_order_follows_the_plan() -> None:
    """Sans ordre imposé, les piliers apparaissent dans l'ordre du plan."""
    domains = domain_progress(WEEK_DAYS, set())
    assert domains[0].domain == "Dev & Archi"
    assert domains[1].domain == "Révision Active"  # rappel actif du 1er bloc
    assert {item.domain for item in domains} == set(DOMAINS)


def test_domain_progress_puts_unknown_domains_last() -> None:
    domains = domain_progress(WEEK_DAYS, set(), order=("Arabe MSA",))
    assert domains[0].domain == "Arabe MSA"
    assert domains[-1].domain != "Arabe MSA"
    assert len(domains) == 5


def test_domain_progress_reflects_completion() -> None:
    first_task = WEEK_DAYS[0].tasks[0]
    domains = {item.domain: item for item in domain_progress(WEEK_DAYS, {first_task.tid})}
    assert domains[first_task.domain].progress.done == 1
    assert domains["Projets"].progress.done == 0


def test_colour_thresholds_are_ordered() -> None:
    assert 0 < REFOCUS_BELOW < MASTERY_FROM < 100
