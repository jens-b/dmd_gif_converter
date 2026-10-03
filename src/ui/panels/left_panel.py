import os
import re
import sys
import glob
import logging
import shutil
import threading
import tempfile
import subprocess
from pathlib import Path
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
from smbprotocol.exceptions import SMBException

from src.engine.conversion.core import (
    get_metadata, process_file, process_folder,
    DEFAULT_PARAMS, SUPPORTED_EXTENSIONS,
)
from src.engine.auto_action.main import AutoActionConfig, preprocess_video_for_dmd
from src.engine.conversion.colorimetry import analyze_and_compensate as _ui_analyze_color
from src.engine.conversion.services.gif_search_service import (
    GifSearchService, GifSearchFilter, GIF_SEARCH_AVAILABLE,
)
from src.engine.conversion.services.launchbox_artwork_service import LaunchBoxArtworkService
from src.engine.media_sources.batocera_smb import (
    BatoceraConnectionConfig,
    BatoceraSmbMediaService,
)
from src.ui.dialogs.batocera_connection_dialog import BatoceraConnectionDialog
from src.ui.dialogs.batocera_system_dialog import BatoceraSystemDialog
from src.ui.dialogs.screenscraper_search_dialog import ScreenScraperSearchDialog
from src.ui.widgets import _InfoBadge
from src.ui.constants import *
from src.ui.i18n import localize_widget_tree, tr
from src.ui.dmd_led_sim import LED_SIM_SCALE, LED_SIM_GAP, LED_SIM_MAX_W, apply_led_grid as _apply_led_grid
from src.ui.events.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)

_gif_search_available = GIF_SEARCH_AVAILABLE  # backward-compat alias
_QUEUE_STATUS_LABELS = {
    "idle": "Wartend",
    "converting": "Wird konvertiert",
    "done": "Fertig",
    "error": "Fehler",
}
_SEARCH_RATIO_LABELS = {
    "Alle": "All",
    "Querformat": "Landscape",
    "Hochformat": "Portrait",
    "Quadratisch": "Square",
}


