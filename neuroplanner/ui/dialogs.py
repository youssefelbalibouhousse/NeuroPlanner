"""Dialogues modaux : gestion des domaines et édition d'une tâche.

Les dialogues modifient directement :class:`~neuroplanner.data.plan_store.PlanStore`
et signalent via ``changed`` que l'appelant doit reconstruire ses vues.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox

import customtkinter as ctk

from neuroplanner.data.plan_store import PlanStore
from neuroplanner.formatting import plural
from neuroplanner.models import TaskNode
from neuroplanner.theme import DOMAIN_PALETTE, PALETTE, font, mix

#: Durées proposées, en minutes.
DURATION_STEPS: tuple[int, ...] = tuple(range(5, 185, 5))
DEFAULT_DURATION = 45


class ModalDialog(ctk.CTkToplevel):
    """Fenêtre modale centrée sur son parent, fermable par Échap."""

    def __init__(self, master: ctk.CTkBaseClass, title: str, width: int, height: int) -> None:
        super().__init__(master, fg_color=PALETTE.bg)
        self._width = width
        self._height = height
        self.changed = False

        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        self.after(10, self._center)

    def _center(self) -> None:
        """Centre la fenêtre en pixels physiques (CustomTkinter met à l'échelle)."""
        with contextlib.suppress(tk.TclError):
            if not self.winfo_exists():
                return
        factor = max(1.0, float(self._get_window_scaling() or 1.0))
        self._current_width, self._current_height = self._width, self._height
        width, height = int(self._width * factor), int(self._height * factor)

        parent = self.master
        with contextlib.suppress(tk.TclError):
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 3)
            tk.Toplevel.geometry(self, f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def run(self) -> bool:
        """Affiche la fenêtre et attend sa fermeture ; renvoie ``changed``."""
        self.grab_set()
        self.wait_window()
        return self.changed

    def close(self) -> None:
        with contextlib.suppress(tk.TclError):
            self.grab_release()
        self.destroy()


class _DialogFooter(ctk.CTkFrame):
    """Pied de dialogue : message d'erreur + boutons."""

    def __init__(self, master: ctk.CTkBaseClass, text: str = "Fermer") -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        self.error = ctk.CTkLabel(
            self, text="", anchor="w", font=font(10), text_color=PALETTE.red, wraplength=340
        )
        self.error.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.close_button = ctk.CTkButton(
            self,
            text=text,
            height=36,
            corner_radius=10,
            fg_color=PALETTE.raised,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            font=font(12),
        )
        self.close_button.grid(row=1, column=0, sticky="ew")

    def show_error(self, message: str) -> None:
        self.error.configure(text=message)

    def clear_error(self) -> None:
        self.error.configure(text="")


class DomainDialog(ModalDialog):
    """Ajouter, renommer, recolorer ou supprimer les piliers d'apprentissage."""

    def __init__(self, master: ctk.CTkBaseClass, plan: PlanStore) -> None:
        super().__init__(master, "Domaines d'apprentissage", 560, 640)
        self.plan = plan
        self._rows: list[ctk.CTkFrame] = []
        self._loading = False
        self._build()
        self.reload()

    # -- construction ------------------------------------------------------ #
    def _build(self) -> None:
        ctk.CTkLabel(
            self,
            text="Domaines d'apprentissage",
            anchor="w",
            font=font(18, "bold"),
            text_color=PALETTE.text,
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 0))
        ctk.CTkLabel(
            self,
            text=(
                "Ces piliers structurent le graphique de refocalisation. "
                "Clique sur une pastille pour changer sa couleur."
            ),
            anchor="w",
            justify="left",
            wraplength=500,
            font=font(10),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(4, 14))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=2, column=0, sticky="ew", padx=24)
        form.grid_columnconfigure(0, weight=1)

        self.name_entry = ctk.CTkEntry(
            form,
            height=36,
            corner_radius=10,
            fg_color=PALETTE.card,
            border_color=PALETTE.border,
            text_color=PALETTE.text,
            placeholder_text="Nouveau pilier (ex. Mathématiques)",
            font=font(12),
        )
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.name_entry.bind("<Return>", lambda _event: self.add_domain())

        self.add_button = ctk.CTkButton(
            form,
            text="Ajouter",
            width=96,
            height=36,
            corner_radius=10,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent_hover,
            text_color="#FFFFFF",
            font=font(12, "bold"),
            command=self.add_domain,
        )
        self.add_button.grid(row=0, column=1)

        self.list = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=PALETTE.border,
            scrollbar_button_hover_color=PALETTE.raised,
        )
        self.list.grid(row=3, column=0, sticky="nsew", padx=(18, 12), pady=(14, 6))
        self.list.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.footer = _DialogFooter(self)
        self.footer.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 20))
        self.footer.close_button.configure(command=self.close)

    # -- rendu ------------------------------------------------------------- #
    def reload(self) -> None:
        """Reconstruit la liste des domaines."""
        self._loading = True
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        for domain in self.plan.domains:
            row = self._build_row(domain.name, domain.color)
            row.grid(row=len(self._rows), column=0, sticky="ew", pady=(0, 6))
            self._rows.append(row)
        self._loading = False

    def _build_row(self, name: str, color: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(
            self.list,
            fg_color=PALETTE.card,
            corner_radius=12,
            border_width=1,
            border_color=PALETTE.border,
        )
        row.grid_columnconfigure(2, weight=1)

        swatch = ctk.CTkButton(
            row,
            text="●",
            width=30,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=mix(PALETTE.card, color, 0.22),
            text_color=color,
            font=font(15),
            command=lambda: self.cycle_color(name),
        )
        swatch.grid(row=0, column=0, padx=(10, 4), pady=8)

        name_entry = ctk.CTkEntry(
            row,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE.border,
            text_color=PALETTE.text,
            font=font(12, "bold"),
        )
        name_entry.insert(0, name)
        name_entry.grid(row=0, column=1, sticky="ew", padx=(4, 10), pady=8)
        name_entry.bind("<Return>", lambda _event, entry=name_entry, old=name: self.rename(old, entry.get()))
        name_entry.bind("<FocusOut>", lambda _event, entry=name_entry, old=name: self.rename(old, entry.get()))

        count = self.plan.task_count(name)
        ctk.CTkLabel(
            row,
            text=f"{count} {plural(count, 'tâche')}",
            anchor="e",
            font=font(10, mono=True),
            text_color=PALETTE.dim if count else PALETTE.muted,
        ).grid(row=0, column=2, padx=(0, 8))

        delete = ctk.CTkButton(
            row,
            text="✕",
            width=30,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=PALETTE.raised,
            text_color=PALETTE.muted,
            font=font(13),
            command=lambda: self.delete_domain(name),
        )
        delete.grid(row=0, column=3, padx=(0, 10))
        if len(self.plan.domains) <= 1:
            delete.configure(state="disabled", text_color=PALETTE.dim)
        return row

    # -- actions ----------------------------------------------------------- #
    def add_domain(self) -> None:
        self.footer.clear_error()
        raw = self.name_entry.get()
        try:
            domain = self.plan.add_domain(raw)
        except ValueError as error:
            self.footer.show_error(str(error))
            return
        self.name_entry.delete(0, "end")
        self.changed = True
        self.reload()
        self.footer.show_error(f"« {domain.name} » ajouté : ajoute-lui des tâches avec « + ».")

    def rename(self, old: str, new: str) -> None:
        if self._loading or not new.strip() or new.strip() == old:
            return
        self.footer.clear_error()
        try:
            self.plan.rename_domain(old, new)
        except ValueError as error:
            self.footer.show_error(str(error))
            self.reload()
            return
        self.changed = True
        self.reload()

    def delete_domain(self, name: str) -> None:
        if self._loading:
            return
        count = self.plan.task_count(name)
        detail = (
            f"{count} {plural(count, 'tâche sera supprimée', 'tâches seront supprimées')} "
            f"du planning.\n"
            if count
            else "Ce domaine ne contient aucune tâche.\n"
        )
        if not messagebox.askyesno(
            "Supprimer le domaine",
            f"Supprimer « {name} » ?\n\n{detail}"
            "Les statistiques de focus sont conservées.",
            parent=self,
        ):
            return
        self.footer.clear_error()
        try:
            removed = self.plan.delete_domain(name)
        except ValueError as error:
            self.footer.show_error(str(error))
            return
        self.changed = True
        self.reload()
        if removed:
            self.footer.show_error(f"« {name} » supprimé, {removed} tâche(s) retirée(s).")

    def cycle_color(self, name: str) -> None:
        """Passe à la couleur suivante de la palette."""
        current = self.plan.color_of(name).upper()
        colors = [color.upper() for color in DOMAIN_PALETTE]
        index = colors.index(current) if current in colors else -1
        self.plan.set_domain_color(name, DOMAIN_PALETTE[(index + 1) % len(DOMAIN_PALETTE)])
        self.changed = True
        self.reload()

    # -- accès (tests) ----------------------------------------------------- #
    @property
    def domain_names(self) -> tuple[str, ...]:
        return self.plan.domain_names


class TaskDialog(ModalDialog):
    """Créer ou modifier une tâche d'un bloc donné."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        plan: PlanStore,
        day_key: str,
        block_index: int,
        task: TaskNode | None = None,
    ) -> None:
        self.plan = plan
        self.day_key = day_key
        self.block_index = block_index
        self.task = task
        block = plan.day(day_key).blocks[block_index]
        self.block_title = f"{block.start} – {block.end} · {block.title}"
        self._durations = self._duration_options(task.minutes if task else DEFAULT_DURATION)

        title = "Modifier la tâche" if task else "Nouvelle tâche"
        super().__init__(master, title, 520, 460)
        self._build()
        self.name_entry.focus_set()

    # -- construction ------------------------------------------------------ #
    @staticmethod
    def _duration_options(current: int) -> list[str]:
        values = set(DURATION_STEPS)
        values.add(max(1, int(current)))
        return [f"{minutes} min" for minutes in sorted(values)]

    def _build(self) -> None:
        ctk.CTkLabel(
            self,
            text="Modifier la tâche" if self.task else "Nouvelle tâche",
            anchor="w",
            font=font(18, "bold"),
            text_color=PALETTE.text,
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(22, 0))
        ctk.CTkLabel(
            self,
            text=self.block_title,
            anchor="w",
            font=font(10),
            text_color=PALETTE.dim,
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(4, 16))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=2, column=0, sticky="ew", padx=24)
        form.grid_columnconfigure(0, weight=1)

        self.name_entry = ctk.CTkEntry(
            form,
            height=38,
            corner_radius=10,
            fg_color=PALETTE.card,
            border_color=PALETTE.border,
            text_color=PALETTE.text,
            placeholder_text="Intitulé de la tâche",
            font=font(12),
        )
        self.name_entry.grid(row=0, column=0, columnspan=2, sticky="ew")
        if self.task:
            self.name_entry.insert(0, self.task.label)
        self.name_entry.bind("<Return>", lambda _event: self.save())

        self._field_label(form, 1, "Pilier")
        self.domain_menu = ctk.CTkOptionMenu(
            form,
            values=list(self.plan.domain_names) or ["—"],
            height=34,
            corner_radius=9,
            fg_color=PALETTE.card,
            button_color=PALETTE.raised,
            button_hover_color=PALETTE.border,
            text_color=PALETTE.text,
            dropdown_fg_color=PALETTE.card,
            dropdown_text_color=PALETTE.text,
            dropdown_hover_color=PALETTE.raised,
            font=font(11),
            dropdown_font=font(11),
        )
        self.domain_menu.grid(row=2, column=0, columnspan=2, sticky="ew")
        if self.task and self.plan.has_domain(self.task.domain):
            self.domain_menu.set(self.task.domain)
        elif self.plan.domain_names:
            self.domain_menu.set(self.plan.domain_names[0])

        self._field_label(form, 3, "Durée")
        self.duration_menu = ctk.CTkOptionMenu(
            form,
            values=self._durations,
            height=34,
            corner_radius=9,
            fg_color=PALETTE.card,
            button_color=PALETTE.raised,
            button_hover_color=PALETTE.border,
            text_color=PALETTE.text,
            dropdown_fg_color=PALETTE.card,
            dropdown_text_color=PALETTE.text,
            dropdown_hover_color=PALETTE.raised,
            font=font(11),
            dropdown_font=font(11),
            command=self._refresh_total,
        )
        self.duration_menu.grid(row=4, column=0, columnspan=2, sticky="ew")
        self.duration_menu.set(f"{self.task.minutes if self.task else DEFAULT_DURATION} min")

        self.total_label = ctk.CTkLabel(
            form, text="", anchor="w", font=font(10), text_color=PALETTE.dim
        )
        self.total_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._refresh_total()

        self.footer = _DialogFooter(self)
        self.footer.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 20))
        self.grid_rowconfigure(3, weight=1)

        buttons = ctk.CTkFrame(self.footer, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew")
        buttons.grid_columnconfigure(0, weight=1)
        buttons.grid_columnconfigure(1, weight=1)
        buttons.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(
            buttons,
            text="Enregistrer",
            height=36,
            corner_radius=10,
            fg_color=PALETTE.accent,
            hover_color=PALETTE.accent_hover,
            text_color="#FFFFFF",
            font=font(12, "bold"),
            command=self.save,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            buttons,
            text="Annuler",
            height=36,
            corner_radius=10,
            fg_color=PALETTE.raised,
            hover_color=PALETTE.border,
            text_color=PALETTE.text,
            font=font(12),
            command=self.close,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 6))

        delete = ctk.CTkButton(
            buttons,
            text="Supprimer",
            height=36,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color=PALETTE.border,
            hover_color=mix(PALETTE.card, PALETTE.red, 0.25),
            text_color=PALETTE.red,
            font=font(12),
            command=self.delete,
        )
        delete.grid(row=0, column=2, sticky="ew")
        if self.task is None:
            delete.grid_remove()

    def _field_label(self, master: ctk.CTkFrame, row: int, text: str) -> None:
        ctk.CTkLabel(
            master, text=text, anchor="w", font=font(9, "bold"), text_color=PALETTE.dim
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(14, 4))

    # -- logique ----------------------------------------------------------- #
    def _refresh_total(self, _value: str | None = None) -> None:
        minutes = self.selected_minutes()
        others = sum(task.minutes for task in self._block_tasks() if not self._is_self(task))
        self.total_label.configure(text=f"Ce bloc : {others + minutes} min au total")

    def _block_tasks(self) -> tuple[TaskNode, ...]:
        return self.plan.day(self.day_key).blocks[self.block_index].tasks

    def _is_self(self, task: TaskNode) -> bool:
        return self.task is not None and task.tid == self.task.tid

    def selected_minutes(self) -> int:
        value = self.duration_menu.get().split()[0]
        with contextlib.suppress(ValueError):
            return int(value)
        return DEFAULT_DURATION

    def save(self) -> None:
        self.footer.clear_error()
        label = self.name_entry.get()
        domain = self.domain_menu.get()
        minutes = self.selected_minutes()
        try:
            if self.task is None:
                created = self.plan.add_task(
                    self.day_key,
                    self.block_index,
                    label=label,
                    domain=domain,
                    minutes=minutes,
                )
                self.task = created
            else:
                self.plan.update_task(
                    self.task.tid, label=label, domain=domain, minutes=minutes
                )
        except ValueError as error:
            self.footer.show_error(str(error))
            return
        self.changed = True
        self.close()

    def delete(self) -> None:
        if self.task is None:
            return
        if not messagebox.askyesno(
            "Supprimer la tâche",
            f"Supprimer « {self.task.label} » ?\n\nLa progression de cette tâche sera perdue.",
            parent=self,
        ):
            return
        removed = self.plan.delete_task(self.task.tid)
        if removed:
            self.changed = True
        self.close()


#: Signature d'une fabrique de dialogue, injectable dans l'application (tests).
DialogFactory = Callable[..., ModalDialog]
