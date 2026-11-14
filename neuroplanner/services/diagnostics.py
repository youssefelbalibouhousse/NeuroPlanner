"""Diagnostic du fournisseur LLM, utilisable sans interface (``--check-llm``).

L'appel ne consomme aucun jeton : il vérifie la joignabilité et la clé via
``GET /models`` (ou ``GET /api/tags`` pour Ollama).
"""

from __future__ import annotations

from dataclasses import dataclass

from neuroplanner.services.llm import LlmError, LlmSettings
from neuroplanner.services.providers import Provider, create_client, get_provider, preferred_model


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Résultat d'un test de fournisseur."""

    provider: str
    base_url: str
    model: str
    key_state: str
    models: tuple[str, ...] = ()
    error: str = ""
    warning: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def lines(self) -> list[str]:
        provider = get_provider(self.provider)
        status = "OK" if self.ok else "ÉCHEC"
        lines = [
            f"{provider.label} — {status}",
            f"  URL      : {self.base_url}",
            f"  Modèle   : {self.model}",
            f"  Clé      : {self.key_state}",
        ]
        if self.warning:
            lines.append(f"  Note     : {self.warning}")
        if self.ok:
            preview = ", ".join(self.models[:6]) or "(aucun modèle listé)"
            suffix = "" if len(self.models) <= 6 else f" … (+{len(self.models) - 6})"
            lines.append(f"  Modèles  : {preview}{suffix}")
        else:
            lines.append("  Erreur   : " + self.error.replace("\n", "\n             "))
            if provider.requires_key and not provider.default_model:
                lines.append(f"  Clé gratuite : {provider.docs_url}")
        return lines


def check_provider(settings: LlmSettings) -> DiagnosticReport:
    """Teste le fournisseur : joignabilité, clé, liste des modèles."""
    provider = get_provider(settings.provider)
    key_state = _key_state(settings, provider.requires_key)

    if provider.requires_key and not settings.api_key.strip():
        return DiagnosticReport(
            provider=provider.key,
            base_url=settings.base_url,
            model=settings.model,
            key_state="absente",
            error=(
                f"Clé manquante. Crée une clé gratuite sur {provider.docs_url} puis "
                f"définis {provider.env_var} (ou colle-la dans le dialogue d'import)."
            ),
        )

    client = create_client(settings)
    try:
        models = client.models(strict=True)  # type: ignore[attr-defined]
    except LlmError as error:
        return DiagnosticReport(
            provider=provider.key,
            base_url=settings.base_url,
            model=settings.model,
            key_state=key_state,
            error=str(error),
        )
    return DiagnosticReport(
        provider=provider.key,
        base_url=settings.base_url,
        model=settings.model,
        key_state=key_state,
        models=tuple(models),
        warning=_model_warning(provider, settings.model, models),
    )


def _model_warning(provider: Provider, model: str, models: list[str]) -> str:
    """Signale un modèle configuré que le fournisseur ne propose plus.

    Les catalogues changent souvent (Groq a retiré ``llama-3.3-70b-versatile``) :
    prévenir ici évite de chercher longtemps la cause d'un HTTP 404.
    """
    if not models or not model or _has_model(models, model):
        return ""
    fallback = preferred_model(provider, models)
    if provider.key == "ollama":
        return f"« {model} » n'est pas installé localement (ollama pull {model})."
    if fallback:
        return f"« {model} » n'existe plus chez {provider.label} ; repli auto sur « {fallback} »."
    return f"« {model} » n'est pas proposé par {provider.label} avec cette clé."


def _has_model(models: list[str], wanted: str) -> bool:
    """Compare aussi les noms sans étiquette de version (``gemma4`` ~ ``gemma4:latest``)."""
    bare = {name.split(":", 1)[0] for name in models}
    return wanted in models or wanted.split(":", 1)[0] in bare


def _key_state(settings: LlmSettings, requires_key: bool) -> str:
    if settings.api_key:
        tail = settings.api_key[-4:] if len(settings.api_key) > 8 else ""
        return f"présente (••••{tail})" if tail else "présente"
    return "inutile (local)" if not requires_key else "absente"
