"""Préréglages des minuteurs neuroplastiques."""

from __future__ import annotations

from neuroplanner.models import TimerPreset

#: Trois temps distincts : encodage, consolidation, récupération active.
TIMER_PRESETS: tuple[TimerPreset, ...] = (
    TimerPreset(
        key="focus",
        label="Focus 45",
        seconds=45 * 60,
        caption="Focus 45 min · encodage : une seule tâche, notifications coupées.",
        finished_hint="Encodage terminé — feuille blanche 3 min, puis pause.",
    ),
    TimerPreset(
        key="pause",
        label="Pause 10",
        seconds=10 * 60,
        caption="Pause 10 min · consolidation : bouge, hydrate, aucun écran.",
        finished_hint="Pause terminée — reprends le bloc en cours.",
    ),
    TimerPreset(
        key="whiteboard",
        label="Feuille 3",
        seconds=3 * 60,
        caption="Feuille blanche 3 min · récupération active : restitue sans support.",
        finished_hint="Récupération terminée — note l'écart, la consolidation est faite.",
    ),
)

DEFAULT_PRESET: TimerPreset = TIMER_PRESETS[0]
