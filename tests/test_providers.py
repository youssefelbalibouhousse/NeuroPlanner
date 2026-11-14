"""Fournisseurs hébergés : registre, réglages et client « OpenAI compatible »."""

from __future__ import annotations

import urllib.error

import pytest

from neuroplanner.services.llm import LlmError, LlmSettings
from neuroplanner.services.providers import (
    PROVIDERS,
    OpenAiCompatClient,
    create_client,
    get_provider,
    provider_from_label,
    provider_labels,
    resolve_settings,
    settings_for,
)


def fake_transport(response: dict, calls: list | None = None):
    def transport(url: str, payload: dict | None, headers: dict, timeout: float) -> dict:
        if calls is not None:
            calls.append({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
        return response

    return transport


def chat_response(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


# --------------------------------------------------------------------------- #
# Registre
# --------------------------------------------------------------------------- #
def test_registry_contains_local_and_free_tiers() -> None:
    keys = {provider.key for provider in PROVIDERS}
    assert {"ollama", "groq", "gemini", "mistral"} <= keys
    assert get_provider("ollama").kind == "ollama"
    for key in ("groq", "gemini", "mistral"):
        provider = get_provider(key)
        assert provider.kind == "openai"
        assert provider.requires_key and provider.base_url.startswith("https://")
        assert provider.env_var


def test_unknown_provider_falls_back_to_ollama() -> None:
    assert get_provider("inconnu").key == "ollama"
    assert get_provider(None).key == "ollama"
    assert provider_from_label("n'importe quoi").key == "ollama"


def test_labels_round_trip() -> None:
    for provider in PROVIDERS:
        assert provider_from_label(provider.label) == provider
    assert "Groq (gratuit)" in provider_labels()


# --------------------------------------------------------------------------- #
# Réglages
# --------------------------------------------------------------------------- #
def test_settings_for_hosted_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = settings_for("groq", api_key="gsk_test")
    assert settings.provider == "groq"
    assert settings.model == "llama-3.3-70b-versatile"
    assert settings.base_url == "https://api.groq.com/openai/v1"
    assert settings.api_key == "gsk_test"
    assert settings.think is None


def test_settings_read_the_provider_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_from_env")
    assert settings_for("groq").api_key == "gsk_from_env"


def test_settings_generic_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("NEUROPLANNER_LLM_KEY", "cle-generique")
    assert settings_for("gemini").api_key == "cle-generique"


def test_think_is_ignored_for_hosted_providers() -> None:
    assert settings_for("groq", api_key="x", think=True).think is None
    assert settings_for("ollama", think=True).think is True


def test_resolve_settings_prefers_the_config_file(monkeypatch: pytest.MonkeyPatch) -> None:
    class Config:
        provider = "groq"
        model = "llama-3.1-8b-instant"
        api_key = "gsk_config"

    settings = resolve_settings(Config())
    assert (settings.provider, settings.model, settings.api_key) == (
        "groq",
        "llama-3.1-8b-instant",
        "gsk_config",
    )


def test_resolve_settings_uses_env_when_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEUROPLANNER_LLM_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "mk-env")
    settings = resolve_settings()
    assert settings.provider == "mistral"
    assert settings.api_key == "mk-env"


def test_resolve_settings_defaults_to_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("NEUROPLANNER_LLM_PROVIDER", "NEUROPLANNER_LLM_MODEL", "NEUROPLANNER_LLM_KEY"):
        monkeypatch.delenv(variable, raising=False)
    settings = resolve_settings()
    assert settings.provider == "ollama"
    assert settings.base_url.startswith("http://localhost")


def test_create_client_returns_the_right_class() -> None:
    from neuroplanner.services.llm import OllamaClient

    assert isinstance(create_client(settings_for("ollama")), OllamaClient)
    assert isinstance(create_client(settings_for("groq", api_key="x")), OpenAiCompatClient)


# --------------------------------------------------------------------------- #
# Client compatible OpenAI
# --------------------------------------------------------------------------- #
def test_complete_posts_a_chat_completion() -> None:
    calls: list = []
    client = OpenAiCompatClient(
        settings_for("groq", api_key="gsk_secret"),
        transport=fake_transport(chat_response("[{\"titre\": \"A\"}]"), calls),
    )

    assert client.complete("salut").startswith("[{\"titre\"")

    call = calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert call["payload"]["model"] == "llama-3.3-70b-versatile"
    assert call["payload"]["messages"] == [{"role": "user", "content": "salut"}]
    assert call["headers"]["Authorization"] == "Bearer gsk_secret"


def test_gemini_base_url_is_used() -> None:
    calls: list = []
    client = OpenAiCompatClient(
        settings_for("gemini", api_key="AIza_test"),
        transport=fake_transport(chat_response("ok"), calls),
    )
    client.complete("x")
    assert calls[0]["url"].startswith("https://generativelanguage.googleapis.com/v1beta/openai")


def test_missing_key_is_reported_with_the_signup_url() -> None:
    settings = LlmSettings(provider="groq", base_url="https://api.groq.com/openai/v1", model="m")
    client = OpenAiCompatClient(settings, transport=fake_transport(chat_response("ok")))
    with pytest.raises(LlmError, match="console.groq.com/keys"):
        client.complete("x")


def test_models_are_normalised_and_sorted() -> None:
    payload = {"data": [{"id": "models/b"}, {"id": "a"}, {"id": ""}, "invalide"]}
    client = OpenAiCompatClient(
        settings_for("gemini", api_key="k"), transport=fake_transport(payload)
    )
    assert client.models() == ["a", "b"]


def test_models_returns_empty_on_failure() -> None:
    def broken(url: str, payload: dict | None, headers: dict, timeout: float) -> dict:
        raise LlmError("indisponible")

    client = OpenAiCompatClient(settings_for("groq", api_key="k"), transport=broken)
    assert client.models() == []


def test_content_parts_are_concatenated() -> None:
    payload = {"choices": [{"message": {"content": [{"text": "a"}, {"text": "b"}]}}]}
    client = OpenAiCompatClient(settings_for("groq", api_key="k"), transport=fake_transport(payload))
    assert client.complete("x") == "ab"


def test_reasoning_content_is_a_fallback() -> None:
    payload = {"choices": [{"message": {"content": "", "reasoning_content": "réponse"}}]}
    client = OpenAiCompatClient(settings_for("groq", api_key="k"), transport=fake_transport(payload))
    assert client.complete("x") == "réponse"


def test_empty_answer_is_reported() -> None:
    client = OpenAiCompatClient(
        settings_for("groq", api_key="k"), transport=fake_transport({"choices": []})
    )
    with pytest.raises(LlmError, match="vide"):
        client.complete("x")


# --------------------------------------------------------------------------- #
# Erreurs HTTP (via le transport réel, monkeypatché : pas de réseau)
# --------------------------------------------------------------------------- #
def _http_error_client(monkeypatch: pytest.MonkeyPatch, code: int, body: bytes) -> OpenAiCompatClient:
    import io
    import urllib.request

    def boom(*args, **kwargs):
        raise urllib.error.HTTPError("http://x", code, "erreur", {}, io.BytesIO(body))

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    return OpenAiCompatClient(settings_for("groq", api_key="gsk_test1234"))


def test_http_401_mentions_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _http_error_client(monkeypatch, 401, b"{}")
    with pytest.raises(LlmError, match="Clé refusée"):
        client.complete("x")


def test_http_429_suggests_waiting_or_switching_model(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _http_error_client(monkeypatch, 429, b"{}")
    with pytest.raises(LlmError, match="Quota atteint"):
        client.complete("x")


def test_http_503_is_reported_as_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _http_error_client(monkeypatch, 503, b"{}")
    with pytest.raises(LlmError, match="indisponible"):
        client.complete("x")


def test_error_detail_never_leaks_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une API qui renverrait la clé dans son message ne doit pas la propager."""
    import io

    from neuroplanner.services.llm import request_json

    body = b'{"error": "invalid key gsk_ABCDEFGHIJKLMNOP"}'
    error = urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, io.BytesIO(body))

    def boom(*args, **kwargs):
        raise error

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(LlmError) as caught:
        request_json(
            "http://x",
            {"a": 1},
            {"Authorization": "Bearer gsk_ABCDEFGHIJKLMNOP"},
            1.0,
            provider_label="Groq",
            api_key="gsk_ABCDEFGHIJKLMNOP",
        )
    assert "gsk_ABCDEFGHIJKLMNOP" not in str(caught.value)
    assert "clé masquée" in str(caught.value)
