from __future__ import annotations

import base64
import io
import logging
import math
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk

import numpy as np

from .main import export_xy_value_map_step, export_xy_value_maps
from .processor import (
    DataSource,
    Roi,
    RoiGrid,
    build_colormap,
    clamp_roi_to_bounds,
    compute_global_value_range_rotated,
    downsample_grid_for_preview,
    estimate_grid_spacing,
    frame_to_grids,
    parse_color,
    prepare_rotated_grid,
    prepare_rotated_grid_from_grid,
    roi_bounds,
    roi_corners,
    slice_grids_to_bounds,
)

logger = logging.getLogger(__name__)



MANUAL_URL = "https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=73"


@dataclass
class _GlobalScaleState:
    token: int = 0
    vmin: float | None = None
    vmax: float | None = None
    running: bool = False


class XYValueMapGUI(tk.Toplevel):
    def __init__(self, master, input_path: Path, output_dir: Path):
        super().__init__(master)
        self.master = master
        self.input_path = input_path
        self.output_dir = output_dir

        self.title("X-Y 分布画像出力")
        self.resizable(True, True)

        self._data_source: DataSource | None = None
        self._data_ready = False
        self._step_count = 1
        self._value_columns: list[str] | None = None

        self._global_scale = _GlobalScaleState()
        self._preview_frame_cache: dict[tuple[int, str], object] = {}
        self._base_dx = 1.0
        self._base_dy = 1.0
        self._base_spacing_ready = False
        self._edit_base_bounds: tuple[float, float, float, float] | None = None
        self._edit_view_bounds: tuple[float, float, float, float] | None = None
        self._edit_map_dirty = True
        self._edit_fig = None
        self._edit_ax = None
        self._edit_agg = None
        self._edit_image_id = None
        self._edit_image_tk = None
        self._edit_render_job = None
        self._edit_render_context: dict[str, object] | None = None
        self._edit_domain_rect_id = None
        self._edit_pad_rect_id = None
        self._edit_overlay_text_id = None
        self._edit_overlay_bg_id = None
        self._edit_hint_text_id = None
        self._edit_hint_bg_id = None
        self._edit_outline_id = None
        self._edit_outline_points: np.ndarray | None = None
        self._edit_context: dict[str, object] = {"step": None, "time": None, "value": ""}
        self._last_output_opts: dict[str, object] | None = None
        self._roi_patch = None
        self._roi_bottom_edge = None
        self._roi_rotate_line = None
        self._roi_handles: list[dict[str, object]] = []
        self._roi_var_lock = False
        self._drag_state: dict[str, object] | None = None
        self._preview_dragging = False
        self._step_var_lock = False
        self._scale_var_lock = False
        self._slider_lock = False
        self._auto_range: tuple[float, float] | None = None
        self._scale_ratio: tuple[float, float] = (0.0, 1.0)
        self._output_opts_lock = False
        self._roi_confirmed = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_menu()
        self._build_ui()
        self._set_controls_enabled(False)
        self.status_var.set("Loading...")
        self.after(0, self._start_initial_load)

    def _build_menu(self):
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label="マニュアルを開く",
            accelerator="Alt+H",
            command=lambda: webbrowser.open(MANUAL_URL),
        )
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)
        self.bind_all("<Alt-h>", lambda e: webbrowser.open(MANUAL_URL))

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # 入力/出力パス（readonly）
        ttk.Label(self, text="入力:").grid(row=0, column=0, sticky="e", **pad)
        self.input_var = tk.StringVar(value=str(self.input_path))
        ttk.Entry(self, textvariable=self.input_var, width=60, state="readonly").grid(
            row=0, column=1, columnspan=5, sticky="ew", **pad
        )
        ttk.Label(self, text="出力:").grid(row=1, column=0, sticky="e", **pad)
        self.output_var = tk.StringVar(value=str(self.output_dir))
        ttk.Entry(self, textvariable=self.output_var, width=60, state="readonly").grid(
            row=1, column=1, columnspan=5, sticky="ew", **pad
        )

        # Value 変数
        ttk.Label(self, text="Value:").grid(row=2, column=0, sticky="e", **pad)
        self.value_var = tk.StringVar()
        self.value_combo = ttk.Combobox(self, textvariable=self.value_var, state="readonly", width=30)
        self.value_combo.grid(row=2, column=1, sticky="w", **pad)
        self.value_combo.bind("<<ComboboxSelected>>", lambda e: self._on_value_changed())

        # プレビュー対象ステップ
        ttk.Label(self, text="プレビュー step:").grid(row=2, column=2, sticky="e", **pad)
        self.step_var = tk.IntVar(value=1)
        self.step_spin = tk.Spinbox(self, from_=1, to=max(1, self._step_count), textvariable=self.step_var, width=8, command=self._on_step_changed)
        self.step_spin.grid(row=2, column=3, sticky="w", **pad)
        self.step_var.trace_add("write", lambda *_: self._on_step_changed())

        # ROI
        ttk.Label(self, text="ROI (Cx/Cy/W/H/Angle):").grid(row=3, column=0, sticky="e", **pad)
        self.cx_var = tk.DoubleVar()
        self.cy_var = tk.DoubleVar()
        self.width_var = tk.DoubleVar()
        self.height_var = tk.DoubleVar()
        self.angle_var = tk.DoubleVar()
        self.cx_entry = ttk.Entry(self, textvariable=self.cx_var, width=10)
        self.cy_entry = ttk.Entry(self, textvariable=self.cy_var, width=10)
        self.width_entry = ttk.Entry(self, textvariable=self.width_var, width=10)
        self.height_entry = ttk.Entry(self, textvariable=self.height_var, width=10)
        self.angle_entry = ttk.Entry(self, textvariable=self.angle_var, width=10)
        self.cx_entry.grid(row=3, column=1, sticky="w", **pad)
        self.cy_entry.grid(row=3, column=2, sticky="w", **pad)
        self.width_entry.grid(row=3, column=3, sticky="w", **pad)
        self.height_entry.grid(row=3, column=4, sticky="w", **pad)
        self.angle_entry.grid(row=3, column=5, sticky="w", **pad)
        self.reset_roi_btn = ttk.Button(self, text="全体表示", command=self._reset_roi_to_full)
        self.reset_roi_btn.grid(row=3, column=6, sticky="w", **pad)

        for var in (self.cx_var, self.cy_var, self.width_var, self.height_var, self.angle_var):
            var.trace_add("write", lambda *_: self._on_roi_changed())
        for entry in (self.cx_entry, self.cy_entry, self.width_entry, self.height_entry, self.angle_entry):
            entry.bind("<Return>", self._on_roi_entry_confirm)
            entry.bind("<FocusOut>", self._on_roi_entry_confirm)

        # 色（最小/最大）
        ttk.Label(self, text="最小色:").grid(row=4, column=0, sticky="e", **pad)
        self.min_color_var = tk.StringVar(value="#0000ff")
        self.min_color_btn = ttk.Button(self, text="選択", command=lambda: self._choose_color(self.min_color_var))
        self.min_color_btn.grid(row=4, column=1, sticky="w", **pad)
        self.min_color_sample = tk.Label(self, width=6, background=self.min_color_var.get())
        self.min_color_sample.grid(row=4, column=2, sticky="w", **pad)

        ttk.Label(self, text="最大色:").grid(row=4, column=3, sticky="e", **pad)
        self.max_color_var = tk.StringVar(value="#ff0000")
        self.max_color_btn = ttk.Button(self, text="選択", command=lambda: self._choose_color(self.max_color_var))
        self.max_color_btn.grid(row=4, column=4, sticky="w", **pad)
        self.max_color_sample = tk.Label(self, width=6, background=self.max_color_var.get())
        self.max_color_sample.grid(row=4, column=5, sticky="w", **pad)

        self.min_color_var.trace_add("write", lambda *_: self._on_color_changed())
        self.max_color_var.trace_add("write", lambda *_: self._on_color_changed())

        # スケール
        ttk.Label(self, text="スケール:").grid(row=5, column=0, sticky="e", **pad)
        self.scale_mode = tk.StringVar(value="global")
        self.scale_global_radio = ttk.Radiobutton(self, text="global", value="global", variable=self.scale_mode, command=self._on_scale_mode_changed)
        self.scale_manual_radio = ttk.Radiobutton(self, text="manual", value="manual", variable=self.scale_mode, command=self._on_scale_mode_changed)
        self.scale_global_radio.grid(row=5, column=1, sticky="w", **pad)
        self.scale_manual_radio.grid(row=5, column=2, sticky="w", **pad)

        ttk.Label(self, text="vmin/vmax:").grid(row=5, column=3, sticky="e", **pad)
        self.vmin_var = tk.DoubleVar()
        self.vmax_var = tk.DoubleVar()
        self.vmin_entry = ttk.Entry(self, textvariable=self.vmin_var, width=10, state="disabled")
        self.vmax_entry = ttk.Entry(self, textvariable=self.vmax_var, width=10, state="disabled")
        self.vmin_entry.grid(row=5, column=4, sticky="w", **pad)
        self.vmax_entry.grid(row=5, column=5, sticky="w", **pad)
        self.vmin_var.trace_add("write", lambda *_: self._on_manual_scale_changed())
        self.vmax_var.trace_add("write", lambda *_: self._on_manual_scale_changed())

        # vmin/vmax range slider
        ttk.Label(self, text="スケール範囲:").grid(row=6, column=0, sticky="e", **pad)
        self.range_slider = _RangeSlider(self, height=24, command=self._on_range_slider_changed)
        self.range_slider.grid(row=6, column=1, columnspan=5, sticky="ew", **pad)

        # 出力オプション
        opt_frame = ttk.LabelFrame(self, text="出力オプション")
        opt_frame.grid(row=7, column=0, columnspan=7, sticky="ew", padx=8, pady=6)
        opt_frame.columnconfigure(0, weight=1)
        opt_frame.columnconfigure(1, weight=1)
        opt_frame.columnconfigure(2, weight=1)
        opt_frame.columnconfigure(3, weight=1)

        self.show_title_var = tk.BooleanVar(value=True)
        self.show_step_var = tk.BooleanVar(value=True)
        self.show_time_var = tk.BooleanVar(value=True)
        self.show_value_var = tk.BooleanVar(value=True)
        self.show_ticks_var = tk.BooleanVar(value=True)
        self.show_frame_var = tk.BooleanVar(value=True)
        self.show_cbar_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(opt_frame, text="タイトル", variable=self.show_title_var, command=self._on_output_option_changed).grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.Checkbutton(opt_frame, text="step", variable=self.show_step_var, command=self._on_output_option_changed).grid(row=0, column=1, sticky="w", padx=6, pady=2)
        ttk.Checkbutton(opt_frame, text="t", variable=self.show_time_var, command=self._on_output_option_changed).grid(row=0, column=2, sticky="w", padx=6, pady=2)
        ttk.Checkbutton(opt_frame, text="value", variable=self.show_value_var, command=self._on_output_option_changed).grid(row=0, column=3, sticky="w", padx=6, pady=2)

        ttk.Checkbutton(opt_frame, text="目盛り", variable=self.show_ticks_var, command=self._on_output_option_changed).grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Checkbutton(opt_frame, text="枠線", variable=self.show_frame_var, command=self._on_output_option_changed).grid(row=1, column=1, sticky="w", padx=6, pady=2)
        ttk.Checkbutton(opt_frame, text="カラーバー", variable=self.show_cbar_var, command=self._on_output_option_changed).grid(row=1, column=2, sticky="w", padx=6, pady=2)

        # 解像度
        ttk.Label(self, text="解像度倍率:").grid(row=8, column=0, sticky="e", **pad)
        self.resolution_var = tk.DoubleVar(value=1.0)
        self.resolution_spin = tk.Spinbox(
            self,
            from_=0.5,
            to=8.0,
            increment=0.5,
            textvariable=self.resolution_var,
            width=8,
        )
        self.resolution_spin.grid(row=8, column=1, sticky="w", **pad)

        self.resolution_var.trace_add("write", lambda *_: self._on_resolution_changed())

        # ステータス
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var).grid(row=9, column=0, columnspan=7, sticky="w", padx=8, pady=(2, 6))

        # 編集/プレビュー
        canvas_frame = ttk.Frame(self)
        canvas_frame.grid(row=10, column=0, columnspan=7, sticky="nsew", padx=8, pady=8)
        canvas_frame.grid_columnconfigure(0, weight=1, uniform="canvas")
        canvas_frame.grid_columnconfigure(1, weight=1, uniform="canvas")
        canvas_frame.grid_rowconfigure(0, weight=1)
        edit_frame = ttk.LabelFrame(canvas_frame, text="編集（全体表示）")
        preview_frame = ttk.LabelFrame(canvas_frame, text="プレビュー")
        edit_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self._build_edit_canvas(edit_frame)
        self._build_preview(preview_frame)

        # 実行
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=11, column=0, columnspan=7, sticky="ew", padx=8, pady=10)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        self.run_step_btn = ttk.Button(btn_frame, text="このステップのみ出力", command=self._run_single_step)
        self.run_btn = ttk.Button(btn_frame, text="実行（全ステップ出力）", command=self._run)
        self.run_step_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.run_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(4, weight=1)
        self.grid_rowconfigure(10, weight=1)

        self._interactive_widgets = [
            self.value_combo,
            self.step_spin,
            self.cx_entry,
            self.cy_entry,
            self.width_entry,
            self.height_entry,
            self.angle_entry,
            self.reset_roi_btn,
            self.min_color_btn,
            self.max_color_btn,
            self.scale_global_radio,
            self.scale_manual_radio,
            self.vmin_entry,
            self.vmax_entry,
            self.range_slider,
            self.resolution_spin,
            self.run_step_btn,
            self.run_btn,
        ]

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for widget in getattr(self, "_interactive_widgets", []):
            try:
                widget.configure(state=state)
            except Exception:
                pass
        if enabled:
            try:
                self.value_combo.configure(state="readonly")
            except Exception:
                pass
            self._on_scale_mode_changed()
        else:
            try:
                self.vmin_entry.configure(state="disabled")
                self.vmax_entry.configure(state="disabled")
            except Exception:
                pass
            if hasattr(self, "range_slider"):
                try:
                    self.range_slider.set_enabled(False)
                except Exception:
                    pass

    def _start_initial_load(self):
        if self._data_ready:
            return

        def worker():
            try:
                ds = DataSource.from_input(self.input_path)
                vars_ = ds.list_value_columns()
                if not vars_:
                    raise ValueError("入力データに利用可能な変数が見つかりませんでした。")
                base_dx, base_dy = 1.0, 1.0
                try:
                    frame0 = ds.get_frame(step=1, value_col=vars_[0])
                    x0, y0, _ = frame_to_grids(frame0, value_col=vars_[0])
                    base_dx, base_dy = estimate_grid_spacing(x0, y0)
                except Exception:
                    base_dx, base_dy = 1.0, 1.0
            except Exception as e:
                err = e

                def on_err(err=err):
                    messagebox.showerror("エラー", f"入力データの読み込みに失敗しました:\n{err}")
                    self.destroy()

                self.after(0, on_err)
                return

            def on_done():
                self._data_source = ds
                self._data_ready = True
                self._value_columns = vars_
                self._base_dx = base_dx
                self._base_dy = base_dy
                self._base_spacing_ready = True
                self._step_count = max(1, ds.step_count)
                self.step_spin.configure(to=self._step_count)
                self.status_var.set("")
                self._init_defaults()
                self._set_controls_enabled(True)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _build_edit_canvas(self, parent):
        self.edit_canvas = tk.Canvas(parent, highlightthickness=0, background="#ffffff")
        self.edit_canvas.pack(fill="both", expand=True)

        self.edit_canvas.bind("<ButtonPress-1>", self._on_edit_press)
        self.edit_canvas.bind("<B1-Motion>", self._on_edit_motion)
        self.edit_canvas.bind("<ButtonRelease-1>", self._on_edit_release)
        self.edit_canvas.bind("<MouseWheel>", self._on_edit_scroll)
        self.edit_canvas.bind("<Control-MouseWheel>", self._on_edit_scroll)
        self.edit_canvas.bind("<Control-Button-4>", self._on_edit_scroll)
        self.edit_canvas.bind("<Control-Button-5>", self._on_edit_scroll)
        self.edit_canvas.bind("<Configure>", self._on_edit_configure)

    def _build_preview(self, parent):
        # Matplotlib は重いので遅延 import
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self.preview_fig = Figure(figsize=(6, 4), dpi=100)
        self.preview_ax = self.preview_fig.add_subplot(111)

        self.preview_canvas = FigureCanvasTkAgg(self.preview_fig, master=parent)
        self.preview_canvas.get_tk_widget().pack(fill="both", expand=True)

        self.mesh = None
        self.cbar = None

    def _init_defaults(self):
        if self._data_source is None:
            return
        vars_ = self._value_columns
        if vars_ is None:
            try:
                vars_ = self._data_source.list_value_columns()
            except Exception as e:
                messagebox.showerror("エラー", f"入力データの変数取得に失敗しました:\n{e}")
                self.destroy()
                return
            if not vars_:
                messagebox.showerror("エラー", "入力データに利用可能な変数が見つかりませんでした。")
                self.destroy()
                return
            self._value_columns = vars_

        self.value_combo["values"] = vars_
        self.value_var.set(vars_[0])

        xmin, xmax, ymin, ymax = self._data_source.domain_bounds
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        width = max(xmax - xmin, 1e-12)
        height = max(ymax - ymin, 1e-12)
        self._set_roi_vars(Roi(cx=cx, cy=cy, width=width, height=height, angle_deg=0.0))

        pad_x = max(width * 0.10, 1e-12)
        pad_y = max(height * 0.10, 1e-12)
        self._edit_base_bounds = (xmin - pad_x, xmax + pad_x, ymin - pad_y, ymax + pad_y)
        self._edit_view_bounds = self._edit_base_bounds

        if not self._base_spacing_ready:
            try:
                frame0 = self._data_source.get_frame(step=1, value_col=self.value_var.get())
                x0, y0, _ = frame_to_grids(frame0, value_col=self.value_var.get())
                self._base_dx, self._base_dy = estimate_grid_spacing(x0, y0)
            except Exception:
                self._base_dx, self._base_dy = 1.0, 1.0
            self._base_spacing_ready = True
        self.resolution_var.set(1.0)

        self._on_scale_mode_changed()
        self._on_output_option_changed()
        self._roi_confirmed = False
        self._schedule_view_update(immediate=True)

    def _on_close(self):
        try:
            if self._data_source is not None:
                self._data_source.close()
        finally:
            self.destroy()

    def _on_value_changed(self):
        self._preview_frame_cache.clear()
        self._invalidate_global_scale()
        self._edit_map_dirty = True
        self._schedule_view_update(immediate=True)

    def _on_step_changed(self):
        if self._step_var_lock:
            return
        if self._data_source is None:
            return
        try:
            step = int(self.step_var.get())
        except Exception:
            return
        step = max(1, min(step, self._data_source.step_count))
        if step != self.step_var.get():
            self._step_var_lock = True
            try:
                self.step_var.set(step)
            finally:
                self._step_var_lock = False
        self._edit_map_dirty = True
        self._schedule_view_update(immediate=True)

    def _choose_color(self, var: tk.StringVar):
        current = var.get()
        _, hex_color = colorchooser.askcolor(color=current, parent=self)
        if hex_color:
            var.set(hex_color)

    def _on_color_changed(self):
        self.min_color_sample.configure(background=self.min_color_var.get())
        self.max_color_sample.configure(background=self.max_color_var.get())
        self._edit_map_dirty = True
        self._schedule_view_update()

    def _on_resolution_changed(self):
        self._invalidate_global_scale()
        self._schedule_view_update()

    def _on_scale_mode_changed(self):
        manual = self.scale_mode.get() == "manual"
        self.vmin_entry.configure(state="normal" if manual else "disabled")
        self.vmax_entry.configure(state="normal" if manual else "disabled")
        if hasattr(self, "range_slider"):
            self.range_slider.set_enabled(manual and self._auto_range is not None)
        if manual:
            self._ensure_manual_scale_defaults()
            self._sync_slider_from_vars()
        self._edit_map_dirty = True
        self._schedule_view_update(immediate=True)

    def _on_manual_scale_changed(self):
        if self.scale_mode.get() != "manual":
            return
        if self._scale_var_lock:
            return
        self._clamp_manual_scale()
        self._update_scale_ratio_from_vars()
        self._sync_slider_from_vars()
        self._edit_map_dirty = True
        self._schedule_view_update()

    def _on_output_option_changed(self):
        if self._output_opts_lock:
            return
        self._edit_map_dirty = True
        self._schedule_view_update(immediate=True)

    def _reset_roi_to_full(self):
        if self._data_source is None:
            return
        xmin, xmax, ymin, ymax = self._data_source.domain_bounds
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        width = max(xmax - xmin, 1e-12)
        height = max(ymax - ymin, 1e-12)
        self._apply_roi_update(
            Roi(cx=cx, cy=cy, width=width, height=height, angle_deg=0.0),
            update_vars=True,
            schedule_views=True,
            invalidate_scale=True,
            confirm=True,
        )
        self._reset_edit_view()

    def _invalidate_global_scale(self):
        self._global_scale.token += 1
        self._global_scale.vmin = None
        self._global_scale.vmax = None
        self._clear_auto_range()

    def _on_roi_changed(self):
        if self._roi_var_lock:
            return
        self._roi_confirmed = False
        self._invalidate_global_scale()
        try:
            roi = self._get_roi()
        except Exception:
            return
        self._update_edit_roi_artists(roi)
        self._schedule_view_update()

    def _get_roi(self) -> Roi:
        try:
            cx = float(self.cx_var.get())
            cy = float(self.cy_var.get())
            width = float(self.width_var.get())
            height = float(self.height_var.get())
            angle = float(self.angle_var.get())
        except Exception as e:
            raise ValueError("ROI の数値が不正です。") from e
        roi = Roi(cx=cx, cy=cy, width=width, height=height, angle_deg=angle)
        return self._clamp_roi_for_edit(roi)

    def _on_roi_entry_confirm(self, _event=None):
        if self._data_source is None:
            return
        try:
            roi = self._get_roi()
        except Exception:
            return
        self._apply_roi_update(roi, schedule_views=True, invalidate_scale=True, confirm=True)

    def _get_scale(self) -> tuple[float, float] | None:
        if self.scale_mode.get() == "manual":
            return float(self.vmin_var.get()), float(self.vmax_var.get())
        if self._global_scale.vmin is not None and self._global_scale.vmax is not None:
            return self._global_scale.vmin, self._global_scale.vmax
        return None

    def _get_output_options(self) -> dict[str, object]:
        return {
            "show_title": bool(self.show_title_var.get()),
            "show_step": bool(self.show_step_var.get()),
            "show_time": bool(self.show_time_var.get()),
            "show_value": bool(self.show_value_var.get()),
            "show_ticks": bool(self.show_ticks_var.get()),
            "show_frame": bool(self.show_frame_var.get()),
            "show_cbar": bool(self.show_cbar_var.get()),
            "cbar_width": 0.04,
            "cbar_pad": 0.02,
        }

    def _set_manual_scale_vars(self, vmin: float, vmax: float):
        self._scale_var_lock = True
        try:
            self.vmin_var.set(vmin)
            self.vmax_var.set(vmax)
        finally:
            self._scale_var_lock = False

    def _ensure_manual_scale_defaults(self):
        if self._auto_range is None:
            return
        auto_min, auto_max = self._auto_range
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())
        except Exception:
            self._set_manual_scale_vars(auto_min, auto_max)
            self._scale_ratio = (0.0, 1.0)
            return
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
            self._set_manual_scale_vars(auto_min, auto_max)
            self._scale_ratio = (0.0, 1.0)

    def _clamp_manual_scale(self) -> bool:
        if self._auto_range is None:
            return False
        auto_min, auto_max = self._auto_range
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())
        except Exception:
            self._set_manual_scale_vars(auto_min, auto_max)
            return True
        if not np.isfinite(vmin) or not np.isfinite(vmax):
            self._set_manual_scale_vars(auto_min, auto_max)
            return True
        vmin = min(max(vmin, auto_min), auto_max)
        vmax = min(max(vmax, auto_min), auto_max)
        if vmin >= vmax:
            span = max(auto_max - auto_min, 1e-12)
            eps = max(span * 1e-6, 1e-12)
            vmin = min(max(vmin, auto_min), auto_max - eps)
            vmax = min(max(vmax, vmin + eps), auto_max)
        if vmin != float(self.vmin_var.get()) or vmax != float(self.vmax_var.get()):
            self._set_manual_scale_vars(vmin, vmax)
            return True
        return False

    def _sync_slider_from_vars(self):
        if self._slider_lock or self._auto_range is None:
            return
        if not hasattr(self, "range_slider"):
            return
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())
        except Exception:
            return
        self._slider_lock = True
        try:
            self.range_slider.set_values(vmin, vmax)
        finally:
            self._slider_lock = False

    def _on_range_slider_changed(self, vmin: float, vmax: float):
        if self.scale_mode.get() != "manual":
            return
        if self._slider_lock:
            return
        self._set_manual_scale_vars(vmin, vmax)
        self._update_scale_ratio_from_values(vmin, vmax)
        self._edit_map_dirty = True
        self._schedule_view_update()

    def _set_auto_range(self, vmin: float, vmax: float):
        if not np.isfinite(vmin) or not np.isfinite(vmax):
            return
        if vmin == vmax:
            vmax = vmin + 1e-12
        if vmax < vmin:
            vmin, vmax = vmax, vmin
        self._auto_range = (float(vmin), float(vmax))
        ratio = self._clamp_ratio(*self._scale_ratio)
        self._scale_ratio = ratio
        new_vmin, new_vmax = self._values_from_ratio(ratio[0], ratio[1])
        if hasattr(self, "range_slider"):
            self.range_slider.set_range(vmin, vmax, keep_values=False)
            self.range_slider.set_values(new_vmin, new_vmax)
            if self.scale_mode.get() == "manual":
                self.range_slider.set_enabled(True)
        changed = self._set_manual_scale_vars_if_changed(new_vmin, new_vmax)
        if self.scale_mode.get() == "manual":
            self._sync_slider_from_vars()
            if changed:
                self._schedule_view_update()

    def _clear_auto_range(self):
        self._auto_range = None
        if hasattr(self, "range_slider"):
            self.range_slider.set_enabled(False)

    def _set_manual_scale_vars_if_changed(self, vmin: float, vmax: float) -> bool:
        try:
            cur_vmin = float(self.vmin_var.get())
            cur_vmax = float(self.vmax_var.get())
        except Exception:
            self._set_manual_scale_vars(vmin, vmax)
            return True
        if cur_vmin == vmin and cur_vmax == vmax:
            return False
        self._set_manual_scale_vars(vmin, vmax)
        return True

    def _clamp_ratio(self, rmin: float, rmax: float) -> tuple[float, float]:
        rmin = min(max(float(rmin), 0.0), 1.0)
        rmax = min(max(float(rmax), 0.0), 1.0)
        if rmax < rmin:
            rmin, rmax = rmax, rmin
        eps = 1e-6
        if rmax - rmin < eps:
            if rmin + eps <= 1.0:
                rmax = rmin + eps
            elif rmax - eps >= 0.0:
                rmin = rmax - eps
        return rmin, rmax

    def _values_from_ratio(self, rmin: float, rmax: float) -> tuple[float, float]:
        if self._auto_range is None:
            return rmin, rmax
        auto_min, auto_max = self._auto_range
        span = max(auto_max - auto_min, 1e-12)
        return auto_min + rmin * span, auto_min + rmax * span

    def _ratio_from_values(self, vmin: float, vmax: float) -> tuple[float, float]:
        if self._auto_range is None:
            return self._scale_ratio
        auto_min, auto_max = self._auto_range
        span = max(auto_max - auto_min, 1e-12)
        rmin = (vmin - auto_min) / span
        rmax = (vmax - auto_min) / span
        return self._clamp_ratio(rmin, rmax)

    def _update_scale_ratio_from_values(self, vmin: float, vmax: float):
        if self._auto_range is None:
            return
        self._scale_ratio = self._ratio_from_values(vmin, vmax)

    def _update_scale_ratio_from_vars(self):
        if self._auto_range is None:
            return
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())
        except Exception:
            return
        self._scale_ratio = self._ratio_from_values(vmin, vmax)


    def _get_resolution(self) -> tuple[float, float]:
        scale = float(self.resolution_var.get() or 1.0)
        if scale <= 0:
            raise ValueError("解像度倍率は正の値である必要があります。")
        dx = self._base_dx / scale
        dy = self._base_dy / scale
        if dx <= 0 or dy <= 0:
            raise ValueError("解像度設定が不正です。")
        return dx, dy

    def _schedule_view_update(self, immediate: bool = False):
        if hasattr(self, "_preview_job") and self._preview_job:
            try:
                self.after_cancel(self._preview_job)
            except Exception:
                pass
        delay = 0 if immediate else 200
        self._preview_job = self.after(delay, self._update_views)

    def _update_views(self):
        if self._data_source is None or not self._data_ready:
            return
        value_col = self.value_var.get().strip()
        if not value_col:
            return

        try:
            roi = self._get_roi()
        except Exception:
            return
        try:
            dx, dy = self._get_resolution()
        except Exception as e:
            self.status_var.set(str(e))
            return

        current_step = int(self.step_var.get() or 1)
        step = max(1, min(current_step, self._data_source.step_count))
        if step != current_step:
            self._step_var_lock = True
            try:
                self.step_var.set(step)
            finally:
                self._step_var_lock = False

        output_opts = self._get_output_options()

        # global スケールの計算（非同期）
        if not self._preview_dragging and self._roi_confirmed:
            self._ensure_global_scale_async(value_col, roi, dx, dy)

        try:
            frame = self._get_preview_frame(step, value_col)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビューデータの取得に失敗しました:\n{e}")
            return

        cmap = build_colormap(self.min_color_var.get(), self.max_color_var.get())
        if self._edit_map_dirty or self._edit_image_id is None:
            try:
                # Keep edit background scale tied to full-domain values (ROI independent).
                self._update_edit_view(frame, value_col, roi, cmap, None)
                self._edit_map_dirty = False
            except Exception as e:
                self.status_var.set("")
                messagebox.showerror("エラー", f"編集表示の描画に失敗しました:\n{e}")
                return
        else:
            self._update_edit_roi_artists(roi)

        if not self._roi_confirmed:
            self.status_var.set("ROI確定待ち")
            self._draw_pending_preview(roi, output_opts)
            return

        scale = self._get_scale()
        self._update_preview_view(frame, value_col, roi, dx, dy, cmap, scale, output_opts)

    def _update_preview_view(self, frame, value_col, roi: Roi, dx: float, dy: float, cmap, scale, output_opts):
        self._last_output_opts = output_opts
        try:
            x, y, v = frame_to_grids(frame, value_col=value_col)
            bounds = roi_bounds(roi)
            grid = slice_grids_to_bounds(x, y, v, bounds=bounds)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビュー描画用データの準備に失敗しました:\n{e}")
            return None

        if grid is None:
            self.status_var.set("ROI内に点がありません")
            self._draw_empty_preview(roi, output_opts)
            return None

        dx_p, dy_p = dx, dy
        status_note = ""
        if self._preview_dragging:
            preview_max = 60000
            base_dx, base_dy = estimate_grid_spacing(grid.x, grid.y)
            fx = base_dx / dx if dx > 0 else 1.0
            fy = base_dy / dy if dy > 0 else 1.0
            if not np.isfinite(fx) or fx <= 0:
                fx = 1.0
            if not np.isfinite(fy) or fy <= 0:
                fy = 1.0
            est_points = grid.x.size * fx * fy
            if est_points > preview_max:
                scale_factor = math.sqrt(est_points / preview_max)
                dx_p = dx * scale_factor
                dy_p = dy * scale_factor
                scale_preview = (self._base_dx / dx_p) if dx_p > 0 else 0.0
                if scale_preview > 0:
                    status_note = f"プレビュー軽量化のため解像度倍率を {scale_preview:.3g} に調整しました"
                else:
                    status_note = "プレビュー軽量化のため解像度を調整しました"

        try:
            prepared = prepare_rotated_grid_from_grid(
                grid,
                roi=roi,
                dx=dx_p,
                dy=dy_p,
                local_origin=True,
            )
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビュー補間の準備に失敗しました:\n{e}")
            return None
        out_x, out_y, vals_resampled, mask = prepared

        if not np.any(mask):
            self.status_var.set("ROI内に点がありません")
            self._draw_empty_preview(roi, output_opts)
            return None

        finite = vals_resampled[np.isfinite(vals_resampled) & mask]

        if scale is None:
            if finite.size:
                vmin, vmax = float(finite.min()), float(finite.max())
            else:
                vmin, vmax = 0.0, 1.0
            if not status_note and self.scale_mode.get() == "global":
                if self._roi_confirmed:
                    status_note = "globalスケール計算中（暫定表示）"
                else:
                    status_note = "globalスケール未確定（ROI確定待ち）"
        else:
            vmin, vmax = scale
            status_note = ""

        self.status_var.set(status_note)
        self._draw_preview(
            x=out_x,
            y=out_y,
            vals=vals_resampled,
            roi=roi,
            value_col=value_col,
            step=frame.step,
            t=frame.time,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            output_opts=output_opts,
        )
        return vmin, vmax

    def _update_edit_view(self, frame, value_col, roi: Roi, cmap, scale):
        self._edit_context = {"step": frame.step, "time": frame.time, "value": value_col}
        edit_cmap = self._edit_colormap()
        self._edit_render_context = {
            "frame": frame,
            "value_col": value_col,
            "cmap": edit_cmap,
            "scale": scale,
        }
        self._render_edit_background(frame, value_col, edit_cmap, scale)
        self._update_edit_roi_artists(roi)

    def _edit_colormap(self):
        from matplotlib import cm

        return cm.get_cmap("Greys")

    def _edit_canvas_size(self) -> tuple[int, int]:
        if self.edit_canvas is None:
            return 1, 1
        width = max(int(self.edit_canvas.winfo_width()), 1)
        height = max(int(self.edit_canvas.winfo_height()), 1)
        return width, height

    def _fit_bounds_to_canvas(
        self, bounds: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        xmin, xmax, ymin, ymax = bounds
        width, height = self._edit_canvas_size()
        if width <= 0 or height <= 0:
            return bounds
        span_x = max(xmax - xmin, 1e-12)
        span_y = max(ymax - ymin, 1e-12)
        canvas_ratio = width / height
        bounds_ratio = span_x / span_y
        if abs(bounds_ratio - canvas_ratio) < 1e-6:
            return bounds
        if bounds_ratio > canvas_ratio:
            new_span_y = span_x / canvas_ratio
            pad = (new_span_y - span_y) * 0.5
            ymin -= pad
            ymax += pad
        else:
            new_span_x = span_y * canvas_ratio
            pad = (new_span_x - span_x) * 0.5
            xmin -= pad
            xmax += pad
        return xmin, xmax, ymin, ymax

    def _edit_view_bounds_or_base(self) -> tuple[float, float, float, float]:
        if self._edit_view_bounds is not None:
            return self._fit_bounds_to_canvas(self._edit_view_bounds)
        if self._edit_base_bounds is not None:
            return self._fit_bounds_to_canvas(self._edit_base_bounds)
        if self._data_source is not None:
            return self._fit_bounds_to_canvas(self._data_source.domain_bounds)
        return self._fit_bounds_to_canvas((0.0, 1.0, 0.0, 1.0))

    def _roi_edit_bounds(self) -> tuple[float, float, float, float]:
        if self._edit_base_bounds is not None:
            return self._fit_bounds_to_canvas(self._edit_base_bounds)
        if self._data_source is not None:
            return self._fit_bounds_to_canvas(self._data_source.domain_bounds)
        return self._fit_bounds_to_canvas((0.0, 1.0, 0.0, 1.0))

    def _roi_min_size(self) -> tuple[float, float]:
        min_w = float(self._base_dx)
        min_h = float(self._base_dy)
        if not np.isfinite(min_w) or min_w <= 0:
            min_w = 1.0
        if not np.isfinite(min_h) or min_h <= 0:
            min_h = 1.0
        return min_w, min_h

    def _clamp_roi_for_edit(self, roi: Roi) -> Roi:
        min_w, min_h = self._roi_min_size()
        width = max(abs(float(roi.width)), min_w)
        height = max(abs(float(roi.height)), min_h)
        roi = Roi(cx=roi.cx, cy=roi.cy, width=width, height=height, angle_deg=float(roi.angle_deg))
        return clamp_roi_to_bounds(roi, self._roi_edit_bounds())

    def _edit_transform(self):
        xmin, xmax, ymin, ymax = self._edit_view_bounds_or_base()
        width, height = self._edit_canvas_size()
        span_x = max(xmax - xmin, 1e-12)
        span_y = max(ymax - ymin, 1e-12)
        scale = width / span_x
        return (xmin, xmax, ymin, ymax), scale, 0.0, 0.0

    def _edit_zoom_ratio(self) -> float:
        if self._edit_base_bounds is None:
            return 1.0
        base = self._fit_bounds_to_canvas(self._edit_base_bounds)
        view = self._edit_view_bounds_or_base()
        base_span = max(base[1] - base[0], 1e-12)
        view_span = max(view[1] - view[0], 1e-12)
        return base_span / view_span

    def _data_to_canvas(self, x: float, y: float) -> tuple[float, float] | None:
        (xmin, xmax, ymin, ymax), scale, offset_x, offset_y = self._edit_transform()
        if scale <= 0:
            return None
        cx = offset_x + (x - xmin) * scale
        cy = offset_y + (ymax - y) * scale
        return cx, cy

    def _canvas_to_data(self, cx: float, cy: float) -> tuple[float, float] | None:
        (xmin, xmax, ymin, ymax), scale, offset_x, offset_y = self._edit_transform()
        if scale <= 0:
            return None
        x = xmin + (cx - offset_x) / scale
        y = ymax - (cy - offset_y) / scale
        return x, y

    def _update_canvas_rect(
        self,
        rect_id: int | None,
        bounds: tuple[float, float, float, float],
        *,
        outline: str,
        dash: tuple[int, int] | None = None,
    ) -> int | None:
        if self.edit_canvas is None:
            return rect_id
        xmin, xmax, ymin, ymax = bounds
        p1 = self._data_to_canvas(xmin, ymax)
        p2 = self._data_to_canvas(xmax, ymin)
        if p1 is None or p2 is None:
            return rect_id
        if rect_id is None:
            rect_id = self.edit_canvas.create_rectangle(
                p1[0],
                p1[1],
                p2[0],
                p2[1],
                outline=outline,
                dash=dash,
                width=1,
            )
        else:
            self.edit_canvas.coords(rect_id, p1[0], p1[1], p2[0], p2[1])
            self.edit_canvas.itemconfig(rect_id, outline=outline, dash=dash, width=1)
        return rect_id

    def _update_canvas_text_with_bg(
        self,
        text_id: int | None,
        bg_id: int | None,
        text: str,
        *,
        x: float,
        y: float,
        anchor: str,
    ) -> tuple[int | None, int | None]:
        if self.edit_canvas is None:
            return text_id, bg_id
        if text_id is None:
            text_id = self.edit_canvas.create_text(
                x,
                y,
                anchor=anchor,
                text=text,
                fill="#333333",
                font=("TkDefaultFont", 9),
            )
        else:
            self.edit_canvas.coords(text_id, x, y)
            self.edit_canvas.itemconfig(
                text_id,
                text=text,
                anchor=anchor,
                fill="#333333",
                font=("TkDefaultFont", 9),
            )
        bbox = self.edit_canvas.bbox(text_id)
        if bbox:
            pad = 3
            rect_coords = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
            if bg_id is None:
                bg_id = self.edit_canvas.create_rectangle(
                    *rect_coords,
                    fill="#ffffff",
                    outline="#dddddd",
                    width=1,
                )
            else:
                self.edit_canvas.coords(bg_id, *rect_coords)
                self.edit_canvas.itemconfig(bg_id, fill="#ffffff", outline="#dddddd", width=1)
            self.edit_canvas.tag_lower(bg_id, text_id)
        return text_id, bg_id

    def _update_edit_bounds_overlay(self):
        if self.edit_canvas is None or self._data_source is None:
            return
        if self._edit_domain_rect_id is not None:
            self.edit_canvas.delete(self._edit_domain_rect_id)
            self._edit_domain_rect_id = None
        if self._edit_pad_rect_id is not None:
            self.edit_canvas.delete(self._edit_pad_rect_id)
            self._edit_pad_rect_id = None

    def _update_edit_overlay_text(self):
        if self.edit_canvas is None:
            return
        step = self._edit_context.get("step")
        time_val = self._edit_context.get("time")
        value_col = self._edit_context.get("value")
        zoom = self._edit_zoom_ratio()

        lines = ["編集ビュー（全体表示）", "表示: 全体+余白"]
        if step is not None:
            if time_val is None:
                lines.append(f"step={step}  value={value_col}")
            else:
                lines.append(f"step={step}  t={time_val:g}  value={value_col}")
        lines.append("スケール: 全体min/max（1ステップ）")
        lines.append(f"ズーム: {zoom:.2f}x")
        text = "\n".join(lines)

        self._edit_overlay_text_id, self._edit_overlay_bg_id = self._update_canvas_text_with_bg(
            self._edit_overlay_text_id,
            self._edit_overlay_bg_id,
            text,
            x=8,
            y=6,
            anchor="nw",
        )

        guide = "ドラッグ: 移動\nハンドル: 拡縮 / 回転\nCtrl+ホイール: ズーム"
        width, height = self._edit_canvas_size()
        self._edit_hint_text_id, self._edit_hint_bg_id = self._update_canvas_text_with_bg(
            self._edit_hint_text_id,
            self._edit_hint_bg_id,
            guide,
            x=8,
            y=height - 6,
            anchor="sw",
        )

    def _update_edit_overlay(self):
        if self.edit_canvas is None:
            return
        self._update_edit_outline()
        self._update_edit_bounds_overlay()
        if self._roi_patch is not None:
            if self._edit_pad_rect_id is not None:
                self.edit_canvas.tag_lower(self._edit_pad_rect_id, self._roi_patch)
            if self._edit_domain_rect_id is not None:
                self.edit_canvas.tag_lower(self._edit_domain_rect_id, self._roi_patch)
        self._update_edit_overlay_text()
        for item_id in (
            self._edit_overlay_bg_id,
            self._edit_overlay_text_id,
            self._edit_hint_bg_id,
            self._edit_hint_text_id,
        ):
            if item_id is not None:
                self.edit_canvas.tag_raise(item_id)

    def _compute_grid_outline(self, grid: RoiGrid) -> np.ndarray | None:
        try:
            x = np.asarray(grid.x, dtype=float)
            y = np.asarray(grid.y, dtype=float)
        except Exception:
            return None
        if x.size == 0 or y.size == 0:
            return None
        top = np.column_stack([x[0, :], y[0, :]])
        right = np.column_stack([x[1:, -1], y[1:, -1]])
        bottom = np.column_stack([x[-1, -2::-1], y[-1, -2::-1]])
        left = np.column_stack([x[-2:0:-1, 0], y[-2:0:-1, 0]])
        outline = np.vstack([top, right, bottom, left, top[:1]])
        return outline

    def _update_edit_outline(self):
        if self.edit_canvas is None:
            return
        outline = self._edit_outline_points
        if outline is None or outline.size == 0:
            if self._edit_outline_id is not None:
                self.edit_canvas.delete(self._edit_outline_id)
                self._edit_outline_id = None
            return
        coords: list[float] = []
        for x, y in outline:
            pt = self._data_to_canvas(float(x), float(y))
            if pt is None:
                continue
            coords.extend([pt[0], pt[1]])
        if len(coords) < 4:
            return
        if self._edit_outline_id is None:
            self._edit_outline_id = self.edit_canvas.create_line(
                *coords,
                fill="#666666",
                width=1,
                smooth=False,
            )
        else:
            self.edit_canvas.coords(self._edit_outline_id, *coords)
            self.edit_canvas.itemconfig(self._edit_outline_id, fill="#666666", width=1)

    def _render_edit_background(self, frame, value_col, cmap, scale):
        width, height = self._edit_canvas_size()
        if width < 2 or height < 2:
            return

        x, y, v = frame_to_grids(frame, value_col=value_col)
        grid = RoiGrid(x=x, y=y, v=v, mask=np.ones_like(v, dtype=bool))
        grid = downsample_grid_for_preview(grid, max_points=40000)
        self._edit_outline_points = self._compute_grid_outline(grid)

        vals = np.asarray(grid.v, dtype=float)
        if scale is None:
            finite = vals[np.isfinite(vals)]
            if finite.size:
                vmin, vmax = float(finite.min()), float(finite.max())
            else:
                vmin, vmax = 0.0, 1.0
        else:
            vmin, vmax = scale

        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        dpi = 100
        if self._edit_fig is None:
            self._edit_fig = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
            self._edit_ax = self._edit_fig.add_axes([0, 0, 1, 1])
            self._edit_agg = FigureCanvasAgg(self._edit_fig)
        else:
            self._edit_fig.set_size_inches(width / dpi, height / dpi, forward=True)

        ax = self._edit_ax
        ax.clear()
        ax.set_axis_off()
        ax.set_aspect("equal", adjustable="box")
        bounds = self._edit_view_bounds_or_base()
        ax.set_xlim(bounds[0], bounds[1])
        ax.set_ylim(bounds[2], bounds[3])
        ax.pcolormesh(
            grid.x,
            grid.y,
            vals,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            shading="gouraud",
        )

        assert self._edit_agg is not None
        self._edit_agg.draw()
        buf = io.BytesIO()
        self._edit_agg.print_png(buf)
        png_data = base64.b64encode(buf.getvalue()).decode("ascii")
        self._edit_image_tk = tk.PhotoImage(data=png_data)

        if self._edit_image_id is None:
            self._edit_image_id = self.edit_canvas.create_image(0, 0, anchor="nw", image=self._edit_image_tk)
        else:
            self.edit_canvas.itemconfig(self._edit_image_id, image=self._edit_image_tk)
        self.edit_canvas.tag_lower(self._edit_image_id)
        self._update_edit_outline()

    def _schedule_edit_background_render(self, immediate: bool = False):
        if self._edit_render_context is None:
            return
        if self._edit_render_job is not None:
            try:
                self.after_cancel(self._edit_render_job)
            except Exception:
                pass
        delay = 0 if immediate else 120
        self._edit_render_job = self.after(delay, self._render_edit_background_from_context)

    def _render_edit_background_from_context(self):
        self._edit_render_job = None
        context = self._edit_render_context
        if context is None:
            return
        self._render_edit_background(
            context["frame"],
            context["value_col"],
            context["cmap"],
            context["scale"],
        )
        self._edit_map_dirty = False

    def _on_edit_configure(self, _event):
        if self._data_source is None:
            return
        if self._edit_view_bounds is not None:
            self._edit_view_bounds = self._fit_bounds_to_canvas(self._edit_view_bounds)
        elif self._edit_base_bounds is not None:
            self._edit_view_bounds = self._fit_bounds_to_canvas(self._edit_base_bounds)
        self._edit_map_dirty = True
        self._schedule_edit_background_render()
        try:
            roi = self._get_roi()
        except Exception:
            return
        self._update_edit_roi_artists(roi)

    def _set_roi_vars(self, roi: Roi):
        angle = float(roi.angle_deg)
        while angle <= -180:
            angle += 360
        while angle > 180:
            angle -= 360
        self._roi_var_lock = True
        try:
            self.cx_var.set(roi.cx)
            self.cy_var.set(roi.cy)
            self.width_var.set(roi.width)
            self.height_var.set(roi.height)
            self.angle_var.set(angle)
        finally:
            self._roi_var_lock = False

    def _apply_roi_update(
        self,
        roi: Roi,
        *,
        update_vars: bool = True,
        schedule_views: bool = True,
        invalidate_scale: bool = True,
        confirm: bool | None = None,
    ):
        roi = self._clamp_roi_for_edit(roi)
        if update_vars:
            self._set_roi_vars(roi)
        if confirm is True:
            self._roi_confirmed = True
        elif confirm is False:
            self._roi_confirmed = False
        self._update_edit_roi_artists(roi)
        if invalidate_scale:
            self._invalidate_global_scale()
        if schedule_views:
            self._schedule_view_update()

    def _reset_edit_view(self):
        if self._edit_base_bounds is None:
            return
        self._edit_view_bounds = self._fit_bounds_to_canvas(self._edit_base_bounds)
        self._edit_map_dirty = True
        self._schedule_edit_background_render(immediate=True)

    def _update_edit_roi_artists(self, roi: Roi):
        if self.edit_canvas is None:
            return
        corners = roi_corners(roi)
        canvas_corners = []
        for x, y in corners:
            pt = self._data_to_canvas(float(x), float(y))
            if pt is None:
                return
            canvas_corners.extend([pt[0], pt[1]])

        theta = math.radians(roi.angle_deg)
        ux = np.array([math.cos(theta), math.sin(theta)])
        uy = np.array([-math.sin(theta), math.cos(theta)])
        half_w = 0.5 * roi.width
        half_h = 0.5 * roi.height
        width_vec = half_w * ux
        height_vec = half_h * uy

        handle_radius = 6.0
        (_, _, _, _), scale, _, _ = self._edit_transform()
        if scale <= 0:
            scale = 1.0
        rotate_offset_px = max(handle_radius * 3.0, 18.0)
        rotate_offset = rotate_offset_px / scale
        rotate_vec = (half_h + rotate_offset) * uy
        handles = [
            ("width", 1, roi.cx + width_vec[0], roi.cy + width_vec[1]),
            ("width", -1, roi.cx - width_vec[0], roi.cy - width_vec[1]),
            ("height", 1, roi.cx + height_vec[0], roi.cy + height_vec[1]),
            ("height", -1, roi.cx - height_vec[0], roi.cy - height_vec[1]),
            ("rotate", 0, roi.cx + rotate_vec[0], roi.cy + rotate_vec[1]),
        ]

        bottom_start = self._data_to_canvas(float(corners[0, 0]), float(corners[0, 1]))
        bottom_end = self._data_to_canvas(float(corners[1, 0]), float(corners[1, 1]))
        top_center = np.array([roi.cx, roi.cy]) + height_vec
        rotate_pos = np.array([roi.cx + rotate_vec[0], roi.cy + rotate_vec[1]])
        top_center_canvas = self._data_to_canvas(float(top_center[0]), float(top_center[1]))
        rotate_canvas = self._data_to_canvas(float(rotate_pos[0]), float(rotate_pos[1]))

        if self._roi_patch is None:
            self._roi_patch = self.edit_canvas.create_polygon(
                canvas_corners,
                outline="#ffcc00",
                width=2,
                fill="",
                joinstyle=tk.ROUND,
            )
            self._roi_bottom_edge = self.edit_canvas.create_line(
                0,
                0,
                0,
                0,
                fill="#00bcd4",
                width=3,
            )
            self._roi_rotate_line = self.edit_canvas.create_line(
                0,
                0,
                0,
                0,
                fill="#00bcd4",
                width=1,
            )
            self._roi_handles = []
            for _ in range(5):
                hid = self.edit_canvas.create_oval(
                    0,
                    0,
                    0,
                    0,
                    fill="#ffcc00",
                    outline="#333333",
                    width=1,
                )
                self._roi_handles.append({"id": hid, "kind": "width", "sign": 1, "cx": 0.0, "cy": 0.0})
        else:
            self.edit_canvas.coords(self._roi_patch, *canvas_corners)

        if self._roi_bottom_edge is not None and bottom_start and bottom_end:
            self.edit_canvas.coords(
                self._roi_bottom_edge,
                bottom_start[0],
                bottom_start[1],
                bottom_end[0],
                bottom_end[1],
            )
        if self._roi_rotate_line is not None and top_center_canvas and rotate_canvas:
            self.edit_canvas.coords(
                self._roi_rotate_line,
                top_center_canvas[0],
                top_center_canvas[1],
                rotate_canvas[0],
                rotate_canvas[1],
            )

        for handle, (kind, sign, hx, hy) in zip(self._roi_handles, handles):
            pos = self._data_to_canvas(float(hx), float(hy))
            if pos is None:
                continue
            handle["kind"] = kind
            handle["sign"] = sign
            handle["cx"] = pos[0]
            handle["cy"] = pos[1]
            hid = handle["id"]
            self.edit_canvas.coords(
                hid,
                pos[0] - handle_radius,
                pos[1] - handle_radius,
                pos[0] + handle_radius,
                pos[1] + handle_radius,
            )
            fill = "#00bcd4" if kind == "rotate" else "#ffcc00"
            self.edit_canvas.itemconfig(hid, fill=fill)

        if self._roi_patch is not None:
            self.edit_canvas.tag_raise(self._roi_patch)
        if self._roi_bottom_edge is not None:
            self.edit_canvas.tag_raise(self._roi_bottom_edge)
        if self._roi_rotate_line is not None:
            self.edit_canvas.tag_raise(self._roi_rotate_line)
        for handle in self._roi_handles:
            self.edit_canvas.tag_raise(handle["id"])

        self._update_edit_overlay()

    def _hit_test_handle(self, event):
        if not self._roi_handles:
            return None
        ex, ey = event.x, event.y
        if ex is None or ey is None:
            return None
        min_dist = 10.0
        hit_handle = None
        for handle in self._roi_handles:
            hx = handle.get("cx")
            hy = handle.get("cy")
            if hx is None or hy is None:
                continue
            dist = math.hypot(ex - hx, ey - hy)
            if dist <= min_dist:
                min_dist = dist
                hit_handle = handle
        return hit_handle

    def _point_in_polygon(self, x: float, y: float, polygon: np.ndarray) -> bool:
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    def _on_edit_press(self, event):
        if self._data_source is None:
            return
        if event.num != 1:
            return
        pos = self._canvas_to_data(event.x, event.y)
        if pos is None:
            return
        try:
            roi = self._get_roi()
        except Exception:
            return
        handle = self._hit_test_handle(event)
        if handle:
            self._drag_state = {"mode": "handle", "kind": handle.get("kind"), "sign": handle.get("sign")}
            return
        if self._point_in_polygon(pos[0], pos[1], roi_corners(roi)):
            self._drag_state = {
                "mode": "move",
                "offset": (roi.cx - pos[0], roi.cy - pos[1]),
            }

    def _on_edit_motion(self, event):
        if self._data_source is None:
            return
        if self._drag_state is None:
            return
        pos = self._canvas_to_data(event.x, event.y)
        if pos is None:
            return
        try:
            roi = self._get_roi()
        except Exception:
            return
        xdata, ydata = pos

        mode = self._drag_state.get("mode")
        if mode == "move":
            offset = self._drag_state.get("offset", (0.0, 0.0))
            new_roi = Roi(
                cx=xdata + offset[0],
                cy=ydata + offset[1],
                width=roi.width,
                height=roi.height,
                angle_deg=roi.angle_deg,
            )
            self._drag_state["roi"] = new_roi
            self._apply_roi_update(new_roi, schedule_views=False, invalidate_scale=False, confirm=False)
            self._preview_dragging = True
            return

        if mode == "handle":
            kind = self._drag_state.get("kind")
            sign = float(self._drag_state.get("sign") or 0.0)
            vx = xdata - roi.cx
            vy = ydata - roi.cy
            min_size = 1e-9

            theta = math.radians(roi.angle_deg)
            ux = np.array([math.cos(theta), math.sin(theta)])
            uy = np.array([-math.sin(theta), math.cos(theta)])

            if kind == "rotate":
                angle = math.degrees(math.atan2(vy, vx)) - 90.0
                new_roi = Roi(
                    cx=roi.cx,
                    cy=roi.cy,
                    width=roi.width,
                    height=roi.height,
                    angle_deg=angle,
                )
            elif kind == "width":
                half_w = 0.5 * roi.width
                opposite_edge = np.array([roi.cx, roi.cy]) - sign * half_w * ux
                proj = np.dot(np.array([xdata, ydata]) - opposite_edge, ux)
                if sign >= 0:
                    proj = max(proj, min_size)
                else:
                    proj = min(proj, -min_size)
                half_new = abs(proj) * 0.5
                new_center = opposite_edge + ux * (proj * 0.5)
                new_roi = Roi(
                    cx=float(new_center[0]),
                    cy=float(new_center[1]),
                    width=float(half_new * 2.0),
                    height=roi.height,
                    angle_deg=roi.angle_deg,
                )
            elif kind == "height":
                half_h = 0.5 * roi.height
                opposite_edge = np.array([roi.cx, roi.cy]) - sign * half_h * uy
                proj = np.dot(np.array([xdata, ydata]) - opposite_edge, uy)
                if sign >= 0:
                    proj = max(proj, min_size)
                else:
                    proj = min(proj, -min_size)
                half_new = abs(proj) * 0.5
                new_center = opposite_edge + uy * (proj * 0.5)
                new_roi = Roi(
                    cx=float(new_center[0]),
                    cy=float(new_center[1]),
                    width=roi.width,
                    height=float(half_new * 2.0),
                    angle_deg=roi.angle_deg,
                )
            else:
                return
            self._drag_state["roi"] = new_roi
            self._apply_roi_update(new_roi, schedule_views=False, invalidate_scale=False, confirm=False)
            self._preview_dragging = True

    def _on_edit_release(self, event):
        if self._data_source is None:
            return
        if self._drag_state is None:
            return
        roi = self._drag_state.get("roi")
        self._drag_state = None
        self._preview_dragging = False
        if roi is not None:
            self._apply_roi_update(roi, schedule_views=True, invalidate_scale=True, confirm=True)
            self._schedule_view_update(immediate=True)

    def _on_edit_scroll(self, event):
        if self._data_source is None:
            return
        if event.state & 0x0004 == 0:
            return
        pos = self._canvas_to_data(event.x, event.y)
        if pos is None:
            return

        xmin, xmax, ymin, ymax = self._edit_view_bounds_or_base()
        cur_w = xmax - xmin
        cur_h = ymax - ymin
        if cur_w <= 0 or cur_h <= 0:
            return
        delta = getattr(event, "delta", 0)
        direction = 1 if delta > 0 or getattr(event, "num", None) == 4 else -1
        zoom = 0.9 if direction > 0 else 1.1
        new_w = cur_w * zoom
        new_h = cur_h * zoom
        relx = (pos[0] - xmin) / cur_w
        rely = (pos[1] - ymin) / cur_h

        base_fit = None
        if self._edit_base_bounds is not None:
            base_fit = self._fit_bounds_to_canvas(self._edit_base_bounds)
            base_w = base_fit[1] - base_fit[0]
            base_h = base_fit[3] - base_fit[2]
            new_w = min(new_w, base_w)
            new_h = min(new_h, base_h)

        new_xmin = pos[0] - new_w * relx
        new_xmax = pos[0] + new_w * (1 - relx)
        new_ymin = pos[1] - new_h * rely
        new_ymax = pos[1] + new_h * (1 - rely)

        if base_fit is not None:
            bxmin, bxmax, bymin, bymax = base_fit
            if new_w >= (bxmax - bxmin):
                new_xmin, new_xmax = bxmin, bxmax
            else:
                if new_xmin < bxmin:
                    shift = bxmin - new_xmin
                    new_xmin += shift
                    new_xmax += shift
                if new_xmax > bxmax:
                    shift = new_xmax - bxmax
                    new_xmin -= shift
                    new_xmax -= shift
            if new_h >= (bymax - bymin):
                new_ymin, new_ymax = bymin, bymax
            else:
                if new_ymin < bymin:
                    shift = bymin - new_ymin
                    new_ymin += shift
                    new_ymax += shift
                if new_ymax > bymax:
                    shift = new_ymax - bymax
                    new_ymin -= shift
                    new_ymax -= shift

        self._edit_view_bounds = (new_xmin, new_xmax, new_ymin, new_ymax)
        self._edit_map_dirty = True
        self._schedule_edit_background_render()
        try:
            roi = self._get_roi()
            self._update_edit_roi_artists(roi)
        except Exception:
            pass

    def _draw_empty_preview(
        self,
        roi: Roi,
        output_opts: dict[str, object] | None = None,
        *,
        title: str = "No points in ROI",
    ):
        if self.mesh is not None:
            try:
                self.mesh.remove()
            except Exception:
                pass
            self.mesh = None
        opts = output_opts or self._last_output_opts or {}
        self._apply_plot_options(ax=self.preview_ax, mesh=None, output_opts=opts)
        title = title if opts.get("show_title", True) else ""
        self.preview_ax.set_title(title)
        width = max(float(roi.width), 1e-12)
        height = max(float(roi.height), 1e-12)
        self.preview_ax.set_xlim(0.0, width)
        self.preview_ax.set_ylim(0.0, height)
        self.preview_ax.set_aspect("equal", adjustable="box")
        self.preview_canvas.draw_idle()

    def _draw_pending_preview(self, roi: Roi, output_opts: dict[str, object] | None = None):
        self._draw_empty_preview(roi, output_opts, title="ROI not confirmed")

    def _draw_preview(
        self,
        *,
        x,
        y,
        vals,
        roi: Roi,
        value_col: str,
        step: int,
        t: float,
        cmap,
        vmin: float,
        vmax: float,
        output_opts: dict[str, object],
    ):
        if self.mesh is not None:
            try:
                self.mesh.remove()
            except Exception:
                pass
            self.mesh = None
        self.mesh = self.preview_ax.pcolormesh(
            x,
            y,
            vals,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            shading="gouraud",
        )
        from matplotlib.patches import Rectangle

        width = max(float(roi.width), 1e-12)
        height = max(float(roi.height), 1e-12)
        clip_rect = Rectangle(
            (0.0, 0.0),
            width,
            height,
            transform=self.preview_ax.transData,
        )
        self.mesh.set_clip_path(clip_rect)
        self._apply_plot_options(
            ax=self.preview_ax,
            mesh=self.mesh,
            output_opts=output_opts,
        )

        title = self._build_plot_title(step=step, t=t, value_col=value_col, output_opts=output_opts)
        if title:
            self.preview_ax.set_title(title)
        else:
            self.preview_ax.set_title("")
        self.preview_ax.set_xlim(0.0, width)
        self.preview_ax.set_ylim(0.0, height)
        self.preview_ax.set_aspect("equal", adjustable="box")
        self.preview_canvas.draw_idle()

    def _build_plot_title(self, *, step: int, t: float, value_col: str, output_opts: dict[str, object]) -> str:
        if not output_opts.get("show_title", True):
            return ""
        parts: list[str] = []
        if output_opts.get("show_step", True):
            parts.append(f"step={step}")
        if output_opts.get("show_time", True):
            parts.append(f"t={t:g}")
        if output_opts.get("show_value", True):
            parts.append(f"value={value_col}")
        return "  ".join(parts)

    def _apply_plot_options(self, *, ax, mesh, output_opts: dict[str, object]):
        show_ticks = bool(output_opts.get("show_ticks", True))
        show_frame = bool(output_opts.get("show_frame", True))
        show_cbar = bool(output_opts.get("show_cbar", True))

        ax.tick_params(
            bottom=show_ticks,
            left=show_ticks,
            labelbottom=show_ticks,
            labelleft=show_ticks,
        )

        for spine in ax.spines.values():
            spine.set_visible(show_frame)

        if show_cbar:
            if mesh is None:
                if self.cbar is not None:
                    try:
                        self.cbar.ax.set_visible(False)
                    except Exception:
                        pass
                return
            if self.cbar is None:
                self.cbar = self.preview_fig.colorbar(
                    mesh,
                    ax=ax,
                    fraction=0.04,
                    pad=0.02,
                )
            else:
                try:
                    self.cbar.ax.set_visible(True)
                except Exception:
                    pass
                self.cbar.update_normal(mesh)
        else:
            if self.cbar is not None:
                try:
                    self.cbar.ax.set_visible(False)
                except Exception:
                    pass

    def _get_preview_frame(self, step: int, value_col: str):
        key = (step, value_col)
        if key in self._preview_frame_cache:
            return self._preview_frame_cache[key]
        if self._data_source is None:
            raise RuntimeError("データが読み込まれていません。")
        frame = self._data_source.get_frame(step=step, value_col=value_col)
        self._preview_frame_cache[key] = frame
        return frame

    def _ensure_global_scale_async(self, value_col: str, roi: Roi, dx: float, dy: float):
        if self._data_source is None:
            return
        if self._global_scale.running:
            return
        if self._global_scale.vmin is not None and self._global_scale.vmax is not None:
            return

        self._global_scale.running = True
        self._global_scale.token += 1
        token = self._global_scale.token
        self.status_var.set("globalスケール計算中...")

        def worker():
            try:
                vmin, vmax = compute_global_value_range_rotated(
                    self._data_source,
                    value_col=value_col,
                    roi=roi,
                    dx=dx,
                    dy=dy,
                )
            except ValueError as e:
                logger.info("globalスケール計算をスキップ: %s", e)

                def on_empty():
                    token_matches = token == self._global_scale.token
                    self._global_scale.running = False
                    if not token_matches:
                        self._schedule_view_update(immediate=True)
                        return
                    self._clear_auto_range()
                    self.status_var.set("ROI内に有効な値がありません。")

                self.after(0, on_empty)
                return
            except Exception as e:
                err = e
                logger.exception("globalスケール計算に失敗")

                def on_err(err=err):
                    token_matches = token == self._global_scale.token
                    self._global_scale.running = False
                    self.status_var.set("")
                    # 既にパラメータが変わっている場合は無視して再計算に任せる
                    if not token_matches:
                        self._schedule_view_update(immediate=True)
                        return
                    messagebox.showerror("エラー", f"globalスケール計算に失敗しました:\n{err}")

                self.after(0, on_err)
                return

            def on_done():
                token_matches = token == self._global_scale.token
                self._global_scale.running = False
                self.status_var.set("")
                if token_matches:
                    self._global_scale.vmin = vmin
                    self._global_scale.vmax = vmax
                    self._set_auto_range(vmin, vmax)
                # token 不一致の場合は最新のROI/Valueで再計算する
                self._schedule_view_update(immediate=True)

            self.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()

    def _run(self):
        value_col = self.value_var.get().strip()
        if not value_col:
            messagebox.showerror("エラー", "Value（変数）を選択してください。")
            return

        try:
            roi = self._get_roi()
        except Exception as e:
            messagebox.showerror("エラー", f"ROI が不正です:\n{e}")
            return
        try:
            dx, dy = self._get_resolution()
        except Exception as e:
            messagebox.showerror("エラー", f"解像度の指定が不正です:\n{e}")
            return

        scale_mode = self.scale_mode.get()
        if scale_mode == "manual":
            try:
                vmin = float(self.vmin_var.get())
                vmax = float(self.vmax_var.get())
            except Exception:
                messagebox.showerror("エラー", "manual の場合は vmin/vmax を数値で入力してください。")
                return
            if vmin >= vmax:
                messagebox.showerror("エラー", "vmin は vmax より小さい必要があります。")
                return
            scale = (vmin, vmax)
        else:
            scale = None

        try:
            min_color = parse_color(self.min_color_var.get())
            max_color = parse_color(self.max_color_var.get())
        except Exception as e:
            messagebox.showerror("エラー", f"色の指定が不正です:\n{e}")
            return
        output_opts = self._get_output_options()

        out_base = Path(self.output_var.get())
        out_dir = out_base / f"xy_value_map_{value_col}"

        progress = _ProgressWindow(self, title="出力中", maximum=self._data_source.step_count)
        try:
            export_xy_value_maps(
                data_source=self._data_source,
                output_dir=out_dir,
                value_col=value_col,
                roi=roi,
                min_color=min_color,
                max_color=max_color,
                scale_mode=scale_mode,
                manual_scale=scale,
                dx=dx,
                dy=dy,
                show_title=output_opts["show_title"],
                show_step=output_opts["show_step"],
                show_time=output_opts["show_time"],
                show_value=output_opts["show_value"],
                show_ticks=output_opts["show_ticks"],
                show_frame=output_opts["show_frame"],
                show_cbar=output_opts["show_cbar"],
                progress=progress,
            )
        except Exception as e:
            logger.exception("画像出力に失敗しました")
            progress.close()
            messagebox.showerror("エラー", f"画像出力に失敗しました:\n{e}")
            return
        finally:
            progress.close()

        messagebox.showinfo("完了", f"画像を出力しました:\n{out_dir}")

    def _run_single_step(self):
        value_col = self.value_var.get().strip()
        if not value_col:
            messagebox.showerror("エラー", "Value（変数）を選択してください。")
            return

        try:
            roi = self._get_roi()
        except Exception as e:
            messagebox.showerror("エラー", f"ROI が不正です:\n{e}")
            return
        try:
            dx, dy = self._get_resolution()
        except Exception as e:
            messagebox.showerror("エラー", f"解像度の指定が不正です:\n{e}")
            return

        step = int(self.step_var.get() or 1)
        step = max(1, min(step, self._data_source.step_count))
        self.step_var.set(step)

        scale_mode = self.scale_mode.get()
        if scale_mode == "manual":
            try:
                vmin = float(self.vmin_var.get())
                vmax = float(self.vmax_var.get())
            except Exception:
                messagebox.showerror("エラー", "manual の場合は vmin/vmax を数値で入力してください。")
                return
            if vmin >= vmax:
                messagebox.showerror("エラー", "vmin は vmax より小さい必要があります。")
                return
        else:
            # global が計算済みならそれを使用。未計算の場合は暫定スケール（このステップのmin/max）で出力する。
            if self._global_scale.vmin is not None and self._global_scale.vmax is not None:
                vmin, vmax = self._global_scale.vmin, self._global_scale.vmax
            else:
                msg = (
                    "global スケールがまだ計算されていないため、\n"
                    "このステップの min/max（プレビューと同じ暫定スケール）で出力します。\n"
                    "よろしいですか？"
                )
                if not messagebox.askyesno("確認", msg):
                    return
                try:
                    frame = self._get_preview_frame(step, value_col)
                    x, y, v = frame_to_grids(frame, value_col=value_col)
                    prepared = prepare_rotated_grid(
                        x,
                        y,
                        v,
                        roi=roi,
                        dx=dx,
                        dy=dy,
                        local_origin=True,
                    )
                    if prepared is None:
                        messagebox.showerror("エラー", "ROI内に点がありません。")
                        return
                    _, _, vals, mask = prepared
                    finite = vals[np.isfinite(vals) & mask]
                    if finite.size == 0:
                        messagebox.showerror("エラー", "ROI 内の Value が全て NaN/Inf です。")
                        return
                    vmin = float(finite.min())
                    vmax = float(finite.max())
                    if vmin == vmax:
                        vmax = vmin + 1e-12
                except Exception as e:
                    messagebox.showerror("エラー", f"スケール計算に失敗しました:\n{e}")
                    return

        try:
            min_color = parse_color(self.min_color_var.get())
            max_color = parse_color(self.max_color_var.get())
        except Exception as e:
            messagebox.showerror("エラー", f"色の指定が不正です:\n{e}")
            return
        output_opts = self._get_output_options()

        out_base = Path(self.output_var.get())
        out_dir = out_base / f"xy_value_map_{value_col}"

        progress = _ProgressWindow(self, title="出力中", maximum=1)
        progress.update(current=0, total=1, text=f"出力中: step={step}")
        try:
            out_path = export_xy_value_map_step(
                data_source=self._data_source,
                output_dir=out_dir,
                step=step,
                value_col=value_col,
                roi=roi,
                min_color=min_color,
                max_color=max_color,
                vmin=vmin,
                vmax=vmax,
                dx=dx,
                dy=dy,
                show_title=output_opts["show_title"],
                show_step=output_opts["show_step"],
                show_time=output_opts["show_time"],
                show_value=output_opts["show_value"],
                show_ticks=output_opts["show_ticks"],
                show_frame=output_opts["show_frame"],
                show_cbar=output_opts["show_cbar"],
            )
        except Exception as e:
            logger.exception("このステップのみ出力に失敗しました")
            progress.close()
            messagebox.showerror("エラー", f"画像出力に失敗しました:\n{e}")
            return
        finally:
            progress.close()

        messagebox.showinfo("完了", f"画像を出力しました:\n{out_path}")


class _RangeSlider(tk.Canvas):
    def __init__(self, master, *, command=None, height: int = 24):
        super().__init__(master, height=height, highlightthickness=0, background="#ffffff")
        self._command = command
        self._min = 0.0
        self._max = 1.0
        self._vmin = 0.0
        self._vmax = 1.0
        self._active: str | None = None
        self._enabled = True
        self._pad = 10
        self._radius = 6

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda _e: self._redraw())
        self._redraw()

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)
        self._redraw()

    def set_range(self, min_val: float, max_val: float, *, keep_values: bool = True):
        if not np.isfinite(min_val) or not np.isfinite(max_val):
            return
        if min_val == max_val:
            max_val = min_val + 1e-12
        if max_val < min_val:
            min_val, max_val = max_val, min_val
        self._min, self._max = float(min_val), float(max_val)
        if keep_values:
            self.set_values(self._vmin, self._vmax)
        else:
            self._vmin, self._vmax = self._min, self._max
            self._redraw()

    def set_values(self, vmin: float, vmax: float):
        if not np.isfinite(vmin) or not np.isfinite(vmax):
            return
        vmin = float(vmin)
        vmax = float(vmax)
        if vmax < vmin:
            vmin, vmax = vmax, vmin
        vmin, vmax = self._clamp_values(vmin, vmax)
        self._vmin, self._vmax = vmin, vmax
        self._redraw()

    def _track_bounds(self) -> tuple[float, float]:
        width = max(self.winfo_width(), 1)
        return self._pad, max(self._pad, width - self._pad)

    def _value_to_x(self, value: float) -> float:
        x0, x1 = self._track_bounds()
        span = max(self._max - self._min, 1e-12)
        ratio = (value - self._min) / span
        return x0 + (x1 - x0) * ratio

    def _x_to_value(self, x: float) -> float:
        x0, x1 = self._track_bounds()
        if x1 <= x0:
            return self._min
        ratio = (x - x0) / (x1 - x0)
        ratio = min(max(ratio, 0.0), 1.0)
        return self._min + (self._max - self._min) * ratio

    def _clamp_values(self, vmin: float, vmax: float) -> tuple[float, float]:
        vmin = min(max(vmin, self._min), self._max)
        vmax = min(max(vmax, self._min), self._max)
        if vmax < vmin:
            vmin, vmax = vmax, vmin
        span = max(self._max - self._min, 1e-12)
        eps = max(span * 1e-6, 1e-12)
        if vmax - vmin < eps:
            if vmin + eps <= self._max:
                vmax = vmin + eps
            elif vmax - eps >= self._min:
                vmin = vmax - eps
        return vmin, vmax

    def _emit(self):
        if self._command is not None:
            self._command(self._vmin, self._vmax)

    def _on_press(self, event):
        if not self._enabled:
            return
        x = event.x
        dist_min = abs(x - self._value_to_x(self._vmin))
        dist_max = abs(x - self._value_to_x(self._vmax))
        self._active = "min" if dist_min <= dist_max else "max"
        self._move_active(x)

    def _on_motion(self, event):
        if not self._enabled or self._active is None:
            return
        self._move_active(event.x)

    def _on_release(self, _event):
        if not self._enabled:
            return
        self._active = None

    def _move_active(self, x: float):
        value = self._x_to_value(x)
        if self._active == "min":
            vmin = min(value, self._vmax)
            vmin, vmax = self._clamp_values(vmin, self._vmax)
        else:
            vmax = max(value, self._vmin)
            vmin, vmax = self._clamp_values(self._vmin, vmax)
        if vmin == self._vmin and vmax == self._vmax:
            return
        self._vmin, self._vmax = vmin, vmax
        self._redraw()
        self._emit()

    def _redraw(self):
        self.delete("all")
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        y = height / 2.0
        x0, x1 = self._track_bounds()

        track_color = "#dddddd" if self._enabled else "#eeeeee"
        range_color = "#7aa6ff" if self._enabled else "#dddddd"
        handle_color = "#2b78e4" if self._enabled else "#aaaaaa"

        self.create_line(x0, y, x1, y, fill=track_color, width=4, capstyle=tk.ROUND)
        hx_min = self._value_to_x(self._vmin)
        hx_max = self._value_to_x(self._vmax)
        self.create_line(hx_min, y, hx_max, y, fill=range_color, width=4, capstyle=tk.ROUND)

        for hx in (hx_min, hx_max):
            self.create_oval(
                hx - self._radius,
                y - self._radius,
                hx + self._radius,
                y + self._radius,
                fill=handle_color,
                outline="#333333",
                width=1,
            )


class _ProgressWindow:
    def __init__(self, master: tk.Tk | tk.Toplevel, title: str, maximum: int):
        self.win = tk.Toplevel(master)
        self.win.title(title)
        self.win.transient(master)
        self.win.resizable(False, False)
        self.label_var = tk.StringVar(value="")
        ttk.Label(self.win, textvariable=self.label_var, padding=10).pack(fill="x")
        self.bar = ttk.Progressbar(self.win, maximum=max(1, maximum), mode="determinate", length=380)
        self.bar.pack(fill="x", padx=10, pady=(0, 10))
        self.win.update_idletasks()

    def update(self, current: int, total: int, text: str):
        self.label_var.set(text)
        self.bar["maximum"] = max(1, total)
        self.bar["value"] = current
        self.win.update_idletasks()
        self.win.update()

    def close(self):
        if self.win and self.win.winfo_exists():
            self.win.destroy()
