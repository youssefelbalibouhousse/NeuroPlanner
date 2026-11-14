"""Dialogue « Importer un programme » : chapitres → planning de la semaine.

Deux entrées possibles, un seul pipeline :

1. **coller une table des matières** (ou toute liste de chapitres) ;
2. **demander à un LLM** — local (Ollama) ou hébergé à palier gratuit (Groq,
   Gemini, Mistral) — de proposer les chapitres. Le résultat est écrit dans la
   zone de texte pour relecture, jamais appliqué en aveugle.

Le planning lui-même est construit par :mod:`neuroplanner.services.generation`,
de façon déterministe et vérifiable dans l'aperçu avant application.
"""

from __future__ import annotations

import contextlib
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

import customtkinter as ctk

from neuroplanner.config import DAY_LABELS
from neuroplanner.data.llm_config import LlmConfig, LlmConfigStore
from neuroplanner.data.plan_store import PlanStore
from neuroplanner.models import Chapter
from neuroplanner.services.chapters import format_chapters, parse_chapters
from neuroplanner.services.generation import build_week, describe_week
from neuroplanner.services.llm import DEFAULT_CHAPTER_COUNT, LlmError, LlmSettings, generate_outline
from neuroplanner.services.providers import (
    PROVIDERS,
    Provider,
    create_client,
    get_provider,
    preferred_model,
    provider_from_label,
    settings_for,
)
from neuroplanner.theme import PALETTE, font
from neuroplanner.ui.dialogs import ModalDialog, _DialogFooter

PLACEHOLDER = (
    "Colle une table des matières, un chapitre par ligne :\n"
    "1. Limites et continuité (90 min)\n"
    "2. Dérivées et applications\n"
    "- Intégration — 1 h 30\n\n"
    "La durée entre parenthèses est facultative."
)

#: Nombres de chapitres proposés à l'assistant.
CHAPTER_COUNTS: tuple[int, ...] = (6, 8, 12, 16)
POLL_MS = 250


