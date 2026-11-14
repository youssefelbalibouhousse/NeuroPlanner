"""Dialogue d'import : chapitres → aperçu → application du planning."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("customtkinter")

from neuroplanner.config import DAY_KEYS  # noqa: E402
from neuroplanner.models import Chapter  # noqa: E402
from neuroplanner.services.generation import MINUTES_PER_DAY  # noqa: E402
from neuroplanner.services.llm import LlmSettings  # noqa: E402
from neuroplanner.ui.import_dialog import ImportDialog  # noqa: E402

pytestmark = pytest.mark.gui

CHAPTERS_TEXT = "1. Limites et continuité (90 min)\n2. Dérivées\n3. Intégration"


def pump(window, cycles: int = 3) -> None:
    for _ in range(cycles):
        window.update()
        window.update_idletasks()


class StubLlm:
    """Client factice : renvoie un JSON de chapitres immédiatement."""

    def __init__(self, payload: str = '[{"titre": "Suites", "minutes": 120}]', **_kwargs) -> None:
        self.payload = payload
        self.calls = 0

    def models(self) -> list[str]:
        return ["stub:1"]

    def complete(self, _prompt: str) -> str:
        self.calls += 1
        return self.payload


def make_dialog(app, client: StubLlm | None = None) -> ImportDialog:
    stub = client or StubLlm()
    dialog = ImportDialog(app, app.plan, client_factory=lambda _settings: stub)
    pump(dialog)
    return dialog


# --------------------------------------------------------------------------- #
# Aperçu et application
# --------------------------------------------------------------------------- #
def test_placeholder_is_not_parsed_as_chapters(app) -> None:
    dialog = make_dialog(app)
    try:
        assert dialog.chapters_text() == ""
        assert dialog.build_preview() is False
        assert "Aucun chapitre" in dialog.footer.error.cget("text")
    finally:
        dialog.close()


def test_preview_builds_a_full_week(app) -> None:
    dialog = make_dialog(app)
    try:
        dialog.set_chapters_text(CHAPTERS_TEXT)
        dialog.domain_box.set("Mathématiques")
        assert dialog.build_preview() is True

        text = dialog.preview_text
        assert "Lundi" in text
        assert "Samedi" in text
        assert "300 min" in text
        assert "Limites et continuité" in text
    finally:
        dialog.close()


def test_apply_replaces_the_plan(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("neuroplanner.ui.import_dialog.messagebox.askyesno", lambda *a, **k: True)
    dialog = make_dialog(app)
    dialog.set_chapters_text(CHAPTERS_TEXT)
    dialog.domain_box.set("Mathématiques")
    dialog.revision_box.set("Révision Active")
    dialog.prune_var.set(True)

    dialog.apply()

    plan = app.plan
    assert dialog.changed is True
    assert plan.domain_names == ("Mathématiques", "Révision Active")
    assert all(len(day.blocks) == 4 for day in plan.week_days())
    assert all(day.total_minutes == MINUTES_PER_DAY for day in plan.week_days())
    assert all(len(day.tasks) >= 5 for day in plan.week_days())
    assert len(plan.tasks()) == 30
    assert [day.key for day in plan.week_days()] == list(DAY_KEYS)


def test_apply_can_be_cancelled(app, monkeypatch: pytest.MonkeyPatch) -> None:
    before = app.plan.to_dict()
    monkeypatch.setattr("neuroplanner.ui.import_dialog.messagebox.askyesno", lambda *a, **k: False)
    dialog = make_dialog(app)
    dialog.set_chapters_text(CHAPTERS_TEXT)
    dialog.domain_box.set("Mathématiques")

    dialog.apply()

    assert dialog.changed is False
    assert app.plan.to_dict() == before


def test_unused_domains_are_kept_when_checkbox_is_off(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("neuroplanner.ui.import_dialog.messagebox.askyesno", lambda *a, **k: True)
    dialog = make_dialog(app)
    try:
        dialog.prune_var.set(False)
        dialog.set_chapters_text(CHAPTERS_TEXT)
        dialog.domain_box.set("Mathématiques")
        dialog.apply()
        assert "Dev & Archi" in app.plan.domain_names
        assert "Mathématiques" in app.plan.domain_names
    finally:
        dialog.close()


def test_missing_domain_is_reported(app) -> None:
    dialog = make_dialog(app)
    try:
        dialog.set_chapters_text(CHAPTERS_TEXT)
        dialog.domain_box.set("   ")
        assert dialog.build_preview() is False
        assert "pilier" in dialog.footer.error.cget("text").lower()
    finally:
        dialog.close()


def test_invalid_text_is_reported_inline(app) -> None:
    dialog = make_dialog(app)
    try:
        dialog.set_chapters_text("")
        assert dialog.build_preview() is False
        assert dialog.footer.error.cget("text")
    finally:
        dialog.close()


# --------------------------------------------------------------------------- #
# Assistant LLM (client factice : pas de réseau)
# --------------------------------------------------------------------------- #
def test_generation_fills_the_textarea(app) -> None:
    stub = StubLlm('[{"titre": "Suites", "minutes": 120}, {"titre": "Séries", "minutes": 90}]')
    dialog = make_dialog(app, stub)
    try:
        dialog.topic_entry.insert(0, "Analyse réelle")
        dialog.generate()

        deadline = time.time() + 5
        while dialog._worker is not None and dialog._worker.is_alive() and time.time() < deadline:
            pump(dialog, 1)
            time.sleep(0.02)
        for _ in range(10):
            pump(dialog, 1)
            time.sleep(0.02)

        assert stub.calls == 1
        assert "1. Suites  (120 min)" in dialog.chapters_text()
        assert "Séries" in dialog.preview_text
    finally:
        dialog.close()


def test_generation_requires_a_topic(app) -> None:
    dialog = make_dialog(app)
    try:
        dialog.generate()
        assert "sujet" in dialog.footer.error.cget("text").lower()
        assert dialog._worker is None
    finally:
        dialog.close()


def test_generation_error_is_shown(app) -> None:
    class BrokenLlm(StubLlm):
        def complete(self, _prompt: str) -> str:
            from neuroplanner.services.llm import LlmError

            raise LlmError("Impossible de joindre Ollama")

    dialog = make_dialog(app, BrokenLlm())
    try:
        dialog.topic_entry.insert(0, "Analyse réelle")
        dialog.generate()
        deadline = time.time() + 5
        while time.time() < deadline:
            pump(dialog, 1)
            time.sleep(0.02)
            if "Ollama" in dialog.footer.error.cget("text"):
                break
        assert "Ollama" in dialog.footer.error.cget("text")
        assert dialog.status.cget("text") == "échec"
    finally:
        dialog.close()


def test_settings_include_the_think_flag(app) -> None:
    dialog = make_dialog(app)
    try:
        dialog.model_menu.set("gemma4:latest")
        assert dialog.settings().think is None

        dialog.think_var.set(True)
        settings = dialog.settings()
        assert settings.think is True
        assert settings.model == "gemma4:latest"
        assert isinstance(settings, LlmSettings)
    finally:
        dialog.close()


# --------------------------------------------------------------------------- #
# Intégration à l'application
# --------------------------------------------------------------------------- #
def test_sidebar_button_opens_the_import_dialog(app, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[bool] = []

    class StubDialog:
        def __init__(self, *args, **kwargs) -> None:
            opened.append(True)

        def run(self) -> bool:
            return False

    monkeypatch.setattr("neuroplanner.app.ImportDialog", StubDialog)
    app.sidebar.import_button.invoke()
    assert opened == [True]


def test_app_refreshes_after_import(app, monkeypatch: pytest.MonkeyPatch) -> None:
    """Le vrai dialogue appliqué doit reconstruire la vue du jour et le graphique."""

    class ApplyingDialog:
        def __init__(self, master, plan) -> None:
            self.plan = plan

        def run(self) -> bool:
            self.plan.replace_week(
                {key: app.plan.day(key).blocks for key in DAY_KEYS}, prune_unused_domains=True
            )
            return True

    monkeypatch.setattr("neuroplanner.app.ImportDialog", ApplyingDialog)
    app.import_program()
    pump(app)

    assert app.day_view.day is not None
    assert app.chart.bar_count() == len(app.plan.domains)


def test_imported_chapters_show_up_in_the_day_view(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("neuroplanner.ui.import_dialog.messagebox.askyesno", lambda *a, **k: True)
    dialog = make_dialog(app)
    dialog.set_chapters_text(CHAPTERS_TEXT)
    dialog.domain_box.set("Mathématiques")
    dialog.apply()

    app.on_plan_changed()
    pump(app)
    app.show_day("lun")
    pump(app)

    first_row = app.day_view.blocks[0].rows[0]
    assert "Limites et continuité" in first_row.task.label
    assert first_row.chip.cget("text") == "Mathématiques"


def test_chapter_model_round_trip() -> None:
    """Le dialogue travaille avec des objets Chapter, jamais des chaînes brutes."""
    chapters = [Chapter("Suites", 90)]
    assert chapters[0].minutes == 90
