"""Carte d'un bloc horaire : en-tête (plage, intention) + tâches."""

from __future__ import annotations

from collections.abc import Collection

import customtkinter as ctk

from neuroplanner.formatting import fmt_duration
from neuroplanner.models import BlockNode
from neuroplanner.theme import PALETTE, font
from neuroplanner.ui.task_row import TaskRow, ToggleHandler


class BlockCard(ctk.CTkFrame):
    """Affiche un bloc de la journée et synchronise ses lignes avec l'état persisté."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        block: BlockNode,
        completed: Collection[str],
        on_toggle: ToggleHandler,
    ) -> None:
        super().__init__(
            master,
            fg_color=PALETTE.card,
            corner_radius=16,
            border_width=1,
            border_color=PALETTE.border,
        )
        self.block = block
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
        ctk.CTkLabel(
            head,
            text=f"{block.intent} · {fmt_duration(block.minutes)}",
            anchor="w",
            font=font(10),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w")

        self.counter = ctk.CTkLabel(
            self, text="", anchor="e", font=font(11, mono=True), text_color=PALETTE.dim
        )
        self.counter.grid(row=0, column=2, sticky="e", padx=(12, 18), pady=(18, 0))

        ctk.CTkFrame(self, height=1, fg_color=PALETTE.border, corner_radius=0).grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=18, pady=(14, 2)
        )

        self.rows: list[TaskRow] = []
        for index, task in enumerate(block.tasks):
            row = TaskRow(self, task, task.tid in completed, on_toggle)
            row.grid(row=2 + index, column=0, columnspan=3, sticky="ew", padx=10)
            self.rows.append(row)

        ctk.CTkFrame(self, height=8, fg_color="transparent").grid(
            row=2 + len(self.rows), column=0, columnspan=3
        )
        self.sync(completed)

    def sync(self, completed: Collection[str]) -> None:
        """Aligne les cases sur l'état persisté (après un reset, par exemple)."""
        for row in self.rows:
            row.set_done(row.task.tid in completed)
        self._refresh_counter(completed)

    def _refresh_counter(self, completed: Collection[str]) -> None:
        done = sum(1 for task in self.block.tasks if task.tid in completed)
        total = len(self.block.tasks)
        self.counter.configure(
            text=f"{done}/{total}",
            text_color=PALETTE.green if done == total else PALETTE.dim,
        )