class LeftPanel(ctk.CTkFrame):
    def __init__(self, parent, app_state, **kwargs):
        super().__init__(parent, width=295, corner_radius=0, **kwargs)
        self.app_state = app_state
        self._file_data = {}
        self._file_paths = set()
        self._queue_filter = tk.StringVar(value="Alle Medien")
        self._per_gif_configs = {}
        self._selected_iid = ""
        self._gif_tmpdirs = []
        self._download_active = False
        self._download_cancel = False
        self._launchbox_service = None
        self._batocera_import_active = False
        self._last_source_folder = ""
        self._adv_refresh_job = None
        self._restoring_params = False
        self._busy = False
        self._build_ui()
        # Listen for files added from other panels (e.g. AI Moments)
        EventBus.subscribe(EventType.FILES_ADDED_TO_QUEUE, self._on_files_added_to_queue)

    def _on_files_added_to_queue(self, payload):
        """Receives a list of paths and inserts them into the conversion queue."""
        files = payload if isinstance(payload, list) else []
        if files:
            self.after(0, lambda: self._batch_insert(files, 0))

    def _build_ui(self):
        lp = self
        lp.grid_propagate(False)
        lp.grid_rowconfigure(4, weight=1)
        lp.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(lp, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=10, pady=(12, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hdr, text="1️⃣ 📁  Quelldateien",
            font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        self._count_lbl = ctk.CTkLabel(
            hdr, text="leer", text_color="#666688", font=ctk.CTkFont(size=11)
        )
        self._count_lbl.grid(row=0, column=1, sticky="e")

        br = ctk.CTkFrame(lp, fg_color="transparent")
        br.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
        br.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(br, text="➕ Dateien", command=self.add_files, height=30).grid(
            row=0, column=0, padx=2, sticky="ew")
        ctk.CTkButton(br, text="📂 Ordner",  command=self.add_folder, height=30).grid(
            row=0, column=1, padx=2, sticky="ew")
        ctk.CTkButton(br, text="✕ Entfernen", command=self._remove_selected,
                      height=30, fg_color="#3a3a4a", hover_color="#7b241c").grid(
            row=0, column=2, padx=2, sticky="ew")

        self._btn_refresh_folder = ctk.CTkButton(
            br, text="🔄 Ordner neu einlesen", command=self.refresh_folder,
            height=28, fg_color="#1a3a1a", hover_color="#2a5a2a",
            font=ctk.CTkFont(size=11), state="disabled"
        )
        self._btn_refresh_folder.grid(
            row=1, column=0, columnspan=3, padx=2, pady=(3, 0), sticky="ew"
        )
        ctk.CTkButton(
            br, text="🎮  LaunchBox-Logos (PNG) laden", command=self._open_launchbox_dialog,
            height=28, fg_color="#3a2b55", hover_color="#564078",
            font=ctk.CTkFont(size=11),
        ).grid(row=2, column=0, columnspan=3, padx=2, pady=(3, 0), sticky="ew")
        ctk.CTkButton(
            br, text="🌐  ScreenScraper-Medien suchen",
            command=self._open_screenscraper_dialog, height=28,
            fg_color="#24506b", hover_color="#2d6687",
            font=ctk.CTkFont(size=11),
        ).grid(row=3, column=0, columnspan=3, padx=2, pady=(3, 0), sticky="ew")
        ctk.CTkButton(
            br, text="🕹  Batocera-Medien importieren",
            command=self._open_batocera_import_dialog, height=28,
            fg_color="#234a3d", hover_color="#30644f",
            font=ctk.CTkFont(size=11),
        ).grid(row=4, column=0, columnspan=3, padx=2, pady=(3, 0), sticky="ew")

        # ── GIF Search section ────────────────────────────────────────────────
        self._build_search_section(lp)

        self._style_treeview()
        tree_host = tk.Frame(lp, bg="#12121f")
        tree_host.grid(row=4, column=0, padx=6, pady=4, sticky="nsew")
        tree_host.grid_rowconfigure(1, weight=1)
        tree_host.grid_columnconfigure(0, weight=1)

        self._queue_filter_menu = ctk.CTkOptionMenu(
            tree_host,
            variable=self._queue_filter,
            values=["Alle Medien", "Videos/GIFs", "Bilder"],
            command=self._apply_queue_filter,
            height=26,
        )
        self._queue_filter_menu.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        self._tree = ttk.Treeview(
            tree_host, style="File.Treeview",
            columns=("Duration", "Status"),
            show="tree headings", selectmode="extended"
        )
        self._tree.heading("#0", text="Quelle", anchor="w")
        self._tree.heading("Duration", text="Dauer", anchor="w")
        self._tree.heading("Status", text="Status", anchor="w")
        
        self._tree.column("#0", width=140, stretch=True)
        self._tree.column("Duration", width=60, stretch=False)
        self._tree.column("Status", width=60, stretch=False)
        sb = ttk.Scrollbar(tree_host, orient="vertical",
                           command=self._tree.yview, style="File.Vertical.TScrollbar")
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.grid(row=1, column=0, sticky="nsew")
        sb.grid(row=1, column=1, sticky="ns")

        self._tree.tag_configure("idle",       foreground="#aaaacc")
        self._tree.tag_configure("converting", foreground="#f39c12")
        self._tree.tag_configure("done",       foreground="#2ecc71")
        self._tree.tag_configure("error",      foreground="#e74c3c")

        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<Delete>",           lambda _e: self._remove_selected())
        self._tree.bind("<BackSpace>",        lambda _e: self._remove_selected())

        ctk.CTkLabel(
            lp,
            text="Klick: Vorschau · Strg/Umschalt: Mehrfachauswahl\nMehrere markiert? → Alle werden mit „Ausgewählte Datei(en) konvertieren“ umgewandelt · Entf: Auswahl entfernen",
            text_color="#444466",
            font=ctk.CTkFont(size=10),
            justify="left",
            wraplength=270,
        ).grid(row=5, column=0, padx=8, pady=(0, 2), sticky="w")

        bot = ctk.CTkFrame(lp, fg_color="transparent")
        bot.grid(row=6, column=0, padx=6, pady=6, sticky="ew")
        bot.grid_columnconfigure(0, weight=1)

        # Output folder moved to middle panel

        ctk.CTkButton(
            bot, text="🗑  Quelldateien leeren", command=self.clear_files,
            fg_color="#3a3a4a", hover_color="#7b241c", height=28
        ).grid(row=2, column=0, columnspan=2, padx=4, pady=(8, 2), sticky="ew")

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_lbl = ctk.CTkLabel(
            lp, text="Bereit", text_color="#556677", font=ctk.CTkFont(size=10)
        )
        self._status_lbl.grid(row=7, column=0, padx=8, pady=(0, 2), sticky="w")

        self._progress = ctk.CTkProgressBar(lp, height=6)
        self._progress.set(0)
        self._progress.grid(row=8, column=0, padx=8, pady=(0, 6), sticky="ew")

        # Hidden trim placeholder (used by preview/remove logic)
        self._trim_frame = ctk.CTkFrame(lp, fg_color="transparent", height=0)
        # kept hidden — real trim controls live in PreviewPanel

    def _build_search_section(self, parent):
        """Compact GIF-search panel inserted between the file buttons and the tree."""
        sf = ctk.CTkFrame(parent, fg_color="#0d1a2a", corner_radius=6)
        sf.grid(row=3, column=0, padx=8, pady=(0, 4), sticky="ew")
        sf.grid_columnconfigure(0, weight=1)

        # Header row
        head = ctk.CTkFrame(sf, fg_color="transparent")
        head.grid(row=0, column=0, padx=8, pady=(6, 2), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head, text="🔍  GIF-Suche",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#5ba3d9"
        ).grid(row=0, column=0, sticky="w")

        # Search bar row: [keyword entry] [qty entry] [Download btn]
        sr = ctk.CTkFrame(sf, fg_color="transparent")
        sr.grid(row=1, column=0, padx=8, pady=2, sticky="ew")
        sr.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            sr, textvariable=self.app_state.v_search_keyword,
            placeholder_text="Suchbegriff …", height=28
        )
        self._search_entry.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self._search_entry.bind("<Return>", lambda _e: self._search_and_download())

        # Quantity entry (clamped to 1-300)
        qty_frame = ctk.CTkFrame(sr, fg_color="transparent")
        qty_frame.grid(row=0, column=1, padx=(0, 4))
        ctk.CTkLabel(qty_frame, text="Anz.", font=ctk.CTkFont(size=11),
                     text_color="#888899").pack(side="left")
        self._qty_entry = ctk.CTkEntry(
            qty_frame, textvariable=self.app_state.v_search_qty,
            width=52, height=28, justify="center"
        )
        self._qty_entry.pack(side="left")

        self._btn_search = ctk.CTkButton(
            sr, text="Suchen", width=64, height=28,
            fg_color="#1a4f6e", hover_color="#1a618d",
            command=self._search_and_download,
            state="normal" if _gif_search_available else "disabled"
        )
        self._btn_search.grid(row=0, column=2, padx=(0, 2))
        # Filters toggle
        self._filters_visible = False
        self._btn_toggle_filters = ctk.CTkButton(
            sf, text="▼ Filter und Suchquelle", height=24,
            fg_color="transparent", hover_color="#2a2a3e",
            text_color="#888899", anchor="w",
            command=self._toggle_search_filters
        )
        self._btn_toggle_filters.grid(row=2, column=0, padx=8, pady=(0, 2), sticky="ew")

        # Filters frame
        self._filters_frame = ctk.CTkFrame(sf, fg_color="transparent")
        # Hidden by default, will grid at row=3 when toggled
        
        # Engine
        ctk.CTkLabel(
            self._filters_frame, text="Suchquelle",
            font=ctk.CTkFont(size=11), text_color="#888899",
        ).pack(anchor="w", pady=(0, 2))
        self._engine_menu = ctk.CTkOptionMenu(
            self._filters_frame, variable=self.app_state.v_search_engine,
            values=["DuckDuckGo", "Tenor 🔒", "Giphy 🔒"], height=24
        )
        self._engine_menu.pack(fill="x", pady=(0, 4))
        
        # Dimensions & Layout
        dim_f = ctk.CTkFrame(self._filters_frame, fg_color="transparent")
        dim_f.pack(fill="x")
        
        ctk.CTkLabel(dim_f, text="Min.:", font=ctk.CTkFont(size=11), text_color="#888899").pack(side="left", padx=(0, 4))
        
        self._min_w_entry = ctk.CTkEntry(dim_f, textvariable=self.app_state.v_search_min_w, width=40, height=24)
        self._min_w_entry.pack(side="left")
        
        ctk.CTkLabel(dim_f, text="x", font=ctk.CTkFont(size=11), text_color="#888899").pack(side="left", padx=(2, 2))
        
        self._min_h_entry = ctk.CTkEntry(dim_f, textvariable=self.app_state.v_search_min_h, width=40, height=24)
        self._min_h_entry.pack(side="left", padx=(0, 4))
        
        self._ratio_menu = ctk.CTkOptionMenu(
            dim_f,
            variable=tk.StringVar(value="Alle"),
            values=list(_SEARCH_RATIO_LABELS),
            command=self._on_search_ratio_selected,
            width=100,
            height=24,
        )
        self._ratio_menu.pack(side="left", fill="x", expand=True)

        # Cancel button (hidden by default)
        self._btn_cancel_dl = ctk.CTkButton(
            sf, text="✕ Abbrechen", height=24,
            fg_color="#4a1a1a", hover_color="#7b241c",
            font=ctk.CTkFont(size=11),
            command=self._cancel_download
        )
        # Not shown until a download starts

        # Status label
        self._search_status = ctk.CTkLabel(
            sf, text="" if _gif_search_available else "⚠ Suchpakete fehlen; siehe Hinweise beim Suchen",
            text_color="#556677", font=ctk.CTkFont(size=10)
        )
        self._search_status.grid(row=5, column=0, padx=8, pady=(2, 6), sticky="w")

    def _toggle_search_filters(self):
        if self._filters_visible:
            self._filters_frame.grid_remove()
            self._btn_toggle_filters.configure(text=tr("▼ Filter und Suchquelle"))
            self._filters_visible = False
        else:
            self._filters_frame.grid(row=3, column=0, padx=8, pady=2, sticky="ew")
            self._btn_toggle_filters.configure(text=tr("▲ Filter ausblenden"))
            self._filters_visible = True

    def _on_search_ratio_selected(self, label: str):
        self.app_state.v_search_ratio.set(_SEARCH_RATIO_LABELS.get(label, "All"))

    def _search_and_download(self):
        """Validate inputs and launch the download thread."""
        if not _gif_search_available:
            messagebox.showerror(
                "Fehlende Pakete",
                "Die GIF-Suche benötigt zusätzliche Python-Pakete.\n\n"
                "Installiere sie mit:\n  pip install ddgs requests\n\n"
                "Oder starte ./launch_ui.sh erneut; fehlende Pakete werden installiert."
            )
            return

        keyword = self.app_state.v_search_keyword.get().strip()
        if not keyword:
            messagebox.showwarning("GIF-Suche", "Bitte gib einen Suchbegriff ein.")
            self._search_entry.focus_set()
            return

        try:
            qty = int(self.app_state.v_search_qty.get())
            if qty < 1:
                qty = 1
            if qty > 300:
                qty = 300
            self.app_state.v_search_qty.set(qty)
        except (ValueError, tk.TclError):
            messagebox.showwarning("GIF-Suche", "Die Anzahl muss eine Zahl zwischen 1 und 300 sein.")
            self._qty_entry.focus_set()
            return
            
        engine_full = self.app_state.v_search_engine.get()
        engine = engine_full.split()[0]  # Remove 🔒 if present
        
        if engine == "Tenor" and not self.app_state.v_action_tenor_api_key.get().strip():
            messagebox.showerror(
                "🔑 API-Schlüssel erforderlich",
                "Für Tenor wird ein API-Schlüssel benötigt.\n\n"
                "Trage ihn rechts im Bereich „Einstellungen“ unter "
                "„Such-API-Schlüssel“ ein.",
            )
            return
        if engine == "Giphy" and not self.app_state.v_action_giphy_api_key.get().strip():
            messagebox.showerror(
                "🔑 API-Schlüssel erforderlich",
                "Für Giphy wird ein API-Schlüssel benötigt.\n\n"
                "Trage ihn rechts im Bereich „Einstellungen“ unter "
                "„Such-API-Schlüssel“ ein.",
            )
            return
            
        try:
            min_w = int(self.app_state.v_search_min_w.get()) if self.app_state.v_search_min_w.get().strip() else 0
            min_h = int(self.app_state.v_search_min_h.get()) if self.app_state.v_search_min_h.get().strip() else 0
        except ValueError:
            min_w, min_h = 0, 0
            
        ratio = self.app_state.v_search_ratio.get()

        if self._download_active:
            messagebox.showwarning("Bitte warten", "Ein Download läuft bereits.")
            return

        # Create a dedicated temp dir for this search
        tmpdir = tempfile.mkdtemp(prefix="dmd_gifsearch_")
        self._gif_tmpdirs.append(tmpdir)

        self._download_active = True
        self._download_cancel = False

        # UI feedback
        self._btn_search.configure(state="disabled", text="⏳…")
        self._btn_cancel_dl.grid(row=4, column=0, padx=8, pady=(0, 2), sticky="ew")
        self._search_status.configure(
            text=f"🔍 Suche nach „{keyword}“ …", text_color="#5ba3d9"
        )
        self._progress.set(0)
        self._status_lbl.configure(text="⬇  GIFs werden geladen …")
        self._log(f"🔍  GIF-Suche: „{keyword}“ × {qty}  →  {tmpdir}")

        threading.Thread(
            target=self._run_download,
            args=(keyword, qty, tmpdir, engine, min_w, min_h, ratio),
            daemon=True
        ).start()

    def _open_batocera_import_dialog(self):
        """Configure a direct Batocera SMB connection and import scraped media."""
        if self._batocera_import_active:
            messagebox.showwarning(
                "Batocera-Import", "Ein Batocera-Import läuft bereits."
            )
            return

        BatoceraConnectionDialog(
            self.winfo_toplevel(),
            on_connect=self._start_batocera_import,
        )

    def _open_screenscraper_dialog(self):
        """Search ScreenScraper by game title and add selected media to the source file list."""
        def add_media(paths: list[str]):
            self._batch_insert(paths, 0)
            self._log(
                f"ScreenScraper: {len(paths)} Medium/Medien zu den Quelldateien hinzugefügt."
            )

        ScreenScraperSearchDialog(
            self.winfo_toplevel(),
            on_media_ready=add_media,
        )

    def _start_batocera_import(self, config: BatoceraConnectionConfig):
        """Load the shallow Batocera system list, then import only selected systems."""
        BatoceraSystemDialog(
            self.winfo_toplevel(),
            config,
            on_import=lambda systems, include_videos, include_images: (
                self._run_batocera_import(
                    config, systems, include_videos, include_images
                )
            ),
        )

    def _run_batocera_import(
        self,
        config: BatoceraConnectionConfig,
        systems: list[str],
        include_videos: bool,
        include_images: bool,
    ):
        dialog = ctk.CTkToplevel(self)
        dialog.title(tr("Batocera-Medien importieren"))
        dialog.geometry("540x280")
        dialog.transient(self.winfo_toplevel())
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text=tr("Selected systems ({count}) will be read; found media is copied to the local cache.").format(
                count=len(systems)
            ),
            wraplength=450,
            justify="left",
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        status = ctk.CTkLabel(
            dialog, text=tr("Import wird vorbereitet …"), anchor="w", wraplength=500
        )
        status.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=16, pady=(8, 16), sticky="ew")
        buttons.grid_columnconfigure((0, 1), weight=1)

        cancel_event = threading.Event()
        self._batocera_import_active = True

        def close_dialog():
            if self._batocera_import_active:
                cancel_event.set()
                status.configure(text=tr("Abbruch angefordert; laufende Datei wird noch beendet …"))
            else:
                dialog.destroy()

        cancel_button = ctk.CTkButton(
            buttons,
            text="Abbrechen",
            fg_color="#4a1a1a",
            hover_color="#7b241c",
            command=close_dialog,
        )
        cancel_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        close_button = ctk.CTkButton(
            buttons,
            text="Schließen",
            fg_color="#3a3a4a",
            hover_color="#55556a",
            command=dialog.destroy,
            state="disabled",
        )
        close_button.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        localize_widget_tree(dialog)

        def progress(current: int, total: int, path: str):
            try:
                text = tr("System {current}/{total}: {path} — reading game list …").format(
                    current=current, total=total, path=path
                )
                dialog.after(
                    0,
                    lambda: (status.configure(text=text), localize_widget_tree(status)),
                )
            except tk.TclError:
                pass

        streamed_paths: set[str] = set()

        def media_progress(
            completed: int, total: int, remote_path: str, cached_path: str | None
        ):
            if cached_path:
                select_first = not streamed_paths
                streamed_paths.add(cached_path)

                def add_media(path=cached_path, select=select_first):
                    self._batch_insert([path], 0, select_first=select)

                try:
                    self.after(0, add_media)
                except tk.TclError:
                    pass
            try:
                dialog.after(
                    0,
                    lambda: status.configure(
                        text=tr("{completed} media processed; {loaded} loaded — {filename}").format(
                            completed=completed,
                            loaded=len(streamed_paths),
                            filename=Path(remote_path).name,
                        )
                    ),
                )
            except tk.TclError:
                pass

        def worker():
            result = None
            error = ""
            try:
                result = BatoceraSmbMediaService().import_media(
                    config,
                    systems,
                    include_videos=include_videos,
                    include_images=include_images,
                    cancel_flag=cancel_event.is_set,
                    progress_callback=progress,
                    media_progress_callback=media_progress,
                )
            except (OSError, ValueError, RuntimeError, SMBException) as exc:
                error = f"{type(exc).__name__}: {exc}"

            def finish():
                self._batocera_import_active = False
                if result and result.media_paths:
                    new_paths = [
                        path for path in result.media_paths if path not in streamed_paths
                    ]
                    if new_paths:
                        self._batch_insert(
                            new_paths, 0, select_first=not streamed_paths
                        )
                    self._log(
                        f"Batocera: {len(result.media_paths)} Medium/Medien "
                        "zu den Quelldateien hinzugefügt."
                    )
                if result and result.skipped_media:
                    self._log(
                        f"Batocera: {result.skipped_media} fehlende oder "
                        "nicht unterstützte Medien-Verweise übersprungen.",
                        "warning",
                    )
                if result:
                    self._log(
                        "Batocera-Diagnose: "
                        f"{result.games_seen} Spiele, "
                        f"{result.video_references} Video- und "
                        f"{result.image_references} Bildverweise, "
                        f"{result.unresolved_references} nicht gefunden, "
                        f"{result.unsupported_references} nicht unterstützt."
                    )
                    for system in result.missing_gamelists:
                        self._log(
                            f"Batocera: roms/{system}/gamelist.xml fehlt.",
                            "warning",
                        )
                if error:
                    self._log(f"Batocera-Import fehlgeschlagen: {error}", "error")

                try:
                    if not dialog.winfo_exists():
                        return
                except tk.TclError:
                    return

                if error:
                    status.configure(text=tr("Import failed: {error}").format(error=error))
                elif result and result.cancelled:
                    status.configure(
                        text=tr("Cancelled. {count} file(s) were added.").format(
                            count=len(result.media_paths)
                        )
                    )
                elif result:
                    summary = (
                        tr("Import complete: {count} media found. ").format(
                            count=len(result.media_paths)
                        )
                        if result.media_paths
                        else tr("No media imported. ")
                    )
                    if result.missing_gamelists:
                        summary += tr("No game list for: {systems}. ").format(
                            systems=", ".join(result.missing_gamelists[:5])
                        )
                    elif result.games_seen and not (
                        result.video_references or result.image_references
                    ):
                        summary += tr(
                            "{count} games read, but no <video>/<image>/<marquee>/<fanart> entries were found. "
                        ).format(count=result.games_seen)
                    elif result.unresolved_references:
                        summary += tr(
                            "{count} media path(s) could not be found on the share. "
                        ).format(count=result.unresolved_references)
                    elif not result.games_seen:
                        summary += tr("The game list contains no game entries. ")
                    summary += tr(
                        "Read: {games} games, {videos} video and {images} image references."
                    ).format(
                        games=result.games_seen,
                        videos=result.video_references,
                        images=result.image_references,
                    )
                    status.configure(text=summary)
                else:
                    status.configure(text=tr("Import finished without results."))
                cancel_button.configure(state="disabled", text="Abbrechen")
                close_button.configure(state="normal")

            try:
                self.after(0, finish)
            except tk.TclError:
                self._batocera_import_active = False

        threading.Thread(target=worker, daemon=True).start()

    def _open_launchbox_dialog(self):
        """Open the LaunchBox platform selector and logo download controls."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(tr("LaunchBox-Logos herunterladen"))
        dialog.geometry("520x540")
        dialog.transient(self.winfo_toplevel())
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            dialog,
            text="Lade die Plattformliste, wähle eine oder mehrere Plattformen aus und füge deren Clear Logos als PNG zu den Quelldateien hinzu.",
            wraplength=400,
            justify="left",
        ).grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")

        status = ctk.CTkLabel(
            dialog,
            text="Beim ersten Mal werden die LaunchBox-Metadaten geladen. Danach nutzt die App den lokalen Cache. Bereits geladene Logos werden übersprungen.",
            wraplength=400,
            justify="left",
        )
        status.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        list_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        list_frame.grid(row=2, column=0, padx=16, pady=4, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        platform_list = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            exportselection=False,
            background="#12121f",
            foreground="#aaaacc",
            selectbackground="#1e3a5f",
            selectforeground="#ffffff",
            highlightthickness=0,
        )
        platform_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=platform_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        platform_list.configure(yscrollcommand=scrollbar.set)

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.grid(row=3, column=0, padx=16, pady=8, sticky="ew")
        buttons.grid_columnconfigure((0, 1, 2), weight=1)
        load_button = ctk.CTkButton(buttons, text="Plattformen laden", height=32)
        load_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        download_button = ctk.CTkButton(
            buttons, text="Auswahl herunterladen", height=32,
            fg_color="#1a4f6e", hover_color="#1a618d",
            state="disabled",
        )
        download_button.grid(row=0, column=1, padx=4, sticky="ew")
        cancel_button = ctk.CTkButton(
            buttons, text="Abbrechen", height=32,
            fg_color="#4a1a1a", hover_color="#7b241c",
            state="disabled",
        )
        cancel_button.grid(row=0, column=2, padx=(4, 0), sticky="ew")
        ctk.CTkButton(
            dialog, text="Schließen", command=dialog.destroy, height=28,
            fg_color="#3a3a4a", hover_color="#55556a",
        ).grid(row=4, column=0, padx=16, pady=(0, 14), sticky="e")

        localize_widget_tree(dialog)

        service = LaunchBoxArtworkService()
        self._launchbox_service = service
        platforms_loaded = False
        busy = False
        cancel_event = threading.Event()

        def cancel_operation():
            if busy:
                cancel_event.set()
                cancel_button.configure(state="disabled", text="Abbruch läuft …")
                update_status("Abbruch angefordert. Laufende Netzwerkzugriffe werden beendet …")

        def update_status(text):
            try:
                if dialog.winfo_exists():
                    status.configure(text=text)
            except tk.TclError:
                pass

        def load_platforms():
            nonlocal busy, platforms_loaded
            if busy:
                return
            busy = True
            cancel_event.clear()
            load_button.configure(state="disabled", text="Lade …")
            download_button.configure(state="disabled")
            cancel_button.configure(state="normal", text="Abbrechen")
            status.configure(text="LaunchBox-Plattformliste wird aus dem lokalen Metadatenarchiv gelesen …")

            def worker():
                try:
                    platforms = service.get_platforms(cancel_flag=cancel_event.is_set)
                    error = ""
                except Exception as exc:
                    platforms = []
                    error = str(exc)

                def finish():
                    nonlocal busy, platforms_loaded
                    busy = False
                    try:
                        if not dialog.winfo_exists():
                            return
                    except tk.TclError:
                        return
                    cancel_button.configure(state="disabled", text="Abbrechen")
                    load_button.configure(
                        state="normal",
                        text="Plattformen aktualisieren" if not error else "Plattformen laden",
                    )
                    if error:
                        if cancel_event.is_set():
                            update_status("Einlesen der Plattformliste abgebrochen.")
                        else:
                            update_status(f"Plattformen konnten nicht geladen werden: {error}")
                            self._log(f"LaunchBox-Plattformliste fehlgeschlagen: {error}", "error")
                        return
                    platform_list.delete(0, tk.END)
                    for platform in platforms:
                        platform_list.insert(tk.END, platform)
                    platforms_loaded = True
                    download_button.configure(state="normal" if platforms else "disabled")
                    update_status(f"{len(platforms)} Plattform(en) geladen.")

                try:
                    self.after(0, finish)
                except tk.TclError:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        def download_selected():
            nonlocal busy
            if busy:
                return
            selected_indices = platform_list.curselection()
            selected_platforms = [platform_list.get(index) for index in selected_indices]
            if not selected_platforms:
                messagebox.showwarning(
                    "LaunchBox", "Bitte wähle mindestens eine Plattform aus.",
                    parent=dialog,
                )
                return

            busy = True
            cancel_event.clear()
            load_button.configure(state="disabled")
            download_button.configure(state="disabled", text="Lade herunter …")
            cancel_button.configure(state="normal", text="Abbrechen")
            update_status(
                f"Clear Logos für {len(selected_platforms)} Plattform(en) werden in der XML gesucht …"
            )

            def progress(current, total):
                try:
                    dialog.after(
                        0, lambda: update_status(f"Logos werden geladen … {current}/{total}")
                    )
                except tk.TclError:
                    pass

            def worker():
                try:
                    paths, errors = service.download_logos(
                        selected_platforms,
                        cancel_flag=cancel_event.is_set,
                        progress_callback=progress,
                    )
                    error = ""
                except Exception as exc:
                    paths, errors = [], []
                    error = str(exc)

                def finish():
                    nonlocal busy
                    busy = False
                    if paths:
                        self._batch_insert(paths, 0)
                        self._update_count()
                        self._log(f"LaunchBox: {len(paths)} Clear-Logo-PNG(s) zu den Quelldateien hinzugefügt.")
                    if errors:
                        for item in errors:
                            self._log(f"LaunchBox-Logo konnte nicht geladen werden: {item}", "error")
                    try:
                        if not dialog.winfo_exists():
                            return
                    except tk.TclError:
                        return
                    load_button.configure(state="normal")
                    cancel_button.configure(state="disabled", text="Abbrechen")
                    download_button.configure(
                        state="normal" if platforms_loaded else "disabled",
                        text="Auswahl herunterladen",
                    )
                    if error:
                        if cancel_event.is_set():
                            update_status(f"Vorgang abgebrochen. {len(paths)} Logo(s) wurden geladen.")
                        else:
                            update_status(f"LaunchBox-Download fehlgeschlagen: {error}")
                            self._log(f"LaunchBox-Download fehlgeschlagen: {error}", "error")
                    else:
                        summary = f"{len(paths)} Logo(s) geladen."
                        if errors:
                            summary += f" {len(errors)} fehlgeschlagen; Details stehen im Protokoll."
                        if cancel_event.is_set():
                            summary += " Vorgang abgebrochen."
                        update_status(summary)

                try:
                    self.after(0, finish)
                except tk.TclError:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        load_button.configure(command=load_platforms)
        download_button.configure(command=download_selected)
        cancel_button.configure(command=cancel_operation)

    def _run_download(self, keyword: str, qty: int, tmpdir: str, engine: str, min_w: int, min_h: int, ratio: str):
        """Background thread: delegate search + download to :class:`GifSearchService`."""
        downloaded = 0
        errors = 0

        def _ui(fn):
            self.after(0, fn)

        api_key = ""
        if engine == "Tenor":
            api_key = self.app_state.v_action_tenor_api_key.get().strip()
        elif engine == "Giphy":
            api_key = self.app_state.v_action_giphy_api_key.get().strip()

        service = GifSearchService()
        filters = GifSearchFilter(min_width=min_w, min_height=min_h, ratio=ratio)

        try:
            _ui(lambda: self._search_status.configure(
                text=f"🔍 Suche bei {engine} …", text_color="#5ba3d9"
            ))
            results = service.search(
                keyword, qty, engine, filters,
                api_key=api_key,
                cancel_flag=lambda: self._download_cancel,
            )
        except Exception as exc:
            logger.warning("Search failed: %s", exc)
            _err = str(exc)
            _ui(lambda: self._on_download_done(keyword, 0, 0, qty, error=f"Search failed: {_err}"))
            return

        if not results:
            _ui(lambda: self._on_download_done(
                keyword, 0, 0, qty, error=f"Keine GIFs für „{keyword}“ gefunden."
            ))
            return

        total = len(results)
        _ui(lambda: self._log(f"   {total} Treffer gefunden — Download läuft …"))

        for i, result in enumerate(results):
            if self._download_cancel:
                break

            try:
                file_path = service.download(
                    result, tmpdir, i, keyword,
                    cancel_flag=lambda: self._download_cancel,
                )
            except Exception as exc:
                errors += 1
                logger.warning("Download error: %s", exc)
                _ui(lambda e=str(exc): self._log(f"   ⚠ Downloadfehler: {e[:80]}", "error"))
                continue

            if file_path is None:
                if not self._download_cancel:
                    errors += 1  # skipped (non-image content-type)
                continue

            downloaded += 1
            _fp = file_path
            _ui(lambda p=_fp: self._add_downloaded_gif(p))
            prog = downloaded / total
            _ui(lambda v=prog: self._progress.set(v))
            _ui(lambda d=downloaded, t=total: self._search_status.configure(
                text=f"⬇ {d}/{t} downloaded…", text_color="#5ba3d9"
            ))


        _ui(lambda: self._on_download_done(keyword, downloaded, errors, total))

    def _add_downloaded_gif(self, path: str):
        """Main thread: add a freshly downloaded GIF to the file list."""
        if not os.path.isfile(path):
            return
        self._add_file_raw(path)
        self._update_count()

    def _cancel_download(self):
        """Request cancellation of an active download."""
        if self._download_active:
            self._download_cancel = True
            self._search_status.configure(text="⏹ Abbruch läuft …", text_color="#f39c12")

    def _on_download_done(self, keyword: str, downloaded: int, errors: int, total: int,
                          error: str = ""):
        """Main thread: reset download UI state."""
        self._download_active = False
        self._download_cancel = False

        self._btn_search.configure(state="normal" if _gif_search_available else "disabled",
                                   text="Suchen")
        self._btn_cancel_dl.grid_remove()

        if error:
            self._search_status.configure(text=f"❌ {error}", text_color="#e74c3c")
            self._log(f"❌  GIF-Suche fehlgeschlagen: {error}", "error")
            self._progress.set(0)
            self._status_lbl.configure(text="Bereit")
            return

        cancelled = downloaded < total and not error
        txt = f"✅ {downloaded}/{total} GIFs geladen"
        if errors:
            txt += f"  ({errors} Fehler)"
        if cancelled:
            txt += "  [abgebrochen]"
        self._search_status.configure(text=txt, text_color="#2ecc71" if downloaded else "#e74c3c")
        self._log(f"✅  GIF-Suche „{keyword}“: {downloaded} geladen, {errors} Fehler.")
        self._progress.set(1.0)
        self._status_lbl.configure(text="Bereit")
        self.after(2500, lambda: self._progress.set(0))

    def _style_treeview(self):
        s = ttk.Style()
        s.theme_use("default")
        s.configure("File.Treeview",
                    background="#12121f", foreground="#aaaacc",
                    fieldbackground="#12121f", borderwidth=0,
                    rowheight=26, font=("Helvetica", 12))
        s.map("File.Treeview",
              background=[("selected", "#1e3a5f")],
              foreground=[("selected", "#ffffff")])
        s.layout("File.Treeview", [("File.Treeview.treearea", {"sticky": "nswe"})])
        s.configure("File.Vertical.TScrollbar",
                    background="#2a2a3e", troughcolor="#12121f",
                    arrowcolor="#555577", relief="flat")

    def _update_count(self):
        n = len(self._file_data)
        self._count_lbl.configure(
            text=f"{n} Datei" if n == 1 else f"{n} Dateien" if n else "leer"
        )

    # ── Right panel ───────────────────────────────────────────────────────────
    def add_files(self):
        ext_list = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="Video-, GIF- oder PNG-Dateien auswählen",
            filetypes=[("Video / GIF / PNG", ext_list), ("Alle Dateien", "*.*")]
        )
        if paths:
            self._batch_insert(list(paths), 0)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Quellordner auswählen")
        if not folder:
            return
        self._last_source_folder = folder
        if hasattr(self, "_btn_refresh_folder"):
            self._btn_refresh_folder.configure(state="normal")
        threading.Thread(target=self._scan_folder, args=(folder,), daemon=True).start()

    def refresh_folder(self):
        """Re-scan the last selected folder and add any new files."""
        if not self._last_source_folder:
            return
        folder = self._last_source_folder
        self._log(f"🔄  Ordner wird neu eingelesen: {Path(folder).name} …")
        threading.Thread(target=self._scan_folder_refresh, args=(folder,), daemon=True).start()

    def _scan_folder_refresh(self, folder):
        """Like _scan_folder but only adds new files (silent if nothing new)."""
        paths = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
        ])
        if not paths:
            self.after(0, lambda: self._log("   Keine unterstützten Dateien im Ordner gefunden."))
            return
        new_paths = [p for p in paths if p not in self._file_paths]
        if not new_paths:
            self.after(0, lambda: self._log("   ✅  Keine neuen Dateien — der Ordner ist aktuell."))
            return
        self.after(0, lambda: self._batch_insert(new_paths, 0, folder))

    def _scan_folder(self, folder):
        paths = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
        ])
        if not paths:
            self.after(0, lambda: messagebox.showinfo(
                "Information", "In diesem Ordner wurden keine unterstützten Dateien gefunden."))
            return
        self.after(0, lambda: self._batch_insert(paths, 0, folder))

    def _batch_insert(
        self, paths, start, source_folder=None, batch_size=150, select_first=False
    ):
        batch = paths[start:start + batch_size]
        for p in batch:
            self._add_file_raw(p)
        self._update_count()
        if select_first and start == 0 and paths:
            first_iid = next(
                (
                    iid for iid, path in self._file_data.items()
                    if path == paths[0]
                ),
                None,
            )
            if first_iid:
                self._tree.selection_set(first_iid)
                self._tree.focus(first_iid)
                self._on_tree_select()
        remaining = start + batch_size
        if remaining < len(paths):
            self.after(
                0,
                lambda: self._batch_insert(
                    paths, remaining, source_folder, batch_size, select_first
                ),
            )
        else:
            folder_name = Path(source_folder).name if source_folder else ""
            if folder_name:
                self._log(f"📂  {len(paths)} Datei(en) aus „{folder_name}“ hinzugefügt")

    def _add_file_raw(self, path):
        if path in self._file_paths:
            return
        ext  = Path(path).suffix.lower()
        icon = "🎞" if ext == ".gif" else "🎨" if ext == ".png" else "🎬"
        name = Path(path).name
        disp = (name[:20] + "…") if len(name) > 22 else name
        iid  = self._tree.insert(
            "", "end", text=f"  {icon}  {disp}",
            values=("", _QUEUE_STATUS_LABELS["idle"]), tags=("idle",)
        )
        self._file_data[iid]  = path
        self._file_paths.add(path)
        if not self._queue_filter_matches(path):
            self._tree.detach(iid)

    @staticmethod
    def _media_kind(path):
        extension = Path(path).suffix.lower()
        if extension in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            return "image"
        if extension in SUPPORTED_EXTENSIONS:
            return "video"
        return "other"

    def _queue_filter_matches(self, path):
        selected_filter = getattr(self, "_queue_filter", None)
        if selected_filter is None:
            return True
        value = selected_filter.get()
        kind = self._media_kind(path)
        return (
            value == "Alle Medien"
            or (value == "Videos/GIFs" and kind == "video")
            or (value == "Bilder" and kind == "image")
        )

    def _apply_queue_filter(self, _value=None):
        selected = set(self._tree.selection())
        for iid, path in self._file_data.items():
            if self._queue_filter_matches(path):
                self._tree.move(iid, "", "end")
            else:
                self._tree.detach(iid)
                if iid in selected:
                    self._tree.selection_remove(iid)
                    if self._selected_iid == iid:
                        self._stop_src_preview()
                        self._stop_auto_preview()
                        self._stop_dmd_preview()
                        self._selected_iid = ""
                        self._trim_frame.grid_remove()
                        self._draw_canvas_idle()
                        self._draw_auto_canvas_idle()
                        self._draw_dmd_canvas_idle()

    def _on_tree_select(self, _event=None):
        sel = self._tree.selection()
        # Always publish the current selection count first, even for an empty
        # selection or a Ctrl-click that doesn't move the preview focus — this is
        # what keeps the "Convert selected" button's label/enabled-state in sync
        # with a multi-selection.
        EventBus.publish(EventType.SELECTION_CHANGED, {"count": len(sel)})
        if not sel:
            return
        # With extended selectmode, use the focused item (last clicked) for preview.
        iid = self._tree.focus() or sel[0]
        if iid not in sel:
            iid = sel[0]

        # ── Short-circuit: same item re-clicked ──────────────────────────────
        if iid == self._selected_iid:
            return

        # ── SAVE first — synchronous, instant, before ANY state change ───────
        # This must happen before _restore_params overwrites the UI vars.
        if self.app_state.v_per_gif_config.get() and self._selected_iid:
            self._per_gif_configs[self._selected_iid] = self.app_state.snapshot()

        # ── Cancel any pending debounce refresh (stale render for old GIF) ───
        if self._adv_refresh_job:
            self.after_cancel(self._adv_refresh_job)
            self._adv_refresh_job = None

        self._selected_iid = iid
        path = self._file_data.get(iid)
        if path:
            # Per-GIF config: load saved config (if any) when mode is enabled.
            if self.app_state.v_per_gif_config.get():
                if iid in self._per_gif_configs:
                    self._restoring_params = True
                    try:
                        self.app_state.restore(self._per_gif_configs[iid])
                    finally:
                        self._restoring_params = False
                    self._update_per_gif_status(path, saved=True)
                else:
                    self._update_per_gif_status(path, saved=False)

            # Cancel debounce once more
            if self._adv_refresh_job:
                self.after_cancel(self._adv_refresh_job)
                self._adv_refresh_job = None

            self._load_preview(path)
            # If Smart Color Boost is active, refresh computed values for this file
            if self.app_state.v_auto_color_enabled.get():
                self._refresh_auto_color_values(path)

    def _remove_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        if self._selected_iid in sel:
            self._stop_src_preview()
            self._stop_auto_preview()
            self._stop_dmd_preview()
            self._selected_iid = ""
            self._trim_frame.grid_remove()
            self._draw_canvas_idle()
            self._draw_auto_canvas_idle()
            self._draw_dmd_canvas_idle()
        for iid in sel:
            path = self._file_data.pop(iid, None)
            if path:
                self._file_paths.discard(path)
            self._per_gif_configs.pop(iid, None)  # remove per-gif config
            self._tree.delete(iid)
        self._update_count()

    def _remove_specific_file(self, iid):
        if self._selected_iid == iid:
            self._stop_src_preview()
            self._stop_auto_preview()
            self._stop_dmd_preview()
            self._selected_iid = ""
            self._trim_frame.grid_remove()
            self._draw_canvas_idle()
            self._draw_auto_canvas_idle()
            self._draw_dmd_canvas_idle()
        path = self._file_data.pop(iid, None)
        if path:
            self._file_paths.discard(path)
        self._per_gif_configs.pop(iid, None)
        if self._tree.exists(iid):
            self._tree.delete(iid)
        self._update_count()

    def clear_files(self):
        self._stop_src_preview()
        self._stop_auto_preview()
        self._stop_dmd_preview()
        children = self._tree.get_children()
        if children:
            self._tree.delete(*children)
        self._file_data.clear()
        self._file_paths.clear()
        self._per_gif_configs.clear()  # clear all per-gif configs
        self._selected_iid = ""
        self._trim_frame.grid_remove()
        self._draw_canvas_idle()
        self._draw_auto_canvas_idle()
        self._draw_dmd_canvas_idle()
        self._update_count()
        if hasattr(self, "_per_gif_status_lbl"):
            self._per_gif_status_lbl.configure(text="")

    def _set_file_status(self, iid, status):
        try:
            self._tree.item(iid, tags=(status,))
            vals = self._tree.item(iid, "values")
            if vals:
                dur = vals[0]
                status_text = _QUEUE_STATUS_LABELS.get(status.lower(), status.capitalize())
                self._tree.item(iid, values=(dur, status_text))
        except tk.TclError:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #  LOGGING  (lightweight — no log-box in left panel)
    # ══════════════════════════════════════════════════════════════════════════

    def _log(self, message: str, level: str = "info"):
        """Log to Python logger."""
        lvl = {"debug": logging.DEBUG, "info": logging.INFO,
               "warning": logging.WARNING, "error": logging.ERROR}.get(level.lower(), logging.INFO)
        logger.log(lvl, message)

    # ══════════════════════════════════════════════════════════════════════════
    #  PREVIEW DELEGATION  (preview lives in PreviewPanel)
    # ══════════════════════════════════════════════════════════════════════════

    def _load_preview(self, path: str, **kwargs):
        """Ask PreviewPanel to load a preview for *path* via EventBus."""
        EventBus.publish(EventType.PREVIEW_SOURCE_CHANGED, {"path": path, **kwargs})

    def _stop_src_preview(self):
        EventBus.publish(EventType.PREVIEW_REFRESH_REQUESTED, {"action": "stop_src"})

    def _stop_auto_preview(self):
        EventBus.publish(EventType.PREVIEW_REFRESH_REQUESTED, {"action": "stop_auto"})

    def _stop_dmd_preview(self):
        EventBus.publish(EventType.PREVIEW_REFRESH_REQUESTED, {"action": "stop_dmd"})

    def _draw_canvas_idle(self):
        EventBus.publish(EventType.PREVIEW_REFRESH_REQUESTED, {"action": "idle_src"})

    def _draw_auto_canvas_idle(self):
        EventBus.publish(EventType.PREVIEW_REFRESH_REQUESTED, {"action": "idle_auto"})

    def _draw_dmd_canvas_idle(self):
        EventBus.publish(EventType.PREVIEW_REFRESH_REQUESTED, {"action": "idle_dmd"})

    # ══════════════════════════════════════════════════════════════════════════
    #  PER-GIF / AUTO-COLOR  helpers (stubs — real logic in settings panel)
    # ══════════════════════════════════════════════════════════════════════════

    def _update_per_gif_status(self, path: str, saved: bool = False):
        """Update the per-gif config status label (if present)."""
        if hasattr(self, "_per_gif_status_lbl"):
            name = Path(path).name
            if saved:
                self._per_gif_status_lbl.configure(text=f"✅ Eigene Einstellungen: {name[:20]}")
            else:
                self._per_gif_status_lbl.configure(text=f"(Standard) {name[:20]}")

    def _refresh_auto_color_values(self, path: str):
        """Publish a request to refresh Smart Color Boost values for *path*."""
        EventBus.publish(EventType.SETTINGS_CHANGED, {"action": "refresh_auto_color", "path": path})
