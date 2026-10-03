"""Settings UI for ScreenScraper credentials."""

from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from src.engine.media_sources.screenscraper import (
    ScreenScraperCredentialStore,
    ScreenScraperCredentials,
)


class ScreenScraperSettingsPanel(ctk.CTkFrame):
    def __init__(self, parent, store: ScreenScraperCredentialStore | None = None):
        super().__init__(parent, fg_color="#101522", corner_radius=8)
        self.store = store or ScreenScraperCredentialStore()
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="ScreenScraper-Zugang",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 3))
        ctk.CTkLabel(
            self,
            text=(
                "Nach dem Speichern kannst du links über „ScreenScraper-Medien suchen“ "
                "einen Spieltitel suchen. API-Zugriff erfordert gültige Entwicklerdaten "
                "und gegebenenfalls die ScreenScraper-Freigabe."
            ),
            justify="left",
            wraplength=380,
            text_color="#a0a0b5",
        ).pack(fill="x", padx=14, pady=(0, 8))

        fields = ctk.CTkFrame(self, fg_color="transparent")
        fields.pack(fill="x", padx=12)
        fields.grid_columnconfigure(1, weight=1)
        self._entries = {}
        definitions = (
            ("username", "ScreenScraper-Benutzername", True),
            ("password", "ScreenScraper-Passwort", False),
            ("developer_id", "API-Entwickler-ID (devid)", True),
            ("developer_password", "API-Entwickler-Passwort", False),
        )
        try:
            credentials = self.store.load()
        except Exception as exc:
            credentials = ScreenScraperCredentials()
            messagebox.showerror(
                "ScreenScraper-Zugang",
                f"Gespeicherte Zugangsdaten konnten nicht gelesen werden:\n{exc}",
                parent=self.winfo_toplevel(),
            )
        for row, (field, label, _) in enumerate(definitions):
            ctk.CTkLabel(fields, text=label, anchor="w").grid(
                row=row, column=0, padx=(2, 10), pady=4, sticky="w"
            )
            entry = ctk.CTkEntry(
                fields,
                show="*" if field in ("password", "developer_password") else "",
            )
            entry.insert(0, getattr(credentials, field))
            entry.grid(row=row, column=1, padx=2, pady=4, sticky="ew")
            self._entries[field] = entry

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(8, 12))
        self._status = ctk.CTkLabel(actions, text="", anchor="w", text_color="#83c98b")
        self._status.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            actions,
            text="Zugangsdaten sicher speichern",
            width=180,
            command=self._save,
        ).pack(side="right")

    def _save(self):
        credentials = ScreenScraperCredentials(
            **{field: entry.get().strip() for field, entry in self._entries.items()}
        )
        try:
            self.store.save(credentials)
        except Exception as exc:
            messagebox.showerror(
                "ScreenScraper-Zugang",
                f"Zugangsdaten konnten nicht im System-Schlüsselbund gespeichert werden:\n{exc}",
                parent=self.winfo_toplevel(),
            )
            return
        self._status.configure(text="Zugangsdaten im System-Schlüsselbund gespeichert.")
