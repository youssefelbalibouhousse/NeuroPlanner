"""Génère l'icône et le logo de NeuroPlanner (outil de maintenance, non requis pour exécuter l'app).

    python tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "neuroplanner" / "assets"
ACCENT = "#7C5CFF"
ACCENT_DARK = "#5B3FD9"
WHITE = "#FFFFFF"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
SUPERSAMPLE = 4

BOLD_FONTS = (
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in BOLD_FONTS:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def render(size: int) -> Image.Image:
    """Carré arrondi violet avec un « N » blanc centré."""
    canvas = size * SUPERSAMPLE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    radius = int(canvas * 0.24)
    draw.rounded_rectangle((0, 0, canvas - 1, canvas - 1), radius=radius, fill=ACCENT)

    # Liseré bas pour donner du relief, sans dégradé coûteux à rendre.
    draw.rounded_rectangle(
        (0, int(canvas * 0.82), canvas - 1, canvas - 1),
        radius=radius,
        fill=ACCENT_DARK,
    )
    draw.rounded_rectangle(
        (0, 0, canvas - 1, int(canvas * 0.88)),
        radius=radius,
        fill=ACCENT,
    )

    font = load_font(int(canvas * 0.62))
    left, top, right, bottom = draw.textbbox((0, 0), "N", font=font)
    draw.text(
        ((canvas - (right - left)) / 2 - left, (canvas - (bottom - top)) / 2 - top),
        "N",
        font=font,
        fill=WHITE,
    )
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    largest = render(256)
    largest.save(
        ASSETS / "neuroplanner.ico",
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
    )
    largest.save(ASSETS / "logo.png", format="PNG")
    print(f"icône : {ASSETS / 'neuroplanner.ico'}")
    print(f"logo  : {ASSETS / 'logo.png'}")


if __name__ == "__main__":
    main()
