"""Réglages LLM persistés : lecture, écriture, confidentialité de la clé."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from neuroplanner.data.llm_config import LlmConfig, LlmConfigStore


@pytest.fixture
def store(tmp_path: Path) -> LlmConfigStore:
    return LlmConfigStore(tmp_path / "llm_settings.json")


def test_defaults_when_file_is_missing(store: LlmConfigStore) -> None:
    config = store.load()
    assert (config.provider, config.model, config.api_key) == ("ollama", "", "")


def test_round_trip(store: LlmConfigStore) -> None:
    store.save(LlmConfig(provider="groq", model="llama-3.3-70b-versatile", api_key="gsk_secret"))
    config = store.load()
    assert config.provider == "groq"
    assert config.model == "llama-3.3-70b-versatile"
    assert config.api_key == "gsk_secret"
    assert config.has_key is True


def test_file_is_valid_json(store: LlmConfigStore) -> None:
    store.save(LlmConfig(provider="gemini", model="gemini-2.5-flash", api_key="AIza_secret"))
    saved = json.loads(store.path.read_text(encoding="utf-8"))
    assert saved == {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "api_key": "AIza_secret",
    }


def test_key_is_hidden_from_repr(store: LlmConfigStore) -> None:
    config = LlmConfig(provider="groq", model="m", api_key="gsk_tres_secret")
    assert "gsk_tres_secret" not in repr(config)


def test_masked_key_shows_only_the_tail() -> None:
    assert LlmConfig(api_key="gsk_abcdefgh1234").masked_key == "••••••••1234"
    assert LlmConfig(api_key="court").masked_key == "••••••••"
    assert LlmConfig().masked_key == ""


def test_corrupted_file_is_tolerated(store: LlmConfigStore) -> None:
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text("{pas du json", encoding="utf-8")
    config = store.load()
    assert config.provider == "ollama"
    assert config.api_key == ""


def test_provider_is_normalised(store: LlmConfigStore) -> None:
    store.save(LlmConfig(provider="GROQ", model="m", api_key="k"))
    assert store.load().provider == "groq"


def test_clear_removes_the_file(store: LlmConfigStore) -> None:
    store.save(LlmConfig(api_key="k"))
    store.clear()
    assert not store.path.exists()


@pytest.mark.skipif(os.name == "nt", reason="chmod n'est pas significatif sous Windows")
def test_posix_permissions_are_restrictive(store: LlmConfigStore) -> None:
    store.save(LlmConfig(api_key="k"))
    assert store.path.stat().st_mode & 0o777 == 0o600
