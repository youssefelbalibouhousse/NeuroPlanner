"""Helpers d'interaction pour CustomTkinter.

Les widgets CTk dessinent leur contenu dans des canvas internes : un ``bind``
sur le widget racine ne capte donc pas les clics ni les survols. Ces helpers
parcourent l'arbre des enfants pour rendre une zone entièrement cliquable.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable, Iterable

#: Délai avant d'éteindre un survol : évite le clignotement quand le pointeur
#: passe d'un enfant à un autre.
LEAVE_DELAY_MS = 25


def widget_tree(root: tk.Misc, skip: Iterable[tk.Misc] = ()) -> list[tk.Misc]:
    """Tous les descendants de ``root`` (``root`` inclus), sauf les branches ignorées."""
    skipped = {id(widget) for widget in skip}
    found: list[tk.Misc] = []
    stack: list[tk.Misc] = [root]
    while stack:
        widget = stack.pop()
        if id(widget) in skipped:
            continue
        found.append(widget)
        stack.extend(widget.winfo_children())
    return found


def bind_tree(
    root: tk.Misc,
    sequence: str,
    handler: Callable,
    skip: Iterable[tk.Misc] = (),
) -> None:
    """Attache ``handler`` à ``sequence`` sur ``root`` et tous ses descendants."""
    for widget in widget_tree(root, skip):
        with contextlib.suppress(tk.TclError):  # widget détruit ou non bindable
            widget.bind(sequence, handler)


def pointer_inside(widget: tk.Misc) -> bool:
    """Le pointeur est-il encore au-dessus de ``widget`` (ou d'un enfant) ?"""
    try:
        under = widget.winfo_containing(widget.winfo_pointerx(), widget.winfo_pointery())
    except tk.TclError:
        return False
    while under is not None:
        if under is widget:
            return True
        under = getattr(under, "master", None)
    return False


def deferred_leave(widget: tk.Misc, on_leave: Callable[[], None]) -> None:
    """N'éteint le survol que si le pointeur a réellement quitté la zone."""

    def check() -> None:
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        if not pointer_inside(widget):
            on_leave()

    with contextlib.suppress(tk.TclError):
        widget.after(LEAVE_DELAY_MS, check)


def bind_hover(
    widget: tk.Misc,
    on_enter: Callable[[], None],
    on_leave: Callable[[], None],
    skip: Iterable[tk.Misc] = (),
) -> None:
    """Survol cohérent sur un widget composite."""
    bind_tree(widget, "<Enter>", lambda _event: on_enter(), skip=skip)
    bind_tree(
        widget,
        "<Leave>",
        lambda _event: deferred_leave(widget, on_leave),
        skip=skip,
    )


def make_interactive(
    widget: tk.Misc,
    on_click: Callable[[], None],
    on_enter: Callable[[], None] | None = None,
    on_leave: Callable[[], None] | None = None,
    skip: Iterable[tk.Misc] = (),
) -> None:
    """Rend ``widget`` cliquable (et éventuellement survolable) sur toute sa surface."""
    bind_tree(widget, "<Button-1>", lambda _event: on_click(), skip=skip)
    if on_enter is not None:
        bind_tree(widget, "<Enter>", lambda _event: on_enter(), skip=skip)
    if on_leave is not None:
        bind_tree(
            widget,
            "<Leave>",
            lambda _event: deferred_leave(widget, on_leave),
            skip=skip,
        )
