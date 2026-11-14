"""Connexion à un LLM local (Ollama) pour produire une structure de chapitres.

Aucune dépendance supplémentaire : ``urllib`` suffit, et le transport est
injectable, ce qui permet de tester la logique sans réseau ni modèle.

Le modèle ne génère **que** la liste des chapitres ; la construction du planning
reste déterministe (:mod:`neuroplanner.services.generation`).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from neuroplanner.models import Chapter
from neuroplanner.services.chapters import (
    MAX_CHAPTER_MINUTES,
    MIN_CHAPTER_MINUTES,
    parse_chapters,
)

#: Modèle conseillé : petit, rapide, correct en français.
DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_BASE_URL = "http://localhost:11434"
#: Nombre de chapitres demandé par défaut (un par jour, deux pour les gros sujets).
DEFAULT_CHAPTER_COUNT = 12

Transport = Callable[[str, dict, float], dict]


class LlmError(RuntimeError):
    """Erreur d'appel au modèle, avec un message actionnable."""


@dataclass(frozen=True, slots=True)
class LlmSettings:
    """Paramètres de connexion au serveur Ollama."""

    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: float = 300.0
    #: ``True`` active le raisonnement étendu des modèles qui le proposent
    #: (ex. gemma4) ; ``None`` laisse le comportement par défaut du serveur.
    think: bool | None = None

    @classmethod
    def from_env(cls) -> LlmSettings:
        raw_think = os.environ.get("NEUROPLANNER_LLM_THINK", "").strip().lower()
        think = None if raw_think == "" else raw_think in {"1", "true", "yes", "oui", "on"}
        return cls(
            base_url=os.environ.get("NEUROPLANNER_OLLAMA_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=os.environ.get("NEUROPLANNER_LLM_MODEL", DEFAULT_MODEL),
            think=think,
        )


class OllamaClient:
    """Client minimal de l'API Ollama (``/api/tags`` et ``/api/generate``)."""

    def __init__(
        self,
        settings: LlmSettings | None = None,
        *,
        transport: Transport | None = None,
    ) -> None:
        self.settings = settings or LlmSettings.from_env()
        self._transport = transport or _post_json

    def models(self) -> list[str]:
        """Modèles installés localement (liste vide si le serveur est absent)."""
        try:
            payload = self._transport(f"{self.settings.base_url}/api/tags", {}, 10.0)
        except LlmError:
            return []
        entries = payload.get("models", [])
        names = [entry.get("name", "") for entry in entries if isinstance(entry, dict)]
        return [name for name in names if name]

    def complete(self, prompt: str) -> str:
        """Envoie un prompt et renvoie la réponse texte du modèle."""
        payload: dict = {
            "model": self.settings.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if self.settings.think is not None:
            payload["think"] = self.settings.think
        response = self._transport(
            f"{self.settings.base_url}/api/generate", payload, self.settings.timeout
        )
        # Les modèles « thinking » renvoient parfois le raisonnement à part :
        # on ne garde que la réponse finale, avec repli sur le raisonnement.
        text = response.get("response") or response.get("thinking")
        if not isinstance(text, str) or not text.strip():
            raise LlmError("Réponse vide du modèle : réessaie avec un autre modèle.")
        return text


def build_prompt(topic: str, *, count: int = DEFAULT_CHAPTER_COUNT) -> str:
    """Prompt volontairement contraint : JSON seul, durées explicites."""
    return (
        "Tu es ingénieur pédagogique. Découpe le sujet suivant en chapitres "
        "étudiables, du plus fondamental au plus avancé.\n\n"
        f"Sujet : {topic.strip()}\n\n"
        f"Contraintes :\n"
        f"- exactement {count} chapitres ;\n"
        f"- intitulés courts, en français, sans sous-listes ;\n"
        f"- durée estimée entre {MIN_CHAPTER_MINUTES} et {MAX_CHAPTER_MINUTES} minutes "
        "par chapitre.\n\n"
        "Réponds UNIQUEMENT par un tableau JSON, sans texte avant ni après :\n"
        '[{"titre": "Nom du chapitre", "minutes": 120}]\n'
    )


def generate_outline(
    topic: str,
    *,
    client: OllamaClient | None = None,
    count: int = DEFAULT_CHAPTER_COUNT,
) -> list[Chapter]:
    """Demande au modèle une liste de chapitres et la valide.

    Lève :class:`LlmError` si le sujet est vide, ou une erreur réseau si le
    serveur ne répond pas.
    """
    subject = topic.strip()
    if len(subject) < 3:
        raise LlmError("Décris le sujet en quelques mots avant de lancer la génération.")

    active = client or OllamaClient()
    raw = active.complete(build_prompt(subject, count=count))
    chapters = parse_outline(raw)
    if not chapters:
        raise LlmError("Le modèle n'a renvoyé aucun chapitre exploitable.")
    return chapters


def parse_outline(text: str) -> list[Chapter]:
    """Extrait les chapitres d'une réponse de modèle, JSON ou texte libre."""
    best = _best_array_chapters(text)
    if best:
        return best

    # Repli : le modèle a répondu par une liste à puces malgré la consigne.
    # On ne retient que les lignes qui ressemblent vraiment à des items, pour
    # ne pas transformer une phrase d'excuse en chapitre.
    items = [line for line in text.splitlines() if _LIST_ITEM.match(line)]
    if not items:
        return []
    try:
        return parse_chapters("\n".join(items))
    except ValueError:
        return []


#: Ligne de liste : puce ou numérotation suivie d'un intitulé.
_LIST_ITEM = re.compile(r"^\s*(?:[-*•·–—]|\d{1,3}[.)]|\d{1,3}\s*[-–—:]\s+)\s*\S")


def _best_array_chapters(text: str) -> list[Chapter]:
    """Meilleur tableau JSON de la réponse, en ignorant un brouillon de raisonnement.

    Un modèle « thinking » peut écrire ``[étape 1]`` dans son raisonnement : on
    privilégie donc les tableaux d'objets portant une clé ``titre``/``title``.
    """
    best: list[Chapter] = []
    best_score = 0

    for array in _decodable_arrays(text):
        chapters = [chapter for chapter in map(_chapter_from_entry, array) if chapter]
        if not chapters:
            continue
        score = sum(2 if isinstance(entry, dict) else 1 for entry in array)
        if score > best_score or (score == best_score and len(chapters) > len(best)):
            best, best_score = chapters, score
    return best


def _decodable_arrays(text: str) -> list[list]:
    """Tous les tableaux JSON décodables, y compris ceux imbriqués dans du texte."""
    decoder = json.JSONDecoder()
    arrays: list[list] = []
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            data, _end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            data = data.get("chapitres") or data.get("chapters")
        if isinstance(data, list) and data:
            arrays.append(data)
    return arrays


def _chapter_from_entry(entry: object) -> Chapter | None:
    if isinstance(entry, str):
        title, minutes = entry.strip(), None
    elif isinstance(entry, dict):
        title = str(entry.get("titre") or entry.get("title") or "").strip()
        minutes = entry.get("minutes") or entry.get("duree") or entry.get("durée")
    else:
        return None

    title = " ".join(title.split())[:120]
    if len(title) < 2:
        return None

    try:
        value = int(minutes) if minutes is not None else None
    except (TypeError, ValueError):
        value = None
    if value is not None and not MIN_CHAPTER_MINUTES <= value <= MAX_CHAPTER_MINUTES:
        value = None
    return Chapter(title=title, minutes=value)


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    """Transport par défaut : POST JSON via ``urllib``, erreurs traduites."""
    data = json.dumps(payload).encode("utf-8") if payload else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise LlmError(_http_message(error)) from None
    except urllib.error.URLError as error:
        raise LlmError(
            f"Impossible de joindre Ollama sur {url}.\n"
            "Vérifie que le serveur tourne : `ollama serve` "
            f"(détail : {error.reason})."
        ) from None
    except TimeoutError:
        raise LlmError("Le modèle n'a pas répondu à temps : réduis le nombre de chapitres.") from None

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise LlmError("Réponse illisible du serveur Ollama.") from None
    if not isinstance(parsed, dict):
        raise LlmError("Réponse inattendue du serveur Ollama.")
    return parsed


def _http_message(error: urllib.error.HTTPError) -> str:
    try:
        detail = error.read().decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover - corps indisponible
        detail = ""
    hint = ""
    if error.code == 404:
        hint = " Le modèle est probablement absent : `ollama pull <modèle>`."
    elif error.code in (401, 403):
        hint = " Accès refusé par le serveur."
    elif error.code == 400:
        hint = (
            " Le modèle ne gère peut-être pas le raisonnement étendu : "
            "décoche l'option « raisonnement »."
        )
    return f"Ollama a répondu HTTP {error.code}.{hint}\n{detail[:300]}".strip()
