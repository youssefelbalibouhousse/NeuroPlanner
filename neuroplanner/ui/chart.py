"""Graphique de refocalisation : complétion par pilier, code couleur intégré."""

from __future__ import annotations

from collections.abc import Sequence

import customtkinter as ctk
import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from neuroplanner.services.stats import DomainProgress  # noqa: E402
from neuroplanner.theme import (  # noqa: E402
    DOMAIN_SHORT,
    PALETTE,
    color_for,
    font,
)

#: Largeur d'axe réservée à droite pour les étiquettes de pourcentage.
VALUE_HEADROOM = 18.0


class DomainChart(ctk.CTkFrame):
    """Barres horizontales : un pilier par ligne, couleur = niveau de maîtrise."""

    def __init__(self, master: ctk.CTkBaseClass) -> None:
        super().__init__(
            master,
            fg_color=PALETTE.card,
            corner_radius=16,
            border_width=1,
            border_color=PALETTE.border,
        )
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Refocalisation", anchor="w", font=font(14, "bold"), text_color=PALETTE.text
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 0))
        ctk.CTkLabel(
            self,
            text="Taux de complétion par pilier · semaine entière",
            anchor="w",
            font=font(10),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w", padx=18)

        self.figure = Figure(figsize=(3.0, 2.1), dpi=100, facecolor=PALETTE.card)
        self.figure.subplots_adjust(left=0.32, right=0.94, top=0.96, bottom=0.15)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        widget = self.canvas.get_tk_widget()
        widget.configure(bg=PALETTE.card, highlightthickness=0, bd=0)
        widget.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 2))

        self._build_legend()

    def _build_legend(self) -> None:
        legend = ctk.CTkFrame(self, fg_color="transparent")
        legend.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 14))
        entries = (
            (PALETTE.red, "< 50 % à refocaliser"),
            (PALETTE.orange, "50–79 % en cours"),
            (PALETTE.green, "≥ 80 % maîtrisé"),
        )
        for index, (color, label) in enumerate(entries):
            ctk.CTkLabel(legend, text="●", text_color=color, font=font(9)).grid(
                row=0, column=2 * index, padx=(0, 4)
            )
            ctk.CTkLabel(legend, text=label, text_color=PALETTE.muted, font=font(9)).grid(
                row=0, column=2 * index + 1, padx=(0, 10)
            )

    def refresh(self, data: Sequence[DomainProgress]) -> None:
        """Redessine les barres à partir des progressions par pilier."""
        axes = self.axes
        axes.clear()
        axes.set_facecolor(PALETTE.card)

        labels = [DOMAIN_SHORT.get(item.domain, item.domain) for item in data]
        values = [item.percent for item in data]
        positions = list(range(len(data)))[::-1]
        colors = [color_for(value) for value in values]

        axes.barh(positions, values, height=0.56, color=colors, edgecolor="none", zorder=3)
        axes.set_yticks(positions)
        axes.set_yticklabels(labels, fontsize=8.5, color=PALETTE.text)
        axes.set_xlim(0, 100 + VALUE_HEADROOM)
        axes.set_ylim(-0.62, max(0.38, len(data) - 0.38))
        axes.set_xticks([0, 50, 80, 100])
        axes.set_xticklabels(["0", "50", "80", "100"], fontsize=7.5, color=PALETTE.dim)
        axes.grid(axis="x", color=PALETTE.border, linestyle=(0, (2, 3)), linewidth=0.8, zorder=0)
        axes.set_axisbelow(True)
        axes.tick_params(length=0, pad=4)
        for spine in axes.spines.values():
            spine.set_visible(False)

        for position, value in zip(positions, values, strict=True):
            axes.text(
                min(value + 2.5, 100 + VALUE_HEADROOM - 10),
                position,
                f"{value:.0f} %",
                va="center",
                ha="left",
                fontsize=8,
                color=color_for(value),
                fontweight="bold",
            )

        self.canvas.draw_idle()

    # -- introspection (tests, diagnostic) --------------------------------- #
    def bar_count(self) -> int:
        return len(self.axes.patches)

    def colour_of(self, index: int) -> str:
        """Couleur hexadécimale (majuscules) de la barre ``index``."""
        red, green, blue, *_ = self.axes.patches[index].get_facecolor()
        return f"#{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"

    def value_of(self, index: int) -> float:
        return float(self.axes.patches[index].get_width())
