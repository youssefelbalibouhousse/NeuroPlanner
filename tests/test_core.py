"""Formatage, configuration et thème (aucun écran requis)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from neuroplanner import formatting
from neuroplanner.config import (
    DATA_ENV_VAR,
    DAY_KEYS,
    initial_day,
    resolve_data_file,
    user_data_dir,
)
from neuroplanner.theme import FALLBACK_DOMAIN_COLOR, color_for, domain_color, mix


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(0, "0 min"), (15, "15 min"), (59, "59 min"), (60, "1 h"), (75, "1 h 15"), (300, "5 h")],
)
def test_fmt_duration(minutes: int, expected: str) -> None:
    assert formatting.fmt_duration(minutes) == expected


def test_fmt_duration_rounds() -> None:
    assert formatting.fmt_duration(74.6) == "1 h 15"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "00:00"), (59, "00:59"), (60, "01:00"), (2700, "45:00")],
)
def test_fmt_clock(seconds: int, expected: str) -> None:
    assert formatting.fmt_clock(seconds) == expected


def test_fmt_clock_rounds_up_and_never_negative() -> None:
    assert formatting.fmt_clock(0.2) == "00:01"
    assert formatting.fmt_clock(-3) == "00:00"


def test_fmt_date_uses_french_months() -> None:
    assert formatting.fmt_date(date(2026, 11, 14)) == "14 nov."


def test_plural() -> None:
    assert formatting.plural(0, "session") == "session"
    assert formatting.plural(1, "session") == "session"
    assert formatting.plural(2, "session") == "sessions"


def test_initial_day_maps_weekdays_to_plan() -> None:
    assert initial_day(0) == DAY_KEYS[0]
    assert initial_day(5) == DAY_KEYS[5]
    assert initial_day(6) == DAY_KEYS[0]  # dimanche -> lundi


def test_data_file_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DATA_ENV_VAR, raising=False)
    assert resolve_data_file() == user_data_dir() / "neuro_progress.json"

    monkeypatch.setenv(DATA_ENV_VAR, str(tmp_path / "env.json"))
    assert resolve_data_file() == tmp_path / "env.json"

    explicit = tmp_path / "explicit.json"
    assert resolve_data_file(explicit) == explicit


def test_data_file_expands_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DATA_ENV_VAR, raising=False)
    resolved = resolve_data_file("~/neuro.json")
    assert resolved.is_absolute()


@pytest.mark.parametrize(
    ("pct", "attribute"),
    [(0, "red"), (49.9, "red"), (50, "orange"), (79.9, "orange"), (80, "green"), (100, "green")],
)
def test_color_for_thresholds(pct: float, attribute: str) -> None:
    from neuroplanner.theme import PALETTE

    assert color_for(pct) == getattr(PALETTE, attribute)


def test_mix_interpolates() -> None:
    assert mix("#000000", "#ffffff", 0) == "#000000"
    assert mix("#000000", "#ffffff", 1) == "#ffffff"
    assert mix("#000000", "#ffffff", 0.5) == "#808080"


def test_domain_color_falls_back() -> None:
    assert domain_color("Dev & Archi") != FALLBACK_DOMAIN_COLOR
    assert domain_color("Inconnu") == FALLBACK_DOMAIN_COLOR
