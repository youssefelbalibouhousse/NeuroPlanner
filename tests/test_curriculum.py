"""Le plan doit tenir la promesse « 4 blocs, 5 h, 5 piliers, 6 jours »."""

from __future__ import annotations

import pytest

from neuroplanner.config import DAILY_TARGET_MINUTES, DAY_KEYS, DAY_LABELS
from neuroplanner.data.curriculum import (
    DOMAINS,
    RAW_WEEK,
    TASKS_BY_DAY,
    TASKS_BY_ID,
    TOTAL_TASKS,
    WEEK,
    WEEK_DAYS,
    build_week,
    day_total_minutes,
    find_task,
    get_day,
)
from neuroplanner.models import Block, Task


def test_six_days_in_order() -> None:
    assert [day.key for day in WEEK_DAYS] == list(DAY_KEYS)
    assert [day.label for day in WEEK_DAYS] == [DAY_LABELS[key] for key in DAY_KEYS]


@pytest.mark.parametrize("day_key", DAY_KEYS)
def test_each_day_has_four_blocks(day_key: str) -> None:
    assert len(get_day(day_key).blocks) == 4


@pytest.mark.parametrize("day_key", DAY_KEYS)
def test_each_day_lasts_five_hours(day_key: str) -> None:
    assert day_total_minutes(day_key) == DAILY_TARGET_MINUTES


@pytest.mark.parametrize("day_key", DAY_KEYS)
def test_each_day_covers_all_domains(day_key: str) -> None:
    assert {task.domain for task in TASKS_BY_DAY[day_key]} == set(DOMAINS)


@pytest.mark.parametrize(
    ("domain", "minutes"),
    [
        ("Dev & Archi", 65),
        ("IA & World Models", 75),
        ("Projets", 90),
        ("Arabe MSA", 45),
        ("Révision Active", 25),
    ],
)
def test_daily_minutes_per_domain(domain: str, minutes: int) -> None:
    """Répartition quotidienne volontaire : 5 h, pondérées par pilier."""
    total = sum(task.minutes for task in TASKS_BY_DAY["lun"] if task.domain == domain)
    assert total == minutes


def test_domain_count() -> None:
    assert len(DOMAINS) == 5


def test_task_ids_are_unique_and_stable() -> None:
    tids = [task.tid for task in TASKS_BY_ID.values()]
    assert len(tids) == len(set(tids)) == TOTAL_TASKS
    assert TOTAL_TASKS == 60
    assert find_task("lun-0-0") is not None
    assert find_task("lun-0-0").label in {task.label for task in TASKS_BY_DAY["lun"]}


def test_task_ids_follow_the_documented_pattern() -> None:
    for day_key, tasks in TASKS_BY_DAY.items():
        for task in tasks:
            day_part, block_part, task_part = task.tid.split("-")
            assert day_part == day_key
            assert block_part.isdigit() and task_part.isdigit()


def test_blocks_have_positive_durations() -> None:
    for day in WEEK_DAYS:
        for block in day.blocks:
            assert block.minutes > 0
            assert all(task.minutes > 0 for task in block.tasks)


def test_get_day_rejects_unknown_key() -> None:
    with pytest.raises(KeyError):
        get_day("dim")


def test_build_week_rejects_incomplete_plan() -> None:
    with pytest.raises(ValueError, match="jours manquants"):
        build_week({"lun": RAW_WEEK["lun"]})


def test_build_week_is_deterministic() -> None:
    rebuilt = build_week(RAW_WEEK)
    assert {key: [task.tid for task in day.tasks] for key, day in rebuilt.items()} == {
        key: [task.tid for task in day.tasks] for key, day in WEEK.items()
    }


def test_custom_plan_is_supported() -> None:
    """Un plan personnalisé peut être matérialisé sans toucher au reste du code."""
    block = Block("08:00", "09:00", "Test", "Essai", (Task("Faire X", "Dev & Archi", 60),))
    plan = build_week({key: (block,) for key in DAY_LABELS})
    assert plan["mar"].blocks[0].tasks[0].tid == "mar-0-0"
    assert plan["mar"].total_minutes == 60
