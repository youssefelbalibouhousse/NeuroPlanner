"""Fournisseurs de modèles : Ollama local et APIs hébergées « OpenAI-compatibles ».

Groq, Gemini et Mistral exposent tous une API ``/chat/completions`` au format
OpenAI : un seul client (:class:`OpenAiCompatClient`) suffit, avec une URL de
base et une clé différentes. Ajouter un fournisseur = ajouter une entrée dans
:data:`PROVIDERS`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from neuroplanner.services.llm import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    LlmError,
    LlmSettings,
    Transport,
    request_json,
)

Kind = Literal["ollama", "openai"]


@dataclass(frozen=True, slots=True)
class Provider:
    """Description d'un fournisseur et de sa configuration par défaut."""

    key: str
    label: str
    kind: Kind
    base_url: str
    env_var: str = ""
    models: tuple[str, ...] = ()
    requires_key: bool = False
    docs_url: str = ""
    supports_think: bool = False

    @property
    def default_model(self) -> str:
        return self.models[0] if self.models else DEFAULT_MODEL


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        key="ollama",
        label="Ollama (local)",
        kind="ollama",
        base_url=DEFAULT_BASE_URL,
        models=(DEFAULT_MODEL, "llama3.1:latest", "gemma4:latest"),
        supports_think=True,
        docs_url="https://ollama.com/download",
    ),
    Provider(
        key="groq",
        label="Groq (gratuit)",
        kind="openai",
        base_url="https://api.groq.com/openai/v1",
        env_var="GROQ_API_KEY",
        models=(
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "qwen/qwen3-32b",
        ),
        requires_key=True,
        docs_url="https://console.groq.com/keys",
    ),
    Provider(
        key="gemini",
        label="Gemini (gratuit)",
        kind="openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        env_var="GEMINI_API_KEY",
        models=("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"),
        requires_key=True,
        docs_url="https://aistudio.google.com/apikey",
    ),
    Provider(
        key="mistral",
        label="Mistral (gratuit)",
        kind="openai",
        base_url="https://api.mistral.ai/v1",
        env_var="MISTRAL_API_KEY",
        models=("mistral-small-latest", "open-mistral-nemo", "mistral-large-latest"),
        requires_key=True,
        docs_url="https://console.mistral.ai/api-keys",
    ),
)

_BY_KEY = {provider.key: provider for provider in PROVIDERS}
#: Provider hébergé de secours quand l'utilisateur saisit une clé inconnue.
DEFAULT_PROVIDER_KEY = "ollama"


def get_provider(key: str | None) -> Provider:
    """Fournisseur par clé (insensible à la casse), avec repli sur Ollama."""
    return _BY_KEY.get((key or "").strip().lower(), _BY_KEY[DEFAULT_PROVIDER_KEY])


def provider_labels() -> list[str]:
    return [provider.label for provider in PROVIDERS]


def provider_from_label(label: str) -> Provider:
    return next(
        (provider for provider in PROVIDERS if provider.label == label),
        _BY_KEY[DEFAULT_PROVIDER_KEY],
    )


# --------------------------------------------------------------------------- #
# Réglages
# --------------------------------------------------------------------------- #
def settings_for(
    provider_key: str,
    *,
    model: str = "",
    api_key: str = "",
    think: bool | None = None,
) -> LlmSettings:
    """Construit des réglages cohérents pour un fournisseur donné."""
    provider = get_provider(provider_key)
    resolved_model = (model or "").strip() or provider.default_model
    resolved_key = (api_key or "").strip()
    if not resolved_key and provider.env_var:
        resolved_key = os.environ.get(provider.env_var, "").strip()
    if not resolved_key:
        resolved_key = os.environ.get("NEUROPLANNER_LLM_KEY", "").strip()

    base_url = provider.base_url
    if provider.kind == "ollama":
        base_url = os.environ.get("NEUROPLANNER_OLLAMA_URL", base_url).rstrip("/")

    return LlmSettings(
        provider=provider.key,
        base_url=base_url,
        model=resolved_model,
        api_key=resolved_key,
        think=think if provider.supports_think else None,
    )


