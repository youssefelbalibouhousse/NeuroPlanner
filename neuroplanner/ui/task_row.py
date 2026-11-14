"""Ligne de tâche : case à cocher, intitulé, pilier, durée et action d'édition."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from neuroplanner.models import TaskNode
from neuroplanner.theme import PALETTE, font, mix
from neuroplanner.ui.widgets import deferred_leave, make_interactive, widget_tree

#: Signature des callbacks de tâche.
ToggleHandler = Callable[[TaskNode, bool], None]
EditHandler = Callable[[TaskNode], None]


class TaskRow(ctk.CTkFrame):
    """Une tâche cochable ; toute la ligne est cliquable, pas seulement la case."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        task: TaskNode,
        done: bool,
        color: str,
        on_toggle: ToggleHandler,
        on_edit: EditHandler | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent", corner_radius=10)
        self.task = task
        self.color = color
        self._on_toggle = on_toggle
        self._on_edit = on_edit
        self.grid_columnconfigure(1, weight=1)

        self.var = tk.BooleanVar(master=self, value=done)
        self.check = ctk.CTkCheckBox(
            self,
            text="",
            width=24,
            height=24,
            checkbox_width=22,
            checkbox_height=22,
            corner_radius=7,
            border_width=2,
            border_color=PALETTE.dim,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent,
            checkmark_color=PALETTE.bg,
            variable=self.var,
            command=self._commit,
        )
        self.check.grid(row=0, column=0, padx=(8, 12), pady=11)

        self.label = ctk.CTkLabel(
            self,
            text=task.label,
            anchor="w",
            justify="left",
            font=font(13),
            text_color=PALETTE.text,
        )
        self.label.grid(row=0, column=1, sticky="ew", pady=11)

        self.chip = ctk.CTkLabel(
            self,
            text=task.domain,
            height=22,
            corner_radius=8,
            fg_color=mix(PALETTE.card, color, 0.16),
            text_color=color,
            font=font(10, "bold"),
        )
        self.chip.grid(row=0, column=2, padx=(10, 10))

        self.minutes = ctk.CTkLabel(
            self,
            text=f"{task.minutes} min",
            width=48,
            anchor="e",
            font=font(11, mono=True),
            text_color=PALETTE.dim,
        )
        self.minutes.grid(row=0, column=3, padx=(0, 6))

        self.edit_button = ctk.CTkButton(
            self,
            text="✎",
            width=26,
            height=24,
            corner_radius=7,
            fg_color="transparent",
            hover_color=PALETTE.raised,
            text_color=PALETTE.dim,
            font=font(13),
            command=self._edit,
        )
        self.edit_button.grid(row=0, column=4, padx=(0, 8))
        if on_edit is None:
            self.edit_button.grid_remove()

        self._bind_interactions()
        self._render()

    # -- interactions ------------------------------------------------------ #
    def _bind_interactions(self) -> None:
        # La case et le bouton d'édition gèrent leur propre clic : on les exclut
        # pour éviter un basculement involontaire de la tâche.
        skip = (self.check, self.edit_button)
        make_interactive(
            self,
            self.toggle,
            lambda: self._set_hover(True),
            lambda: self._set_hover(False),
            skip=skip,
        )
        for root_widget in skip:
            for widget in widget_tree(root_widget):
                widget.bind("<Enter>", lambda _event: self._set_hover(True))
                widget.bind(
                    "<Leave>",
                    lambda _event: deferred_leave(self, lambda: self._set_hover(False)),
                )

    def _set_hover(self, active: bool) -> None:
        self.configure(fg_color=PALETTE.card_hover if active else "transparent")
        self.edit_button.configure(text_color=PALETTE.text if active else PALETTE.dim)

    def _edit(self) -> None:
        if self._on_edit is not None:
            self._on_edit(self.task)

    # -- état -------------------------------------------------------------- #
    def is_done(self) -> bool:
        return bool(self.var.get())

    def set_done(self, done: bool) -> None:
        self.var.set(done)
        self._render()

    def toggle(self) -> None:
        """Bascule l'état puis notifie le parent (persistance immédiate)."""
        self.var.set(not bool(self.var.get()))
        self._commit()

    def apply(self, task: TaskNode, color: str) -> None:
        """Reflète une tâche modifiée sans reconstruire la vue."""
        self.task = task
        self.color = color
        self.label.configure(text=task.label)
        self.chip.configure(
            text=task.domain,
            fg_color=mix(PALETTE.card, color, 0.16),
        )
        self.minutes.configure(text=f"{task.minutes} min")
        self._render()

    def _commit(self) -> None:
        done = bool(self.var.get())
        self._render()
        self._on_toggle(self.task, done)

    def _render(self) -> None:
        done = bool(self.var.get())
        self.label.configure(
            font=font(13, overstrike=done),
            text_color=PALETTE.dim if done else PALETTE.text,
        )
        self.check.configure(border_color=PALETTE.accent if done else PALETTE.dim)
        self.chip.configure(
            text_color=mix(self.color, PALETTE.card, 0.45) if done else self.color
        )
