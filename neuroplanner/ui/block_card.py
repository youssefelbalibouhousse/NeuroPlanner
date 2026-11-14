"""Carte d'un bloc horaire : en-tête (plage, intention) + tâches."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping

import customtkinter as ctk

from neuroplanner.formatting import fmt_duration
from neuroplanner.models import BlockNode, TaskNode
from neuroplanner.theme import FALLBACK_DOMAIN_COLOR, PALETTE, font
from neuroplanner.ui.task_row import EditHandler, TaskRow, ToggleHandler

#: Callback d'ajout : (jour, index du bloc).
AddTaskHandler = Callable[[str, int], None]


class BlockCard(ctk.CTkFrame):
    """Affiche un bloc de la journée et synchronise ses lignes avec l'état persisté."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        block: BlockNode,
        day_key: str,
        block_index: int,
        completed: Collection[str],
        colors: Mapping[str, str],
        on_toggle: ToggleHandler,
        on_edit_task: EditHandler | None = None,
        on_add_task: AddTaskHandler | None = None,
    ) -> None:
        super().__init__(
            master,
            fg_color=PALETTE.card,
            corner_radius=16,
            border_width=1,
            border_color=PALETTE.border,
        )
        self.block = block
        self.day_key = day_key
        self.block_index = block_index
        self._colors = colors
        self._on_add_task = on_add_task
        self.grid_columnconfigure(1, weight=1)

        time_chip = ctk.CTkLabel(
            self,
            text=f"{block.start} – {block.end}",
            height=24,
            width=104,
            fg_color=PALETTE.track,
            corner_radius=8,
            text_color=PALETTE.muted,
            font=font(11, mono=True),
        )
        time_chip.grid(row=0, column=0, sticky="w", padx=(18, 14), pady=(16, 0))

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=1, sticky="w", pady=(14, 0))
        ctk.CTkLabel(
            head,
            text=block.title,
            anchor="w",
            font=font(15, "bold"),
            text_color=PALETTE.text,
        ).grid(row=0, column=0, sticky="w")
        self.subtitle = ctk.CTkLabel(
            head,
            text="",
            anchor="w",
            font=font(10),
            text_color=PALETTE.dim,
        )
        self.subtitle.grid(row=1, column=0, sticky="w")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=2, sticky="e", padx=(12, 14), pady=(14, 0))

        self.counter = ctk.CTkLabel(
            actions, text="", anchor="e", font=font(11, mono=True), text_color=PALETTE.dim
        )
        self.counter.grid(row=0, column=0, padx=(0, 8))

        self.add_button = ctk.CTkButton(
            actions,
            text="+",
            width=26,
            height=24,
            corner_radius=7,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE.border,
            hover_color=PALETTE.raised,
            text_color=PALETTE.muted,
            font=font(14, "bold"),
            command=self._add_task,
        )
        self.add_button.grid(row=0, column=1)
        if on_add_task is None:
            self.add_button.grid_remove()

        ctk.CTkFrame(self, height=1, fg_color=PALETTE.border, corner_radius=0).grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=18, pady=(14, 2)
        )

        self.rows: list[TaskRow] = []
        for index, task in enumerate(block.tasks):
            row = self._make_row(task, task.tid in completed, on_toggle, on_edit_task)
            row.grid(row=2 + index, column=0, columnspan=3, sticky="ew", padx=10)
            self.rows.append(row)

        self.empty_label: ctk.CTkLabel | None = None
        if not block.tasks:
            self.empty_label = ctk.CTkLabel(
                self,
                text="Aucune tâche dans ce bloc — ajoute-en une avec « + ».",
                anchor="w",
                font=font(11),
                text_color=PALETTE.dim,
            )
            self.empty_label.grid(
                row=2, column=0, columnspan=3, sticky="ew", padx=28, pady=(10, 14)
            )

        ctk.CTkFrame(self, height=8, fg_color="transparent").grid(
            row=2 + max(len(self.rows), 1), column=0, columnspan=3
        )
        self.sync(completed)

    # -- construction ------------------------------------------------------ #
    def _make_row(
        self,
        task: TaskNode,
        done: bool,
        on_toggle: ToggleHandler,
        on_edit: EditHandler | None,
    ) -> TaskRow:
        color = self._colors.get(task.domain, FALLBACK_DOMAIN_COLOR)
        return TaskRow(self, task, done, color, on_toggle, on_edit)

    def _add_task(self) -> None:
        if self._on_add_task is not None:
            self._on_add_task(self.day_key, self.block_index)

    # -- synchronisation --------------------------------------------------- #
    def sync(self, completed: Collection[str]) -> None:
        """Aligne les cases sur l'état persisté (après un reset, par exemple)."""
        for row in self.rows:
            row.set_done(row.task.tid in completed)
        self._refresh_counter(completed)

    def _refresh_counter(self, completed: Collection[str]) -> None:
        done = sum(1 for task in self.block.tasks if task.tid in completed)
        total = len(self.block.tasks)
        self.counter.configure(
            text=f"{done}/{total}" if total else "vide",
            text_color=PALETTE.green if total and done == total else PALETTE.dim,
        )
        minutes = sum(task.minutes for task in self.block.tasks)
        self.subtitle.configure(
            text=f"{self.block.intent} · {fmt_duration(minutes)}"
            if self.block.intent
            else fmt_duration(minutes)
        )