def resolve_settings(config: object | None = None) -> LlmSettings:
    """Réglages effectifs : fichier local > variables d'environnement > défauts.

    ``config`` est n'importe quel objet exposant ``provider``, ``model`` et
    ``api_key`` (typiquement :class:`neuroplanner.data.llm_config.LlmConfig`).
    """
    provider_key = ""
    model = ""
    api_key = ""
    if config is not None:
        provider_key = str(getattr(config, "provider", "") or "")
        model = str(getattr(config, "model", "") or "")
        api_key = str(getattr(config, "api_key", "") or "")

    provider_key = (
        provider_key
        or os.environ.get("NEUROPLANNER_LLM_PROVIDER", "")
        or DEFAULT_PROVIDER_KEY
    )
    if not model:
        model = os.environ.get("NEUROPLANNER_LLM_MODEL", "")
    return settings_for(provider_key, model=model, api_key=api_key)


def create_client(
    settings: LlmSettings,
    *,
    transport: Transport | None = None,
) -> object:
    """Instancie le client adapté au fournisseur des réglages."""
    provider = get_provider(settings.provider)
    if provider.kind == "ollama":
        from neuroplanner.services.llm import OllamaClient

        return OllamaClient(settings, transport=transport)
    return OpenAiCompatClient(settings, transport=transport)


# --------------------------------------------------------------------------- #
# Client compatible OpenAI
# --------------------------------------------------------------------------- #
class OpenAiCompatClient:
    """Client ``/chat/completions`` (Groq, Gemini, Mistral, OpenRouter…)."""

    def __init__(
        self,
        settings: LlmSettings,
        *,
        transport: Transport | None = None,
        label: str | None = None,
    ) -> None:
        self.settings = settings
        self.label = label or get_provider(settings.provider).label
        self._transport = transport or self._default_transport

    # -- API --------------------------------------------------------------- #
    def models(self, *, strict: bool = False) -> list[str]:
        """Modèles disponibles pour cette clé.

        Avec ``strict``, une erreur de clé ou de réseau remonte au lieu de
        renvoyer une liste vide (utilisé par ``--check-llm``).
        """
        try:
            payload = self._transport(f"{self._base}/models", None, self._headers(), 20.0)
        except LlmError:
            if strict:
                raise
            return []
        entries = payload.get("data", [])
        names = [
            str(entry.get("id", "")).removeprefix("models/")
            for entry in entries
            if isinstance(entry, dict)
        ]
        return sorted({name for name in names if name})

    def complete(self, prompt: str) -> str:
        self._require_key()
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        response = self._transport(
            f"{self._base}/chat/completions", payload, self._headers(), self.settings.timeout
        )
        text = _message_text(response)
        if not text:
            raise LlmError(f"Réponse vide de {self.label} : essaie un autre modèle.")
        return text

    # -- interne ----------------------------------------------------------- #
    @property
    def _base(self) -> str:
        return self.settings.base_url.rstrip("/")

    def _headers(self) -> dict:
        key = self.settings.api_key.strip()
        return {"Authorization": f"Bearer {key}"} if key else {}

    def _require_key(self) -> None:
        provider = get_provider(self.settings.provider)
        if provider.requires_key and not self.settings.api_key.strip():
            raise LlmError(
                f"Clé API manquante pour {provider.label}.\n"
                f"Crée une clé gratuite sur {provider.docs_url or provider.base_url}, "
                f"puis colle-la dans le champ « clé » (ou définis {provider.env_var})."
            )

    def _default_transport(self, url: str, payload: dict | None, headers: dict, timeout: float) -> dict:
        return request_json(
            url,
            payload,
            headers,
            timeout,
            provider_label=self.label,
            api_key=self.settings.api_key,
        )


def _message_text(response: dict) -> str:
    """Extrait le texte d'une réponse ``chat/completions`` (contenu string ou parts)."""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):  # certains fournisseurs renvoient des « parts »
        parts = [
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("text")
        ]
        if "".join(parts).strip():
            return "".join(parts).strip()
    # Repli : certains modèles de raisonnement remplissent `reasoning_content`.
    fallback = message.get("reasoning_content")
    return fallback.strip() if isinstance(fallback, str) else ""


#: Signature d'une fabrique de client, injectable dans l'interface (tests).
ClientFactory = Callable[..., object]
