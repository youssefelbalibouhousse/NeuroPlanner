"""Réglages du fournisseur LLM, persistés hors du dépôt.

Le fichier contient éventuellement une clé d'API : il est créé avec des
permissions restrictives (0600) sur les systèmes qui le permettent, il est
ignoré par git, et la clé n'apparaît jamais dans un ``repr`` ni dans un message
d'erreur.
"""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from neuroplanner.data.jsonfile import read_json, write_json_atomic

#: Nom du fichier de réglages (à côté de la progression, hors dépôt).
CONFIG_FILENAME = "llm_settings.json"


@dataclass(frozen=True, slots=True)
class LlmConfig:
    """Fournisseur et modèle retenus ; la clé est optionnelle."""

    provider: str = "ollama"
    model: str = ""
    api_key: str = field(default="", repr=False)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    @property
    def masked_key(self) -> str:
        """Aperçu sûr pour l'interface : ``••••••1a2b``."""
        if not self.api_key:
            return ""
        tail = self.api_key[-4:] if len(self.api_key) > 8 else ""
        return "•" * 8 + tail


class LlmConfigStore:
    """Lecture/écriture du fichier de réglages ; tolérant aux fichiers abîmés."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> LlmConfig:
        raw = read_json(self.path) or {}
        return LlmConfig(
            provider=str(raw.get("provider") or "ollama").strip().lower(),
            model=str(raw.get("model") or "").strip(),
            api_key=str(raw.get("api_key") or "").strip(),
        )

    def save(self, config: LlmConfig) -> None:
        write_json_atomic(
            self.path,
            {
                "provider": config.provider,
                "model": config.model,
                "api_key": config.api_key,
            },
        )
        self._restrict_permissions()

    def _restrict_permissions(self) -> None:
        """``0600`` : la clé ne doit pas être lisible par les autres comptes."""
        with contextlib.suppress(OSError):
            os.chmod(self.path, 0o600)

    def clear(self) -> None:
        with contextlib.suppress(OSError):
            self.path.unlink(missing_ok=True)
