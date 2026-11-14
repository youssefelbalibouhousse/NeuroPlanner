"""Génération du planning : 5 h par jour, contenu complet, déterminisme."""

from __future__ import annotations

import pytest

from neuroplanner.config import DAY_KEYS
from neuroplanner.models import Chapter
from neuroplanner.services.generation import (
    MIN_TASK_MINUTES,
    MINUTES_PER_DAY,
    STUDY_SLOTS,
    build_week,
    chapter_titles,
    describe_week,
)

CHAPTERS = [Chapter(f"Chapitre {index}", None) for index in range(1, 13)]


def test_week_has_six_days_of_four_blocks() -> None:
    week = build_week(CHAPTERS, domain="Mathématiques")
    assert list(week) == list(DAY_KEYS)
    assert all(len(blocks) == 4 for blocks in week.values())


@pytest.mark.parametrize("count", [1, 2, 5, 6, 12, 30])
def test_each_day_lasts_five_hours(count: int) -> None:
    chapters = [Chapter(f"C{index}", None) for index in range(count)]
    week = build_week(chapters, domain="Mathématiques")
    for blocks in week.values():
        assert sum(block.minutes for block in blocks) == MINUTES_PER_DAY


def test_all_chapters_are_placed() -> None:
    week = build_week(CHAPTERS, domain="Mathématiques")
    placed = chapter_titles(week)
    assert placed == [chapter.title for chapter in CHAPTERS]


def test_content_fills_the_study_slots_exactly() -> None:
    week = build_week(CHAPTERS, domain="Mathématiques")
    study_minutes = sum(slot.minutes for slot in STUDY_SLOTS)
    for blocks in week.values():
        assert sum(block.minutes for block in blocks[:-1]) == study_minutes


def test_recall_block_is_last_and_sixty_minutes() -> None:
    week = build_week(CHAPTERS, domain="Mathématiques")
    for blocks in week.values():
        recall = blocks[-1]
        assert recall.title == "Récupération active"
        assert recall.minutes == 60
        assert any(task.label.startswith("Rappel actif") for task in recall.tasks)
        assert any(task.label.startswith("Feuille blanche") for task in recall.tasks)


def test_no_task_is_shorter_than_the_minimum() -> None:
    chapters = [Chapter(f"C{index}", None) for index in range(40)]
    week = build_week(chapters, domain="Domain")
    for blocks in week.values():
        for block in blocks:
            for task in block.tasks:
                assert task.minutes >= MIN_TASK_MINUTES


def test_revision_domain_defaults_to_the_study_domain() -> None:
    week = build_week(CHAPTERS, domain="Mathématiques")
    recall = week["lun"][-1]
    assert {task.domain for task in recall.tasks} == {"Mathématiques"}


def test_revision_domain_can_differ() -> None:
    week = build_week(CHAPTERS, domain="Mathématiques", revision_domain="Révision Active")
    recall = week["lun"][-1]
    assert {task.domain for task in recall.tasks} == {"Révision Active"}
    assert {task.domain for task in week["lun"][0].tasks} == {"Mathématiques"}


def test_estimated_minutes_are_respected() -> None:
    chapters = [Chapter("Court", 30), Chapter("Long", 210)]
    week = build_week(chapters, domain="Domain")
    totals: dict[str, int] = {}
    for blocks in week.values():
        for block in blocks[:-1]:
            for task in block.tasks:
                title = task.label.split(" — ", 1)[1]
                totals[title] = totals.get(title, 0) + task.minutes
    assert totals["Court"] + totals["Long"] == 6 * sum(slot.minutes for slot in STUDY_SLOTS)
    assert totals["Long"] > totals["Court"] * 3


def test_generation_is_deterministic() -> None:
    first = build_week(CHAPTERS, domain="Mathématiques")
    second = build_week(CHAPTERS, domain="Mathématiques")
    assert first == second


def test_task_labels_carry_the_slot_prefix() -> None:
    week = build_week([Chapter("Limites")], domain="Domain")
    labels = [task.label for task in week["lun"][0].tasks]
    assert labels == ["Lecture active — Limites"]
    assert week["lun"][1].tasks[0].label == "Exercices — Limites"
    assert week["lun"][2].tasks[0].label == "Synthèse — Limites"


def test_a_long_chapter_spans_several_days() -> None:
    week = build_week([Chapter("Tout le programme", 1400)], domain="Domain")
    for day_key in DAY_KEYS:
        assert week[day_key][0].tasks[0].label == "Lecture active — Tout le programme"


def test_rejects_empty_chapter_list() -> None:
    with pytest.raises(ValueError, match="au moins un chapitre"):
        build_week([], domain="Mathématiques")


def test_rejects_empty_domain() -> None:
    with pytest.raises(ValueError, match="pilier"):
        build_week(CHAPTERS, domain="   ")


def test_rejects_absurd_chapter_count() -> None:
    many = [Chapter(f"C{index}") for index in range(400)]
    with pytest.raises(ValueError, match="Trop de chapitres"):
        build_week(many, domain="Domain")


def test_rejects_blank_chapter_title() -> None:
    with pytest.raises(ValueError, match="intitulé vide"):
        build_week([Chapter("   ")], domain="Domain")


def test_custom_day_keys() -> None:
    week = build_week(CHAPTERS, domain="Domain", day_keys=("lun", "mar"))
    assert list(week) == ["lun", "mar"]
    assert sum(block.minutes for block in week["lun"]) == MINUTES_PER_DAY


def test_describe_week_is_readable() -> None:
    week = build_week([Chapter("Limites")], domain="Domain")
    text = describe_week(week)
    assert "Lundi" in text
    assert "300 min" in text
    assert "Lecture active — Limites" in text
