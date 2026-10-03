"""Select Batocera systems before importing their scraped videos."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

import customtkinter as ctk

from src.engine.media_sources.batocera_smb import (
    BatoceraConnectionConfig,
    BatoceraSmbMediaService,
)
from src.ui.i18n import localize_widget_tree, tr


class BatoceraSystemDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        config: BatoceraConnectionConfig,
        on_import: Callable[[list[str], bool, bool], None],
        service: BatoceraSmbMediaService | None = None,
    ):
        super().__init__(parent)
        self.title(tr("Batocera-Systeme auswählen"))
        self.geometry("440x570")
        self.minsize(360, 360)
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.config = config
        self.on_import = on_import
        self.service = service or BatoceraSmbMediaService()
        self._cancel_event = threading.Event()
        self._loading = True
        self._systems: list[str] = []
        self._type_search = ""
        self._type_search_job = None
        self.protocol("WM_DELETE_WINDOW", self._close)

        ctk.CTkLabel(
            self,
            text=tr("Welche Batocera-Systeme importieren?"),
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        ctk.CTkLabel(
            self,
            text=tr(
                "Es werden zuerst nur die Systemordner unter „roms“ aufgelistet. "
                "Nur ausgewählte Systeme und darin gescrapte Medien werden importiert. "
                "Tippe einen Anfangsbuchstaben, um direkt dorthin zu springen."
            ),
            wraplength=400,
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

        list_frame = ctk.CTkFrame(self, fg_color="transparent")
        list_frame.grid(row=2, column=0, padx=16, pady=4, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        self._list = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            exportselection=False,
            background="#12121f",
            foreground="#ddddee",
            selectbackground="#1e3a5f",
            selectforeground="#ffffff",
            highlightthickness=0,
        )
        self._list.grid(row=0, column=0, sticky="nsew")
        self._list.bind("<KeyPress>", self._on_type_search, add="+")
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self._list.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._list.configure(yscrollcommand=scrollbar.set)

        self._include_videos = ctk.BooleanVar(value=True)
        self._include_images = ctk.BooleanVar(value=True)
        media_options = ctk.CTkFrame(self, fg_color="transparent")
        media_options.grid(row=3, column=0, padx=16, pady=(8, 2), sticky="ew")
        ctk.CTkCheckBox(
            media_options,
            text="Videos und GIFs",
            variable=self._include_videos,
        ).pack(anchor="w", pady=3)
        ctk.CTkCheckBox(
            media_options,
            text="Artwork (Cover, Marquee, Fanart, Thumbnail)",
            variable=self._include_images,
        ).pack(anchor="w", pady=3)

        self._status = ctk.CTkLabel(
            self,             text=tr("Verbinde und lese Systemordner …"), anchor="w", wraplength=400
        )
        self._status.grid(row=4, column=0, padx=16, pady=6, sticky="ew")
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=5, column=0, padx=16, pady=(4, 16), sticky="ew")
        buttons.grid_columnconfigure((0, 1, 2), weight=1)
        self._select_all = ctk.CTkButton(
            buttons, text="Alle auswählen", command=self._select_everything,
            state="disabled", fg_color="#3a3a4a", hover_color="#55556a",
        )
        self._select_all.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self._import_button = ctk.CTkButton(
            buttons,
            text="Auswahl importieren",
            command=self._submit,
            state="disabled",
        )
        self._import_button.grid(row=0, column=1, padx=5, sticky="ew")
        self._cancel_button = ctk.CTkButton(
            buttons,
            text="Abbrechen",
            command=self._close,
            fg_color="#4a1a1a",
            hover_color="#7b241c",
        )
        self._cancel_button.grid(row=0, column=2, padx=(5, 0), sticky="ew")

        localize_widget_tree(self)
        threading.Thread(target=self._load_systems, daemon=True).start()

    def _load_systems(self):
        error = ""
        try:
            systems = self.service.list_systems(
                self.config,
                cancel_flag=self._cancel_event.is_set,
                progress_callback=self._loading_progress,
            )
        except Exception as exc:
            systems = []
            error = str(exc)

        def finish():
            if not self.winfo_exists():
                return
            self._loading = False
            self._cancel_button.configure(text="Schließen")
            if error:
                self._status.configure(
                    text=tr("Systemliste konnte nicht geladen werden: {error}").format(error=error)
                )
                return
            if self._cancel_event.is_set():
                self._status.configure(text="Systemsuche abgebrochen.")
                return
            self._systems = systems
            for system in systems:
                self._list.insert(tk.END, system)
            if systems:
                self._status.configure(
                    text=tr("{count} Systeme gefunden. Wähle ein oder mehrere aus.").format(
                        count=len(systems)
                    )
                )
                self._select_all.configure(state="normal")
                self._import_button.configure(state="normal")
            else:
                self._status.configure(
                    text=tr("Keine Systemordner im Batocera-Share „roms“ gefunden.")
                )

        self._dispatch(finish)

    def _loading_progress(self, count: int, _total: int):
        self._dispatch(
            lambda: self._status.configure(
                text=tr("Systemordner werden gelesen … {count} gefunden").format(count=count)
            )
        )

    def _select_everything(self):
        self._list.selection_set(0, tk.END)

    @staticmethod
    def _find_system_prefix(
        systems: list[str], prefix: str, start: int = 0
    ) -> int | None:
        if not systems or not prefix:
            return None
        for offset in range(len(systems)):
            index = (start + offset) % len(systems)
            if systems[index].casefold().startswith(prefix.casefold()):
                return index
        return None

    def _on_type_search(self, event):
        if (
            len(event.char) != 1
            or not event.char.isprintable()
            or event.state & 0x4
            or event.state & 0x8
        ):
            return
        char = event.char.casefold()
        repeated = self._type_search == char
        self._type_search = char if repeated else self._type_search + char
        if self._type_search_job:
            self.after_cancel(self._type_search_job)
        self._type_search_job = self.after(900, self._clear_type_search)

        active = self._list.index(tk.ACTIVE) if self._systems else -1
        start = (active + 1) % len(self._systems) if repeated and active >= 0 else 0
        match = self._find_system_prefix(self._systems, self._type_search, start)
        if match is None and not repeated and len(self._type_search) > 1:
            self._type_search = char
            match = self._find_system_prefix(self._systems, char)
        if match is not None:
            self._list.activate(match)
            self._list.see(match)
        return "break"

    def _clear_type_search(self):
        self._type_search = ""
        self._type_search_job = None

    def _submit(self):
        if self._loading:
            return
        selected = [self._systems[index] for index in self._list.curselection()]
        if not selected:
            self._status.configure(text=tr("Bitte mindestens ein System auswählen."))
            return
        if not self._include_videos.get() and not self._include_images.get():
            self._status.configure(text=tr("Bitte Videos/GIFs und/oder Artwork auswählen."))
            return
        include_videos = self._include_videos.get()
        include_images = self._include_images.get()
        self.destroy()
        self.on_import(selected, include_videos, include_images)

    def _close(self):
        if self._loading:
            self._cancel_event.set()
            self._cancel_button.configure(state="disabled", text="Abbruch läuft …")
            self._status.configure(text="Abbruch der Systemsuche angefordert …")
            return
        self.destroy()

    def _dispatch(self, callback: Callable[[], None]):
        try:
            self.after(0, callback)
        except tk.TclError:
            pass
