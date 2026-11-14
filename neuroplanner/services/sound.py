"""Signal sonore de fin de minuteur (sans bloquer l'interface)."""

from __future__ import annotations

import threading
from collections.abc import Callable

try:  # Windows uniquement, dégradation silencieuse ailleurs.
    import winsound
except ImportError:  # pragma: no cover - dépend de la plateforme
    winsound = None  # type: ignore[assignment]

#: Accord ascendant, joué en fin de bloc.
_CHIME: tuple[tuple[int, int], ...] = ((784, 150), (988, 150), (1175, 150), (1568, 320))


def play_chime(fallback: Callable[[], None] | None = None) -> None:
    """Joue le signal de fin ; utilise ``fallback`` (ex. ``root.bell``) si besoin."""
    if winsound is not None:
        threading.Thread(target=_beep, daemon=True, name="neuroplanner-chime").start()
        return
    if fallback is not None:
        fallback()


def _beep() -> None:
    try:
        for frequency, duration in _CHIME:
            winsound.Beep(frequency, duration)
    except Exception:  # pragma: no cover - audio indisponible (pas de périphérique)
        pass
