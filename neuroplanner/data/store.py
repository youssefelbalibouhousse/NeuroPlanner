"""Persistance locale de la progression (JSON, écriture atomique)."""

from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime
from pathlib import Path

from neuroplanner.data.curriculum import TASKS_BY_ID

#: Une session de ``Focus 45`` compte comme du temps de focus.
FOCUS_SESSION_SECONDS = 45 * 60


class ProgressStore:
    """État persistant : tâches cochées et statistiques d'assiduité.

    Le fichier est réécrit intégralement à chaque changement via un fichier
    temporaire puis ``os.replace`` : une coupure ne peut pas le corrompre.
    """

    VERSION = 1

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.completed: set[str] = set()
        self.sessions = 0
        self.focus_seconds = 0
        self.load()
        if not self.path.exists():
            self.save()

    # -- lecture ---------------------------------------------------------- #
    def is_done(self, tid: str) -> bool:
        return tid in self.completed

    def load(self) -> None:
        """Recharge l'état ; un fichier illisible est mis en quarantaine."""
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            self._quarantine()
            return
        if not isinstance(raw, dict):
            return

        completed = raw.get("completed", {})
        if isinstance(completed, dict):
            self.completed = {
                tid for tid, done in completed.items() if done and tid in TASKS_BY_ID
            }
        elif isinstance(completed, list):
            self.completed = {
                tid for tid in completed if isinstance(tid, str) and tid in TASKS_BY_ID
            }

        stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
        self.sessions = max(0, _as_int(stats.get("sessions")))
        self.focus_seconds = max(0, _as_int(stats.get("focus_seconds")))

    # -- écriture --------------------------------------------------------- #
    def save(self) -> None:
        payload = {
            "version": self.VERSION,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "completed": {tid: True for tid in sorted(self.completed)},
            "stats": {"sessions": self.sessions, "focus_seconds": self.focus_seconds},
        }
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, self.path)
        except OSError:
            tmp.unlink(missing_ok=True)

    def _quarantine(self) -> None:
        """Écarte un fichier illisible plutôt que de le perdre silencieusement."""
        with contextlib.suppress(OSError):
            self.path.replace(self.path.with_suffix(".corrupt.json"))

    # -- mutations -------------------------------------------------------- #
    def set_done(self, tid: str, done: bool) -> bool:
        """Enregistre l'état d'une tâche ; renvoie l'état effectif."""
        if done:
            self.completed.add(tid)
        else:
            self.completed.discard(tid)
        self.save()
        return self.is_done(tid)

    def toggle(self, tid: str) -> bool:
        return self.set_done(tid, tid not in self.completed)

    def reset_week(self) -> None:
        """Décoche tout ; les statistiques de focus sont conservées."""
        self.completed.clear()
        self.save()

    def add_session(self, seconds: int) -> None:
        """Comptabilise un minuteur terminé."""
        self.sessions += 1
        if seconds >= FOCUS_SESSION_SECONDS:
            self.focus_seconds += seconds
        self.save()


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
