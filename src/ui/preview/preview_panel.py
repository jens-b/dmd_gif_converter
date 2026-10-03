"""
PreviewPanel  —  standalone preview widget for the new modular UI.

Subscribes to EventBus:
  • PREVIEW_SOURCE_CHANGED  {"path": str, ...}   → load a new file preview
  • PREVIEW_REFRESH_REQUESTED {"action": str}     → stop / idle individual canvases
"""
import os
import glob
import logging
import shutil
import threading
import tempfile
import subprocess
import concurrent.futures
from pathlib import Path
from tkinter import filedialog, messagebox

import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

from src.engine.conversion.core import (
    get_metadata, process_file, process_folder,
    DEFAULT_PARAMS, SUPPORTED_EXTENSIONS,
)
from src.engine.auto_action.main import AutoActionConfig, preprocess_video_for_dmd
from src.ui.widgets import _InfoBadge
from src.ui.constants import (
    BG_CANVAS,
    SRC_CANVAS_W, SRC_CANVAS_H,
    AUTO_CANVAS_W, AUTO_CANVAS_H,
    DMD_DISPLAY_SCALE_FACTOR,
    DMD_REFRESH_DELAY_MS,
)
from src.ui.dmd_led_sim import (
    LED_SIM_SCALE, LED_SIM_GAP, LED_SIM_MAX_W,
    apply_led_grid as _apply_led_grid,
)
from src.ui.events.event_bus import EventBus, EventType
from src.ui.i18n import tr

logger = logging.getLogger(__name__)


