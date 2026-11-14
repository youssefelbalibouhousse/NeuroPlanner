"""Fixtures partagées par la suite de tests."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """Fichier de progression isolé, propre à chaque test."""
    return tmp_path / "neuro_progress.json"


@pytest.fixture
def has_display() -> None:
    """Ignore le test si aucune fenêtre Tk ne peut être créée (CI sans écran)."""
    tkinter = pytest.importorskip("tkinter")
    try:
        root = tkinter.Tk()
    except tkinter.TclError as exc:  # pragma: no cover - dépend de la machine
        pytest.skip(f"pas d'affichage disponible : {exc}")
    root.destroy()


@pytest.fixture
def app(data_file: Path, has_display: None) -> Iterator[Any]:
    """Application réelle avec un fichier de données temporaire."""
    from neuroplanner.app import NeuroPlanner
    from neuroplanner.theme import apply_appearance

    apply_appearance()
    window = NeuroPlanner(data_file)
    _pump(window, 6)
    try:
        yield window
    finally:
        window.timer.shutdown()
        with contextlib.suppress(Exception):  # fenêtre déjà détruite
            window.destroy()


def _pump(window, cycles: int = 4) -> None:
    for _ in range(cycles):
        window.update()
        window.update_idletasks()
