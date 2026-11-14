"""Navigation latérale : jours de la semaine, progression globale, reset."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from neuroplanner.config import APP_NAME, APP_TAGLINE, DAYS
from neuroplanner.formatting import fmt_duration, fmt_percent
from neuroplanner.services.stats import Progress
from neuroplanner.theme import PALETTE, color_for, font
from neuroplanner.ui.widgets import make_interactive


class DayNavItem(ctk.CTkFrame):
    """Entrée de navigation d'un jour : libellé, pourcentage et mini-barre."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        label: str,
        on_click: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent", corner_radius=11)
        self._selected = False
        self.grid_columnconfigure(1, weight=1)

        self.rail = ctk.CTkFrame(
            self, width=3, height=26, corner_radius=2, fg_color="transparent"
        )
        self.rail.grid(row=0, column=0, rowspan=2, padx=(8, 10), pady=(9, 7), sticky="ns")

        self.name = ctk.CTkLabel(
            self, text=label, anchor="w", font=font(13), text_color=PALETTE.muted
        )
        self.name.grid(row=0, column=1, sticky="w", pady=(8, 0))

        self.percent_label = ctk.CTkLabel(
            self, text="0 %", anchor="e", font=font(10, mono=True), text_color=PALETTE.dim
        )
        self.percent_label.grid(row=0, column=2, sticky="e", padx=(8, 12), pady=(8, 0))

        self.bar = ctk.CTkProgressBar(
            self, height=3, corner_radius=2, fg_color=PALETTE.track, progress_color=PALETTE.track
        )
        self.bar.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 12), pady=(4, 9))
        self.bar.set(0)

        make_interactive(
            self,
            on_click,
            lambda: self._hover(True),
            lambda: self._hover(False),
        )

    def set_state(self, *, selected: bool, progress: Progress) -> None:
        self._selected = selected
        color = color_for(progress.percent)
        self.configure(fg_color=PALETTE.accent_soft if selected else "transparent")
        self.name.configure(
            text_color=PALETTE.text if selected else PALETTE.muted,
            font=font(13, "bold") if selected else font(13),
        )
        self.percent_label.configure(
            text=fmt_percent(progress.percent),
            text_color=color if progress.done else PALETTE.dim,
        )
        self.rail.configure(fg_color=PALETTE.accent if selected else "transparent")
        self.bar.configure(progress_color=color)
        self.bar.set(progress.percent / 100)

    def _hover(self, active: bool) -> None:
        if self._selected:
            return
        self.configure(fg_color=PALETTE.card if active else "transparent")


class Sidebar(ctk.CTkFrame):
    """Barre latérale : marque, navigation des 6 jours, résumé, réinitialisation."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_select: Callable[[str], None],
        on_reset: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color=PALETTE.sidebar, corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.nav_items: dict[str, DayNavItem] = {}

        self._build_brand()
        self._build_nav(on_select)
        self._build_summary()
        self._build_reset(on_reset)

    # -- construction ------------------------------------------------------ #
    def _build_brand(self) -> None:
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(24, 18))
        brand.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            brand,
            text=APP_NAME[0],
            width=36,
            height=36,
            corner_radius=11,
            fg_color=PALETTE.accent,
            text_color="#FFFFFF",
            font=font(17, "bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(
            brand, text=APP_NAME, anchor="w", font=font(15, "bold"), text_color=PALETTE.text
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            brand, text=APP_TAGLINE, anchor="w", font=font(10), text_color=PALETTE.dim
        ).grid(row=1, column=1, sticky="w")

        ctk.CTkLabel(
            self, text="SEMAINE", anchor="w", font=font(9, "bold"), text_color=PALETTE.dim
        ).grid(row=1, column=0, sticky="w", padx=24)

    def _build_nav(self, on_select: Callable[[str], None]) -> None:
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 0))
        nav.grid_columnconfigure(0, weight=1)
        for index, (day_key, label) in enumerate(DAYS):
            item = DayNavItem(nav, label, lambda key=day_key: on_select(key))
            item.grid(row=index, column=0, sticky="ew", pady=(0, 2))
            self.nav_items[day_key] = item

    def _build_summary(self) -> None:
        summary = ctk.CTkFrame(
            self,
            fg_color=PALETTE.card,
            corner_radius=14,
            border_width=1,
            border_color=PALETTE.border,
        )
        summary.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 10))
        summary.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            summary, text="PROGRESSION", anchor="w", font=font(9, "bold"), text_color=PALETTE.dim
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        self.percent_label = ctk.CTkLabel(
            summary, text="0 %", anchor="w", font=font(22, "bold"), text_color=PALETTE.text
        )
        self.percent_label.grid(row=1, column=0, sticky="w", padx=14)
        self.bar = ctk.CTkProgressBar(
            summary, height=5, corner_radius=3, fg_color=PALETTE.track, progress_color=PALETTE.accent
        )
        self.bar.grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 0))
        self.bar.set(0)
        self.stat_label = ctk.CTkLabel(
            summary, text="", anchor="w", font=font(9), text_color=PALETTE.dim
        )
        self.stat_label.grid(row=3, column=0, sticky="w", padx=14, pady=(6, 12))

    def _build_reset(self, on_reset: Callable[[], None]) -> None:
        ctk.CTkButton(
            self,
            text="Réinitialiser la semaine",
            height=38,
            corner_radius=11,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE.border,
            hover_color=PALETTE.raised,
            text_color=PALETTE.muted,
            font=font(11),
            command=on_reset,
        ).grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 12))

        ctk.CTkLabel(
            self, text="Ctrl + 1…6 : changer de jour", font=font(9), text_color=PALETTE.dim
        ).grid(row=6, column=0, pady=(0, 16))

    # -- mise à jour ------------------------------------------------------- #
    def update_day(self, day_key: str, progress: Progress, *, selected: bool) -> None:
        self.nav_items[day_key].set_state(selected=selected, progress=progress)

    def set_week(self, progress: Progress, focus_seconds: int) -> None:
        pct = progress.percent
        color = color_for(pct)
        self.percent_label.configure(text=fmt_percent(pct), text_color=color)
        self.bar.configure(progress_color=color)
        self.bar.set(pct / 100)
        self.stat_label.configure(
            text=(
                f"{progress.done}/{progress.total} tâches · "
                f"{fmt_duration(focus_seconds / 60)} de focus"
            )
        )
