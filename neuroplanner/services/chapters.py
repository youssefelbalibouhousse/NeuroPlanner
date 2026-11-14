"""Lecture d'une table des matières collée par l'utilisateur.

Le parser est volontairement tolérant : il accepte les listes à puces, les
numérotations, les titres « Chapitre N », et une durée explicite facultative
(``(45 min)``, ``— 1 h 30``, ``[90]``).
"""

from __future__ import annotations

import re

from neuroplanner.models import Chapter

#: En dessous, une durée estimée n'est pas crédible.
MIN_CHAPTER_MINUTES = 15
MAX_CHAPTER_MINUTES = 600
MAX_TITLE_LENGTH = 120

#: Marqueurs de puce ou de numérotation en début de ligne.
_BULLET = re.compile(
    r"^\s*(?:[-*•·–—]|\d{1,3}[.)]|\d{1,3}\s*[-–—:]\s+|[IVXLC]{1,6}[.)])\s*"
)
_PREFIX = re.compile(
    r"^\s*(?:chapitre|chapter|le[çc]on|module|partie|section)\s+\d{1,3}\s*[:.\-–—]?\s*",
    re.IGNORECASE,
)
#: Durée en fin de ligne : « (45 min) », « — 1 h 30 », « [90] ».
_LINE_SUFFIX_DURATION = re.compile(
    r"(?:[(\[]|\s[-–—:]\s*)\s*"
    r"(?:(?P<hours>\d{1,2})\s*h(?:eures?)?\s*)?"
    r"(?P<minutes>\d{1,3})?\s*(?:min(?:utes?)?)?\s*[)\]]?\s*$",
    re.IGNORECASE,
)

#: Lignes d'en-tête à ignorer.
_HEADINGS = {
    "sommaire",
    "table des matières",
    "table des matieres",
    "programme",
    "plan",
    "chapitres",
    "contenu",
    "objectifs",
}


def parse_chapters(text: str) -> list[Chapter]:
    """Transforme un texte libre en liste de chapitres ordonnés et uniques.

    Lève :class:`ValueError` si aucun chapitre exploitable n'est trouvé.
    """
    chapters: list[Chapter] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _is_heading(line):
            continue

        title, minutes = _split_duration(line)
        title = _clean_title(title)
        if len(title) < 2:
            continue

        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        chapters.append(Chapter(title=title, minutes=minutes))

    if not chapters:
        raise ValueError(
            "Aucun chapitre détecté : colle une liste, un chapitre par ligne "
            "(par exemple « 1. Limites et continuité »)."
        )
    return chapters


def format_chapters(chapters: list[Chapter]) -> str:
    """Rend une liste de chapitres éditable (utilisé pour pré-remplir l'UI)."""
    lines = []
    for index, chapter in enumerate(chapters, start=1):
        suffix = f"  ({chapter.minutes} min)" if chapter.minutes else ""
        lines.append(f"{index}. {chapter.title}{suffix}")
    return "\n".join(lines)


def _is_heading(line: str) -> bool:
    normalized = line.strip(" :.-\t").casefold()
    return normalized in _HEADINGS


def _split_duration(line: str) -> tuple[str, int | None]:
    """Sépare le titre de sa durée éventuelle, en fin de ligne uniquement."""
    match = _LINE_SUFFIX_DURATION.search(line)
    if not match:
        return line, None

    fragment = match.group(0)
    lowered = fragment.casefold()
    # Sans unité, seules les formes entre crochets/parenthèses sont des durées :
    # « Algorithmes 2 » ou « Module 3 : 45 » ne doivent pas être tronqués.
    bracketed = fragment.lstrip().startswith(("(", "["))
    if not bracketed and "min" not in lowered and "h" not in lowered:
        return line, None

    total = int(match.group("hours") or 0) * 60 + int(match.group("minutes") or 0)
    if not MIN_CHAPTER_MINUTES <= total <= MAX_CHAPTER_MINUTES:
        return line, None

    return line[: match.start()].strip(), total


def _clean_title(text: str) -> str:
    title = _PREFIX.sub("", text.strip())
    title = _BULLET.sub("", title).strip(" .:-–—\t")
    title = " ".join(title.split())
    return title[:MAX_TITLE_LENGTH]
