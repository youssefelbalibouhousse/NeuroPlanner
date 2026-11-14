"""Vue défilante d'une journée : en-tête + blocs modifiables + barre d'avancement."""

from __future__ import annotations

from collections.abc import Collection, Mapping

import customtkinter as ctk

from neuroplanner.formatting import fmt_duration, fmt_percent
from neuroplanner.models import DayPlan, TaskNode
from neuroplanner.services.stats import Progress
from neuroplanner.theme import PALETTE, color_for, font
from neuroplanner.ui.block_card import AddTaskHandler, BlockCard
from neuroplanner.ui.task_row import EditHandler, ToggleHandler


class DayView(ctk.CTkScrollableFrame):
    """Contenu du jour sélectionné ; se reconstruit quand le plan change."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_toggle: ToggleHandler,
        on_edit_task: EditHandler | None = None,
        on_add_task: AddTaskHandler | None = None,
    ) -> None:
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=PALETTE.raised,
            scrollbar_button_hover_color=PALETTE.dim,
        )
        self._on_toggle = on_toggle
        self._on_edit_task = on_edit_task
        self._on_add_task = on_add_task
        self.day: DayPlan | None = None
        self.blocks: list[BlockCard] = []

        self._bar: ctk.CTkProgressBar | None = None
        self._percent_label: ctk.CTkLabel | None = None
        self._stat_label: ctk.CTkLabel | None = None

    # -- construction ------------------------------------------------------ #
    def show(
        self,
        day: DayPlan,
        completed: Collection[str],
        colors: Mapping[str, str],
    ) -> None:
        """Reconstruit la vue pour ``day``."""
        self.day = day
        for child in self.winfo_children():
            child.destroy()
        self.blocks.clear()
        self.grid_columnconfigure(0, weight=1)

        self._build_header(day)
        for index, block in enumerate(day.blocks, start=0):
            card = BlockCard(
                self,
                block,
                day_key=day.key,
                block_index=index,
                completed=completed,
                colors=colors,
                on_toggle=self._on_toggle,
                on_edit_task=self._on_edit_task,
                on_add_task=self._on_add_task,
            )
            card.grid(row=3 + index, column=0, sticky="ew", pady=(0, 12))
            self.blocks.append(card)

        ctk.CTkFrame(self, height=6, fg_color="transparent").grid(
            row=3 + len(self.blocks), column=0
        )
        self._scroll_to_top()

    def _build_header(self, day: DayPlan) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(4, 12))
        head.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(head, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            left, text=day.label, anchor="w", font=font(26, "bold"), text_color=PALETTE.text
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            left,
            text=(
                f"{len(day.blocks)} blocs · {fmt_duration(day.total_minutes)} · "
                f"{len({task.domain for task in day.tasks})} piliers"
            ),
            anchor="w",
            font=font(11),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self._percent_label = ctk.CTkLabel(
            head, text="0 %", anchor="e", font=font(24, "bold"), text_color=PALETTE.accent
        )
        self._percent_label.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        self._bar = ctk.CTkProgressBar(
            self, height=6, corner_radius=3, fg_color=PALETTE.track, progress_color=PALETTE.accent
        )
        self._bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self._bar.set(0)

        self._stat_label = ctk.CTkLabel(
            self, text="", anchor="w", font=font(10), text_color=PALETTE.muted
        )
        self._stat_label.grid(row=2, column=0, sticky="w", pady=(0, 12))

    def _scroll_to_top(self) -> None:
        canvas = getattr(self, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(0.0)

    # -- synchronisation --------------------------------------------------- #
    @property
    def percent_text(self) -> str:
        """Pourcentage affiché pour le jour courant (tests, diagnostic)."""
        return self._percent_label.cget("text") if self._percent_label else ""

    def sync(self, completed: Collection[str]) -> None:
        """Répercute un état persisté sur toutes les cases (reset, rechargement)."""
        for card in self.blocks:
            card.sync(completed)

    def update_task(self, task: TaskNode, color: str) -> None:
        """Met à jour une ligne après édition, sans reconstruire la journée."""
        for card in self.blocks:
            for row in card.rows:
                if row.task.tid == task.tid:
                    row.apply(task, color)
                    return

    def set_progress(self, progress: Progress) -> None:
        """Met à jour la barre et les libellés d'en-tête."""
        if self._bar is None or self._percent_label is None or self._stat_label is None:
            return
        pct = progress.percent
        color = color_for(pct)
        self._bar.set(pct / 100)
        self._bar.configure(progress_color=color)
        self._percent_label.configure(text=fmt_percent(pct), text_color=color)
        self._stat_label.configure(
            text=(
                f"{progress.done}/{progress.total} tâches · "
                f"{fmt_duration(progress.minutes_done)} sur {fmt_duration(progress.minutes_total)}"
            )
        )
