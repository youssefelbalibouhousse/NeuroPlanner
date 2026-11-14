"""Client LLM : prompt, extraction JSON et gestion d'erreurs, sans réseau."""

from __future__ import annotations

import urllib.error

import pytest

from neuroplanner.models import Chapter
from neuroplanner.services.llm import (
    LlmError,
    LlmSettings,
    OllamaClient,
    build_prompt,
    generate_outline,
    parse_outline,
)


def fake_transport(response: dict, calls: list | None = None):
    def transport(url: str, payload: dict, timeout: float) -> dict:
        if calls is not None:
            calls.append((url, payload, timeout))
        return response

    return transport


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
def test_prompt_contains_topic_count_and_json_contract() -> None:
    prompt = build_prompt("Analyse réelle", count=8)
    assert "Analyse réelle" in prompt
    assert "exactement 8 chapitres" in prompt
    assert '"titre"' in prompt and '"minutes"' in prompt


def test_prompt_rejects_no_topic_at_generation() -> None:
    with pytest.raises(LlmError, match="sujet"):
        generate_outline("  ", client=OllamaClient(transport=fake_transport({})))


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #
def test_parses_plain_json_array() -> None:
    chapters = parse_outline('[{"titre": "Limites", "minutes": 90}, {"titre": "Dérivées"}]')
    assert chapters == [Chapter("Limites", 90), Chapter("Dérivées", None)]


def test_parses_fenced_json_with_prose() -> None:
    text = 'Voici le programme :\n```json\n[{"titre": "Suites", "minutes": 60}]\n```\nBon courage !'
    assert parse_outline(text) == [Chapter("Suites", 60)]


def test_parses_dict_wrapper() -> None:
    assert parse_outline('{"chapitres": [{"titre": "Suites"}]}') == [Chapter("Suites")]


def test_parses_plain_string_entries() -> None:
    assert parse_outline('["Limites", "Dérivées"]') == [Chapter("Limites"), Chapter("Dérivées")]


def test_falls_back_to_bullets_when_json_is_broken() -> None:
    text = "Voici :\n- Limites (90 min)\n- Dérivées"
    assert [chapter.title for chapter in parse_outline(text)] == ["Limites", "Dérivées"]


def test_reasoning_with_brackets_does_not_break_parsing() -> None:
    """Un modèle « thinking » peut écrire [brouillon] avant le JSON final."""
    text = (
        "Je réfléchis [étape 1] au découpage...\n"
        '[{"titre": "Limites", "minutes": 90}, {"titre": "Dérivées", "minutes": 60}]'
    )
    chapters = parse_outline(text)
    assert [chapter.title for chapter in chapters] == ["Limites", "Dérivées"]


def test_invalid_minutes_are_dropped() -> None:
    assert parse_outline('[{"titre": "Limites", "minutes": 9999}]') == [Chapter("Limites", None)]
    assert parse_outline('[{"titre": "Limites", "minutes": "beaucoup"}]') == [
        Chapter("Limites", None)
    ]


def test_ignores_empty_titles() -> None:
    assert parse_outline('[{"titre": ""}, {"titre": "Ok"} ]') == [Chapter("Ok")]


def test_parse_outline_returns_empty_on_garbage() -> None:
    assert parse_outline("???") == []
    assert parse_outline("Désolé, je ne peux pas t'aider sur ce sujet.") == []


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
def test_complete_posts_to_generate_endpoint() -> None:
    calls: list = []
    client = OllamaClient(
        LlmSettings(model="test-model"),
        transport=fake_transport({"response": "ok"}, calls),
    )
    assert client.complete("salut") == "ok"

    url, payload, _timeout = calls[0]
    assert url.endswith("/api/generate")
    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    assert payload["prompt"] == "salut"


def test_think_flag_is_sent_only_when_explicit() -> None:
    calls: list = []
    transport = fake_transport({"response": "ok"}, calls)

    OllamaClient(LlmSettings(), transport=transport).complete("x")
    assert "think" not in calls[-1][1]

    OllamaClient(LlmSettings(think=True), transport=transport).complete("x")
    assert calls[-1][1]["think"] is True


def test_thinking_field_is_used_as_fallback() -> None:
    client = OllamaClient(transport=fake_transport({"thinking": '[{"titre": "A"}]'}))
    assert client.complete("x").startswith('[{"titre"')


def test_empty_response_raises() -> None:
    client = OllamaClient(transport=fake_transport({"response": "  "}))
    with pytest.raises(LlmError, match="vide"):
        client.complete("x")


def test_models_parses_tags() -> None:
    client = OllamaClient(
        transport=fake_transport({"models": [{"name": "a:1"}, {"name": "b:2"}, {"x": 1}]})
    )
    assert client.models() == ["a:1", "b:2"]


def test_models_returns_empty_when_server_is_down() -> None:
    def broken(url: str, payload: dict, timeout: float) -> dict:
        raise LlmError("serveur absent")

    assert OllamaClient(transport=broken).models() == []


def test_connection_error_message_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroplanner.services.llm import _post_json

    def boom(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError("refusé"))

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(LlmError, match="ollama serve"):
        _post_json("http://localhost:11434/api/generate", {"model": "m"}, 1.0)


def test_http_404_mentions_pull(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    from neuroplanner.services.llm import _post_json

    def boom(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost/api/generate", 404, "Not Found", {}, io.BytesIO(b"model not found")
        )

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(LlmError, match="ollama pull"):
        _post_json("http://localhost:11434/api/generate", {"model": "m"}, 1.0)


def test_invalid_json_from_server_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from neuroplanner.services.llm import _post_json

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return b"<html>oups</html>"

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response())
    with pytest.raises(LlmError, match="illisible"):
        _post_json("http://localhost:11434/api/generate", {"model": "m"}, 1.0)


# --------------------------------------------------------------------------- #
# Génération complète (client factice)
# --------------------------------------------------------------------------- #
class StubClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


def test_generate_outline_returns_chapters() -> None:
    client = StubClient('[{"titre": "Limites", "minutes": 90}, {"titre": "Dérivées", "minutes": 60}]')
    chapters = generate_outline("Analyse réelle", client=client, count=2)
    assert [chapter.title for chapter in chapters] == ["Limites", "Dérivées"]
    assert "exactement 2 chapitres" in client.prompts[0]


def test_generate_outline_raises_when_nothing_parsable() -> None:
    with pytest.raises(LlmError, match="aucun chapitre"):
        generate_outline("Analyse réelle", client=StubClient("désolé, je ne peux pas"))
