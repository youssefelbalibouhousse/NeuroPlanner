"""Bout en bout HTTP : client « OpenAI compatible » contre un faux serveur local.

Aucune connexion sortante : le serveur écoute sur 127.0.0.1 et rejoue des réponses
au format ``chat/completions``. Cela valide urllib, les en-têtes, le corps de la
requête et le parsing de la réponse — ce que les transports factices ne couvrent pas.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from neuroplanner.services.llm import LlmError, LlmSettings, generate_outline
from neuroplanner.services.providers import OpenAiCompatClient


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeOpenAI/1.0"

    def do_POST(self) -> None:  # noqa: N802 - nom imposé par http.server
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.requests.append(  # type: ignore[attr-defined]
            {"method": "POST", "path": self.path, "body": body, "auth": self.headers.get("Authorization")}
        )
        if self.headers.get("Authorization") != "Bearer gsk_local_test":
            self._reply(401, {"error": "invalid api key"})
            return
        text = '[{"titre": "Limites et continuité", "minutes": 90}, {"titre": "Dérivées", "minutes": 60}]'
        self._reply(200, {"choices": [{"message": {"role": "assistant", "content": text}}]})

    def do_GET(self) -> None:  # noqa: N802 - nom imposé par http.server
        self.server.requests.append(  # type: ignore[attr-defined]
            {"method": "GET", "path": self.path, "body": None, "auth": self.headers.get("Authorization")}
        )
        self._reply(200, {"data": [{"id": "models/llama-test"}, {"id": "autre-modele"}]})

    def _reply(self, code: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:  # silence : pas de bruit dans pytest
        return


@pytest.fixture
def fake_api() -> Iterator[dict]:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    server.requests = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"base_url": f"http://127.0.0.1:{server.server_port}/v1", "requests": server.requests}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def client_for(api: dict, key: str = "gsk_local_test") -> OpenAiCompatClient:
    settings = LlmSettings(provider="groq", base_url=api["base_url"], model="modele-test", api_key=key)
    return OpenAiCompatClient(settings)


def test_complete_over_http_sends_the_expected_request(fake_api: dict) -> None:
    chapters = generate_outline("Analyse réelle", client=client_for(fake_api), count=2)

    assert [chapter.title for chapter in chapters] == ["Limites et continuité", "Dérivées"]
    assert [chapter.minutes for chapter in chapters] == [90, 60]

    request = fake_api["requests"][0]
    assert request["method"] == "POST"
    assert request["path"] == "/v1/chat/completions"
    assert request["auth"] == "Bearer gsk_local_test"
    assert request["body"]["model"] == "modele-test"
    assert request["body"]["messages"][0]["role"] == "user"
    assert "Analyse réelle" in request["body"]["messages"][0]["content"]


def test_models_are_listed_over_http(fake_api: dict) -> None:
    models = client_for(fake_api).models()
    assert models == ["autre-modele", "llama-test"]  # préfixe « models/ » retiré, trié
    assert fake_api["requests"][0]["path"] == "/v1/models"


def test_bad_key_is_reported_without_leaking_it(fake_api: dict) -> None:
    client = client_for(fake_api, key="gsk_mauvaise")
    with pytest.raises(LlmError) as caught:
        client.complete("x")

    message = str(caught.value)
    assert "Clé refusée" in message
    assert "gsk_mauvaise" not in message


def test_unreachable_server_is_reported() -> None:
    settings = LlmSettings(
        provider="groq", base_url="http://127.0.0.1:1/v1", model="m", api_key="gsk_x"
    )
    with pytest.raises(LlmError, match="Impossible de joindre"):
        OpenAiCompatClient(settings).complete("x")
