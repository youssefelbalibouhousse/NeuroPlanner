"""En-tête : titre, semaine en cours et avancement global."""

from __future__ import annotations

from datetime import date, timedelta

import customtkinter as ctk

from neuroplanner.formatting import fmt_date, fmt_percent
from neuroplanner.services.stats import Progress
from neuroplanner.theme import PALETTE, color_for, font


class Header(ctk.CTkFrame):
    """Bandeau supérieur de la zone de contenu."""

    def __init__(self, master: ctk.CTkBaseClass, today: date | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.today = today or date.today()

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            left,
            text="Rythme d'apprentissage",
            anchor="w",
            font=font(19, "bold"),
            text_color=PALETTE.text,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            left,
            text=(
                f"Semaine du {fmt_date(self.week_start)} au {fmt_date(self.week_end)} · "
                "répétition espacée & récupération active"
            ),
            anchor="w",
            font=font(10),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w")

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")
        self.percent_label = ctk.CTkLabel(
            right, text="0 %", width=64, anchor="e", font=font(20, "bold"), text_color=PALETTE.accent
        )
        self.percent_label.grid(row=0, column=0, rowspan=2, sticky="e", padx=(0, 12))

        stats = ctk.CTkFrame(right, fg_color="transparent")
        stats.grid(row=0, column=1, rowspan=2, sticky="e")
        self.bar = ctk.CTkProgressBar(
            stats, width=150, height=5, corner_radius=3,
            fg_color=PALETTE.track, progress_color=PALETTE.accent,
        )
        self.bar.grid(row=0, column=0, sticky="w")
        self.bar.set(0)
        self.stat_label = ctk.CTkLabel(
            stats, text="", anchor="w", font=font(10), text_color=PALETTE.muted
        )
        self.stat_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

    @property
    def week_start(self) -> date:
        return self.today - timedelta(days=self.today.weekday())

    @property
    def week_end(self) -> date:
        return self.week_start + timedelta(days=5)

    def set_week(self, progress: Progress) -> None:
        pct = progress.percent
        color = color_for(pct)
        self.percent_label.configure(text=fmt_percent(pct), text_color=color)
        self.bar.configure(progress_color=color)
        self.bar.set(pct / 100)
        self.stat_label.configure(text=f"{progress.done}/{progress.total} tâches cochées")
