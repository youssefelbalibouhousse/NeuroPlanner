"""Fenêtre principale : orchestre le plan modifiable, la progression et les vues."""

from __future__ import annotations

import contextlib
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from neuroplanner.config import (
    APP_NAME,
    DAY_KEYS,
    asset_path,
    initial_day,
    resolve_data_file,
    resolve_llm_config_file,
    resolve_plan_file,
)
from neuroplanner.data.plan_store import PlanStore
from neuroplanner.data.store import ProgressStore
from neuroplanner.models import TaskNode
from neuroplanner.services.stats import day_progress, domain_progress, week_progress
from neuroplanner.theme import PALETTE
from neuroplanner.ui.chart import DomainChart
from neuroplanner.ui.day_view import DayView
from neuroplanner.ui.dialogs import DomainDialog, TaskDialog
from neuroplanner.ui.header import Header
from neuroplanner.ui.import_dialog import ImportDialog
from neuroplanner.ui.sidebar import Sidebar
from neuroplanner.ui.timer_panel import TimerPanel


class NeuroPlanner(ctk.CTk):
    """Application : navigation par jour, planning modifiable, minuteurs, graphique."""

    #: Largeur minimale des colonnes latérales (unités logiques).
    SIDEBAR_WIDTH = 220
    RIGHT_PANEL_WIDTH = 350

    def __init__(
        self,
        data_file: Path | str | None = None,
        *,
        plan_file: Path | str | None = None,
        today: date | None = None,
    ) -> None:
        super().__init__(fg_color=PALETTE.bg)
        self.title(APP_NAME)
        self._set_icon()

        self.today = today or date.today()
        progress_path = resolve_data_file(data_file)
        self.plan = PlanStore(resolve_plan_file(plan_file, progress_path))
        self.store = ProgressStore(progress_path, valid_ids=self.plan.task_ids())
        self.current_day = initial_day(self.today.weekday())
        self._dpi_factor = 1.0

        self._configure_window()
        self._build_layout()
        self._bind_shortcuts()

        self.show_day(self.current_day, force=True)
        self.refresh_aggregates()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- mise en place ----------------------------------------------------- #
    def _set_icon(self) -> None:
        icon = asset_path("neuroplanner.ico")
        if not icon.exists():
            return
        with contextlib.suppress(tk.TclError):  # plateforme sans support .ico
            self.iconbitmap(str(icon))

    def _configure_window(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=self.SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=self.RIGHT_PANEL_WIDTH)
        self.grid_rowconfigure(1, weight=1)

        self._apply_window_geometry()
        # CustomTkinter peut réappliquer le facteur DPI juste après le démarrage.
        self._refit_jobs = [
            self.after(delay, self._refit_if_dpi_changed) for delay in (600, 1500, 3000)
        ]

    def _apply_window_geometry(self) -> None:
        """Centre une fenêtre qui tient toujours dans l'écran, quel que soit le DPI."""
        factor = max(1.0, float(self._get_window_scaling() or 1.0))
        self._dpi_factor = factor
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()

        logical_w = min(1240.0, max(720.0, (screen_w - 60) / factor))
        logical_h = min(860.0, max(520.0, (screen_h - 80) / factor))

        physical_w = min(screen_w - 20, int(logical_w * factor))
        physical_h = min(screen_h - 40, int(logical_h * factor))
        self._current_width = max(1, int(physical_w / factor))
        self._current_height = max(1, int(physical_h / factor))
        self.minsize(self._current_width, self._current_height)

        x = max(0, (screen_w - physical_w) // 2)
        y = max(0, (screen_h - physical_h) // 2 - 10)
        # geometry() de CustomTkinter applique le facteur DPI de façon différée :
        # on fixe la taille physique directement pour qu'elle tienne à l'écran,
        # tout en gardant des dimensions logiques cohérentes pour CTk.
        tk.Tk.geometry(self, f"{physical_w}x{physical_h}+{x}+{y}")

    def _refit_if_dpi_changed(self) -> None:
        try:
            if not self.winfo_exists():
                return
            factor = max(1.0, float(self._get_window_scaling() or 1.0))
        except tk.TclError:
            return
        if abs(factor - self._dpi_factor) > 0.01:
            self._apply_window_geometry()

    def _build_layout(self) -> None:
        self.sidebar = Sidebar(
            self,
            on_select=self.show_day,
            on_reset=self.reset_week,
            on_manage_domains=self.manage_domains,
            on_import=self.import_program,
        )
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

        self.header = Header(self, today=self.today)
        self.header.grid(row=0, column=1, columnspan=2, sticky="ew", padx=24, pady=(20, 10))

        self.day_view = DayView(
            self,
            on_toggle=self._on_task_toggle,
            on_edit_task=self.edit_task,
            on_add_task=self.add_task,
        )
        self.day_view.grid(row=1, column=1, sticky="nsew", padx=(24, 18), pady=(0, 20))

        right = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=PALETTE.border,
            scrollbar_button_hover_color=PALETTE.raised,
        )
        right.grid(row=1, column=2, sticky="nsew", padx=(0, 24), pady=(0, 20))
        right.grid_columnconfigure(0, weight=1)

        self.timer = TimerPanel(right, on_finished=self.record_session)
        self.timer.grid(row=0, column=0, sticky="ew")

        self.chart = DomainChart(right)
        self.chart.grid(row=1, column=0, sticky="ew", pady=(14, 0))

    def _bind_shortcuts(self) -> None:
        for index, day_key in enumerate(DAY_KEYS, start=1):
            self.bind(f"<Control-Key-{index}>", lambda _event, key=day_key: self.show_day(key))

    # -- navigation -------------------------------------------------------- #
    def show_day(self, day_key: str, *, force: bool = False) -> None:
        """Affiche ``day_key`` (idempotent sauf ``force``)."""
        if day_key not in DAY_KEYS:
            return
        if not force and day_key == self.current_day:
            return
        self.current_day = day_key
        self.day_view.show(
            self.plan.day(day_key),
            self.store.completed,
            self.plan.colors(),
        )
        self.day_view.set_progress(day_progress(self.plan.day(day_key), self.store.completed))
        self._refresh_nav()

    # -- édition du plan --------------------------------------------------- #
    def manage_domains(self) -> None:
        """Ouvre la gestion des domaines ; reconstruit les vues si besoin."""
        dialog = DomainDialog(self, self.plan)
        if dialog.run():
            self.on_plan_changed()

    def add_task(self, day_key: str, block_index: int) -> None:
        """Ouvre la création d'une tâche dans un bloc donné."""
        dialog = TaskDialog(self, self.plan, day_key, block_index)
        if dialog.run():
            self.on_plan_changed()

    def import_program(self) -> None:
        """Ouvre l'assistant d'import (table des matières ou LLM)."""
        dialog = ImportDialog(
            self,
            self.plan,
            config_path=resolve_llm_config_file(self.store.path),
        )
        if dialog.run():
            self.on_plan_changed()

    def edit_task(self, task: TaskNode) -> None:
        """Ouvre l'édition d'une tâche existante (jour et bloc retrouvés par son id)."""
        location = self._locate(task.tid)
        if location is None:
            return
        day_key, block_index = location
        dialog = TaskDialog(self, self.plan, day_key, block_index, task)
        if dialog.run():
            self.on_plan_changed()

    def _locate(self, tid: str) -> tuple[str, int] | None:
        for day in self.plan.week_days():
            for block_index, block in enumerate(day.blocks):
                if any(task.tid == tid for task in block.tasks):
                    return day.key, block_index
        return None

    def on_plan_changed(self) -> None:
        """Après une modification du plan : recharge les vues et purge les orphelins."""
        self.store.prune(self.plan.task_ids())
        self.show_day(self.current_day, force=True)
        self.refresh_aggregates()

    # -- état -------------------------------------------------------------- #
    def _on_task_toggle(self, task: TaskNode, done: bool) -> None:
        self.store.set_done(task.tid, done)
        self.day_view.sync(self.store.completed)
        self.refresh_aggregates()

    def record_session(self, seconds: int) -> None:
        """Comptabilise un minuteur terminé puis rafraîchit les statistiques."""
        self.store.add_session(seconds)
        self.refresh_aggregates()

    def refresh_aggregates(self) -> None:
        """Recalcule toutes les vues dérivées de la progression."""
        completed = self.store.completed
        days = self.plan.week_days()

        self.chart.refresh(
            domain_progress(days, completed, order=self.plan.domain_names)
        )
        week = week_progress(days, completed)
        self.header.set_week(week)
        self.sidebar.set_week(week, self.store.focus_seconds)
        self.timer.set_stats(self.store.sessions, self.store.focus_seconds)
        self._refresh_nav()
        self.day_view.set_progress(day_progress(self.plan.day(self.current_day), completed))

    def _refresh_nav(self) -> None:
        for day in self.plan.week_days():
            self.sidebar.update_day(
                day.key,
                day_progress(day, self.store.completed),
                selected=day.key == self.current_day,
            )
        self.sidebar.domains_button.configure(
            text=f"Domaines… ({len(self.plan.domains)})"
        )

    def reset_week(self) -> None:
        """Réinitialise la semaine après confirmation (les stats de focus restent)."""
        if not messagebox.askyesno(
            "Réinitialiser la semaine",
            "Toutes les tâches cochées et la progression seront remises à zéro.\n"
            "Les statistiques de focus sont conservées.\n\nContinuer ?",
            parent=self,
        ):
            return
        self.store.reset_week()
        self.day_view.sync(self.store.completed)
        self.refresh_aggregates()

    # -- fermeture --------------------------------------------------------- #
    def _on_close(self) -> None:
        self.timer.shutdown()
        for job in getattr(self, "_refit_jobs", ()):
            with contextlib.suppress(tk.TclError, ValueError):
                self.after_cancel(job)
        self.store.save()
        self.destroy()
