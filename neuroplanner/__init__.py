"""NeuroPlanner — suivi d'un rythme d'apprentissage intensif basé sur la neuroplasticité.

Exemple d'utilisation programmatique ::

    from neuroplanner import NeuroPlanner

    app = NeuroPlanner()
    app.mainloop()
"""

from __future__ import annotations

from neuroplanner.config import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION", "NeuroPlanner", "__version__"]
__version__ = APP_VERSION

_LAZY = {"NeuroPlanner": "neuroplanner.app"}


def __getattr__(name: str):
    """Import paresseux : ``import neuroplanner`` ne charge pas Tk."""
    if name in _LAZY:
        from importlib import import_module

        return getattr(import_module(_LAZY[name]), name)
    raise AttributeError(f"module {__name__!r} n'a pas d'attribut {name!r}")
