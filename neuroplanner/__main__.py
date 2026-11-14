"""Point d'entrée en ligne de commande : ``python -m neuroplanner``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from neuroplanner.config import APP_NAME, APP_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neuroplanner",
        description=f"{APP_NAME} — suivi d'un rythme d'apprentissage intensif (5 h / jour).",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        metavar="CHEMIN",
        help="fichier de progression à utiliser (défaut : dossier de données utilisateur)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # L'apparence doit être fixée avant la création de la fenêtre.
    from neuroplanner.theme import apply_appearance

    apply_appearance()

    from neuroplanner.app import NeuroPlanner

    app = NeuroPlanner(args.data_file)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
