"""Édition du plan depuis l'interface : domaines, tâches, propagation aux vues."""

from __future__ import annotations

import pytest

pytest.importorskip("customtkinter")

from neuroplanner.theme import PALETTE  # noqa: E402
from neuroplanner.ui.dialogs import DomainDialog, TaskDialog  # noqa: E402

pytestmark = pytest.mark.gui


def pump(window, cycles: int = 3) -> None:
    for _ in range(cycles):
        window.update()
        window.update_idletasks()


def chart_values(app) -> list[float]:
    return [app.chart.value_of(index) for index in range(app.chart.bar_count())]


def row_labels(app) -> list[str]:
    return [row.task.label for block in app.day_view.blocks for row in block.rows]


# --------------------------------------------------------------------------- #
# Dialogues (sans attente modale)
# --------------------------------------------------------------------------- #
def test_domain_dialog_adds_a_domain(app) -> None:
    dialog = DomainDialog(app, app.plan)
    pump(dialog)
    try:
        dialog.name_entry.insert(0, "Mathématiques")
        dialog.add_domain()
        pump(dialog)

        assert "Mathématiques" in app.plan.domain_names
        assert dialog.changed is True
        assert len(dialog._rows) == len(app.plan.domains)
    finally:
        dialog.close()


def test_domain_dialog_reports_duplicates_inline(app) -> None:
    dialog = DomainDialog(app, app.plan)
    pump(dialog)
    try:
        dialog.name_entry.insert(0, "projets")
        dialog.add_domain()
        pump(dialog)

        assert "existe déjà" in dialog.footer.error.cget("text")
        assert len(app.plan.domains) == 5
    finally:
        dialog.close()


def test_domain_dialog_renames(app) -> None:
    dialog = DomainDialog(app, app.plan)
    pump(dialog)
    try:
        dialog.rename("Projets", "Produits")
        pump(dialog)
        assert "Produits" in app.plan.domain_names
        assert "Projets" not in app.plan.domain_names
    finally:
        dialog.close()


