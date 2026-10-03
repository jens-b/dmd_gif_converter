"""Connection settings dialog for direct Batocera SMB access."""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from src.engine.media_sources.batocera_smb import (
    BatoceraConnectionConfig,
    BatoceraConnectionStore,
)
from src.ui.i18n import localize_widget_tree
from src.ui.i18n import tr


class BatoceraConnectionDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        on_connect: Callable[[BatoceraConnectionConfig], None],
        store: BatoceraConnectionStore | None = None,
    ):
        super().__init__(parent)
        self.title(tr("Batocera-Verbindung"))
        self.geometry("470x430")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.store = store or BatoceraConnectionStore()
        self.on_connect = on_connect
        self.grid_columnconfigure(1, weight=1)

        try:
            saved = self.store.load()
            stored_password = self.store.load_password(
                saved["server"], saved["share"], saved["username"]
            ) if saved["server"] and saved["username"] else ""
        except Exception as exc:
            messagebox.showerror(
                "Batocera-Einstellungen", f"Einstellungen konnten nicht geladen werden:\n{exc}",
                parent=self,
            )
            saved = {"server": "", "share": "share", "username": "root"}
            stored_password = ""

        ctk.CTkLabel(
            self,
            text="Direkte Verbindung zur Batocera-Netzwerkfreigabe",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=18, pady=(20, 8), sticky="w")
        ctk.CTkLabel(
            self,
            text="Es werden vorhandene Spielelisten und deren <video>-Dateien unter „roms“ gelesen.",
            wraplength=420,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 12), sticky="w")

        self.server_entry = self._add_entry(2, "Server / IP", saved["server"])
        self.share_entry = self._add_entry(3, "Freigabe", saved["share"])
        self.username_entry = self._add_entry(4, "Benutzername", saved["username"])
        self.password_entry = self._add_entry(
            5, "Passwort", stored_password or "linux", show="*"
        )

        self.remember_password = ctk.BooleanVar(value=bool(stored_password))
        ctk.CTkCheckBox(
            self,
            text="Passwort im System-Schlüsselbund speichern",
            variable=self.remember_password,
        ).grid(row=6, column=0, columnspan=2, padx=18, pady=(10, 6), sticky="w")
        ctk.CTkLabel(
            self,
            text="Standardanmeldung: root / linux. Server, Freigabe und Benutzername "
            "werden lokal gespeichert. Das Passwort wird nur mit Auswahl des "
            "Schlüsselbunds dauerhaft gespeichert.",
            wraplength=420,
            justify="left",
            text_color="#a0a0b5",
        ).grid(row=7, column=0, columnspan=2, padx=18, pady=(2, 14), sticky="w")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=8, column=0, columnspan=2, padx=18, pady=(0, 18), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            buttons, text="Abbrechen", fg_color="#3a3a4a",
            hover_color="#55556a", command=self.destroy,
        ).grid(row=0, column=0, padx=(0, 5), sticky="ew")
        ctk.CTkButton(
            buttons, text="Verbinden und importieren", command=self._submit,
        ).grid(row=0, column=1, padx=(5, 0), sticky="ew")
        self._on_connect = on_connect
        localize_widget_tree(self)

    def _add_entry(self, row: int, label: str, value: str, **kwargs):
        ctk.CTkLabel(self, text=label).grid(
            row=row, column=0, padx=(18, 10), pady=5, sticky="w"
        )
        entry = ctk.CTkEntry(self, **kwargs)
        entry.insert(0, value)
        entry.grid(row=row, column=1, padx=(0, 18), pady=5, sticky="ew")
        return entry

    def _submit(self):
        server = self.server_entry.get().strip()
        share = self.share_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not server or not share:
            messagebox.showerror(
                "Batocera-Verbindung", "Bitte Server und Freigabe angeben.", parent=self
            )
            return

        try:
            self.store.save(
                server,
                share,
                username,
                password,
                self.remember_password.get(),
            )
        except Exception as exc:
            messagebox.showerror(
                "Batocera-Einstellungen",
                f"Verbindungseinstellungen konnten nicht gespeichert werden:\n{exc}",
                parent=self,
            )
            return

        self.destroy()
        self._on_connect(
            BatoceraConnectionConfig(server, share, username, password)
        )
