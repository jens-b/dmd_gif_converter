import tkinter as tk
import customtkinter as ctk
from src.ui.i18n import tr

class PreviewControls:
    def __init__(self, app_state, delegates):
        self.app_state = app_state
        self.delegates = delegates
        
        # UI Elements
        self.top_bar = None
        self.bottom_bar = None
        self._pb = None
        self._diagnosis_frame = None
        self._trim_frame = None
        self._lbl_score = None
        self._lbl_reasons = None
        self._sl_start = None
        self._sl_end = None
        self._lbl_start = None
        self._lbl_end = None
        self._btn_conv_sel = None
        self._btn_conv_all = None
        self._btn_batch = None
        self._btn_cancel = None
        self._btn_led_sim = None
        self._conv_progress = None
        self._conv_status_lbl = None
        
        self.v_batch_auto_trash = tk.BooleanVar(value=False)
        self.v_batch_trash_score = tk.StringVar(value="50")

    def build_top_bar(self, parent):
        self.top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        
        ctk.CTkLabel(
            self.top_bar, text=tr("🖥️  Preview  —  SOURCE → AUTO → DMD"),
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self._pb = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self._pb.grid(row=0, column=1, sticky="e")
        
        self._btn_all_prev = ctk.CTkButton(
            self._pb, text=tr("🔄 All"), width=60, height=26,
            command=self.delegates.get("refresh_all"))
        self._btn_all_prev.pack(side="left", padx=2)
        
        self._btn_src = ctk.CTkButton(
            self._pb, text=tr("▶ Source"), width=80, height=26,
            command=self.delegates.get("show_src"))
        self._btn_src.pack(side="left", padx=2)
        
        self._btn_auto = ctk.CTkButton(
            self._pb, text=tr("🎯 Auto"), width=80, height=26,
            fg_color="#2b4b8a", hover_color="#234073",
            command=self.delegates.get("show_auto"))
        self._btn_auto.pack(side="left", padx=2)
        
        self._btn_dmd = ctk.CTkButton(
            self._pb, text=tr("🔬 DMD"), width=80, height=26,
            fg_color="#1e6a3c", hover_color="#155230",
            command=self.delegates.get("show_dmd"))
        self._btn_dmd.pack(side="left", padx=2)
        
        self._btn_led_sim = ctk.CTkButton(
            self._pb, text=tr("💡 LED Sim ✓"), width=90, height=26,
            fg_color="#5a4a00", hover_color="#7a6400",
            command=self.delegates.get("toggle_led"))
        self._btn_led_sim.pack(side="left", padx=2)
        
        return self.top_bar

    def build_bottom_bar(self, parent):
        self.bottom_bar = ctk.CTkFrame(parent, fg_color="transparent")
        self.bottom_bar.grid_columnconfigure(0, weight=1)
        
        # Diagnosis frame
        self._diagnosis_frame = ctk.CTkFrame(self.bottom_bar, fg_color="#1a1a2e", corner_radius=6)
        self._diagnosis_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self._diagnosis_frame.grid_columnconfigure(1, weight=1)
        self._lbl_score = ctk.CTkLabel(self._diagnosis_frame, text="",
                                       font=ctk.CTkFont(size=18, weight="bold"))
        self._lbl_score.grid(row=0, column=0, padx=12, pady=10)
        self._lbl_reasons = ctk.CTkLabel(self._diagnosis_frame, text="",
                                         justify="left", anchor="w")
        self._lbl_reasons.grid(row=0, column=1, sticky="w", padx=10)
        self._diagnosis_frame.grid_remove()

        # Trim frame
        self._trim_frame = ctk.CTkFrame(self.bottom_bar, fg_color="#16213e")
        self._trim_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self._trim_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self._trim_frame, text=tr("✂️  Trim  (single-file only)"),
                     font=ctk.CTkFont(size=11, weight="bold"), text_color="#7ec8e3"
                     ).grid(row=0, column=0, columnspan=4, padx=10, pady=(4, 2), sticky="w")
        
        ctk.CTkLabel(self._trim_frame, text=tr("Start"), width=44,
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=(10, 4), pady=2)
        self._sl_start = ctk.CTkSlider(self._trim_frame, from_=0, to=1,
                                       variable=self.app_state.v_trim_start,
                                       command=self.delegates.get("on_start_drag"))
        self._sl_start.grid(row=1, column=1, sticky="ew", padx=4)
        self._lbl_start = ctk.CTkLabel(self._trim_frame, text="0.0 s", width=54,
                                       font=ctk.CTkFont(size=11))
        self._lbl_start.grid(row=1, column=2, padx=4)
        
        ctk.CTkLabel(self._trim_frame, text=tr("End"), width=44,
                     font=ctk.CTkFont(size=11)).grid(row=2, column=0, padx=(10, 4), pady=2)
        self._sl_end = ctk.CTkSlider(self._trim_frame, from_=0, to=1,
                                     variable=self.app_state.v_trim_end,
                                     command=self.delegates.get("on_end_drag"))
        self._sl_end.grid(row=2, column=1, sticky="ew", padx=4, pady=(2, 6))
        self._lbl_end = ctk.CTkLabel(self._trim_frame, text="0.0 s", width=54,
                                     font=ctk.CTkFont(size=11))
        self._lbl_end.grid(row=2, column=2, padx=4)
        
        ctk.CTkButton(self._trim_frame, text=tr("↺ Reset"), command=self.delegates.get("reset_trim"),
                      width=70, height=24, fg_color="transparent", border_width=1
                      ).grid(row=1, column=3, rowspan=2, padx=(4, 10))
        self._trim_frame.grid_remove()

        # Action section
        af = ctk.CTkFrame(self.bottom_bar, fg_color="#0d1420", corner_radius=8,
                          border_width=1, border_color="#1a3a2a")
        af.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        af.grid_columnconfigure(0, weight=1)

        # Workshop folder — step 2: where new conversions are written.
        of_section = ctk.CTkFrame(af, fg_color="transparent")
        of_section.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="ew")
        of_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            of_section, text="2️⃣ 📤 " + tr("Workshop folder (conversion output)"),
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#7ec8e3"
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        ctk.CTkLabel(
            of_section,
            text=tr("New conversions are written here so you can review their score before moving the good ones to a final folder."),
            font=ctk.CTkFont(size=10), text_color="#8888aa", justify="left", wraplength=320,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        of_entry_row = ctk.CTkFrame(of_section, fg_color="transparent")
        of_entry_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        of_entry_row.grid_columnconfigure(0, weight=1)

        self._output_entry = ctk.CTkEntry(
            of_entry_row, textvariable=self.app_state.v_output_dir,
            placeholder_text=tr("Choose output folder before converting"), height=28
        )
        self._output_entry.grid(row=0, column=0, padx=(0, 2), sticky="ew")

        ctk.CTkButton(
            of_entry_row, text="…", width=28, height=28,
            command=self.delegates.get("browse_output")
        ).grid(row=0, column=1)

        ctk.CTkLabel(
            af, text="2️⃣ " + tr("🚀  Convert"),
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#7ec8e3"
        ).grid(row=1, column=0, padx=12, pady=(6, 2), sticky="w")

        bf = ctk.CTkFrame(af, fg_color="transparent")
        bf.grid(row=2, column=0, padx=8, pady=2, sticky="ew")
        bf.grid_columnconfigure(0, weight=1)

        self._btn_conv_sel = ctk.CTkButton(
            bf, text=tr("▶  Convert selected file"),
            command=self.delegates.get("convert_selected"),
            height=44, fg_color="#1a4f7a", hover_color="#1a618d",
            font=ctk.CTkFont(size=13, weight="bold"), state="disabled"
        )
        self._btn_conv_sel.grid(row=0, column=0, padx=4, pady=(2, 4), sticky="ew")

        r2 = ctk.CTkFrame(bf, fg_color="transparent")
        r2.grid(row=1, column=0, sticky="ew")
        r2.grid_columnconfigure((0, 1), weight=1)

        self._btn_conv_all = ctk.CTkButton(
            r2, text="⚡  " + tr("Convert all"),
            command=self.delegates.get("convert_all"),
            height=32, fg_color="#5b2fa0", hover_color="#4a2585",
            font=ctk.CTkFont(size=12)
        )
        self._btn_conv_all.grid(row=0, column=0, padx=(4, 2), pady=4, sticky="ew")

        self._btn_batch = ctk.CTkButton(
            r2, text="📂  " + tr("Batch folder"),
            command=self.delegates.get("batch_folder"),
            height=32, fg_color="#1e6a3c", hover_color="#155230",
            font=ctk.CTkFont(size=12)
        )
        self._btn_batch.grid(row=0, column=1, padx=(2, 4), pady=4, sticky="ew")

        tr_batch = ctk.CTkFrame(bf, fg_color="transparent")
        tr_batch.grid(row=2, column=0, padx=4, pady=(0, 2), sticky="w")
        ctk.CTkCheckBox(
            tr_batch, text=tr("Auto-Trash ≤"),
            variable=self.v_batch_auto_trash,
            checkbox_height=16, checkbox_width=16, font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=(0, 2))
        ctk.CTkEntry(
            tr_batch, textvariable=self.v_batch_trash_score,
            width=36, height=20, font=ctk.CTkFont(size=11), justify="center"
        ).pack(side="left")
        ctk.CTkLabel(tr_batch, text="%  (batch)", font=ctk.CTkFont(size=11)).pack(side="left", padx=(2, 0))

        self._conv_progress = ctk.CTkProgressBar(bf, height=8)
        self._conv_progress.set(0)
        self._conv_progress.grid(row=3, column=0, padx=4, pady=(6, 2), sticky="ew")

        self._conv_status_lbl = ctk.CTkLabel(
            bf, text=tr("Ready"), text_color="#778899",
            font=ctk.CTkFont(size=11, slant="italic")
        )
        self._conv_status_lbl.grid(row=4, column=0, padx=4, pady=2)

        self._btn_cancel = ctk.CTkButton(
            bf, text=tr("⏹ Force Stop"),
            command=self.delegates.get("cancel_conversion"),
            height=28, fg_color="#801c1c", hover_color="#540f0f",
            font=ctk.CTkFont(size=11), state="disabled"
        )
        self._btn_cancel.grid(row=5, column=0, padx=4, pady=(2, 6), sticky="ew")

        return self.bottom_bar

    def update_convert_selected_button(self, count: int):
        """Reflect how many source files are currently highlighted so it is clear
        that a multi-selection converts all of them, not just the last one clicked."""
        if count > 1:
            text = tr("▶  Convert {count} selected files").format(count=count)
        else:
            text = tr("▶  Convert selected file")
        self._btn_conv_sel.configure(text=text)

    def show_diagnosis(self, score, reasons):
        self._diagnosis_frame.grid()
        self._lbl_score.configure(text=f"{score}%" if score is not None else "N/A")
        self._lbl_reasons.configure(text=reasons if reasons else "")

    def hide_diagnosis(self):
        self._diagnosis_frame.grid_remove()

    def show_trim(self):
        self._trim_frame.grid()

    def hide_trim(self):
        self._trim_frame.grid_remove()

    def update_trim_labels(self, start_text, end_text):
        self._lbl_start.configure(text=start_text)
        self._lbl_end.configure(text=end_text)
        
    def set_trim_sliders(self, start_val, end_val):
        self._sl_start.set(start_val)
        self._sl_end.set(end_val)
        
    def set_conversion_state(self, busy):
        state = "disabled" if busy else "normal"
        self._btn_conv_all.configure(state=state)
        self._btn_batch.configure(state=state)
        # Convert selected should be handled dynamically by the panel
        self._btn_cancel.configure(
            state="normal" if busy else "disabled",
            text=tr("Stopping…") if busy else tr("⏹ Force Stop"),
        )
        
    def set_led_sim_text(self, is_on):
        self._btn_led_sim.configure(
            text=tr("💡 LED Sim ✓") if is_on else tr("💡 LED Sim")
        )
        
    def handle_resize(self, panel_width):
        if self._pb:
            if panel_width < 750:
                self._pb.grid(row=1, column=0, sticky="w", pady=(4, 0))
            else:
                self._pb.grid(row=0, column=1, sticky="e", pady=0)