def test_domain_dialog_deletes_with_confirmation(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("neuroplanner.ui.dialogs.messagebox.askyesno", lambda *a, **k: True)
    before = app.plan.task_count("Arabe MSA")
    dialog = DomainDialog(app, app.plan)
    pump(dialog)
    try:
        dialog.delete_domain("Arabe MSA")
        pump(dialog)
        assert "Arabe MSA" not in app.plan.domain_names
        assert "supprimé" in dialog.footer.error.cget("text")
        assert before > 0
    finally:
        dialog.close()


def test_domain_dialog_delete_can_be_declined(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("neuroplanner.ui.dialogs.messagebox.askyesno", lambda *a, **k: False)
    dialog = DomainDialog(app, app.plan)
    pump(dialog)
    try:
        dialog.delete_domain("Projets")
        assert "Projets" in app.plan.domain_names
    finally:
        dialog.close()


def test_domain_dialog_cycles_colours(app) -> None:
    dialog = DomainDialog(app, app.plan)
    pump(dialog)
    try:
        before = app.plan.color_of("Projets")
        dialog.cycle_color("Projets")
        pump(dialog)
        assert app.plan.color_of("Projets") != before
    finally:
        dialog.close()


def test_task_dialog_creates_a_task(app) -> None:
    dialog = TaskDialog(app, app.plan, "lun", 0)
    pump(dialog)
    dialog.name_entry.insert(0, "Nouvel item")
    dialog.domain_menu.set("Projets")
    dialog.duration_menu.set("30 min")
    dialog.save()

    created = [task for task in app.plan.day("lun").blocks[0].tasks if task.label == "Nouvel item"]
    assert len(created) == 1
    assert (created[0].domain, created[0].minutes) == ("Projets", 30)
    assert dialog.changed is True


def test_task_dialog_validates_the_label(app) -> None:
    dialog = TaskDialog(app, app.plan, "lun", 0)
    pump(dialog)
    try:
        dialog.save()
        pump(dialog)
        assert "intitulé" in dialog.footer.error.cget("text").lower()
        assert dialog.changed is False
    finally:
        dialog.close()


def test_task_dialog_edits_an_existing_task(app) -> None:
    task = app.plan.day("lun").tasks[0]
    dialog = TaskDialog(app, app.plan, "lun", 0, task)
    pump(dialog)
    dialog.name_entry.delete(0, "end")
    dialog.name_entry.insert(0, "Intitulé révisé")
    dialog.duration_menu.set("20 min")
    dialog.save()

    updated = app.plan.find_task(task.tid)
    assert updated.label == "Intitulé révisé"
    assert updated.minutes == 20
    assert updated.tid == task.tid


def test_task_dialog_deletes_with_confirmation(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("neuroplanner.ui.dialogs.messagebox.askyesno", lambda *a, **k: True)
    task = app.plan.day("lun").tasks[0]
    dialog = TaskDialog(app, app.plan, "lun", 0, task)
    pump(dialog)
    dialog.delete()

    assert app.plan.find_task(task.tid) is None
    assert dialog.changed is True


# --------------------------------------------------------------------------- #
# Propagation dans l'application
# --------------------------------------------------------------------------- #
def test_new_domain_appears_in_the_chart_as_empty(app) -> None:
    app.plan.add_domain("Mathématiques")
    app.on_plan_changed()
    pump(app)

    assert app.chart.bar_count() == 6
    values = chart_values(app)
    assert values[-1] == 0.0
    assert app.chart.colour_of(len(values) - 1) == PALETTE.dim
    assert "(6)" in app.sidebar.domains_button.cget("text")


def test_added_task_appears_in_the_day_view(app) -> None:
    app.show_day("lun")
    pump(app)
    app.plan.add_task("lun", 0, label="Tâche ajoutée", domain="Projets", minutes=15)
    app.on_plan_changed()
    pump(app)

    assert "Tâche ajoutée" in row_labels(app)
    assert len(app.day_view.blocks[0].rows) == 4


def test_edited_task_is_visible_immediately(app) -> None:
    app.show_day("lun")
    pump(app)
    task = app.day_view.blocks[0].rows[0].task
    app.plan.update_task(task.tid, label="Intitulé modifié", domain="Arabe MSA", minutes=12)
    app.on_plan_changed()
    pump(app)

    row = app.day_view.blocks[0].rows[0]
    assert row.task.label == "Intitulé modifié"
    assert row.chip.cget("text") == "Arabe MSA"
    assert "12 min" in row.minutes.cget("text")


def test_deleting_a_domain_prunes_progress_and_chart(app) -> None:
    first = app.plan.day("lun").tasks[0]
    assert first.domain == "Dev & Archi"
    app.store.set_done(first.tid, True)

    app.plan.delete_domain("Dev & Archi")
    app.on_plan_changed()
    pump(app)

    assert app.chart.bar_count() == 4
    assert first.tid not in app.store.completed
    assert first.tid not in app.plan.task_ids()


def test_empty_block_shows_a_hint(app) -> None:
    app.show_day("lun")
    pump(app)
    for task in list(app.plan.day("lun").blocks[3].tasks):
        app.plan.delete_task(task.tid)
    app.on_plan_changed()
    pump(app)

    card = app.day_view.blocks[3]
    assert card.rows == []
    assert card.empty_label is not None
    assert card.counter.cget("text") == "vide"


def test_add_task_button_opens_the_dialog(app, monkeypatch: pytest.MonkeyPatch) -> None:
    """Le bouton « + » d'un bloc ouvre le dialogue de création, sur le bon bloc."""
    opened: list[tuple[str, int, object]] = []

    class StubDialog:
        def __init__(self, master, plan, day_key, block_index, task=None) -> None:
            opened.append((day_key, block_index, task))

        def run(self) -> bool:
            return False

    monkeypatch.setattr("neuroplanner.app.TaskDialog", StubDialog)
    app.show_day("lun")
    pump(app)

    app.day_view.blocks[2].add_button.invoke()

    assert opened == [("lun", 2, None)]


def test_edit_button_opens_the_dialog_for_that_task(app, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[tuple[str, int, object]] = []

    class StubDialog:
        def __init__(self, master, plan, day_key, block_index, task=None) -> None:
            opened.append((day_key, block_index, task))

        def run(self) -> bool:
            return False

    monkeypatch.setattr("neuroplanner.app.TaskDialog", StubDialog)
    app.show_day("ven")
    pump(app)

    row = app.day_view.blocks[1].rows[0]
    row.edit_button.invoke()

    assert opened and opened[0][0] == "ven"
    assert opened[0][1] == 1
    assert opened[0][2] is not None
    assert opened[0][2].tid == row.task.tid


def test_confirmed_task_creation_rebuilds_the_view(app, monkeypatch: pytest.MonkeyPatch) -> None:
    class StubDialog:
        def __init__(self, master, plan, day_key, block_index, task=None) -> None:
            self.plan, self.day_key, self.block_index = plan, day_key, block_index

        def run(self) -> bool:
            self.plan.add_task(
                self.day_key, self.block_index, label="Créée via bouton", domain="Projets", minutes=15
            )
            return True

    monkeypatch.setattr("neuroplanner.app.TaskDialog", StubDialog)
    app.show_day("lun")
    pump(app)

    app.day_view.blocks[0].add_button.invoke()
    pump(app)

    assert "Créée via bouton" in row_labels(app)


def test_domain_button_opens_the_dialog(app, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[bool] = []

    class StubDialog:
        def __init__(self, *args, **kwargs) -> None:
            opened.append(True)

        def run(self) -> bool:
            return False

    monkeypatch.setattr("neuroplanner.app.DomainDialog", StubDialog)
    app.sidebar.domains_button.invoke()
    assert opened == [True]


def test_plan_is_persisted_next_to_the_progress_file(app, data_file) -> None:
    plan_path = data_file.parent / "neuro_plan.json"
    assert plan_path.exists()
    app.plan.add_domain("Persistant")
    assert "Persistant" in plan_path.read_text(encoding="utf-8")
