"""Point d'entrée en ligne de commande : ``python -m neuroplanner``."""

from __future__ import annotations

import argparse
import contextlib
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
        "--plan-file",
        type=Path,
        default=None,
        metavar="CHEMIN",
        help=(
            "fichier de plan (domaines, blocs, tâches) ; par défaut à côté de la "
            "progression : neuro_plan.json"
        ),
    )
    parser.add_argument(
        "--check-llm",
        action="store_true",
        help="teste le fournisseur LLM configuré (URL, clé, modèles) puis quitte",
    )
    parser.add_argument(
        "--provider",
        default=None,
        metavar="CLE",
        help="fournisseur à tester avec --check-llm (ollama, groq, gemini, mistral)",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="NOM",
        help="modèle à tester avec --check-llm",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check_llm:
        return check_llm(args)

    # L'apparence doit être fixée avant la création de la fenêtre.
    from neuroplanner.theme import apply_appearance

    apply_appearance()

    from neuroplanner.app import NeuroPlanner

    app = NeuroPlanner(args.data_file, plan_file=args.plan_file)
    app.mainloop()
    return 0


def check_llm(args: argparse.Namespace) -> int:
    """Diagnostic sans interface : aucun jeton consommé, aucune fenêtre ouverte."""
    from neuroplanner.config import resolve_data_file
    from neuroplanner.data.llm_config import LlmConfigStore
    from neuroplanner.services.diagnostics import check_provider
    from neuroplanner.services.providers import resolve_settings

    _tolerate_console_encoding()

    config_path = resolve_data_file(args.data_file).parent / "llm_settings.json"
    settings = resolve_settings(LlmConfigStore(config_path).load())
    if args.provider or args.model:
        from neuroplanner.services.providers import settings_for

        provider_key = (args.provider or settings.provider).strip().lower()
        # Changer de fournisseur sans préciser de modèle doit reprendre SON modèle
        # par défaut, pas celui du fournisseur précédent.
        model = (args.model or "").strip()
        if not model and provider_key == settings.provider:
            model = settings.model
        settings = settings_for(provider_key, model=model, api_key=settings.api_key)

    report = check_provider(settings)
    print("\n".join(report.lines()))
    if not report.ok and settings.provider == "ollama":
        print("  Astuce   : démarre le serveur avec `ollama serve`.")
    return 0 if report.ok else 1


def _tolerate_console_encoding() -> None:
    """Les consoles Windows anciennes ne savent pas tout afficher : ne pas planter."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(errors="replace")


if __name__ == "__main__":
    sys.exit(main())
