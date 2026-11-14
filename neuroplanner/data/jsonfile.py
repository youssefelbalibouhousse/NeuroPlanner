"""Écriture JSON atomique partagée par les fichiers d'état et de plan."""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any] | None:
    """Lit un objet JSON ; ``None`` si le fichier est absent ou illisible."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def write_json_atomic(path: Path, payload: dict[str, Any]) -> bool:
    """Écrit via un fichier temporaire + ``os.replace`` (jamais de JSON tronqué).

    Renvoie ``False`` si le disque refuse l'écriture : l'appelant décide quoi
    faire, l'application ne doit jamais planter pour un problème de permission.
    """
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        # Le nettoyage doit être protégé lui aussi : si un dossier du chemin est
        # en réalité un fichier, ``unlink`` lève NotADirectoryError (Linux).
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        return False
