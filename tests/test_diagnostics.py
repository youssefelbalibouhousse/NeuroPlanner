"""Diagnostic du fournisseur (``--check-llm``) : rapport et codes de sortie."""

from __future__ import annotations

import pytest

from neuroplanner.services.diagnostics import check_provider
from neuroplanner.services.llm import LlmSettings
from neuroplanner.services.providers import settings_for


class StubClient:
    def __init__(self, models: list[str] | None = None, error: str = "") -> None:
        self._models = models or []
        self._error = error
        self.strict_seen = False

    def models(self, *, strict: bool = False) -> list[str]:
        self.strict_seen = strict
        if self._error:
            from neuroplanner.services.llm import LlmError

            raise LlmError(self._error)
        return self._models

    def complete(self, _prompt: str) -> str:  # pragma: no cover - non utilisé ici
        return ""


def test_ollama_report_is_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubClient(models=["qwen2.5:3b", "gemma4:latest"])
    monkeypatch.setattr("neuroplanner.services.diagnostics.create_client", lambda _s: stub)

    report = check_provider(settings_for("ollama"))

    assert report.ok is True
    assert report.models == ("qwen2.5:3b", "gemma4:latest")
    assert stub.strict_seen is True  # le diagnostic veut l'erreur, pas une liste vide
    text = "\n".join(report.lines())
    assert "OK" in text
    assert "inutile (local)" in text


def test_missing_key_is_reported_without_calling_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_settings):  # pragma: no cover - ne doit pas être appelé
        raise AssertionError("aucun appel réseau attendu sans clé")

    monkeypatch.setattr("neuroplanner.services.diagnostics.create_client", boom)
    report = check_provider(settings_for("groq", api_key=""))

    assert report.ok is False
    assert "console.groq.com/keys" in report.error
    assert report.key_state == "absente"


def test_api_error_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubClient(error="Clé refusée ou invalide pour Groq")
    monkeypatch.setattr("neuroplanner.services.diagnostics.create_client", lambda _s: stub)

    report = check_provider(settings_for("groq", api_key="gsk_test1234"))

    assert report.ok is False
    assert "Clé refusée" in report.error
    assert report.key_state == "présente (••••1234)"
    assert "ÉCHEC" in "\n".join(report.lines())


def test_key_state_masks_short_keys() -> None:
    report = check_provider(LlmSettings(provider="groq", api_key="court"))
    assert report.key_state == "présente"


def test_report_truncates_long_model_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = StubClient(models=[f"modele-{index}" for index in range(10)])
    monkeypatch.setattr("neuroplanner.services.diagnostics.create_client", lambda _s: stub)

    text = "\n".join(check_provider(settings_for("ollama")).lines())
    assert "(+4)" in text
