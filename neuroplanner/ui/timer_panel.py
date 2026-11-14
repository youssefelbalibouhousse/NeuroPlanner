"""Panneau des minuteurs neuroplastiques.

L'interface ne fait que refléter l'état de :class:`Countdown` ; toute la
logique temporelle est testable sans Tk.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable, Sequence

import customtkinter as ctk

from neuroplanner.data.presets import DEFAULT_PRESET, TIMER_PRESETS
from neuroplanner.formatting import fmt_clock, fmt_duration, plural
from neuroplanner.models import TimerPreset
from neuroplanner.services.countdown import Countdown
from neuroplanner.services.sound import play_chime
from neuroplanner.theme import PALETTE, font

#: Fréquence de rafraîchissement du compte à rebours.
TICK_MS = 100
#: Durée d'affichage de l'état "terminé" avant retour à la couleur normale.
FINISHED_HIGHLIGHT_MS = 1600


class TimerPanel(ctk.CTkFrame):
    """Trois préréglages scientifiques, un compte à rebours, trois boutons."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_finished: Callable[[int], None],
        presets: Sequence[TimerPreset] = TIMER_PRESETS,
        default: TimerPreset = DEFAULT_PRESET,
    ) -> None:
        super().__init__(
            master,
            fg_color=PALETTE.card,
            corner_radius=16,
            border_width=1,
            border_color=PALETTE.border,
        )
        self._on_finished = on_finished
        self._presets = tuple(presets)
        self._preset = default
        self._countdown = Countdown(default.seconds)
        self._tick_job: str | None = None
        self._color_job: str | None = None
        self._last_display: int | None = None

        self.grid_columnconfigure(0, weight=1)
        self._build()
        self._render()

    # -- accès (tests et orchestration) ------------------------------------ #
    @property
    def preset(self) -> TimerPreset:
        return self._preset

    @property
    def presets(self) -> tuple[TimerPreset, ...]:
        return self._presets

    @property
    def countdown(self) -> Countdown:
        return self._countdown

    # -- construction ------------------------------------------------------ #
    def _build(self) -> None:
        ctk.CTkLabel(
            self, text="Minuteurs", anchor="w", font=font(14, "bold"), text_color=PALETTE.text
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 0))
        ctk.CTkLabel(
            self,
            text="Encodage · consolidation · récupération",
            anchor="w",
            font=font(10),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w", padx=18)

        self.segmented = ctk.CTkSegmentedButton(
            self,
            values=[preset.label for preset in self._presets],
            height=32,
            corner_radius=9,
            border_width=3,
            fg_color=PALETTE.card,
            selected_color=PALETTE.accent,
            selected_hover_color=PALETTE.accent_hover,
            unselected_color=PALETTE.track,
            unselected_hover_color=PALETTE.raised,
            text_color=PALETTE.text,
            font=font(11, "bold"),
            command=self._on_preset_selected,
        )
        self.segmented.grid(row=2, column=0, sticky="ew", padx=18, pady=(12, 0))
        self.segmented.set(self._preset.label)

        self.time_label = ctk.CTkLabel(
            self,
            text=fmt_clock(self._countdown.display_seconds),
            height=56,
            font=font(40, "bold", mono=True),
            text_color=PALETTE.text,
        )
        self.time_label.grid(row=3, column=0, pady=(8, 0))

        self.caption = ctk.CTkLabel(
            self,
            text=self._preset.caption,
            font=font(10),
            text_color=PALETTE.muted,
            wraplength=258,
            justify="center",
        )
        self.caption.grid(row=4, column=0, padx=18, pady=(2, 0))

        self.progress = ctk.CTkProgressBar(
            self, height=6, corner_radius=3, fg_color=PALETTE.track, progress_color=PALETTE.accent
        )
        self.progress.grid(row=5, column=0, sticky="ew", padx=18, pady=(12, 0))
        self.progress.set(1)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=6, column=0, sticky="ew", padx=18, pady=(12, 0))
        buttons.grid_columnconfigure(0, weight=2, uniform="timer")
        buttons.grid_columnconfigure(1, weight=1, uniform="timer")
        buttons.grid_columnconfigure(2, weight=1, uniform="timer")

        ctk.CTkButton(
            buttons,
            text="Démarrer",
            height=36,
            corner_radius=10,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent_hover,
            text_color="#FFFFFF",
            font=font(12, "bold"),
            command=self.start,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            buttons,
            text="Pause",
            height=36,
            corner_radius=10,
            fg_color=PALETTE.raised,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            font=font(12),
            command=self.pause,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            buttons,
            text="Reset",
            height=36,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE.border,
            hover_color=PALETTE.raised,
            text_color=PALETTE.muted,
            font=font(12),
            command=self.reset,
        ).grid(row=0, column=2, sticky="ew")

        self.stats_label = ctk.CTkLabel(
            self, text="", anchor="center", font=font(10), text_color=PALETTE.dim
        )
        self.stats_label.grid(row=7, column=0, pady=(10, 14))

    # -- commandes --------------------------------------------------------- #
    def start(self) -> None:
        if self._countdown.running:
            return
        self._cancel_color_job()
        self._countdown.start()
        self._apply_caption(self._preset.caption, PALETTE.muted)
        self.time_label.configure(text_color=PALETTE.text)
        self._render()
        self._schedule_tick()

    def pause(self) -> None:
        if not self._countdown.running:
            return
        self._countdown.pause()
        self._cancel_tick_job()
        self._render()

    def reset(self) -> None:
        self._countdown.reset()
        self._cancel_tick_job()
        self._cancel_color_job()
        self.time_label.configure(text_color=PALETTE.text)
        self._apply_caption(self._preset.caption, PALETTE.muted)
        self._render()

    def shutdown(self) -> None:
        """Arrête les callbacks ``after`` (obligatoire avant de détruire la fenêtre)."""
        self._cancel_tick_job()
        self._cancel_color_job()

    def set_stats(self, sessions: int, focus_seconds: int) -> None:
        noun = plural(sessions, "session")
        self.stats_label.configure(
            text=f"{sessions} {noun} · {fmt_duration(focus_seconds / 60)} de focus"
        )

    # -- boucle ------------------------------------------------------------ #
    def _schedule_tick(self) -> None:
        if self._tick_job is None:
            self._tick_job = self.after(TICK_MS, self._tick)

    def _tick(self) -> None:
        self._tick_job = None
        finished = self._countdown.tick()
        self._render()
        if finished:
            self._finish()
        elif self._countdown.running:
            self._schedule_tick()

    def _finish(self) -> None:
        play_chime(self.bell)
        self.time_label.configure(text=fmt_clock(0), text_color=PALETTE.accent)
        self._apply_caption(self._preset.finished_hint, PALETTE.accent)
        self._cancel_color_job()
        self._color_job = self.after(FINISHED_HIGHLIGHT_MS, self._restore_time_color)
        self._on_finished(int(self._countdown.duration))

    def _restore_time_color(self) -> None:
        self._color_job = None
        with contextlib.suppress(tk.TclError):
            self.time_label.configure(text_color=PALETTE.text)

    # -- préréglages ------------------------------------------------------- #
    def _on_preset_selected(self, label: str) -> None:
        preset = next((item for item in self._presets if item.label == label), None)
        if preset is None:
            return
        self.select_preset(preset)

    def select_preset(self, preset: TimerPreset) -> None:
        """Change de préréglage et remet le compte à rebours à zéro."""
        self._preset = preset
        self._countdown.set_duration(preset.seconds)
        self._cancel_tick_job()
        self._cancel_color_job()
        if self.segmented.get() != preset.label:
            self.segmented.set(preset.label)
        self.time_label.configure(text_color=PALETTE.text)
        self._apply_caption(preset.caption, PALETTE.muted)
        self._render()

    # -- rendu ------------------------------------------------------------- #
    def _apply_caption(self, text: str, color: str) -> None:
        self.caption.configure(text=text, text_color=color)

    def _render(self) -> None:
        seconds = self._countdown.display_seconds
        if seconds != self._last_display:
            self._last_display = seconds
            self.time_label.configure(text=fmt_clock(seconds))
        self.progress.set(self._countdown.progress)

    def _cancel_tick_job(self) -> None:
        if self._tick_job is not None:
            with contextlib.suppress(tk.TclError, ValueError):
                self.after_cancel(self._tick_job)
            self._tick_job = None

    def _cancel_color_job(self) -> None:
        if self._color_job is not None:
            with contextlib.suppress(tk.TclError, ValueError):
                self.after_cancel(self._color_job)
            self._color_job = None