class PreviewPanel(ctk.CTkFrame):
    """Animated preview + conversion actions."""

    def __init__(self, parent, app_state, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.app_state = app_state
        self._left_panel = None
        self._middle_panel = None
        
        from src.ui.preview.preview_player import PreviewPlayer
        from src.ui.preview.preview_controls import PreviewControls

        self._busy = False
        self._cancel_event = threading.Event()
        self._restoring_params = False
        self._adv_refresh_job = None
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.controls = PreviewControls(app_state, {
            "refresh_all": self._on_refresh_all,
            "show_src": self._on_show_src,
            "show_auto": self._on_show_auto,
            "show_dmd": self._on_show_dmd,
            "toggle_led": self._on_toggle_led,
            "on_start_drag": self._on_start_drag,
            "on_end_drag": self._on_end_drag,
            "reset_trim": self._reset_trim,
            "convert_selected": self.convert_selected,
            "convert_all": self.convert_all,
            "batch_folder": self.batch_folder,
            "cancel_conversion": self.cancel_conversion,
            "browse_output": self.browse_output,
        })
        
        self.controls.build_top_bar(self).grid(row=0, column=0, sticky="ew")
        
        self.player = PreviewPlayer(self, app_state)
        self.player.grid(row=1, column=0, sticky="nsew")
        
        self.controls.build_bottom_bar(self).grid(row=2, column=0, sticky="ew")
        
        self.bind("<Configure>", lambda e: self.controls.handle_resize(self.winfo_width()))
        EventBus.subscribe(EventType.PREVIEW_SOURCE_CHANGED, self._on_source_changed)

    def browse_output(self):
        chosen = filedialog.askdirectory(
            title=tr("Select output folder"),
            initialdir=self.app_state.v_output_dir.get() or None,
        )
        if chosen:
            self.app_state.v_output_dir.set(chosen)

    def set_sibling_panels(self, left_panel, middle_panel):
        self._left_panel = left_panel
        self._middle_panel = middle_panel
        self.player.set_sibling_panels(left_panel, middle_panel)
        
    def _on_source_changed(self, payload):
        self.player._on_source_changed(payload)
        
    def _on_refresh_all(self): self.player.refresh_all_previews()
    def _on_show_src(self): self.player.show_source_preview()
    def _on_show_auto(self): self.player.show_auto_preview()
    def _on_show_dmd(self): self.player.show_dmd_preview()
    def _on_toggle_led(self): 
        is_on = self.player._toggle_led_sim()
        self.controls.set_led_sim_text(is_on)
    def _collect_params(self):
        s = self.app_state
        params = {}
        
        # 1. Dynamically collect all scalar variables from ApplicationState
        # This prevents the recurring problem of forgetting to add new configs here.
        for k, var in s._var_map.items():
            if k in ("v_trim_start", "v_trim_end"):
                continue  # Trim is per-file, not global
            if k.startswith("v_") and not k.startswith("v_action_"):
                # e.g., v_mode -> mode
                params[k[2:]] = var.get()

        # 2. Map aliases expected by the converter's DEFAULT_PARAMS
        if "bottom_crop" in params:
            params["bottom_crop_pct"] = params.pop("bottom_crop")
        if "top_crop" in params:
            params["top_crop_pct"] = params.pop("top_crop")
        if "workers" in params:
            params["max_workers"] = params["workers"]
            
        # 3. Special conditions
        params["max_duration"] = params.get("max_duration", 0.0) if params.get("max_dur_enabled", True) else 0.0
        params["smart_ratio_bypass"] = getattr(s, "v_smart_ratio_bypass", tk.BooleanVar(value=True)).get()
        params["log_level"] = getattr(self.winfo_toplevel(), "v_log_level", tk.StringVar(value="INFO")).get()

        # Inject all auto-action configuration parameters
        from src.engine.config.auto_action_config import AutoActionConfig
        action_cfg = AutoActionConfig.from_app_state(s)
        params.update(action_cfg.to_params_dict())
        # The main enable flag is not part of AutoActionConfig itself
        params["auto_action_enabled"] = s.v_action_enabled.get()
        if s.v_let_me_handle_it.get():
            params.update({
                "auto_color_enabled": True, "auto_action_enabled": True,
                "action_smart_auto_crop": True, "action_auto_pillarbox": True,
                "action_auto_scene_type": True, "action_auto_strength": True,
                "action_auto_smoothness": True, "action_auto_detector_fallback": True,
                "dmd_visibility_score_enabled": True, "dmd_readability_score_enabled": True,
            })
        return params

    # ══════════════════════════════════════════════════════════════════════════
    #  TRIM
    # ══════════════════════════════════════════════════════════════════════════

    def _update_trim_sliders(self):
        dur = max(self.player._source_duration, 0.1)
        self.controls._sl_start.configure(to=dur)
        self.controls._sl_end.configure(to=dur)
        self.app_state.v_trim_start.set(0.0)
        self.app_state.v_trim_end.set(dur)
        self.controls._lbl_start.configure(text="0.0 s")
        self.controls._lbl_end.configure(text=f"{dur:.1f} s")
        self.controls._sl_end.configure(state="normal")

    def _invalidate_auto_cache_and_refresh(self):
        if getattr(self.player, "_auto_tmpdir", None):
            import shutil, os
            if os.path.isdir(self.player._auto_tmpdir):
                shutil.rmtree(self.player._auto_tmpdir, ignore_errors=True)
            self.player._auto_tmpdir = None
        self._schedule_pipeline_refresh()

    def _on_start_drag(self, val):
        v = float(val)
        end = self.app_state.v_trim_end.get()
        if v >= end:
            self.app_state.v_trim_start.set(max(0.0, end - 0.05))
        self.controls._lbl_start.configure(text=f"{self.app_state.v_trim_start.get():.1f} s")
        self._invalidate_auto_cache_and_refresh()

    def _on_end_drag(self, val):
        v = float(val)
        start = self.app_state.v_trim_start.get()
        if v <= start:
            self.app_state.v_trim_end.set(min(self.player._source_duration, start + 0.05))
        self.controls._lbl_end.configure(text=f"{self.app_state.v_trim_end.get():.1f} s")
        self._invalidate_auto_cache_and_refresh()

    def _reset_trim(self):
        self.app_state.v_trim_start.set(0.0)
        self.app_state.v_trim_end.set(self.player._source_duration)
        self.controls._lbl_start.configure(text="0.0 s")
        self.controls._lbl_end.configure(text=f"{self.player._source_duration:.1f} s")
        self._invalidate_auto_cache_and_refresh()

    def _get_trim(self):
        s = self.app_state.v_trim_start.get()
        e = self.app_state.v_trim_end.get()
        return (None, None) if s <= 0.0 and e >= self.player._source_duration - 0.05 else (s, e)

    # ══════════════════════════════════════════════════════════════════════════
    #  DEBOUNCED REFRESH
    # ══════════════════════════════════════════════════════════════════════════

    def _schedule_pipeline_refresh(self, *_):
        if self._restoring_params:
            return
        if self._adv_refresh_job:
            self.after_cancel(self._adv_refresh_job)
        self._adv_refresh_job = self.after(DMD_REFRESH_DELAY_MS, self._auto_refresh_pipeline)

    def _schedule_dmd_only_refresh(self, *_):
        if self._restoring_params:
            return
        if self._adv_refresh_job:
            self.after_cancel(self._adv_refresh_job)
        self._adv_refresh_job = self.after(DMD_REFRESH_DELAY_MS, self._auto_refresh_dmd_only)

    def _auto_refresh_pipeline(self):
        self._adv_refresh_job = None
        if self.player._current_path and not self._busy and not self.player._auto_rendering and not self.player._dmd_rendering:
            self.player._start_auto_generation(self.player._current_path)
            self.player._start_dmd_generation(self.player._current_path)

    def _auto_refresh_dmd_only(self):
        self._adv_refresh_job = None
        if self.player._current_path and not self._busy and not self.player._dmd_rendering:
            self.player._start_dmd_generation(self.player._current_path)

    # ══════════════════════════════════════════════════════════════════════════
    #  CONVERSION LOGIC
    # ══════════════════════════════════════════════════════════════════════════

    def _out_path(self, src, iid=None, reserved: set[str] | None = None):
        base = Path(src).stem + "_dmd" + ".gif"
        if (
            iid
            and self._left_panel
            and self.app_state.v_per_gif_config.get()
        ):
            config = self._left_panel._per_gif_configs.get(iid, {})
            custom_name = config.get("custom_out_name")
            if custom_name:
                base = Path(custom_name).name
                if Path(base).suffix.lower() != ".gif":
                    base = f"{Path(base).stem}.gif"
        out_dir = self.app_state.v_output_dir.get().strip()
        if not out_dir or not os.path.isdir(out_dir):
            raise ValueError(tr("Choose an existing output folder before converting."))
        destination = Path(out_dir) / base
        counter = 2
        while destination.exists() or (
            reserved is not None
            and os.path.normcase(os.path.abspath(destination)).casefold() in reserved
        ):
            destination = Path(out_dir) / f"{Path(base).stem}_{counter}.gif"
            counter += 1
        if reserved is not None:
            reserved.add(os.path.normcase(os.path.abspath(destination)).casefold())
        return str(destination)

    def _choose_output_folder(self):
        current = self.app_state.v_output_dir.get().strip()
        initialdir = current if current and os.path.isdir(current) else str(Path.home())
        output_dir = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title=tr("Choose output folder"),
            initialdir=initialdir,
        )
        if not output_dir:
            return None
        if not os.path.isdir(output_dir):
            messagebox.showerror(
                tr("Invalid output folder"),
                tr("The selected output folder does not exist."),
                parent=self.winfo_toplevel(),
            )
            return None
        self.app_state.v_output_dir.set(output_dir)
        return output_dir

    def convert_selected(self):
        """Convert every file currently highlighted (Ctrl/Shift multi-select) in the
        left panel's source list — not just the single file shown in the preview."""
        if self._busy:
            messagebox.showwarning(tr("Busy"), tr("A conversion is already running."))
            return
        lp = self._left_panel
        sel = lp._tree.selection() if lp is not None else ()
        if lp is None or not sel:
            messagebox.showinfo(tr("Info"), tr("Please select a file from the list first."))
            return
        items = [(iid, lp._file_data.get(iid)) for iid in sel]
        items = [(iid, src) for iid, src in items if src]
        if not items:
            return
        if not self._choose_output_folder():
            return
        self._cancel_event.clear()
        reserved: set[str] = set()
        if len(items) == 1:
            # Single file: honor the trim range currently shown in the preview.
            iid, src = items[0]
            out = self._out_path(src, iid=iid, reserved=reserved)
            start_s, end_s = self._get_trim()
            trim_info = f"  trim [{start_s:.1f}s → {end_s:.1f}s]" if start_s is not None else ""
            self._log(f"▶  Convert: {Path(src).name}{trim_info}")
            tasks = [(src, out, start_s, end_s, iid)]
        else:
            # Multiple files selected: trim only applies to the one file shown in
            # the preview, so it is not meaningful here — convert each in full.
            tasks = [
                (src, self._out_path(src, iid=iid, reserved=reserved), None, None, iid)
                for iid, src in items
            ]
            self._log(f"▶  Converting {len(tasks)} selected file(s)…")
        threading.Thread(
            target=self._run_tasks, args=(tasks, self._collect_params()), daemon=True
        ).start()

    def convert_all(self):
        lp = self._left_panel
        if lp is None or not lp._file_data:
            messagebox.showinfo(tr("Info"), tr("The file list is empty."))
            return
        if self._busy:
            messagebox.showwarning(tr("Busy"), tr("A conversion is already running."))
            return
        if not self._choose_output_folder():
            return
        self._cancel_event.clear()
        reserved = set()
        tasks = [
            (path, self._out_path(path, iid=iid, reserved=reserved), None, None, iid)
            for iid, path in lp._file_data.items()
        ]
        self._log(f"⚡  Converting {len(tasks)} file(s)…")
        threading.Thread(
            target=self._run_tasks, args=(tasks, self._collect_params()), daemon=True
        ).start()

    def batch_folder(self):
        if self._busy:
            messagebox.showwarning(tr("Busy"), tr("A conversion is already running."))
            return
        folder_in = filedialog.askdirectory(title="Source folder — Batch")
        if not folder_in:
            return
        out_dir = self._choose_output_folder()
        if not out_dir:
            return
        files = [f for f in os.listdir(folder_in)
                 if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS]
        if not files:
            messagebox.showinfo(tr("Info"), tr("No supported files found in this folder."))
            return
        expected_outputs = [Path(out_dir) / f"{Path(name).stem}.gif" for name in files]
        output_names = [os.path.normcase(os.path.abspath(path)) for path in expected_outputs]
        conflicts = len(set(output_names)) != len(output_names) or any(
            path.exists() for path in expected_outputs
        )
        if conflicts:
            messagebox.showerror(
                tr("Output filename conflicts"),
                tr(
                    "This batch would overwrite existing output or two sources share a name. "
                    "Choose another output folder or rename the source files."
                ),
            )
            return
        if self.controls.v_batch_auto_trash.get():
            try:
                threshold = int(self.controls.v_batch_trash_score.get())
            except ValueError:
                messagebox.showerror(tr("Invalid threshold"), tr("Enter a whole-number score from 0 to 100."))
                return
            if not 0 <= threshold <= 100:
                messagebox.showerror(tr("Invalid threshold"), tr("The score threshold must be between 0 and 100."))
                return
            if not messagebox.askyesno(
                tr("Confirm automatic cleanup"),
                tr("After this batch, move only newly created GIFs scoring {threshold}% or less to the system trash? Existing files will not be touched.").format(threshold=threshold),
                parent=self.winfo_toplevel(),
            ):
                return
        self._cancel_event.clear()
        params = self._collect_params()
        self._log(f"📂  Batch: {len(files)} file(s)  →  {out_dir}")
        threading.Thread(
            target=self._run_batch_folder, args=(folder_in, out_dir, params), daemon=True
        ).start()

    def cancel_conversion(self):
        self._cancel_event.set()
        self._log("⚠️  Cancellation requested…", "warning")
        self.controls._btn_cancel.configure(state="disabled", text="Stopping…")

    def _run_tasks(self, tasks, params):
        self.after(0, lambda: self._set_conv_busy(True))
        total = len(tasks)
        
        v_auto_workers = params.get("auto_workers", True)
        if v_auto_workers:
            max_workers = max(1, min(16, (os.cpu_count() or 4) // 2))
        else:
            max_workers = int(params.get("max_workers", 2))
            
        self.after(0, lambda w=max_workers: self._log(
            f"🚀  Convert {total} file(s) using {w} worker(s)…"))

        done_count = [0]
        success_count = [0]
        failure_count = [0]
        failures = []
        done_lock = threading.Lock()
        # Per-task sequential worker ID for log isolation
        _wid_seq = [0]
        _wid_lock = threading.Lock()
        lp = self._left_panel
        mp = self._middle_panel
        per_gif_enabled = (
            lp is not None and
            hasattr(lp, "_per_gif_configs") and
            self.app_state.v_per_gif_config.get()
        )

        def _process_one(task_tuple):
            with _wid_lock:
                _wid_seq[0] += 1
            src, out, start_s, end_s, iid = task_tuple
            if self._cancel_event.is_set():
                return

            success = False
            msg = ""
            try:
                task_params = dict(params)
                if per_gif_enabled and iid in lp._per_gif_configs:
                    task_params.update(lp._per_gif_configs[iid])
                if lp:
                    self.after(0, lambda _i=iid: lp._set_file_status(_i, "converting"))
                success, msg = process_file(
                    src, out, task_params, start_s, end_s,
                    cancel_event=self._cancel_event,
                )
                if success:
                    from src.engine.conversion.quality import load_score_sidecar
                    score_result = load_score_sidecar(out) or {
                        "score": 0, "rating": "Unknown", "color": "⚪", "reasons": []
                    }
                    if mp:
                        self.after(0, lambda _o=out, _r=score_result:
                                   mp._add_converted_file(_o, _r))
                    if lp:
                        self.after(0, lambda _i=iid: lp._remove_specific_file(_i))
                elif lp:
                    new_status = "idle" if self._cancel_event.is_set() else "error"
                    self.after(0, lambda _i=iid, _status=new_status: lp._set_file_status(_i, _status))
            except Exception as exc:
                success = False
                msg = f"{type(exc).__name__}: {exc}"
                logger.exception("Conversion failed for %s", src)
                if lp:
                    self.after(0, lambda _i=iid: lp._set_file_status(_i, "error"))

            with done_lock:
                if success:
                    success_count[0] += 1
                elif not self._cancel_event.is_set():
                    failure_count[0] += 1
                    failures.append((src, msg))
                done_count[0] += 1
                completed = done_count[0]
                succeeded = success_count[0]
                failed = failure_count[0]
            progress = completed / total
            self.after(0, lambda p=progress: self.controls._conv_progress.set(p))
            self.after(
                0,
                lambda d=completed, s=succeeded, f=failed:
                    self.controls._conv_status_lbl.configure(
                        text=tr("{done}/{total} processed — {succeeded} succeeded, {failed} failed").format(
                            done=d, total=total, succeeded=s, failed=f
                        )
                    ),
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {
                ex.submit(_process_one, task): task
                for task in tasks
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    src = futures[future][0]
                    logger.exception("Unexpected worker failure for %s", src)
                    with done_lock:
                        failure_count[0] += 1
                        done_count[0] += 1
                        failures.append((src, f"{type(exc).__name__}: {exc}"))

        if self._cancel_event.is_set():
            summary = tr(
                "Cancelled — {success} succeeded, {failed} failed, {pending} not started"
            ).format(
                success=success_count[0],
                failed=failure_count[0],
                pending=total - done_count[0],
            )
            self.after(0, lambda: self._log(f"🛑  {summary}."))
        else:
            summary = tr("Finished — {success} succeeded, {failed} failed").format(
                success=success_count[0], failed=failure_count[0]
            )
            self.after(0, lambda: self._log(f"✅  {summary}."))
        for src, error in failures:
            self.after(0, lambda p=src, e=error: self._log(
                f"Failed: {Path(p).name}: {e}", "error"
            ))
        self.after(0, lambda: self._set_conv_busy(False))
        self.after(0, lambda s=summary: self.controls._conv_status_lbl.configure(text=s))

    def _run_batch_folder(self, folder_in, folder_out, params):
        folder_out = os.path.abspath(folder_out)
        self.after(0, lambda: self._set_conv_busy(True))
        self.after(0, lambda: self.controls._conv_progress.set(0))
        mp = self._middle_panel

        def on_progress(done, total):
            self.after(0, lambda f=done / max(1, total): self.controls._conv_progress.set(f))

        source_files = [
            name for name in os.listdir(folder_in)
            if Path(name).suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        source_files.sort(key=str.casefold)
        try:
            results = process_folder(
                folder_in, folder_out, params,
                progress_callback=on_progress,
                cancel_event=self._cancel_event,
            )
        except Exception as exc:
            logger.exception("Batch conversion failed")
            self.after(0, lambda e=exc: self._log(
                f"Batch conversion failed: {type(e).__name__}: {e}", "error"
            ))
            self.after(0, lambda: self._set_conv_busy(False))
            self.after(0, lambda e=exc:
                       self.controls._conv_status_lbl.configure(
                           text=tr("Batch failed: {error}").format(error=e)
                       ))
            return

        if self._cancel_event.is_set():
            self.after(0, lambda: self._log("🛑  Batch cancelled."))
            self.after(0, lambda: self._set_conv_busy(False))
            return

        result_by_output = {
            os.path.join(folder_out, Path(name).stem + ".gif"): result
            for name, result in zip(source_files, results)
        }
        if self.controls.v_batch_auto_trash.get():
            try:
                threshold = int(self.controls.v_batch_trash_score.get())
                self.after(0, lambda: self._log(f"🧹 Auto-Trash ≤ {threshold}%…"))
                from src.engine.conversion.quality import load_score_sidecar
                try:
                    import send2trash; safe_delete = send2trash.send2trash
                except ImportError:
                    safe_delete = None
                    self.after(0, lambda: self._log(
                        "send2trash is unavailable — automatic cleanup was skipped; "
                        "no files were deleted.", "warning"))
                trashed = 0
                for gp, result in result_by_output.items():
                    if safe_delete is None:
                        break
                    success, _message = result
                    if not success or not os.path.isfile(gp):
                        continue
                    res = load_score_sidecar(gp)
                    if res and res.get("score", 0) <= threshold:
                        try:
                            safe_delete(gp)
                            trashed += 1
                            sc = gp + ".scores.json"
                            if os.path.exists(sc):
                                safe_delete(sc)
                        except Exception as e:
                            self.after(0, lambda err=e: self._log(
                                f"Move to system trash failed: {err}", "warning"))
                if safe_delete is not None:
                    self.after(0, lambda c=trashed: self._log(
                        f"✅  Moved {c} low-scoring file(s) to the system trash."))
            except ValueError:
                self.after(0, lambda: self._log(
                    "⚠️  Invalid threshold — skipping Auto-Trash.", "warning"))

        succeeded = sum(1 for success, _ in results if success)
        failed = sum(1 for success, _ in results if not success)
        summary = tr("Batch finished — {success} succeeded, {failed} failed").format(
            success=succeeded, failed=failed
        )
        self.after(0, lambda s=summary: self._log(f"✅  {s}."))
        self.after(0, lambda: self._set_conv_busy(False))
        self.after(0, lambda s=summary: self.controls._conv_status_lbl.configure(text=s))

    def _set_conv_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        lp = self._left_panel
        for btn in (self.controls._btn_conv_all, self.controls._btn_batch):
            btn.configure(state=state)
        sel_count = len(lp._tree.selection()) if lp else 0
        self.controls.update_convert_selected_button(sel_count)
        if not busy and sel_count:
            self.controls._btn_conv_sel.configure(state="normal")
        else:
            self.controls._btn_conv_sel.configure(state="disabled")
        self.controls._btn_cancel.configure(
            state="normal" if busy else "disabled",
            text="⏹ Force Stop")
        self.controls._conv_status_lbl.configure(
            text=tr("Converting…") if busy else tr("Ready"))
        if not busy:
            self.after(2500, lambda: self.controls._conv_progress.set(0))
        EventBus.publish(
            EventType.CONVERSION_STARTED if busy else EventType.CONVERSION_FINISHED,
            {"busy": busy})

    def _log(self, message: str, level: str = "info"):
        lvl = {"debug": logging.DEBUG, "info": logging.INFO,
               "warning": logging.WARNING, "error": logging.ERROR}.get(level.lower(), logging.INFO)
        logger.log(lvl, message)
