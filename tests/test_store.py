"""Persistance : écriture atomique, rechargement, tolérance aux fichiers abîmés."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroplanner.data.curriculum import TASKS_BY_ID
from neuroplanner.data.store import FOCUS_SESSION_SECONDS, ProgressStore

KNOWN_TID = next(iter(TASKS_BY_ID))


def read_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_store_creates_file_on_first_run(data_file: Path) -> None:
    ProgressStore(data_file)
    assert data_file.exists()
    payload = read_payload(data_file)
    assert payload["version"] == ProgressStore.VERSION
    assert payload["completed"] == {}
    assert payload["stats"] == {"sessions": 0, "focus_seconds": 0}


def test_set_done_persists_immediately(data_file: Path) -> None:
    store = ProgressStore(data_file)
    assert store.set_done(KNOWN_TID, True) is True
    assert read_payload(data_file)["completed"] == {KNOWN_TID: True}

    reloaded = ProgressStore(data_file)
    assert reloaded.is_done(KNOWN_TID)


def test_toggle_round_trip(data_file: Path) -> None:
    store = ProgressStore(data_file)
    assert store.toggle(KNOWN_TID) is True
    assert store.toggle(KNOWN_TID) is False
    assert ProgressStore(data_file).completed == set()


def test_reset_week_keeps_focus_stats(data_file: Path) -> None:
    store = ProgressStore(data_file)
    store.set_done(KNOWN_TID, True)
    store.add_session(FOCUS_SESSION_SECONDS)

    store.reset_week()

    assert store.completed == set()
    assert store.sessions == 1
    assert store.focus_seconds == FOCUS_SESSION_SECONDS
    reloaded = ProgressStore(data_file)
    assert reloaded.completed == set()
    assert reloaded.sessions == 1


def test_add_session_counts_only_long_sessions_as_focus(data_file: Path) -> None:
    store = ProgressStore(data_file)
    store.add_session(3 * 60)  # feuille blanche
    store.add_session(FOCUS_SESSION_SECONDS)  # focus 45
    assert store.sessions == 2
    assert store.focus_seconds == FOCUS_SESSION_SECONDS


def test_unknown_task_ids_are_dropped_when_plan_is_known(data_file: Path) -> None:
    data_file.write_text(
        json.dumps({"completed": {"lun-0-0": True, "obsolète": True}}), encoding="utf-8"
    )
    store = ProgressStore(data_file, valid_ids={"lun-0-0"})
    assert store.completed == {"lun-0-0"}


def test_store_keeps_everything_without_a_plan(data_file: Path) -> None:
    """Sans plan fourni, la validation est désactivée (compatibilité)."""
    data_file.write_text(json.dumps({"completed": {"arbitraire": True}}), encoding="utf-8")
    store = ProgressStore(data_file)
    assert store.completed == {"arbitraire"}


def test_prune_removes_orphans(data_file: Path) -> None:
    store = ProgressStore(data_file)
    store.set_done("lun-0-0", True)
    store.set_done("t-abc", True)

    assert store.prune({"lun-0-0"}) == 1
    assert store.completed == {"lun-0-0"}
    assert ProgressStore(data_file, valid_ids={"lun-0-0"}).completed == {"lun-0-0"}


def test_forget_is_a_noop_for_unknown_ids(data_file: Path) -> None:
    store = ProgressStore(data_file)
    store.set_done("lun-0-0", True)
    assert store.forget({"inconnu"}) == 0
    assert store.completed == {"lun-0-0"}
    assert store.forget({"lun-0-0"}) == 1
    assert store.completed == set()


def test_legacy_list_format_is_accepted(data_file: Path) -> None:
    data_file.write_text(json.dumps({"completed": ["lun-0-0", 42]}), encoding="utf-8")
    store = ProgressStore(data_file)
    assert store.completed == {"lun-0-0"}


def test_corrupted_file_is_quarantined(data_file: Path) -> None:
    data_file.write_text("{ pas du json", encoding="utf-8")

    store = ProgressStore(data_file)

    assert store.completed == set()
    assert data_file.with_suffix(".corrupt.json").exists()


def test_non_object_payload_is_ignored(data_file: Path) -> None:
    data_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert ProgressStore(data_file).completed == set()


def test_save_is_atomic_and_leaves_no_temp_file(data_file: Path) -> None:
    store = ProgressStore(data_file)
    store.set_done(KNOWN_TID, True)
    assert not data_file.with_suffix(".tmp").exists()


def test_unwritable_location_does_not_raise(tmp_path: Path) -> None:
    # Un chemin dont le parent est un fichier ne peut pas être créé.
    blocker = tmp_path / "fichier"
    blocker.write_text("x", encoding="utf-8")
    store = ProgressStore(blocker / "sous" / "progress.json")
    store.set_done(KNOWN_TID, True)  # ne doit pas lever
    assert store.is_done(KNOWN_TID)


def test_stats_payload_is_validated(data_file: Path) -> None:
    data_file.write_text(
        json.dumps({"completed": {}, "stats": {"sessions": "beaucoup", "focus_seconds": -5}}),
        encoding="utf-8",
    )
    store = ProgressStore(data_file)
    assert store.sessions == 0
    assert store.focus_seconds == 0


@pytest.mark.parametrize("done", [True, False])
def test_set_done_returns_effective_state(data_file: Path, done: bool) -> None:
    store = ProgressStore(data_file)
    assert store.set_done(KNOWN_TID, done) is done
