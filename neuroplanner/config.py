"""Constantes, chemins et configuration globale de l'application."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

APP_NAME: Final[str] = "NeuroPlanner"
APP_VERSION: Final[str] = "1.3.1"
APP_TAGLINE: Final[str] = "5 h / jour · neuroplasticité"

DATA_FILENAME: Final[str] = "neuro_progress.json"
DATA_ENV_VAR: Final[str] = "NEUROPLANNER_DATA"
PLAN_FILENAME: Final[str] = "neuro_plan.json"
PLAN_ENV_VAR: Final[str] = "NEUROPLANNER_PLAN"
LLM_CONFIG_FILENAME: Final[str] = "llm_settings.json"

#: Clé courte -> libellé affiché. L'ordre définit la navigation.
DAYS: Final[tuple[tuple[str, str], ...]] = (
    ("lun", "Lundi"),
    ("mar", "Mardi"),
    ("mer", "Mercredi"),
    ("jeu", "Jeudi"),
    ("ven", "Vendredi"),
    ("sam", "Samedi"),
)
DAY_KEYS: Final[tuple[str, ...]] = tuple(key for key, _ in DAYS)
DAY_LABELS: Final[dict[str, str]] = dict(DAYS)

MONTHS_FR: Final[tuple[str, ...]] = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)

#: Objectif quotidien, en minutes (4 blocs).
DAILY_TARGET_MINUTES: Final[int] = 5 * 60


def user_data_dir(app_name: str = APP_NAME) -> Path:
    """Dossier de données de l'utilisateur, conforme aux conventions par OS."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / app_name


def resolve_data_file(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Emplacement du fichier de progression.

    Ordre de priorité : argument explicite (``--data-file``), variable
    d'environnement ``NEUROPLANNER_DATA``, puis dossier de données utilisateur.
    """
    if explicit:
        return Path(explicit).expanduser()
    from_env = os.environ.get(DATA_ENV_VAR)
    if from_env:
        return Path(from_env).expanduser()
    return user_data_dir() / DATA_FILENAME


def resolve_plan_file(
    explicit: str | os.PathLike[str] | None = None,
    data_file: Path | None = None,
) -> Path:
    """Emplacement du fichier de plan (domaines, blocs, tâches).

    Priorité : argument explicite (``--plan-file``), variable
    ``NEUROPLANNER_PLAN``, puis même dossier que la progression.
    """
    if explicit:
        return Path(explicit).expanduser()
    from_env = os.environ.get(PLAN_ENV_VAR)
    if from_env:
        return Path(from_env).expanduser()
    base = data_file.parent if data_file is not None else user_data_dir()
    return base / PLAN_FILENAME


def resolve_llm_config_file(data_file: Path | None = None) -> Path:
    """Fichier de réglages du fournisseur LLM (à côté de la progression)."""
    base = data_file.parent if data_file is not None else user_data_dir()
    return base / LLM_CONFIG_FILENAME


def asset_path(name: str) -> Path:
    """Chemin d'une ressource embarquée dans le package (icône, images)."""
    return Path(__file__).resolve().parent / "assets" / name


def initial_day(today_weekday: int) -> str:
    """Jour affiché au démarrage : aujourd'hui du lundi au samedi, sinon lundi."""
    return DAY_KEYS[0] if today_weekday > 5 else DAY_KEYS[today_weekday]
