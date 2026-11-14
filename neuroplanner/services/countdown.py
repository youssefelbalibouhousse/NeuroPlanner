"""Compte à rebours pur (aucun widget) : logique testable du minuteur.

Le temps ne dépend pas de ``after()`` de Tk : la source de temps est injectable,
ce qui permet de tester le minuteur sans interface ni attente réelle.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

#: En dessous de ce seuil, ``start()`` repart du début.
RESTART_THRESHOLD = 0.05


class Countdown:
    """Chronomètre décomptant, monotone et précis au dixième de seconde."""

    def __init__(self, duration: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        if duration <= 0:
            raise ValueError("duration must be positive")
        self._clock = clock
        self._duration = float(duration)
        self._remaining = float(duration)
        self._deadline = 0.0
        self.running = False
        self.finished = False

    # -- lecture ---------------------------------------------------------- #
    @property
    def duration(self) -> float:
        return self._duration

    @property
    def remaining(self) -> float:
        if self.running:
            return max(0.0, self._deadline - self._clock())
        return max(0.0, self._remaining)

    @property
    def display_seconds(self) -> int:
        """Secondes à afficher : arrondi supérieur pour ne jamais montrer 00:00 avant la fin."""
        return int(math.ceil(self.remaining - 1e-9))

    @property
    def progress(self) -> float:
        """Part restante, dans ``[0, 1]`` (1 = plein, 0 = écoulé)."""
        if self._duration <= 0:
            return 0.0
        return max(0.0, min(1.0, self.remaining / self._duration))

    # -- commandes -------------------------------------------------------- #
    def set_duration(self, duration: float) -> None:
        """Change la durée et remet le minuteur à zéro (arrêté)."""
        if duration <= 0:
            raise ValueError("duration must be positive")
        self._duration = float(duration)
        self._remaining = float(duration)
        self._deadline = 0.0
        self.running = False
        self.finished = False

    def start(self) -> None:
        if self.running:
            return
        if self.finished or self._remaining <= RESTART_THRESHOLD:
            self._remaining = self._duration
            self.finished = False
        self._deadline = self._clock() + self._remaining
        self.running = True

    def pause(self) -> None:
        if not self.running:
            return
        self._remaining = max(0.0, self._deadline - self._clock())
        self.running = False

    def reset(self) -> None:
        self._remaining = self._duration
        self._deadline = 0.0
        self.running = False
        self.finished = False

    def tick(self) -> bool:
        """Rafraîchit l'état ; renvoie ``True`` une seule fois, à l'instant de la fin."""
        if not self.running:
            return False
        if self.remaining > 0.0:
            return False
        self._remaining = 0.0
        self.running = False
        self.finished = True
        return True
