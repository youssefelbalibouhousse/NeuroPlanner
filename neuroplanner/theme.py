"""Palette sombre, couleurs par pilier et fabrique de polices."""

from __future__ import annotations

from dataclasses import dataclass

import customtkinter as ctk

from neuroplanner.services.stats import MASTERY_FROM, REFOCUS_BELOW


@dataclass(frozen=True, slots=True)
class Palette:
    bg: str
    sidebar: str
    card: str
    card_hover: str
    raised: str
    border: str
    track: str
    text: str
    muted: str
    dim: str
    accent: str
    accent_hover: str
    accent_soft: str
    red: str
    orange: str
    green: str


DARK = Palette(
    bg="#0E1015",
    sidebar="#12151C",
    card="#171B23",
    card_hover="#1D222B",
    raised="#20252F",
    border="#242A35",
    track="#1F242E",
    text="#E9ECF4",
    muted="#8B94A7",
    dim="#5A6273",
    accent="#7C5CFF",
    accent_hover="#8F74FF",
    accent_soft="#262045",
    red="#F0554E",
    orange="#F2A33C",
    green="#3FBF7F",
)

#: Thème actif. Remplacer cette valeur suffit à changer toute la palette.
PALETTE: Palette = DARK

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

#: Couleurs d'accent par défaut, pilier par pilier (seed du plan).
DEFAULT_DOMAIN_COLORS: dict[str, str] = {
    "Dev & Archi": "#7C9CFF",
    "IA & World Models": "#B58CFF",
    "Projets": "#3FD0BE",
    "Arabe MSA": "#F2C14E",
    "Révision Active": "#F27AA8",
}

#: Palette de couleurs proposée aux domaines créés par l'utilisateur.
DOMAIN_PALETTE: tuple[str, ...] = (
    "#7C9CFF",
    "#B58CFF",
    "#3FD0BE",
    "#F2C14E",
    "#F27AA8",
    "#6FD3F2",
    "#F2845C",
    "#9BE36B",
    "#D9A7FF",
    "#FF9DBB",
)

FALLBACK_DOMAIN_COLOR = "#8B94A7"

#: Libellés courts pour le graphique (la place est limitée).
DOMAIN_SHORT: dict[str, str] = {
    "Dev & Archi": "Dev / Archi",
    "IA & World Models": "IA / World",
    "Projets": "Projets",
    "Arabe MSA": "Arabe MSA",
    "Révision Active": "Révision",
}


def mix(color_a: str, color_b: str, ratio: float) -> str:
    """Mélange linéaire de deux couleurs hexadécimales (``ratio`` = part de B)."""
    left = tuple(int(color_a[index:index + 2], 16) for index in (1, 3, 5))
    right = tuple(int(color_b[index:index + 2], 16) for index in (1, 3, 5))
    return "#" + "".join(f"{round(a + (b - a) * ratio):02x}" for a, b in zip(left, right, strict=True))


def domain_color(domain: str) -> str:
    """Couleur par défaut d'un pilier connu (le plan fait foi à l'exécution)."""
    return DEFAULT_DOMAIN_COLORS.get(domain, FALLBACK_DOMAIN_COLOR)


def short_label(domain: str) -> str:
    """Libellé compact pour le graphique."""
    if domain in DOMAIN_SHORT:
        return DOMAIN_SHORT[domain]
    return domain if len(domain) <= 14 else f"{domain[:13]}…"


def color_for(percent: float) -> str:
    """Code couleur de refocalisation : rouge < 50, orange 50-79, vert >= 80."""
    if percent < REFOCUS_BELOW:
        return PALETTE.red
    if percent < MASTERY_FROM:
        return PALETTE.orange
    return PALETTE.green


_FONTS: dict[tuple[int, str, bool, bool], ctk.CTkFont] = {}


def font(
    size: int,
    weight: str = "normal",
    *,
    mono: bool = False,
    overstrike: bool = False,
) -> ctk.CTkFont:
    """Police mise en cache : CustomTkinter garde une référence par police."""
    key = (size, weight, mono, overstrike)
    if key not in _FONTS:
        _FONTS[key] = ctk.CTkFont(
            family=MONO_FAMILY if mono else FONT_FAMILY,
            size=size,
            weight=weight,
            overstrike=overstrike,
        )
    return _FONTS[key]


def apply_appearance() -> None:
    """Apparence globale : thème sombre, accents personnalisés."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
