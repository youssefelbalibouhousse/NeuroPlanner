"""Lecture d'une table des matières : tolérance et validation."""

from __future__ import annotations

import pytest

from neuroplanner.models import Chapter
from neuroplanner.services.chapters import format_chapters, parse_chapters


def test_parses_numbered_list() -> None:
    chapters = parse_chapters("1. Limites\n2) Dérivées\n3 - Intégrales")
    assert [chapter.title for chapter in chapters] == ["Limites", "Dérivées", "Intégrales"]
    assert all(chapter.minutes is None for chapter in chapters)


def test_parses_bullets() -> None:
    chapters = parse_chapters("- Suites\n• Séries\n* Fonctions")
    assert [chapter.title for chapter in chapters] == ["Suites", "Séries", "Fonctions"]


@pytest.mark.parametrize(
    ("line", "title", "minutes"),
    [
        ("Intégration (90 min)", "Intégration", 90),
        ("Intégration — 1 h 30", "Intégration", 90),
        ("Intégration [45]", "Intégration", 45),
        ("Intégration - 2h", "Intégration", 120),
        ("Intégration (45 minutes)", "Intégration", 45),
    ],
)
def test_parses_durations(line: str, title: str, minutes: int) -> None:
    chapters = parse_chapters(line)
    assert (chapters[0].title, chapters[0].minutes) == (title, minutes)


@pytest.mark.parametrize("line", ["Algorithmes 2", "Module 3 : 45"])
def test_keeps_trailing_numbers_when_no_unit(line: str) -> None:
    chapters = parse_chapters(line)
    assert chapters[0].minutes is None
    assert chapters[0].title


def test_bare_chapter_heading_is_ignored() -> None:
    """« Chapitre 7 » seul est un titre de section, pas un chapitre exploitable."""
    assert [chapter.title for chapter in parse_chapters("Chapitre 7\n1. Limites")] == ["Limites"]


def test_strips_chapter_prefixes() -> None:
    chapters = parse_chapters("Chapitre 5 : Séries de fonctions\nLeçon 2 - Suites")
    assert [chapter.title for chapter in chapters] == ["Séries de fonctions", "Suites"]


def test_ignores_headings_and_blank_lines() -> None:
    text = """
    Table des matières

    1. Limites

    Sommaire
    2. Dérivées
    """
    assert [chapter.title for chapter in parse_chapters(text)] == ["Limites", "Dérivées"]


def test_deduplicates_case_insensitively() -> None:
    chapters = parse_chapters("1. Limites\n2. LIMITES\n3. Dérivées")
    assert [chapter.title for chapter in chapters] == ["Limites", "Dérivées"]


def test_collapses_whitespace_and_truncates() -> None:
    chapters = parse_chapters("-    Limites    et   continuité   " + "x" * 200)
    assert chapters[0].title.startswith("Limites et continuité")
    assert len(chapters[0].title) == 120


def test_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="Aucun chapitre"):
        parse_chapters("   \n\n  Table des matières\n")


def test_rejects_single_character_titles() -> None:
    with pytest.raises(ValueError):
        parse_chapters("1. x\n2. y")


def test_ignores_absurd_durations() -> None:
    chapters = parse_chapters("Limites (5000 min)\nDérivées (3 min)")
    assert all(chapter.minutes is None for chapter in chapters)


def test_format_round_trip() -> None:
    source = [Chapter("Limites", 90), Chapter("Dérivées")]
    text = format_chapters(source)
    assert text.splitlines() == ["1. Limites  (90 min)", "2. Dérivées"]
    assert parse_chapters(text) == source