class ImportDialog(ModalDialog):
    """Construit un planning complet à partir d'une liste de chapitres."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        plan: PlanStore,
        *,
        client_factory: Callable[[LlmSettings], object] | None = None,
        config_path=None,
    ) -> None:
        self.plan = plan
        self._client_factory = client_factory or create_client
        self._config_store = LlmConfigStore(config_path) if config_path is not None else None
        self._config: LlmConfig = (
            self._config_store.load() if self._config_store else LlmConfig()
        )
        self._provider: Provider = get_provider(self._config.provider)
        self._job: str | None = None
        self._worker: threading.Thread | None = None
        self._result: list[Chapter] | None = None
        self._worker_error: str | None = None
        self._previewed = False
        self._client: object | None = None
        #: Suffixe d'état indiquant un basculement automatique de modèle.
        self._note = ""

        super().__init__(master, "Importer un programme", 680, 780)
        self._build()
        self._apply_provider(self._provider, model=self._config.model, api_key=self._config.api_key)
        self.protocol("WM_DELETE_WINDOW", self.close)

    # -- construction ------------------------------------------------------ #
    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=3)
        self.grid_rowconfigure(7, weight=2)

        ctk.CTkLabel(
            self,
            text="Importer un programme",
            anchor="w",
            font=font(18, "bold"),
            text_color=PALETTE.text,
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(18, 0))
        ctk.CTkLabel(
            self,
            text=(
                "Les chapitres sont répartis sur les 6 jours : encodage, exercices, "
                "synthèse, puis 1 h de récupération active."
            ),
            anchor="w",
            justify="left",
            wraplength=600,
            font=font(10),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(2, 8))

        ctk.CTkLabel(
            self, text="1 · CHAPITRES", anchor="w", font=font(9, "bold"), text_color=PALETTE.dim
        ).grid(row=2, column=0, sticky="w", padx=24)
        self.text = ctk.CTkTextbox(
            self,
            height=150,
            corner_radius=10,
            border_width=1,
            border_color=PALETTE.border,
            fg_color=PALETTE.card,
            text_color=PALETTE.text,
            font=font(12),
            wrap="word",
        )
        self.text.grid(row=3, column=0, sticky="nsew", padx=24, pady=(4, 8))
        self.text.insert("1.0", PLACEHOLDER)
        self._placeholder_active = True
        self.text.bind("<FocusIn>", self._clear_placeholder)
        self.text.bind("<KeyRelease>", self._invalidate_preview)

        self._build_assistant(row=4)
        self._build_destination(row=5)
        self._build_preview(label_row=6, row=7)

        self.footer = _DialogFooter(self)
        self.footer.grid(row=8, column=0, sticky="ew", padx=24, pady=(6, 16))
        self.footer.close_button.configure(text="Annuler", command=self.close)

        buttons = ctk.CTkFrame(self.footer, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="ew")
        buttons.grid_columnconfigure(0, weight=2, uniform="import")
        buttons.grid_columnconfigure(1, weight=3, uniform="import")

        self.preview_button = ctk.CTkButton(
            buttons,
            text="Aperçu",
            height=36,
            corner_radius=10,
            fg_color=PALETTE.raised,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            font=font(12),
            command=self.build_preview,
        )
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.apply_button = ctk.CTkButton(
            buttons,
            text="Appliquer au planning",
            height=36,
            corner_radius=10,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent_hover,
            text_color="#FFFFFF",
            font=font(12, "bold"),
            command=self.apply,
        )
        self.apply_button.grid(row=0, column=1, sticky="ew")

    def _build_assistant(self, row: int) -> None:
        box = ctk.CTkFrame(
            self,
            fg_color=PALETTE.card,
            corner_radius=12,
            border_width=1,
            border_color=PALETTE.border,
        )
        box.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 6))
        box.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(box, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head,
            text="Assistant LLM",
            anchor="w",
            font=font(11, "bold"),
            text_color=PALETTE.text,
        ).grid(row=0, column=0, sticky="w")
        self.status = ctk.CTkLabel(
            head, text="", anchor="e", font=font(9), text_color=PALETTE.dim
        )
        self.status.grid(row=0, column=1, sticky="e")

        form = ctk.CTkFrame(box, fg_color="transparent")
        form.grid(row=1, column=0, sticky="ew", padx=14, pady=(6, 12))
        form.grid_columnconfigure(0, weight=3)
        form.grid_columnconfigure(1, weight=4)
        form.grid_columnconfigure(2, weight=2)

        self.topic_entry = ctk.CTkEntry(
            form,
            height=34,
            corner_radius=9,
            fg_color=PALETTE.bg,
            border_color=PALETTE.border,
            text_color=PALETTE.text,
            placeholder_text="Sujet (ex. Analyse réelle niveau L2)",
            font=font(11),
        )
        self.topic_entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.topic_entry.bind("<Return>", lambda _event: self.generate())

        self.provider_menu = ctk.CTkOptionMenu(
            form,
            values=[provider.label for provider in PROVIDERS],
            height=32,
            corner_radius=9,
            fg_color=PALETTE.bg,
            button_color=PALETTE.raised,
            button_hover_color=PALETTE.border,
            text_color=PALETTE.text,
            dropdown_fg_color=PALETTE.card,
            dropdown_text_color=PALETTE.text,
            dropdown_hover_color=PALETTE.raised,
            font=font(10),
            dropdown_font=font(10),
            command=self._on_provider_change,
        )
        self.provider_menu.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        self.model_menu = ctk.CTkOptionMenu(
            form,
            values=list(self._provider.models) or [self._provider.default_model],
            height=32,
            corner_radius=9,
            fg_color=PALETTE.bg,
            button_color=PALETTE.raised,
            button_hover_color=PALETTE.border,
            text_color=PALETTE.text,
            dropdown_fg_color=PALETTE.card,
            dropdown_text_color=PALETTE.text,
            dropdown_hover_color=PALETTE.raised,
            font=font(10),
            dropdown_font=font(10),
        )
        self.model_menu.grid(row=1, column=1, sticky="ew", padx=(0, 6))

        self.count_menu = ctk.CTkOptionMenu(
            form,
            values=[f"{count} chapitres" for count in CHAPTER_COUNTS],
            width=110,
            height=32,
            corner_radius=9,
            fg_color=PALETTE.bg,
            button_color=PALETTE.raised,
            button_hover_color=PALETTE.border,
            text_color=PALETTE.text,
            dropdown_fg_color=PALETTE.card,
            dropdown_text_color=PALETTE.text,
            dropdown_hover_color=PALETTE.raised,
            font=font(10),
            dropdown_font=font(10),
        )
        self.count_menu.grid(row=1, column=2, sticky="ew")
        self.count_menu.set(f"{DEFAULT_CHAPTER_COUNT} chapitres")

        self.key_entry = ctk.CTkEntry(
            form,
            height=32,
            corner_radius=9,
            fg_color=PALETTE.bg,
            border_color=PALETTE.border,
            text_color=PALETTE.text,
            placeholder_text="Clé API (stockée hors du dépôt)",
            font=font(10),
            show="•",
        )
        self.key_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 6))

        self.generate_button = ctk.CTkButton(
            form,
            text="Générer",
            width=90,
            height=32,
            corner_radius=9,
            fg_color=PALETTE.raised,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            font=font(11, "bold"),
            command=self.generate,
        )
        self.generate_button.grid(row=2, column=2, sticky="ew", pady=(6, 0))

        self.save_key_var = tk.BooleanVar(master=self, value=True)
        self.save_key_check = ctk.CTkCheckBox(
            form,
            text="Mémoriser ce fournisseur et la clé",
            variable=self.save_key_var,
            checkbox_width=16,
            checkbox_height=16,
            corner_radius=5,
            border_width=2,
            border_color=PALETTE.dim,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent,
            checkmark_color=PALETTE.bg,
            text_color=PALETTE.dim,
            font=font(9),
        )
        self.save_key_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.think_var = tk.BooleanVar(master=self, value=False)
        self.think_check = ctk.CTkCheckBox(
            form,
            text="Raisonnement étendu",
            variable=self.think_var,
            checkbox_width=16,
            checkbox_height=16,
            corner_radius=5,
            border_width=2,
            border_color=PALETTE.dim,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent,
            checkmark_color=PALETTE.bg,
            text_color=PALETTE.dim,
            font=font(9),
        )
        self.think_check.grid(row=3, column=2, sticky="w", pady=(6, 0))

    def _build_destination(self, row: int) -> None:
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=row, column=0, sticky="ew", padx=24, pady=(8, 0))
        box.grid_columnconfigure(1, weight=1)
        box.grid_columnconfigure(3, weight=1)

        domains = list(self.plan.domain_names) or ["—"]

        ctk.CTkLabel(
            box, text="2 · PILIER", anchor="w", font=font(9, "bold"), text_color=PALETTE.dim
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.domain_box = ctk.CTkComboBox(
            box,
            values=domains,
            height=34,
            corner_radius=9,
            fg_color=PALETTE.card,
            border_color=PALETTE.border,
            button_color=PALETTE.raised,
            button_hover_color=PALETTE.border,
            text_color=PALETTE.text,
            dropdown_fg_color=PALETTE.card,
            dropdown_text_color=PALETTE.text,
            dropdown_hover_color=PALETTE.raised,
            font=font(11),
            dropdown_font=font(11),
        )
        self.domain_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 12))
        self.domain_box.set(domains[0])

        ctk.CTkLabel(
            box, text="RAPPEL ACTIF", anchor="w", font=font(9, "bold"), text_color=PALETTE.dim
        ).grid(row=0, column=2, columnspan=2, sticky="w", padx=(0, 8), pady=(0, 2))
        revision_values = ["(même pilier)", *domains]
        self.revision_box = ctk.CTkComboBox(
            box,
            values=revision_values,
            height=34,
            corner_radius=9,
            fg_color=PALETTE.card,
            border_color=PALETTE.border,
            button_color=PALETTE.raised,
            button_hover_color=PALETTE.border,
            text_color=PALETTE.text,
            dropdown_fg_color=PALETTE.card,
            dropdown_text_color=PALETTE.text,
            dropdown_hover_color=PALETTE.raised,
            font=font(11),
            dropdown_font=font(11),
        )
        self.revision_box.grid(row=1, column=2, columnspan=2, sticky="ew")
        default_revision = "Révision Active" if "Révision Active" in domains else "(même pilier)"
        self.revision_box.set(default_revision)

        self.prune_var = tk.BooleanVar(master=self, value=True)
        ctk.CTkCheckBox(
            box,
            text="Ne conserver que les piliers utilisés",
            variable=self.prune_var,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=6,
            border_width=2,
            border_color=PALETTE.dim,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent,
            checkmark_color=PALETTE.bg,
            text_color=PALETTE.muted,
            font=font(10),
            command=self._invalidate_preview,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def _build_preview(self, label_row: int, row: int) -> None:
        ctk.CTkLabel(
            self,
            text="3 · APERÇU",
            anchor="w",
            font=font(9, "bold"),
            text_color=PALETTE.dim,
        ).grid(row=label_row, column=0, sticky="w", padx=24, pady=(12, 2))
        self.preview = ctk.CTkTextbox(
            self,
            height=140,
            corner_radius=10,
            border_width=1,
            border_color=PALETTE.border,
            fg_color=PALETTE.bg,
            text_color=PALETTE.muted,
            font=font(10, mono=True),
            wrap="none",
        )
        self.preview.grid(row=row, column=0, sticky="nsew", padx=24, pady=(4, 0))
        self.preview.configure(state="disabled")

    # -- fournisseur ------------------------------------------------------- #
    def _models_for(self, provider: Provider, api_key: str = "") -> list[str]:
        """Modèles du fournisseur : liste réelle si possible, suggestions sinon.

        Quand la liste réelle est disponible, elle fait foi **seule** : y
        réinjecter les suggestions du registre ferait réapparaître un modèle
        retiré par le fournisseur (cas Groq : modèle supprimé → HTTP 404).
        """
        suggested = list(provider.models) or [provider.default_model]
        settings = settings_for(provider.key, model=provider.default_model, api_key=api_key)
        if provider.requires_key and not settings.api_key:
            return suggested
        with contextlib.suppress(Exception):
            found = self._client_factory(settings).models()  # type: ignore[attr-defined]
            if found:
                return list(found)
        return suggested

    def _default_model_for(self, provider: Provider, models: list[str], requested: str) -> str:
        """Modèle à sélectionner : celui demandé s'il existe, sinon le meilleur."""
        chosen = (requested or "").strip()
        if chosen in models:
            return chosen
        return preferred_model(provider, models) or chosen or models[0]

    def _apply_provider(
        self,
        provider: Provider,
        *,
        model: str = "",
        api_key: str = "",
    ) -> None:
        """Applique un fournisseur : menus, champs visibles et message d'état."""
        self._provider = provider
        self.provider_menu.set(provider.label)

        models = self._models_for(provider, api_key)
        self.model_menu.configure(values=models)
        self.model_menu.set(self._default_model_for(provider, models, model))

        self.key_entry.delete(0, "end")
        if api_key:
            self.key_entry.insert(0, api_key)

        if provider.requires_key:
            self.key_entry.grid()
            self.save_key_check.grid()
        else:
            self.key_entry.grid_remove()
            self.save_key_check.grid_remove()

        if provider.supports_think:
            self.think_check.grid()
        else:
            self.think_check.grid_remove()

        if provider.requires_key and not api_key:
            self.status.configure(text="clé requise", text_color=PALETTE.orange)
        elif provider.requires_key:
            self.status.configure(text="clé enregistrée", text_color=PALETTE.green)
        else:
            self.status.configure(text="local", text_color=PALETTE.dim)

    def _on_provider_change(self, label: str) -> None:
        self.footer.clear_error()
        provider = provider_from_label(label)
        # La clé est propre à chaque fournisseur : on repart des variables
        # d'environnement plutôt que de réutiliser celle du précédent.
        self._apply_provider(provider, api_key="")

    # -- zone de texte ----------------------------------------------------- #
    def settings(self) -> LlmSettings:
        """Réglages du prochain appel, déduits des champs de l'interface."""
        provider = self._provider
        # Case décochée = comportement par défaut du serveur (None), pas « false ».
        think = True if provider.supports_think and self.think_var.get() else None
        return settings_for(
            provider.key,
            model=self.model_menu.get().strip(),
            api_key=self.key_entry.get().strip(),
            think=think,
        )

    def _remember(self, settings: LlmSettings) -> None:
        """Mémorise fournisseur, modèle et clé si l'utilisateur le demande."""
        if self._config_store is None or not self.save_key_var.get():
            return
        self._config_store.save(
            LlmConfig(
                provider=settings.provider,
                model=settings.model,
                api_key=settings.api_key,
            )
        )

    def _clear_placeholder(self, _event: object = None) -> None:
        if self._placeholder_active:
            self._placeholder_active = False
            self.text.delete("1.0", "end")

    def chapters_text(self) -> str:
        """Contenu réel de la zone (le texte d'aide n'est pas un chapitre)."""
        if self._placeholder_active:
            return ""
        return self.text.get("1.0", "end")

    def set_chapters_text(self, value: str) -> None:
        self._placeholder_active = False
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self._invalidate_preview()

    def _invalidate_preview(self, _event: object = None) -> None:
        self._note = ""
        if self._previewed:
            self._previewed = False
            self._set_preview("(aperçu obsolète — clique sur « Aperçu »)")

    def _set_preview(self, value: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", value)
        self.preview.configure(state="disabled")

    @property
    def preview_text(self) -> str:
        return self.preview.get("1.0", "end").strip()

    # -- assistant LLM ----------------------------------------------------- #
    def generate(self) -> None:
        """Lance la génération dans un fil pour ne pas geler l'interface."""
        if self._worker is not None and self._worker.is_alive():
            return
        topic = self.topic_entry.get().strip()
        if len(topic) < 3:
            self.footer.show_error("Décris le sujet avant de lancer la génération.")
            return

        settings = self.settings()
        if self._provider.requires_key and not settings.api_key:
            self.footer.show_error(
                f"Colle ta clé {self._provider.label} (gratuite : {self._provider.docs_url})."
            )
            return

        self.footer.clear_error()
        self._remember(settings)
        self._result = None
        self._worker_error = None
        self.generate_button.configure(state="disabled", text="Génération…")
        self.status.configure(text=f"{self._provider.label} · en cours…", text_color=PALETTE.muted)

        client = self._client_factory(settings)
        self._client = client
        count = self._selected_count()

        def work() -> None:
            try:
                self._result = generate_outline(topic, client=client, count=count)
            except LlmError as error:
                self._worker_error = str(error)
            except Exception as error:  # pragma: no cover - garde-fou
                self._worker_error = f"Erreur inattendue : {error}"

        self._worker = threading.Thread(target=work, daemon=True, name="neuroplanner-llm")
        self._worker.start()
        self._schedule_poll()

    def _selected_count(self) -> int:
        return int(f"{self.count_menu.get()}".split()[0])

    def _schedule_poll(self) -> None:
        if self._job is None:
            self._job = self.after(POLL_MS, self._poll_generation)

    def _poll_generation(self) -> None:
        self._job = None
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return

        if self._worker is not None and self._worker.is_alive():
            self._schedule_poll()
            return

        self.generate_button.configure(state="normal", text="Générer")
        if self._worker_error:
            self.status.configure(text="échec", text_color=PALETTE.red)
            self.footer.show_error(self._worker_error)
            return

        chapters = self._result or []
        if not chapters:
            self.status.configure(text="aucun chapitre", text_color=PALETTE.red)
            self.footer.show_error("Le modèle n'a rien renvoyé d'exploitable.")
            return

        self.set_chapters_text(format_chapters(chapters))
        used = getattr(self._client, "used_model", None)
        self._note = f" · modèle {used}" if used else ""
        self.status.configure(
            text=f"{len(chapters)} chapitres · à relire", text_color=PALETTE.green
        )
        self.build_preview()

    # -- application ------------------------------------------------------- #
    def _current_week(self):
        chapters = parse_chapters(self.chapters_text())
        domain = self.domain_box.get().strip()
        if not domain or domain == "—":
            raise ValueError("Choisis le pilier qui recevra ce programme.")
        revision = self.revision_box.get().strip()
        if revision in ("", "(même pilier)", "—"):
            revision = None
        return chapters, domain, revision

    def build_preview(self) -> bool:
        """Calcule le planning et l'affiche ; renvoie ``False`` en cas d'erreur."""
        self.footer.clear_error()
        try:
            chapters, domain, revision = self._current_week()
            week = build_week(chapters, domain=domain, revision_domain=revision)
        except ValueError as error:
            self._set_preview("")
            self.footer.show_error(str(error))
            return False

        self._set_preview(describe_week(week, DAY_LABELS))
        self._previewed = True
        points = " · ".join(
            f"{DAY_LABELS[key][:3]} {sum(block.minutes for block in blocks)} min"
            for key, blocks in week.items()
        )
        self.status.configure(
            text=f"{len(chapters)} chapitres{self._note}", text_color=PALETTE.muted
        )
        self.footer.show_error(f"Prêt : {points}.")
        return True

    def apply(self) -> None:
        """Remplace le planning après confirmation (la progression est purgée)."""
        self.footer.clear_error()
        try:
            chapters, domain, revision = self._current_week()
            week = build_week(chapters, domain=domain, revision_domain=revision)
        except ValueError as error:
            self.footer.show_error(str(error))
            return

        if self.plan.tasks() and not messagebox.askyesno(
            "Remplacer le planning",
            "Le planning actuel sera remplacé et la progression des tâches "
            "existantes sera perdue.\n\nContinuer ?",
            parent=self,
        ):
            return

        self.plan.replace_week(week, prune_unused_domains=bool(self.prune_var.get()))
        self.changed = True
        self.close()

    # -- cycle de vie ------------------------------------------------------ #
    def close(self) -> None:
        if self._job is not None:
            with contextlib.suppress(tk.TclError, ValueError):
                self.after_cancel(self._job)
            self._job = None
        super().close()
