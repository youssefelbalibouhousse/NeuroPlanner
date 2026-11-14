"""Fonctions de formatage partagées par l'interface et les tests."""

from __future__ import annotations

from datetime import date

from neuroplanner.config import MONTHS_FR


def fmt_duration(minutes: float) -> str:
    """``75`` -> ``1 h 15``, ``45`` -> ``45 min``, ``60`` -> ``1 h``."""
    total = int(round(minutes))
    hours, mins = divmod(total, 60)
    if hours and mins:
        return f"{hours} h {mins:02d}"
    if hours:
        return f"{hours} h"
    return f"{mins} min"


def fmt_clock(seconds: float) -> str:
    """Secondes restantes -> ``MM:SS`` (arrondi supérieur, jamais négatif)."""
    total = max(0, int(-(-seconds // 1)))
    return f"{total // 60:02d}:{total % 60:02d}"


def fmt_date(day: date) -> str:
    return f"{day.day} {MONTHS_FR[day.month - 1]}"


def fmt_percent(percent: float) -> str:
    return f"{percent:.0f} %"


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    return singular if count <= 1 else (plural_form or f"{singular}s")
