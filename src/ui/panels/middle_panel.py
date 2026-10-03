import os
import logging
import tkinter as tk
import tkinter.ttk as ttk
import customtkinter as ctk
from pathlib import Path
from tkinter import messagebox

from src.ui.constants import MULTI_SIZE_PRESETS, SIZE_DIR_PATTERN, STATIC_IMAGE_MODE_LABELS
from src.ui.events.event_bus import EventBus, EventType
from src.ui.i18n import tr

logger = logging.getLogger(__name__)

class MiddlePanel(ctk.CTkFrame):
    def __init__(self, parent, app_state, **kwargs):
        super().__init__(parent, width=320, corner_radius=0, **kwargs)
        self.app_state = app_state
        self._converted_files = []
        self._converted_data: dict = {}
        self._converted_paths: set = set()
        self._selected_converted_iid: str = ""
        self._build_ui()

    def _browse_final_destination(self):
        current = self.app_state.v_final_destination_dir.get().strip()
        d = tk.filedialog.askdirectory(
            title=tr("Select output folder"),
            initialdir=current or None,
        )
        if d:
            self.app_state.v_final_destination_dir.set(d)

    def _build_ui(self):
        mp = self
        mp.grid_propagate(False)
        mp.grid_rowconfigure(5, weight=1)  # treeview row expands
        mp.grid_columnconfigure(0, weight=1)

        # ── Quick Settings (row 0) ────────────────────────────────────────────
        qs = ctk.CTkFrame(mp, fg_color="#1a1200", corner_radius=8, border_width=1, border_color="#ffaa22")
        qs.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")
        qs.grid_columnconfigure(0, weight=1)
        
        self._lmh_cb = ctk.CTkCheckBox(
            qs,
            text=tr("🤖 Let me handle it (Auto)"),
            variable=self.app_state.v_let_me_handle_it,
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffaa22",
            fg_color="#cc7700", hover_color="#ff9900"
        )
        self._lmh_cb.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        
        ctk.CTkButton(
            qs, text="⚙️ " + tr("Advanced Settings"), width=120, height=24,
            command=self._open_advanced_settings,
            fg_color="#3a3a4a", hover_color="#5a5a6a"
        ).grid(row=0, column=1, padx=10, pady=8, sticky="e")

        # ── Target Resolution ────────────────────────────────────────────────
        res_frame = ctk.CTkFrame(mp, fg_color="transparent")
        res_frame.grid(row=1, column=0, padx=10, pady=(2, 8), sticky="ew")
        res_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(res_frame, text=tr("Resolution:"), font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._target_preset_menu = ctk.CTkOptionMenu(
            res_frame,
            variable=self.app_state.v_target_preset,
            values=["64x32 (½x1)", "64x64 (½x2)", "128x32 (1x1)", "256x32 (2x1)", "128x64 (1x2)", "256x64 (2x2)", "Original", "Custom"],
            command=self._on_target_preset_change,
            height=24
        )
        self._target_preset_menu.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            res_frame, text="PNG-Darstellung:", font=ctk.CTkFont(size=11)
        ).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(4, 0))
        label_for_mode = {
            mode: label for label, mode in STATIC_IMAGE_MODE_LABELS.items()
        }
        self._static_image_mode_var = tk.StringVar(
            value=label_for_mode.get(self.app_state.v_static_image_mode.get(), "Strecken")
        )
        self._static_image_mode_menu = ctk.CTkOptionMenu(
            res_frame,
            variable=self._static_image_mode_var,
            values=list(STATIC_IMAGE_MODE_LABELS),
            command=self._on_static_image_mode_change,
            height=24,
        )
        self._static_image_mode_menu.grid(
            row=1, column=1, sticky="ew", pady=(4, 0)
        )
        self.app_state.v_static_image_mode.trace_add(
            "write", self._sync_static_image_mode
        )

        ctk.CTkLabel(
            res_frame, text=tr("Multiple sizes:"), font=ctk.CTkFont(size=11)
        ).grid(row=3, column=0, sticky="nw", padx=(0, 6), pady=(6, 0))
        sizes_frame = ctk.CTkFrame(res_frame, fg_color="transparent")
        sizes_frame.grid(row=3, column=1, sticky="ew", pady=(4, 0))
        for index, preset in enumerate(MULTI_SIZE_PRESETS):
            ctk.CTkCheckBox(
                sizes_frame, text=preset, width=80, checkbox_width=16, checkbox_height=16,
                font=ctk.CTkFont(size=11), variable=self.app_state.multi_size_vars[preset],
            ).grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 6), pady=1)
        ctk.CTkLabel(
            res_frame,
            text=tr("Tick one or more sizes: every converted file is created once per ticked size. Nothing ticked = only the resolution selected above."),
            font=ctk.CTkFont(size=10), text_color="#667788", justify="left", wraplength=260,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # Custom inputs
        self._custom_res_frame = ctk.CTkFrame(res_frame, fg_color="transparent")
        self._custom_res_frame.grid_columnconfigure(1, weight=1)
        self._custom_res_frame.grid_columnconfigure(3, weight=1)
        
        ctk.CTkLabel(self._custom_res_frame, text="W:", font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=2)
        ctk.CTkEntry(self._custom_res_frame, textvariable=self.app_state.v_target_width, width=45, height=24).grid(row=0, column=1, padx=2)
        ctk.CTkLabel(self._custom_res_frame, text="H:", font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=2)
        ctk.CTkEntry(self._custom_res_frame, textvariable=self.app_state.v_target_height, width=45, height=24).grid(row=0, column=3, padx=2)

        self._on_target_preset_change(self.app_state.v_target_preset.get())

        # ── Header ──────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(mp, fg_color="transparent")
        hdr.grid(row=2, column=0, padx=10, pady=(8, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hdr, text="3️⃣ " + tr("✅  Converted Files"),
            font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        
        self._converted_count_lbl = ctk.CTkLabel(
            hdr, text=tr("empty"), text_color="#666688", font=ctk.CTkFont(size=11)
        )
        self._converted_count_lbl.grid(row=0, column=1, sticky="e", padx=(0, 8))

        ctk.CTkButton(
            hdr, text=tr("Clear"), width=60, height=20, font=ctk.CTkFont(size=10),
            command=self._clear_converted, fg_color="#3a3a4a", hover_color="#c0392b"
        ).grid(row=0, column=2, sticky="e")

        # ── Global Statistics ───────────────────────────────────────────────
        stat_frame = ctk.CTkFrame(mp, fg_color="#12121f", corner_radius=6)
        stat_frame.grid(row=3, column=0, padx=8, pady=(4, 6), sticky="ew")
        stat_frame.grid_columnconfigure((0,1,2,3,4,5), weight=1)
        
        def _stat_lbl(text, color, col, row=0):
            lbl = ctk.CTkLabel(stat_frame, text=text, text_color=color, font=ctk.CTkFont(size=11, weight="bold"))
            lbl.grid(row=row, column=col, padx=2, pady=2)
            return lbl

        self._stat_vars = {
            "total": _stat_lbl("Tot: 0", "#ffffff", 0),
            "Premium": _stat_lbl("🌟 0", "#2ecc71", 1),
            "Good": _stat_lbl("🟢 0", "#88dd88", 2),
            "Acceptable": _stat_lbl("🟡 0", "#f1c40f", 3),
            "Poor": _stat_lbl("🟠 0", "#e67e22", 4),
            "Bad": _stat_lbl("🔴 0", "#e74c3c", 5),
        }

        # ── Filter & Search ──────────────────────────────────────────────────
        filter_frame = ctk.CTkFrame(mp, fg_color="transparent")
        filter_frame.grid(row=4, column=0, padx=8, pady=2, sticky="ew")
        filter_frame.grid_columnconfigure(1, weight=1)

        self.app_state.v_filter_preset = tk.StringVar(value="Show All")
        preset_menu = ctk.CTkOptionMenu(
            filter_frame, variable=self.app_state.v_filter_preset,
            values=["Show All", "Excellent Only", "Good And Above", "Acceptable And Above", "Poor And Above"],
            command=self._on_filter_changed,
            width=140, height=26
        )
        preset_menu.grid(row=0, column=0, sticky="w", padx=(0, 4))
        
        self.app_state.v_search_converted = tk.StringVar(value="")
        search_entry = ctk.CTkEntry(
            filter_frame, textvariable=self.app_state.v_search_converted,
            placeholder_text=tr("Search..."), height=26
        )
        search_entry.grid(row=0, column=1, sticky="ew")
        search_entry.bind("<KeyRelease>", self._on_filter_changed)

        # ── Treeview ─────────────────────────────────────────────────────────
        tree_host = tk.Frame(mp, bg="#12121f")
        tree_host.grid(row=5, column=0, padx=6, pady=4, sticky="nsew")
        tree_host.grid_rowconfigure(0, weight=1)
        tree_host.grid_columnconfigure(0, weight=1)

        self._tree_converted = ttk.Treeview(
            tree_host, style="Converted.Treeview",
            columns=("Score", "Category"),
            show="tree headings", selectmode="extended"
        )
        
        self._tree_converted.heading("#0", text="File", anchor="w")
        self._tree_converted.heading("Score", text="Score", anchor="w")
        self._tree_converted.heading("Category", text="Category", anchor="w")
        
        self._tree_converted.column("#0", width=140, stretch=True)
        self._tree_converted.column("Score", width=60, stretch=False)
        self._tree_converted.column("Category", width=80, stretch=False)

        sb_conv = ttk.Scrollbar(tree_host, orient="vertical",
                           command=self._tree_converted.yview, style="File.Vertical.TScrollbar")
        self._tree_converted.configure(yscrollcommand=sb_conv.set)
        
        self._tree_converted.grid(row=0, column=0, sticky="nsew")
        sb_conv.grid(row=0, column=1, sticky="ns")

        self._style_converted_treeview()
        
        self._tree_converted.bind("<<TreeviewSelect>>", self._on_converted_tree_select)
        self._tree_converted.bind("<Delete>", lambda _e: self._remove_selected_converted())
        self._tree_converted.bind("<BackSpace>", lambda _e: self._remove_selected_converted())
        
        self._tree_converted.heading("#0", command=lambda: self._sort_converted("name"))
        self._tree_converted.heading("Score", command=lambda: self._sort_converted("score"))
        self._tree_converted.heading("Category", command=lambda: self._sort_converted("Category"))

        # ── Cleanup Assistant ────────────────────────────────────────────────
        cleanup_frame = ctk.CTkFrame(mp, fg_color="#1a1a2e", corner_radius=6)
        cleanup_frame.grid(row=6, column=0, padx=8, pady=(4, 8), sticky="ew")
        cleanup_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(cleanup_frame, text=tr("🧹 Cleanup Assistant"), font=ctk.CTkFont(size=12, weight="bold"), text_color="#7ec8e3").grid(row=0, column=0, columnspan=2, padx=8, pady=(4, 0), sticky="w")
        
        ctk.CTkButton(cleanup_frame, text=tr("Trash Red (<=30%)"), fg_color="#e74c3c", hover_color="#c0392b", height=24, font=ctk.CTkFont(size=11), command=lambda: self._cleanup_by_score(30)).grid(row=1, column=0, padx=(8, 2), pady=(4, 6), sticky="ew")
        ctk.CTkButton(cleanup_frame, text=tr("Trash <=50%"), fg_color="#e67e22", hover_color="#d35400", height=24, font=ctk.CTkFont(size=11), command=lambda: self._cleanup_by_score(50)).grid(row=1, column=1, padx=(2, 8), pady=(4, 6), sticky="ew")

        # Custom cleanup
        custom_frame = ctk.CTkFrame(cleanup_frame, fg_color="transparent")
        custom_frame.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        custom_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(custom_frame, text=tr("Trash <="), font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0,4))
        
        self.app_state.v_cleanup_custom = tk.StringVar(value="70")
        custom_entry = ctk.CTkEntry(custom_frame, textvariable=self.app_state.v_cleanup_custom, width=40, height=24)
        custom_entry.grid(row=0, column=1, sticky="w")
        
        ctk.CTkLabel(custom_frame, text="%", font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(2,4))
        ctk.CTkButton(custom_frame, text=tr("Trash Custom"), fg_color="#8e44ad", hover_color="#732d91", height=24, width=80, font=ctk.CTkFont(size=11), command=self._cleanup_custom).grid(row=0, column=3, padx=(4,0))

        # ── Destination Folder ──────────────────────────────────────────────
        dest_frame = ctk.CTkFrame(mp, fg_color="transparent")
        dest_frame.grid(row=7, column=0, padx=8, pady=(0, 8), sticky="ew")
        dest_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dest_frame, text="4️⃣ 🚚 " + tr("Move good files to final destination"),
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, columnspan=2, padx=4, pady=(2, 2), sticky="w")

        ctk.CTkLabel(
            dest_frame,
            text=tr(
                "This is a separate folder from the workshop folder above —"
                " e.g. your Batocera share or USB stick. Files are only"
                " moved here when you click the button below."
            ),
            font=ctk.CTkFont(size=10),
            text_color="#8888aa",
            justify="left",
            wraplength=280,
        ).grid(row=1, column=0, columnspan=2, padx=4, pady=(0, 4), sticky="w")

        dest_entry_row = ctk.CTkFrame(dest_frame, fg_color="transparent")
        dest_entry_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        dest_entry_row.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(
            dest_entry_row, textvariable=self.app_state.v_final_destination_dir,
            placeholder_text=tr("Choose a final destination folder to enable moving files there."),
            height=28,
        ).grid(row=0, column=0, padx=(4, 2), sticky="ew")

        ctk.CTkButton(
            dest_entry_row, text="…", width=28, height=28, command=self._browse_final_destination
        ).grid(row=0, column=1, padx=(0, 4))

        ctk.CTkButton(
            dest_frame, text=tr("🚚 Move Converted & Clear List"),
            height=28, command=self._move_and_clear_converted,
            fg_color="#1a4f7a", hover_color="#1a618d", font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=3, column=0, columnspan=2, padx=4, pady=(6, 4), sticky="ew")

    def _style_converted_treeview(self):
        s = ttk.Style()
        s.configure("Converted.Treeview",
                    background="#12121f", foreground="#aaaacc",
                    fieldbackground="#12121f", borderwidth=0,
                    rowheight=26, font=("Helvetica", 11))
        s.map("Converted.Treeview",
              background=[("selected", "#1e3a5f")],
              foreground=[("selected", "#ffffff")])
        s.configure("Converted.Treeview.Heading", background="#1a1a2e", foreground="#ffffff", font=("Helvetica", 11, "bold"))
        
        # Tags for colors
        self._tree_converted.tag_configure("Bad", foreground="#e74c3c")
        self._tree_converted.tag_configure("Poor", foreground="#e67e22")
        self._tree_converted.tag_configure("Acceptable", foreground="#f1c40f")
        self._tree_converted.tag_configure("Good", foreground="#2ecc71")
        self._tree_converted.tag_configure("Excellent", foreground="#88ff88")
        s.configure("Converted.Treeview.Heading", background="#1a1a2e", foreground="#ffffff", font=("Helvetica", 11, "bold"))
        
        # Tags for colors
        self._tree_converted.tag_configure("Excellent", foreground="#2ecc71")
        self._tree_converted.tag_configure("Good", foreground="#88dd88")
        self._tree_converted.tag_configure("Acceptable", foreground="#f1c40f")
        self._tree_converted.tag_configure("Poor", foreground="#e67e22")
        self._tree_converted.tag_configure("Bad", foreground="#e74c3c")
        self._tree_converted.tag_configure("Unknown", foreground="#aaaaaa")
        s.map("Converted.Treeview",
              background=[("selected", "#1e3a5f")],
              foreground=[("selected", "#ffffff")])

    def _open_advanced_settings(self):
        # We will dispatch an event or just open the toplevel directly
        # Since we have reference to app_state, maybe SettingsPanel is self-contained.
        from src.ui.settings.settings_panel import SettingsWindow
        SettingsWindow(self, self.app_state)

    def _on_target_preset_change(self, preset):
        if preset == "Original":
            self.app_state.v_target_width.set(0)
            self.app_state.v_target_height.set(0)
            self._custom_res_frame.grid_forget()
        elif preset != "Custom":
            width, height = map(int, preset.split(" ")[0].split("x"))
            self.app_state.v_target_width.set(width)
            self.app_state.v_target_height.set(height)
            self._custom_res_frame.grid_forget()
        else:
            self._custom_res_frame.grid(row=2, column=0, columnspan=2, pady=4, sticky="ew")

    def _on_static_image_mode_change(self, label):
        mode = STATIC_IMAGE_MODE_LABELS.get(label)
        if mode:
            self.app_state.v_static_image_mode.set(mode)

    def _sync_static_image_mode(self, *_):
        mode = self.app_state.v_static_image_mode.get()
        label = next(
            (label for label, value in STATIC_IMAGE_MODE_LABELS.items() if value == mode),
            "Strecken",
        )
        self._static_image_mode_var.set(label)

    def _update_converted_count(self):
        n = len(self._converted_data)
        self._converted_count_lbl.configure(text=f"{n} file{'s' if n != 1 else ''}" if n else "empty")

    def _add_converted_file(self, path, score_result):
        if path in self._converted_paths:
            return
            
        name = Path(path).name
        size_dir = Path(path).parent.name
        if SIZE_DIR_PATTERN.fullmatch(size_dir):
            name = f"{size_dir}/{name}"
        disp = (name[:20] + "…") if len(name) > 22 else name
        
        score_val = score_result.get("score", 0)
        rating = score_result.get("rating", "Unknown")
        color = score_result.get("color", "")
        
        score_str = f"{color} {score_val}%"
        
        iid = self._tree_converted.insert("", "end", text=f" {disp}", values=(score_str, rating), tags=(rating,))
        
        # Store metadata
        self._converted_data[iid] = {
            "path": path,
            "score": score_val,
            "rating": rating,
            "color": color,
            "reasons": score_result.get("reasons", [])
        }
        self._converted_paths.add(path)
        self._update_converted_count()
        self._update_statistics()

    def _on_converted_tree_select(self, event=None):
        sel = self._tree_converted.selection()
        if not sel:
            return
        iid = self._tree_converted.focus() or sel[0]
        if iid not in sel:
            iid = sel[0]
            
        if iid == self._selected_converted_iid:
            return
            
        self._selected_converted_iid = iid
        
        # Deselect pending files if any
        if hasattr(self, "_tree") and self._tree.selection():
            self._tree.selection_remove(self._tree.selection())
            self._selected_iid = ""
        
        data = self._converted_data.get(iid)
        if data:
            path = data["path"]
            # Trigger preview via EventBus → PreviewPanel._on_source_changed
            EventBus.publish(EventType.PREVIEW_SOURCE_CHANGED, {
                "path": path,
                "is_converted": True,
                "converted_data": data,
            })

    def _remove_selected_converted(self):
        sel = self._tree_converted.selection()
        if not sel:
            return
        for iid in sel:
            data = self._converted_data.pop(iid, None)
            if data:
                self._converted_paths.discard(data["path"])
            self._tree_converted.delete(iid)
        self._update_converted_count()
        self._update_statistics()
        self._selected_converted_iid = ""
        self._clear_preview_via_bus()

    def _clear_converted(self):
        if not self._converted_data:
            return
        if not messagebox.askyesno("Clear List", "Clear all items from the converted list AND delete them from disk?"):
            return
            
        try:
            import send2trash
            safe_delete = send2trash.send2trash
        except ImportError:
            messagebox.showerror(
                "Cannot move to trash",
                "The system-trash integration is unavailable. No files were deleted.",
            )
            return
            
        removed = []
        failures = []
        for iid, data in list(self._converted_data.items()):
            path = data["path"]
            if os.path.exists(path):
                try:
                    safe_delete(path)
                except Exception as exc:
                    failures.append((path, exc))
                    continue
            sidecar = path + ".scores.json"
            if os.path.exists(sidecar):
                try:
                    safe_delete(sidecar)
                except Exception as exc:
                    self._log(f"Could not move score data to trash for {path}: {exc}", "warning")
            removed.append(iid)

        for iid in removed:
            self._converted_data.pop(iid, None)
        self._converted_paths = {
            data["path"] for data in self._converted_data.values()
        }
        children = set(self._tree_converted.get_children())
        visible_removed = [iid for iid in removed if iid in children]
        if visible_removed:
            self._tree_converted.delete(*visible_removed)
        self._update_converted_count()
        self._update_statistics()
        if self._selected_converted_iid in removed:
            self._selected_converted_iid = ""
        if failures:
            messagebox.showwarning(
                "Some files could not be moved",
                f"{len(failures)} file(s) remain in the converted list. See the log for details.",
            )
            for path, exc in failures:
                self._log(f"Could not move {path} to system trash: {exc}", "error")
        
        if not self._converted_data:
            self._clear_preview_via_bus()


    def _move_and_clear_converted(self):
        final_dir = self.app_state.v_final_destination_dir.get().strip()
        if not final_dir:
            messagebox.showerror(
                tr("Error"), tr("Please select a final destination folder first.")
            )
            return

        if not os.path.exists(final_dir):
            messagebox.showerror(
                tr("Error"),
                tr("Final destination folder does not exist:\n{path}").format(path=final_dir),
            )
            return

        if not self._converted_data:
            messagebox.showinfo(tr("Move"), tr("The converted list is empty."))
            return

        import shutil
        moved = 0
        already_in_destination = 0
        processed = []
        errors = []
        for iid, data in self._converted_data.items():
            src_path = data["path"]
            if not os.path.exists(src_path):
                processed.append(iid)
                continue
            target_dir = final_dir
            size_dir = Path(src_path).parent.name
            if SIZE_DIR_PATTERN.fullmatch(size_dir):
                # Keep the size subfolder (e.g. 64x32/) so equal names don't collide
                target_dir = os.path.join(final_dir, size_dir)
                os.makedirs(target_dir, exist_ok=True)
            destination = os.path.join(target_dir, os.path.basename(src_path))
            same_path = os.path.abspath(src_path) == os.path.abspath(destination)
            if same_path:
                already_in_destination += 1
                processed.append(iid)
                continue
            if os.path.exists(destination):
                errors.append(src_path)
                self._log(
                    f"Cannot move {src_path}: destination already exists at {destination}",
                    "error",
                )
                continue

            try:
                shutil.move(src_path, destination)
                moved += 1
                processed.append(iid)
            except Exception as exc:
                errors.append(src_path)
                self._log(f"Failed to move {src_path}: {exc}", "error")
                continue

            # The .scores.json sidecar is only useful while the file is still
            # in the workshop folder for review. It must not be copied into
            # the final destination (e.g. a Batocera share or USB stick).
            sidecar_path = src_path + ".scores.json"
            if os.path.exists(sidecar_path):
                try:
                    os.remove(sidecar_path)
                except OSError as exc:
                    self._log(f"Could not remove leftover score data for {src_path}: {exc}", "warning")

        for iid in processed:
            self._converted_data.pop(iid, None)
        self._converted_paths = {
            data["path"] for data in self._converted_data.values()
        }
        visible = set(self._tree_converted.get_children())
        visible_processed = [iid for iid in processed if iid in visible]
        if visible_processed:
            self._tree_converted.delete(*visible_processed)
        self._update_converted_count()
        self._update_statistics()
        if self._selected_converted_iid in processed:
            self._selected_converted_iid = ""
            self._clear_preview_via_bus()
        self._log(
            f"🚚 Moved {moved} file(s); {already_in_destination} were already in the destination."
        )
        if errors:
            messagebox.showwarning(
                tr("Move incomplete"),
                tr("{count} file(s) could not be moved and remain in the list. See the log.").format(count=len(errors)),
            )

    def _on_filter_changed(self, *_):
        # Basic filtering logic
        search_query = self.app_state.v_search_converted.get().lower().strip()
        preset = self.app_state.v_filter_preset.get()
        
        min_score = 0
        if preset == "Excellent Only": min_score = 86
        elif preset == "Good And Above": min_score = 71
        elif preset == "Acceptable And Above": min_score = 51
        elif preset == "Poor And Above": min_score = 31

        # Re-populate tree based on filter
        children = self._tree_converted.get_children()
        if children:
            self._tree_converted.delete(*children)
        
        for iid, data in self._converted_data.items():
            path = data["path"]
            score = data["score"]
            rating = data["rating"]
            color = data["color"]
            
            name = Path(path).name
            if search_query and search_query not in name.lower():
                continue
                
            if score < min_score:
                continue
                
            disp = (name[:20] + "…") if len(name) > 22 else name
            score_str = f"{color} {score}%"
            self._tree_converted.insert("", "end", iid=iid, text=f" {disp}", values=(score_str, rating), tags=(rating,))

    def _sort_converted(self, col):
        if not hasattr(self, "_sort_dirs"):
            self._sort_dirs = {}
            
        # Toggle direction
        self._sort_dirs[col] = not self._sort_dirs.get(col, False)
        reverse = self._sort_dirs[col]
        
        items = [(self._tree_converted.set(k, col) if col != "name" else self._tree_converted.item(k)["text"], k) for k in self._tree_converted.get_children("")]
        
        if col == "score":
            def _get_score(val):
                try:
                    return int(val.split(" ")[1].replace("%", ""))
                except:
                    return 0
            items.sort(key=lambda x: _get_score(x[0]), reverse=reverse)
        elif col == "Category":
            # Sort by predefined category levels
            rating_order = {"Excellent": 5, "Good": 4, "Acceptable": 3, "Poor": 2, "Bad": 1, "Unknown": 0}
            items.sort(key=lambda x: rating_order.get(x[0], 0), reverse=reverse)
        else:
            items.sort(key=lambda t: t[0].lower(), reverse=reverse)
            
        for index, (val, k) in enumerate(items):
            self._tree_converted.move(k, "", index)

    def _update_statistics(self):
        counts = {"Excellent": 0, "Good": 0, "Acceptable": 0, "Poor": 0, "Bad": 0}
        total = len(self._converted_data)
        
        for data in self._converted_data.values():
            r = data.get("rating")
            if r in counts:
                counts[r] += 1
                
        self._stat_vars["total"].configure(text=f"Tot: {total}")
        self._stat_vars["Premium"].configure(text=f"🌟 {counts['Excellent']}")
        self._stat_vars["Good"].configure(text=f"🟢 {counts['Good']}")
        self._stat_vars["Acceptable"].configure(text=f"🟡 {counts['Acceptable']}")
        self._stat_vars["Poor"].configure(text=f"🟠 {counts['Poor']}")
        self._stat_vars["Bad"].configure(text=f"🔴 {counts['Bad']}")

    def _cleanup_custom(self):
        try:
            max_score = int(self.app_state.v_cleanup_custom.get())
            self._cleanup_by_score(max_score)
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid percentage number.")

    def _cleanup_by_score(self, max_score):
        to_remove = []
        for iid, data in self._converted_data.items():
            if data["score"] <= max_score:
                to_remove.append((iid, data["path"]))
                
        if not to_remove:
            messagebox.showinfo("Cleanup", f"No files found with score <= {max_score}%")
            return
            
        if messagebox.askyesno("Confirm Cleanup", f"Move {len(to_remove)} files to trash?"):
            try:
                import send2trash
                safe_delete = send2trash.send2trash
            except ImportError:
                messagebox.showerror(
                    "Cannot move to trash",
                    "The system-trash integration is unavailable. No files were deleted.",
                )
                return
                
            removed = []
            failures = []
            for iid, path in to_remove:
                try:
                    if os.path.exists(path):
                        safe_delete(path)
                except Exception as e:
                    failures.append((path, e))
                    self._log(f"Failed to move {path} to system trash: {e}", "error")
                    continue
                    
                sidecar_path = path + ".scores.json"
                if os.path.exists(sidecar_path):
                    try:
                        safe_delete(sidecar_path)
                    except Exception as e:
                        self._log(f"Failed to move score data to system trash: {e}", "warning")
                        
                self._converted_paths.discard(path)
                if iid in self._converted_data:
                    del self._converted_data[iid]
                if self._tree_converted.exists(iid):
                    self._tree_converted.delete(iid)
                removed.append(iid)
                    
            self._update_converted_count()
            self._update_statistics()
            self._log(f"🧹 Moved {len(removed)} files to the system trash.")
            if failures:
                messagebox.showwarning(
                    "Some files could not be moved",
                    f"{len(failures)} file(s) remain in the converted list.",
                )
            
            # Clear preview if the selected item was trashed
            if self._selected_converted_iid in [iid for iid, _ in to_remove]:
                self._selected_converted_iid = ""
                self._clear_preview_via_bus()

    # ══════════════════════════════════════════════════════════════════════════
    #  LOGGING helper
    # ══════════════════════════════════════════════════════════════════════════

    def _clear_preview_via_bus(self):
        """Stop and reset all PreviewPanel animations via EventBus."""
        for action in ("stop_src", "stop_auto", "stop_dmd",
                       "idle_src", "idle_auto", "idle_dmd"):
            EventBus.publish(EventType.PREVIEW_REFRESH_REQUESTED, {"action": action})

    def _log(self, message: str, level: str = "info"):
        """Log to Python logger."""
        lvl = {"debug": logging.DEBUG, "info": logging.INFO,
               "warning": logging.WARNING, "error": logging.ERROR}.get(level.lower(), logging.INFO)
        logger.log(lvl, message)
