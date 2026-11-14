"""Tests d'intégration de l'interface : la fenêtre réelle, avec un vrai Tk.

Ces tests sont marqués ``gui`` (voir ``pyproject.toml``) car ils ouvrent une
fenêtre : ``pytest -m "not gui"`` les exclut sur une machine sans écran.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

pytest.importorskip("customtkinter")

from neuroplanner.config import DAY_KEYS  # noqa: E402
from neuroplanner.data.curriculum import WEEK, WEEK_DAYS  # noqa: E402
from neuroplanner.data.store import FOCUS_SESSION_SECONDS  # noqa: E402
from neuroplanner.theme import PALETTE  # noqa: E402

pytestmark = pytest.mark.gui


def pump(window, cycles: int = 3) -> None:
    for _ in range(cycles):
        window.update()
        window.update_idletasks()


def first_row(app):
    return app.day_view.blocks[0].rows[0]


def test_window_shows_a_full_day(app) -> None:
    assert len(app.day_view.blocks) == 4
    assert sum(len(block.rows) for block in app.day_view.blocks) == 10
    assert app.timer.time_label.cget("text") == "45:00"
    assert app.day_view.percent_text == "0 %"


def test_toggling_a_task_persists_immediately(app, data_file: Path) -> None:
    row = first_row(app)
    tid = row.task.tid

    row.toggle()
    pump(app)

    assert row.is_done() is True
    assert app.store.is_done(tid) is True
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    assert payload["completed"] == {tid: True}

    row.toggle()
    pump(app)
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    assert payload["completed"] == {}


def test_toggle_updates_counters(app) -> None:
    first_row(app).toggle()
    pump(app)

    assert app.day_view.blocks[0].counter.cget("text") == "1/3"
    assert app.day_view.percent_text != "0 %"
    assert app.header.percent_label.cget("text") != "0 %"
    assert app.chart.bar_count() == 5


def test_every_day_renders(app) -> None:
    for day_key in DAY_KEYS:
        app.show_day(day_key)
        pump(app)
        assert app.current_day == day_key
        assert app.day_view.day.key == day_key
        assert len(app.day_view.blocks) == 4
        assert [nav._selected for nav in app.sidebar.nav_items.values()].count(True) == 1


def test_keyboard_shortcut_changes_day(app) -> None:
    app.show_day("lun")
    pump(app)
    app.event_generate("<Control-Key-2>")
    pump(app)
    assert app.current_day == "mar"


def test_unknown_day_is_ignored(app) -> None:
    before = app.current_day
    app.show_day("dim")
    pump(app)
    assert app.current_day == before


def test_reset_clears_ui_and_file(app, data_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for row in app.day_view.blocks[0].rows:
        row.toggle()
    pump(app)
    assert app.store.completed

    monkeypatch.setattr("neuroplanner.app.messagebox.askyesno", lambda *args, **kwargs: True)
    app.reset_week()
    pump(app)

    assert app.store.completed == set()
    assert all(not row.is_done() for block in app.day_view.blocks for row in block.rows)
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    assert payload["completed"] == {}
    assert app.chart.bar_count() == 5


def test_reset_can_be_cancelled(app, monkeypatch: pytest.MonkeyPatch) -> None:
    first_row(app).toggle()
    pump(app)

    monkeypatch.setattr("neuroplanner.app.messagebox.askyesno", lambda *args, **kwargs: False)
    app.reset_week()
    pump(app)

    assert app.store.completed


def test_timer_completes_and_records_session(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("neuroplanner.ui.timer_panel.play_chime", lambda *args, **kwargs: None)
    app.timer.countdown.set_duration(0.4)

    app.timer.start()
    deadline = time.time() + 5
    while app.timer.countdown.running and time.time() < deadline:
        pump(app, 1)
        time.sleep(0.02)
    pump(app)

    assert app.timer.countdown.finished is True
    assert app.timer.time_label.cget("text") == "00:00"
    assert app.store.sessions == 1
    assert "1 session" in app.timer.stats_label.cget("text")


def test_long_session_counts_as_focus_time(app) -> None:
    app.record_session(FOCUS_SESSION_SECONDS)
    assert app.store.focus_seconds == FOCUS_SESSION_SECONDS
    assert "45 min" in app.timer.stats_label.cget("text")


def test_pause_freezes_the_display(app) -> None:
    app.timer.start()
    pump(app)
    app.timer.pause()
    pump(app)

    assert app.timer.countdown.running is False
    frozen = app.timer.time_label.cget("text")
    time.sleep(0.25)
    pump(app)
    assert app.timer.time_label.cget("text") == frozen

    app.timer.reset()
    pump(app)
    assert app.timer.time_label.cget("text") == "45:00"


def test_preset_switch_updates_duration(app) -> None:
    assert app.timer.preset.label == "Focus 45"

    for preset in app.timer.presets:
        app.timer.select_preset(preset)
        pump(app)
        assert app.timer.time_label.cget("text") == f"{preset.seconds // 60:02d}:00"
        assert app.timer.segmented.get() == preset.label


def test_chart_uses_threshold_colours(app) -> None:
    for day in WEEK_DAYS:
        for task in day.tasks:
            if task.domain == "Dev & Archi":
                app.store.set_done(task.tid, True)
    app.refresh_aggregates()
    pump(app)

    colors = {app.chart.colour_of(index) for index in range(app.chart.bar_count())}
    assert PALETTE.green in colors
    assert PALETTE.red in colors


def test_chart_handles_empty_data(app) -> None:
    app.chart.refresh([])
    pump(app)
    assert app.chart.bar_count() == 0


def test_data_survives_a_restart(data_file: Path, app) -> None:
    row = first_row(app)
    tid = row.task.tid
    row.toggle()
    pump(app)
    app.timer.shutdown()
    app.destroy()

    from neuroplanner.app import NeuroPlanner

    reopened = NeuroPlanner(data_file)
    pump(reopened, 4)
    try:
        assert reopened.store.is_done(tid)
        assert first_row(reopened).is_done() is True
        assert reopened.current_day in WEEK
    finally:
        reopened.timer.shutdown()
        reopened.destroy()
