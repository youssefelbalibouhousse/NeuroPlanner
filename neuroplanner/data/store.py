"""Persistance locale de la progression (JSON, écriture atomique).

La progression est distincte du plan : elle ne contient que les identifiants de
tâches cochées et les statistiques d'assiduité. Si le plan change (domaine ou
tâche supprimés), les identifiants devenus inconnus sont ignorés au chargement.
"""

from __future__ import annotations

import contextlib
from collections.abc import Collection
from datetime import datetime
from pathlib import Path

from neuroplanner.data.jsonfile import read_json, write_json_atomic

#: Une session de ``Focus 45`` compte comme du temps de focus.
FOCUS_SESSION_SECONDS = 45 * 60


class ProgressStore:
    """État persistant : tâches cochées et statistiques d'assiduité.

    Le fichier est réécrit intégralement à chaque changement via un fichier
    temporaire puis ``os.replace`` : une coupure ne peut pas le corrompre.
    """

    VERSION = 1

    def __init__(
        self,
        path: Path | str,
        *,
        valid_ids: Collection[str] | None = None,
    ) -> None:
        self.path = Path(path)
        self._valid_ids = set(valid_ids) if valid_ids is not None else None
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
        raw = read_json(self.path)
        if raw is None:
            if self.path.exists():
                self._quarantine()
            return

        completed = raw.get("completed", {})
        candidates: set[str]
        if isinstance(completed, dict):
            candidates = {tid for tid, done in completed.items() if done and isinstance(tid, str)}
        elif isinstance(completed, list):
            candidates = {tid for tid in completed if isinstance(tid, str)}
        else:
            candidates = set()
        self.completed = self._keep_known(candidates)

        stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
        self.sessions = max(0, _as_int(stats.get("sessions")))
        self.focus_seconds = max(0, _as_int(stats.get("focus_seconds")))

    def _keep_known(self, ids: set[str]) -> set[str]:
        if self._valid_ids is None:
            return ids
        return {tid for tid in ids if tid in self._valid_ids}

    # -- écriture --------------------------------------------------------- #
    def save(self) -> None:
        write_json_atomic(
            self.path,
            {
                "version": self.VERSION,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "completed": {tid: True for tid in sorted(self.completed)},
                "stats": {"sessions": self.sessions, "focus_seconds": self.focus_seconds},
            },
        )

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

    def forget(self, tids: Collection[str]) -> int:
        """Oublie les tâches supprimées du plan ; renvoie le nombre oublié."""
        removed = self.completed & set(tids)
        if not removed:
            return 0
        self.completed -= removed
        self.save()
        return len(removed)

    def prune(self, valid_ids: Collection[str]) -> int:
        """Élimine les identifiants qui ne font plus partie du plan."""
        self._valid_ids = set(valid_ids)
        orphans = self.completed - self._valid_ids
        if not orphans:
            return 0
        self.completed -= orphans
        self.save()
        return len(orphans)


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
