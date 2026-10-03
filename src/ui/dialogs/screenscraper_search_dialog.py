"""ScreenScraper system, title, and media search dialog."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

import customtkinter as ctk

from src.engine.media_sources.screenscraper import (
    ScreenScraperCredentialStore,
    ScreenScraperGame,
    ScreenScraperMedia,
    ScreenScraperService,
    ScreenScraperSystem,
)
from src.ui.i18n import localize_widget_tree


class ScreenScraperSearchDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        on_media_ready: Callable[[list[str]], None],
        service: ScreenScraperService | None = None,
        credential_store: ScreenScraperCredentialStore | None = None,
    ):
        super().__init__(parent)
        self.title("ScreenScraper-Medien suchen")
        self.geometry("640x720")
        self.minsize(540, 560)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.grid_rowconfigure(8, weight=2)
        self.service = service or ScreenScraperService()
        self.credential_store = credential_store or ScreenScraperCredentialStore()
        self.on_media_ready = on_media_ready
        self._systems: dict[str, ScreenScraperSystem] = {}
        self._games: list[ScreenScraperGame] = []
        self._media: list[ScreenScraperMedia] = []
        self._cancel_event = threading.Event()
        self._busy = False
        self.protocol("WM_DELETE_WINDOW", self._close)

        ctk.CTkLabel(
            self,
            text="ScreenScraper: System, Spiel und Medien auswählen",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        ctk.CTkLabel(
            self,
            text=(
                "Erfordert gültige API-Entwicklerdaten und gegebenenfalls die "
                "ScreenScraper-Freigabe. Die API wird der Reihe nach abgefragt."
            ),
            justify="left",
            wraplength=590,
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

        system_row = ctk.CTkFrame(self, fg_color="transparent")
        system_row.grid(row=2, column=0, padx=16, pady=4, sticky="ew")
        system_row.grid_columnconfigure(0, weight=1)
        self._system_menu = ctk.CTkOptionMenu(
            system_row,
            values=["Plattformen erst laden"],
            state="disabled",
        )
        self._system_menu.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self._systems_button = ctk.CTkButton(
            system_row, text="Systeme laden", width=120, command=self._load_systems
        )
        self._systems_button.grid(row=0, column=1, sticky="ew")

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.grid(row=3, column=0, padx=16, pady=4, sticky="ew")
        search_row.grid_columnconfigure(0, weight=1)
        self._query = ctk.CTkEntry(
            search_row, placeholder_text="Spieltitel, z. B. Sonic the Hedgehog"
        )
        self._query.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self._query.bind("<Return>", lambda _event: self._search_games())
        self._search_button = ctk.CTkButton(
            search_row, text="Spiele suchen", width=120, command=self._search_games
        )
        self._search_button.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            self, text="Treffer", anchor="w", font=ctk.CTkFont(weight="bold")
        ).grid(row=4, column=0, padx=18, pady=(8, 2), sticky="w")
        game_frame = ctk.CTkFrame(self, fg_color="transparent")
        game_frame.grid(row=5, column=0, padx=16, pady=(0, 4), sticky="nsew")
        game_frame.grid_rowconfigure(0, weight=1)
        game_frame.grid_columnconfigure(0, weight=1)
        self._game_list = self._make_listbox(game_frame)
        ctk.CTkButton(
            self,
            text="Medien für ausgewähltes Spiel laden",
            command=self._load_selected_game_media,
        ).grid(row=6, column=0, padx=16, pady=4, sticky="ew")

        ctk.CTkLabel(
            self, text="Unterstützte Medien", anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=7, column=0, padx=18, pady=(8, 2), sticky="w")
        media_frame = ctk.CTkFrame(self, fg_color="transparent")
        media_frame.grid(row=8, column=0, padx=16, pady=(0, 4), sticky="nsew")
        media_frame.grid_rowconfigure(0, weight=1)
        media_frame.grid_columnconfigure(0, weight=1)
        self._media_list = self._make_listbox(media_frame, selectmode=tk.EXTENDED)

        self._status = ctk.CTkLabel(self, text="Bereit.", anchor="w", wraplength=590)
        self._status.grid(row=9, column=0, padx=16, pady=4, sticky="ew")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=10, column=0, padx=16, pady=(4, 16), sticky="ew")
        buttons.grid_columnconfigure((0, 1, 2), weight=1)
        self._cancel_button = ctk.CTkButton(
            buttons,
            text="Abbrechen",
            fg_color="#4a1a1a",
            hover_color="#7b241c",
            state="disabled",
            command=self._cancel,
        )
        self._cancel_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self._download_button = ctk.CTkButton(
            buttons,
            text="Auswahl laden und übernehmen",
            state="disabled",
            command=self._download,
        )
        self._download_button.grid(row=0, column=1, padx=5, sticky="ew")
        ctk.CTkButton(
            buttons,
            text="Schließen",
            fg_color="#3a3a4a",
            hover_color="#55556a",
            command=self._close,
        ).grid(row=0, column=2, padx=(5, 0), sticky="ew")
        localize_widget_tree(self)
        self.after(50, self._query.focus_set)

    @staticmethod
    def _make_listbox(parent, selectmode=tk.BROWSE):
        widget = tk.Listbox(
            parent,
            selectmode=selectmode,
            exportselection=False,
            background="#12121f",
            foreground="#ddddee",
            selectbackground="#1e3a5f",
            selectforeground="#ffffff",
            highlightthickness=0,
        )
        widget.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        widget.configure(yscrollcommand=scrollbar.set)
        return widget

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._systems_button.configure(state="disabled" if busy else "normal")
        self._search_button.configure(state="disabled" if busy else "normal")
        self._cancel_button.configure(state="normal" if busy else "disabled")
        self._download_button.configure(
            state="disabled" if busy or not self._media else "normal"
        )

    def _load_systems(self):
        if self._busy:
            return
        self._cancel_event.clear()
        self._set_busy(True)
        self._status.configure(text="ScreenScraper-Systemliste wird geladen …")

        def worker():
            try:
                credentials = self.credential_store.load()
                systems = self.service.list_systems(credentials)
                error = ""
            except Exception as exc:
                systems = []
                error = str(exc)

            def finish():
                if not self.winfo_exists():
                    return
                self._set_busy(False)
                if error:
                    self._status.configure(text=error)
                    return
                self._systems = {
                    f"{system.name} (ID {system.system_id})": system
                    for system in systems
                }
                values = list(self._systems)
                self._system_menu.configure(values=values, state="normal")
                if values:
                    self._system_menu.set(values[0])
                    self._status.configure(
                        text=f"{len(values)} Systeme geladen. Bitte ein System auswählen."
                    )

            self._dispatch(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _search_games(self):
        if self._busy:
            return
        system = self._systems.get(self._system_menu.get())
        if system is None:
            self._status.configure(text="Bitte zuerst die Systemliste laden und ein System wählen.")
            return
        query = self._query.get().strip()
        if not query:
            self._status.configure(text="Bitte einen Spieltitel eingeben.")
            return

        self._cancel_event.clear()
        self._set_busy(True)
        self._games = []
        self._media = []
        self._game_list.delete(0, tk.END)
        self._media_list.delete(0, tk.END)
        self._status.configure(text=f"Suche „{query}“ für {system.name} …")

        def worker():
            try:
                credentials = self.credential_store.load()
                games = self.service.search_games(query, system, credentials)
                error = ""
            except Exception as exc:
                games = []
                error = str(exc)

            def finish():
                if not self.winfo_exists():
                    return
                self._set_busy(False)
                if error:
                    self._status.configure(text=error)
                    return
                self._games = games
                for game in games:
                    self._game_list.insert(tk.END, game.name)
                self._status.configure(
                    text=f"{len(games)} Treffer für {system.name}."
                    if games else f"Keine Treffer für {system.name}."
                )

            self._dispatch(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _load_selected_game_media(self):
        if self._busy:
            return
        selection = self._game_list.curselection()
        if not selection:
            self._status.configure(text="Bitte zuerst einen Spieltreffer auswählen.")
            return
        game = self._games[selection[0]]
        self._cancel_event.clear()
        self._set_busy(True)
        self._media = []
        self._media_list.delete(0, tk.END)
        self._status.configure(text=f"Medien für „{game.name}“ werden gesucht …")

        def worker():
            try:
                credentials = self.credential_store.load()
                game_name, media = self.service.search_media(game, credentials)
                error = ""
            except Exception as exc:
                game_name, media = "", []
                error = str(exc)

            def finish():
                if not self.winfo_exists():
                    return
                self._set_busy(False)
                if error:
                    self._status.configure(text=error)
                    return
                self._media = media
                for item in media:
                    self._media_list.insert(tk.END, item.title)
                self._download_button.configure(
                    state="normal" if media else "disabled"
                )
                self._status.configure(
                    text=f"{game_name}: {len(media)} unterstützte Medien gefunden."
                    if media else f"{game_name}: keine unterstützten Medien gefunden."
                )

            self._dispatch(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _download(self):
        if self._busy:
            return
        selected = list(self._media_list.curselection())
        if not selected:
            self._status.configure(text="Bitte mindestens ein Medium auswählen.")
            return
        media = [self._media[index] for index in selected]
        self._cancel_event.clear()
        self._set_busy(True)
        self._status.configure(text=f"{len(media)} Medium/Medien werden geladen …")

        def progress(completed: int, total: int):
            def update():
                if self.winfo_exists():
                    size = f"{completed / 1024:.0f} KiB"
                    if total:
                        size += f" / {total / 1024:.0f} KiB"
                    self._status.configure(text=f"Medium wird geladen: {size}")

            self._dispatch(update)

        def worker():
            paths: list[str] = []
            errors: list[str] = []
            for item in media:
                if self._cancel_event.is_set():
                    break
                try:
                    path = self.service.download_media(
                        item,
                        cancel_flag=self._cancel_event.is_set,
                        progress_callback=progress,
                    )
                    if path:
                        paths.append(path)
                except Exception as exc:
                    errors.append(str(exc))

            def finish():
                if not self.winfo_exists():
                    return
                self._set_busy(False)
                if paths:
                    self.on_media_ready(paths)
                if errors:
                    self._status.configure(
                        text=f"{len(paths)} Medium/Medien geladen; Fehler: {errors[0]}"
                    )
                elif self._cancel_event.is_set():
                    self._status.configure(
                        text=f"Abgebrochen. {len(paths)} Medium/Medien übernommen."
                    )
                else:
                    self._status.configure(
                        text=f"Fertig: {len(paths)} Medium/Medien übernommen."
                    )

            self._dispatch(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _cancel(self):
        if self._busy:
            self._cancel_event.set()
            self._cancel_button.configure(state="disabled", text="Abbruch läuft …")
            self._status.configure(text="Abbruch angefordert …")

    def _close(self):
        if self._busy:
            self._cancel()
            return
        self.destroy()

    def _dispatch(self, callback: Callable[[], None]):
        try:
            self.after(0, callback)
        except tk.TclError:
            pass
