"""Plan modifiable : domaines, tâches, persistance et format d'échange."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroplanner.config import DAY_KEYS
from neuroplanner.data.curriculum import DEFAULT_DOMAINS, RAW_WEEK
from neuroplanner.data.plan_store import MAX_TASK_MINUTES, PlanStore
from neuroplanner.models import Block, Task
from neuroplanner.theme import DOMAIN_PALETTE


@pytest.fixture
def plan_file(tmp_path: Path) -> Path:
    return tmp_path / "neuro_plan.json"


@pytest.fixture
def plan(plan_file: Path) -> PlanStore:
    return PlanStore(plan_file)


# --------------------------------------------------------------------------- #
# Amorçage et persistance
# --------------------------------------------------------------------------- #
def test_first_run_creates_the_file_from_the_default_week(plan_file: Path) -> None:
    store = PlanStore(plan_file)

    assert plan_file.exists()
    assert store.domain_names == tuple(domain.name for domain in DEFAULT_DOMAINS)
    assert [day.key for day in store.week_days()] == list(DAY_KEYS)
    assert sum(len(day.tasks) for day in store.week_days()) == 60
    assert store.total_minutes() == 1800


def test_default_ids_are_positional_and_stable(plan: PlanStore) -> None:
    assert "lun-0-0" in plan.task_ids()
    assert plan.find_task("lun-0-0") is not None
    assert plan.to_dict()["days"]["lun"][0]["tasks"][0]["id"] == "lun-0-0"


def test_plan_round_trips_through_disk(plan_file: Path) -> None:
    store = PlanStore(plan_file)
    store.add_domain("Mathématiques")
    store.add_task("lun", 0, label="Analyse : limites", domain="Mathématiques", minutes=30)

    reloaded = PlanStore(plan_file)

    assert "Mathématiques" in reloaded.domain_names
    assert reloaded.find_task("lun-0-3") is not None or any(
        task.label == "Analyse : limites" for task in reloaded.day("lun").tasks
    )
    assert reloaded.task_count("Mathématiques") == 1


def test_saved_document_has_the_documented_shape(plan_file: Path) -> None:
    PlanStore(plan_file)
    raw = json.loads(plan_file.read_text(encoding="utf-8"))

    assert raw["version"] == PlanStore.VERSION
    assert isinstance(raw["domains"], list)
    assert set(raw["days"]) == set(DAY_KEYS)
    block = raw["days"]["lun"][0]
    assert {"start", "end", "title", "intent", "tasks"} <= set(block)
    assert {"id", "label", "domain", "minutes"} <= set(block["tasks"][0])


# --------------------------------------------------------------------------- #
# Domaines
# --------------------------------------------------------------------------- #
def test_add_domain_appends_with_a_palette_colour(plan: PlanStore) -> None:
    domain = plan.add_domain("  Mathématiques  ")

    assert domain.name == "Mathématiques"
    assert domain.color in DOMAIN_PALETTE
    assert plan.domain_names[-1] == "Mathématiques"
    assert plan.has_domain("mathématiques")  # insensible à la casse


def test_add_domain_trims_and_limits_length(plan: PlanStore) -> None:
    domain = plan.add_domain("   " + "x" * 80 + "   ")
    assert len(domain.name) == 40


@pytest.mark.parametrize("name", ["", "   ", "dev & archi", "DEV & ARCHI"])
def test_add_domain_rejects_empty_or_duplicate(plan: PlanStore, name: str) -> None:
    with pytest.raises(ValueError):
        plan.add_domain(name)


def test_add_domain_accepts_an_explicit_colour(plan: PlanStore) -> None:
    domain = plan.add_domain("Musique", "#123456")
    assert domain.color == "#123456"


def test_add_domain_falls_back_on_invalid_colour(plan: PlanStore) -> None:
    domain = plan.add_domain("Musique", "rouge")
    assert domain.color in DOMAIN_PALETTE


def test_new_domains_get_distinct_colours(plan: PlanStore) -> None:
    used = {domain.color.upper() for domain in plan.domains}
    added = {plan.add_domain(f"Domaine {index}").color.upper() for index in range(3)}
    assert not (added & used)


def test_rename_domain_updates_its_tasks(plan: PlanStore) -> None:
    before = plan.task_count("Projets")
    plan.rename_domain("Projets", "Produits")

    assert "Projets" not in plan.domain_names
    assert plan.task_count("Produits") == before
    assert {task.domain for task in plan.day("lun").tasks} == set(plan.domain_names)


def test_rename_domain_rejects_duplicates(plan: PlanStore) -> None:
    with pytest.raises(ValueError):
        plan.rename_domain("Projets", "arabe msa")


def test_rename_unknown_domain_fails(plan: PlanStore) -> None:
    with pytest.raises(ValueError):
        plan.rename_domain("Inconnu", "Autre")


def test_delete_domain_removes_its_tasks(plan: PlanStore) -> None:
    expected = plan.task_count("Arabe MSA")
    assert expected > 0

    removed = plan.delete_domain("Arabe MSA")

    assert removed == expected
    assert "Arabe MSA" not in plan.domain_names
    assert all(task.domain != "Arabe MSA" for day in plan.week_days() for task in day.tasks)
    assert not any(task.domain == "Arabe MSA" for task in plan.tasks().values())


def test_delete_domain_persists(plan_file: Path) -> None:
    store = PlanStore(plan_file)
    store.delete_domain("Projets")
    assert "Projets" not in PlanStore(plan_file).domain_names


def test_cannot_delete_the_last_domain(plan: PlanStore) -> None:
    for name in plan.domain_names[1:]:
        plan.delete_domain(name)
    with pytest.raises(ValueError, match="dernier domaine"):
        plan.delete_domain(plan.domain_names[0])


def test_set_domain_color(plan: PlanStore) -> None:
    plan.set_domain_color("Projets", "#ABCDEF")
    assert plan.color_of("Projets") == "#ABCDEF"
    assert plan.colors()["Projets"] == "#ABCDEF"
    with pytest.raises(ValueError):
        plan.set_domain_color("Projets", "pas une couleur")


# --------------------------------------------------------------------------- #
# Tâches
# --------------------------------------------------------------------------- #
def test_add_task_creates_a_stable_id(plan: PlanStore) -> None:
    task = plan.add_task("mar", 1, label="Réviser JEPA", domain="IA & World Models", minutes=25)

    assert task.tid.startswith("t")
    assert task.tid in plan.task_ids()
    assert task.minutes == 25
    assert any(item.label == "Réviser JEPA" for item in plan.day("mar").blocks[1].tasks)


def test_add_task_keeps_ids_unique(plan: PlanStore) -> None:
    first = plan.add_task("lun", 0, label="A", domain="Projets", minutes=10)
    second = plan.add_task("lun", 0, label="B", domain="Projets", minutes=10)
    assert first.tid != second.tid


def test_add_task_does_not_shift_existing_ids(plan: PlanStore) -> None:
    """Le point clé : ajouter une tâche ne décale jamais les identifiants existants."""
    before = plan.task_ids()
    plan.add_task("lun", 0, label="Nouvelle", domain="Projets", minutes=15)
    assert before <= plan.task_ids()


@pytest.mark.parametrize(
    ("label", "domain", "minutes"),
    [
        ("", "Projets", 30),
        ("   ", "Projets", 30),
        ("Valide", "Inconnu", 30),
        ("Valide", "Projets", 0),
        ("Valide", "Projets", MAX_TASK_MINUTES + 1),
        ("Valide", "Projets", "beaucoup"),
    ],
)
def test_add_task_validates_input(plan: PlanStore, label: str, domain: str, minutes: object) -> None:
    with pytest.raises(ValueError):
        plan.add_task("lun", 0, label=label, domain=domain, minutes=minutes)  # type: ignore[arg-type]


def test_add_task_rejects_unknown_block(plan: PlanStore) -> None:
    with pytest.raises(ValueError):
        plan.add_task("lun", 99, label="X", domain="Projets", minutes=10)
    with pytest.raises(ValueError):
        plan.add_task("dim", 0, label="X", domain="Projets", minutes=10)


def test_update_task_changes_fields_and_keeps_id(plan: PlanStore) -> None:
    task = plan.add_task("lun", 0, label="Brouillon", domain="Projets", minutes=10)
    updated = plan.update_task(task.tid, label="Final", domain="Arabe MSA", minutes=40)

    assert updated.tid == task.tid
    assert (updated.label, updated.domain, updated.minutes) == ("Final", "Arabe MSA", 40)
    assert plan.find_task(task.tid).label == "Final"


def test_update_task_is_persisted(plan_file: Path) -> None:
    store = PlanStore(plan_file)
    store.update_task("lun-0-0", minutes=50)
    assert PlanStore(plan_file).find_task("lun-0-0").minutes == 50


def test_update_unknown_task_fails(plan: PlanStore) -> None:
    with pytest.raises(ValueError):
        plan.update_task("t-inconnu", label="X")


def test_delete_task(plan: PlanStore) -> None:
    assert plan.delete_task("lun-0-0") is True
    assert plan.find_task("lun-0-0") is None
    assert plan.delete_task("lun-0-0") is False


def test_block_can_be_emptied(plan: PlanStore) -> None:
    for task in list(plan.day("lun").blocks[3].tasks):
        plan.delete_task(task.tid)
    assert plan.day("lun").blocks[3].tasks == ()


# --------------------------------------------------------------------------- #
# Robustesse et remplacement global
# --------------------------------------------------------------------------- #
def test_malformed_document_is_tolerated(plan_file: Path) -> None:
    plan_file.write_text("{pas du json", encoding="utf-8")
    store = PlanStore(plan_file)
    assert store.domain_names  # amorcé avec les domaines par défaut


def test_partial_document_is_repaired(plan_file: Path) -> None:
    plan_file.write_text(
        json.dumps(
            {
                "domains": [{"name": "", "color": "x"}, {"name": "Dev & Archi"}],
                "days": {
                    "lun": [
                        {"title": "Bloc", "tasks": [{"id": "a", "label": "T", "domain": "Divers", "minutes": 30}]},
                        "invalide",
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    store = PlanStore(plan_file)

    assert "Dev & Archi" in store.domain_names
    assert "Divers" in store.domain_names  # découvert dans les tâches
    assert len(store.day("lun").blocks) == 1
    assert store.day("lun").tasks[0].tid == "a"


def test_duplicate_task_ids_are_dropped(plan_file: Path) -> None:
    tasks = [
        {"id": "dup", "label": "A", "domain": "Divers", "minutes": 10},
        {"id": "dup", "label": "B", "domain": "Divers", "minutes": 10},
    ]
    plan_file.write_text(
        json.dumps({"domains": [{"name": "Divers"}], "days": {"lun": [{"tasks": tasks}]}}),
        encoding="utf-8",
    )
    store = PlanStore(plan_file)
    assert [task.label for task in store.day("lun").tasks] == ["A"]


def test_replace_week_supports_a_generator_payload(plan: PlanStore) -> None:
    """Point d'entrée du futur générateur LLM : fournir des blocs par jour."""
    generated = {
        day_key: [
            Block(
                "08:00",
                "09:00",
                "Chapitre",
                "Lecture active",
                (
                    Task(f"Chapitre 1 — {day_key}", "Mathématiques", 40),
                    Task("Exercices", "Mathématiques", 20),
                ),
            )
        ]
        for day_key in DAY_KEYS
    }

    plan.replace_week(generated)

    assert "Mathématiques" in plan.domain_names
    assert len(plan.day("lun").blocks) == 1
    assert [task.label for task in plan.day("lun").tasks][0] == "Chapitre 1 — lun"
    assert plan.total_minutes() == 6 * 60
    assert len(plan.task_ids()) == 12


def test_replace_week_rejects_unknown_days(plan: PlanStore) -> None:
    with pytest.raises(ValueError, match="jours inconnus"):
        plan.replace_week({"dim": [Block("08:00", "09:00", "X", "", ())]})


def test_replace_week_keeps_existing_domains(plan: PlanStore) -> None:
    plan.replace_week({"lun": [Block("08:00", "09:00", "X", "", (Task("T", "Projets", 10),))]})
    assert {"Projets", "Arabe MSA"} <= set(plan.domain_names)


def test_reset_to_default_restores_the_seed(plan: PlanStore) -> None:
    plan.add_domain("Mathématiques")
    plan.add_task("lun", 0, label="X", domain="Mathématiques", minutes=20)
    plan.delete_domain("Projets")

    plan.reset_to_default()

    assert plan.domain_names == tuple(domain.name for domain in DEFAULT_DOMAINS)
    assert len(plan.task_ids()) == 60
    assert plan.total_minutes() == 1800


def test_default_week_minutes_are_five_hours_per_day() -> None:
    from neuroplanner.data.curriculum import build_week

    week = build_week(RAW_WEEK)
    assert all(day.total_minutes == 300 for day in week.values())
