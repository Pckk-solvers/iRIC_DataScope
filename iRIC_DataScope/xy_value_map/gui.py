from __future__ import annotations

import logging
import math
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk

import numpy as np

from .controller import XYValueMapController
from .data_prep import (
    compute_roi_minmax,
    estimate_base_spacing_from_frame,
    prepare_preview_grid,
    slice_frame_to_roi_grid,
)
from .edit_canvas import EditCanvasManager
from .export_runner import run_export_all, run_export_single_step
from .cache import PreviewFrameCache
from .main import export_xy_value_map_step, export_xy_value_maps, figure_size_from_roi
from .options import OutputOptions
from .preview_renderer import PreviewRenderer
from .state import GuiState
from .tasks import GlobalScaleWorker
from .left_panel import LeftPanelBuilder
from .style import (
    DEFAULT_CBAR_LABEL_FONT_SIZE,
    DEFAULT_TICK_FONT_SIZE,
    DEFAULT_TITLE_FONT_SIZE,
    build_colormap,
    get_edit_colormap,
)
from .processor import (
    DataSource,
    Roi,
    RoiGrid,
    clamp_roi_to_bounds,
    parse_color,
)

logger = logging.getLogger(__name__)



MANUAL_URL = "https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=73"


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

        self._global_scale = GlobalScaleWorker(lambda func: self.after(0, func))
        self._preview_frame_cache = PreviewFrameCache()
        self._base_dx = 1.0
        self._base_dy = 1.0
        self._base_spacing_ready = False
        self.state = GuiState()
        self._edit_fig = None
        self._edit_ax = None
        self._edit_agg = None
        self._edit_image_id = None
        self._edit_image_tk = None
        self._edit_domain_rect_id = None
        self._edit_pad_rect_id = None
        self._edit_overlay_text_id = None
        self._edit_overlay_bg_id = None
        self._edit_hint_text_id = None
        self._edit_hint_bg_id = None
        self._edit_outline_id = None
        self._edit_canvas_mgr: EditCanvasManager | None = None
        self._preview_renderer: PreviewRenderer | None = None
        self._preview_last_size: tuple[int, int] | None = None
        self._roi_patch = None
        self._roi_bottom_edge = None
        self._roi_rotate_line = None
        self._roi_handles: list[dict[str, object]] = []
        self._figsize: tuple[float, float] = (6.0, 4.0)
        self._tight_rect = None
        self._right_frame: ttk.Frame | None = None
        self._preview_height_px: int | None = None
        self._roi_frame: ttk.LabelFrame | None = None
        self._edit_canvas_frame: ttk.Frame | None = None
        self._export_slider_lock = False
        self._export_var_lock = False
        self.controller = XYValueMapController(self)
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
        # 左側パネルを構築
        left_frame = ttk.Frame(self)
        left_frame.grid(row=0, column=0, rowspan=12, sticky="nsew", padx=8, pady=8)
        ttk.Style(self).configure("Hint.TLabel", foreground="#666666")

        self.input_var = tk.StringVar(value=str(self.input_path))
        self.output_var = tk.StringVar(value=str(self.output_dir))
        self.value_var = tk.StringVar()
        self.step_var = tk.IntVar(value=1)
        self.min_color_var = tk.StringVar(value="#0000ff")
        self.max_color_var = tk.StringVar(value="#ff0000")
        self.scale_mode = tk.StringVar(value="global")
        self.vmin_var = tk.DoubleVar()
        self.vmax_var = tk.DoubleVar()
        self.range_slider = _RangeSlider(self, height=24, command=self._on_range_slider_changed)
        self.show_title_var = tk.BooleanVar(value=True)
        self.title_text_var = tk.StringVar(value="title (空で非表示)")
        self.show_ticks_var = tk.BooleanVar(value=True)
        self.show_frame_var = tk.BooleanVar(value=True)
        self.show_cbar_var = tk.BooleanVar(value=True)
        self.cbar_label_var = tk.StringVar(value="colorbar (空で非表示)")
        self.pad_inches_var = tk.DoubleVar(value=0.02)
        self.title_font_size_var = tk.DoubleVar(value=DEFAULT_TITLE_FONT_SIZE)
        self.tick_font_size_var = tk.DoubleVar(value=DEFAULT_TICK_FONT_SIZE)
        self.cbar_label_font_size_var = tk.DoubleVar(value=DEFAULT_CBAR_LABEL_FONT_SIZE)
        self.colormap_mode_var = tk.StringVar(value="最小/最大の2色")
        self.output_scale_var = tk.DoubleVar(value=1.0)
        self.export_start_var = tk.IntVar(value=1)
        self.export_end_var = tk.IntVar(value=1)
        self.export_skip_var = tk.IntVar(value=0)
        self.export_range_slider = _RangeSlider(self, height=24, command=self._on_export_range_changed)
        self.resolution_var = tk.DoubleVar(value=1.0)
        self.cx_var = tk.DoubleVar()
        self.cy_var = tk.DoubleVar()
        self.width_var = tk.DoubleVar()
        self.height_var = tk.DoubleVar()
        self.angle_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="")

        left_builder = LeftPanelBuilder(self)
        left_widgets = left_builder.build(left_frame, gui=self)
        self.value_combo = left_widgets["value_combo"]
        self.step_spin = left_widgets["step_spin"]
        self.min_color_btn = left_widgets["min_color_btn"]
        self.min_color_sample = left_widgets["min_color_sample"]
        self.max_color_btn = left_widgets["max_color_btn"]
        self.max_color_sample = left_widgets["max_color_sample"]
        self.cmap_hint_label = left_widgets["cmap_hint"]
        self.scale_global_radio = left_widgets["scale_global"]
        self.scale_manual_radio = left_widgets["scale_manual"]
        self.vmin_entry = left_widgets["vmin_entry"]
        self.vmax_entry = left_widgets["vmax_entry"]
        self.resolution_spin = left_widgets["resolution_spin"]
        self.title_text_entry = left_widgets["title_entry"]
        self.pad_inches_entry = left_widgets["pad_entry"]
        self.cbar_label_entry = left_widgets["cbar_label_entry"]
        self.title_font_size_entry = left_widgets["title_font_entry"]
        self.tick_font_size_entry = left_widgets["tick_font_entry"]
        self.cbar_label_font_size_entry = left_widgets["cbar_label_font_entry"]
        self.export_start_entry = left_widgets["export_start_entry"]
        self.export_end_entry = left_widgets["export_end_entry"]
        self.export_skip_entry = left_widgets["export_skip_entry"]
        self.export_range_slider = left_widgets["export_range_slider"]
        self.colormap_mode_combo = left_widgets["cmap_combo"]
        self.output_scale_entry = left_widgets["output_scale_entry"]
        self.run_step_btn = left_widgets["run_step_btn"]
        self.run_btn = left_widgets["run_btn"]

        self.value_combo.bind("<<ComboboxSelected>>", lambda e: self._on_value_changed())
        self.step_var.trace_add("write", lambda *_: self._on_step_changed())
        self.min_color_var.trace_add("write", lambda *_: self._on_color_changed())
        self.max_color_var.trace_add("write", lambda *_: self._on_color_changed())
        self.vmin_var.trace_add("write", lambda *_: self._on_manual_scale_changed())
        self.vmax_var.trace_add("write", lambda *_: self._on_manual_scale_changed())
        self.resolution_var.trace_add("write", lambda *_: self._on_resolution_changed())

        self._out_option_checkboxes = [
            left_widgets["show_ticks_chk"],
            left_widgets["show_frame_chk"],
            left_widgets["show_cbar_chk"],
        ]
        for chk in self._out_option_checkboxes:
            try:
                chk.configure(command=self._on_output_option_changed)
            except Exception:
                pass
        self.title_text_var.trace_add("write", lambda *_: self._on_output_option_changed())
        self.pad_inches_var.trace_add("write", lambda *_: self._on_output_option_changed())
        self.cbar_label_var.trace_add("write", lambda *_: self._on_output_option_changed())
        self.title_font_size_var.trace_add("write", lambda *_: self._on_output_option_changed())
        self.tick_font_size_var.trace_add("write", lambda *_: self._on_output_option_changed())
        self.cbar_label_font_size_var.trace_add("write", lambda *_: self._on_output_option_changed())
        self.colormap_mode_var.trace_add("write", lambda *_: self._on_colormap_mode_changed())
        self.output_scale_var.trace_add("write", lambda *_: self._on_output_option_changed())
        self.export_start_var.trace_add("write", lambda *_: self._on_export_range_var_changed())
        self.export_end_var.trace_add("write", lambda *_: self._on_export_range_var_changed())

        for var in (self.cx_var, self.cy_var, self.width_var, self.height_var, self.angle_var):
            var.trace_add("write", lambda *_: self._on_roi_changed())

        self._update_colormap_dependent_controls()

        # 右側にプレビュー（上）・編集（下）を配置
        right_frame = ttk.Frame(self)
        right_frame.grid(row=0, column=7, rowspan=12, sticky="nsew", padx=8, pady=8)
        right_frame.grid_columnconfigure(0, weight=1)
        preview_height_px = int(max(self._figsize[1] * 100, 200))
        self._right_frame = right_frame
        self._preview_height_px = preview_height_px
        right_frame.grid_rowconfigure(0, weight=0, minsize=preview_height_px)
        right_frame.grid_rowconfigure(1, weight=0, minsize=preview_height_px)

        preview_frame = ttk.LabelFrame(right_frame, text="プレビュー")
        edit_frame = ttk.LabelFrame(right_frame, text="編集（全体表示）")
        preview_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=(0, 4))
        edit_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(4, 0))
        edit_frame.grid_rowconfigure(0, weight=0)
        edit_frame.grid_rowconfigure(1, weight=1)
        self._build_preview(preview_frame)
        self._build_edit_panel(edit_frame)
        self.after(0, self._sync_right_panel_heights)

        # layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(7, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._interactive_widgets = [
            self.value_combo,
            self.step_spin,
            self.min_color_btn,
            self.max_color_btn,
            self.scale_global_radio,
            self.scale_manual_radio,
            self.vmin_entry,
            self.vmax_entry,
            self.range_slider,
            self.resolution_spin,
            self.cx_entry,
            self.cy_entry,
            self.width_entry,
            self.height_entry,
            self.angle_entry,
            self.reset_roi_btn,
            self.title_text_entry,
            self.pad_inches_entry,
            self.cbar_label_entry,
            self.title_font_size_entry,
            self.tick_font_size_entry,
            self.cbar_label_font_size_entry,
            self.colormap_mode_combo,
            self.output_scale_entry,
            self.export_range_slider,
            self.export_start_entry,
            self.export_end_entry,
            self.export_skip_entry,
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
            try:
                self.colormap_mode_combo.configure(state="readonly")
            except Exception:
                pass
            if hasattr(self, "export_range_slider"):
                try:
                    self.export_range_slider.set_enabled(True)
                except Exception:
                    pass
            self._update_colormap_dependent_controls()
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
            if hasattr(self, "export_range_slider"):
                try:
                    self.export_range_slider.set_enabled(False)
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
                    base_dx, base_dy = estimate_base_spacing_from_frame(frame0, value_col=vars_[0])
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
        self._edit_canvas_mgr = EditCanvasManager(self)

    def _build_edit_panel(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        roi_frame = ttk.LabelFrame(parent, text="ROI")
        roi_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        for col in (1, 3, 5, 7, 9):
            roi_frame.columnconfigure(col, weight=1)

        ttk.Label(roi_frame, text="Cx").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        self.cx_entry = ttk.Entry(roi_frame, textvariable=self.cx_var, width=8)
        self.cx_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(roi_frame, text="Cy").grid(row=0, column=2, sticky="e", padx=4, pady=2)
        self.cy_entry = ttk.Entry(roi_frame, textvariable=self.cy_var, width=8)
        self.cy_entry.grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        ttk.Label(roi_frame, text="W").grid(row=0, column=4, sticky="e", padx=4, pady=2)
        self.width_entry = ttk.Entry(roi_frame, textvariable=self.width_var, width=8)
        self.width_entry.grid(row=0, column=5, sticky="ew", padx=2, pady=2)
        ttk.Label(roi_frame, text="H").grid(row=0, column=6, sticky="e", padx=4, pady=2)
        self.height_entry = ttk.Entry(roi_frame, textvariable=self.height_var, width=8)
        self.height_entry.grid(row=0, column=7, sticky="ew", padx=2, pady=2)
        ttk.Label(roi_frame, text="Angle").grid(row=0, column=8, sticky="e", padx=4, pady=2)
        self.angle_entry = ttk.Entry(roi_frame, textvariable=self.angle_var, width=8)
        self.angle_entry.grid(row=0, column=9, sticky="ew", padx=2, pady=2)
        self.reset_roi_btn = ttk.Button(roi_frame, text="全体表示", command=self._reset_roi_to_full)
        self.reset_roi_btn.grid(row=0, column=10, sticky="w", padx=6, pady=2)

        for entry in (self.cx_entry, self.cy_entry, self.width_entry, self.height_entry, self.angle_entry):
            entry.bind("<Return>", self._on_roi_entry_confirm)
            entry.bind("<FocusOut>", self._on_roi_entry_confirm)

        self._roi_frame = roi_frame
        canvas_frame = ttk.Frame(parent)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        self._edit_canvas_frame = canvas_frame
        self._build_edit_canvas(canvas_frame)

    def _sync_right_panel_heights(self):
        if self._right_frame is None or self._preview_height_px is None:
            return
        if self._roi_frame is None or self._edit_canvas_frame is None:
            return
        self.update_idletasks()
        roi_height = self._roi_frame.winfo_reqheight()
        preview_height = self._preview_height_px
        self._edit_canvas_frame.configure(height=preview_height)
        self._edit_canvas_frame.grid_propagate(False)
        self._right_frame.grid_rowconfigure(1, minsize=preview_height + roi_height)

    def _build_preview(self, parent):
        # Matplotlib は重いので遅延 import
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self.preview_fig = Figure(figsize=self._figsize, dpi=100, constrained_layout=False)
        self.preview_ax = self.preview_fig.add_subplot(111)
        self.preview_canvas = FigureCanvasTkAgg(self.preview_fig, master=parent)
        widget = self.preview_canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)
        widget.update_idletasks()
        try:
            widget.configure(background="#f5f5f5")
        except Exception:
            pass
        widget.bind("<Configure>", lambda _e: self._on_preview_configure())

        self._preview_renderer = PreviewRenderer(self.preview_fig, self.preview_ax, self.preview_canvas)
        self.mesh = None
        self.cbar = None
        self._sync_preview_figsize_to_widget()

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
        self.state.edit.base_bounds = (xmin - pad_x, xmax + pad_x, ymin - pad_y, ymax + pad_y)
        self.state.edit.view_bounds = self.state.edit.base_bounds

        if not self._base_spacing_ready:
            try:
                frame0 = self._data_source.get_frame(step=1, value_col=self.value_var.get())
                self._base_dx, self._base_dy = estimate_base_spacing_from_frame(
                    frame0,
                    value_col=self.value_var.get(),
                )
            except Exception:
                self._base_dx, self._base_dy = 1.0, 1.0
            self._base_spacing_ready = True
        self.resolution_var.set(1.0)
        self.export_start_var.set(1)
        self.export_end_var.set(self._step_count)
        self.export_skip_var.set(0)
        self._sync_export_step_controls()
        self.output_scale_var.set(1.0)

        self._on_scale_mode_changed()
        self._on_output_option_changed()
        self.state.roi.confirmed = False
        self._schedule_view_update(immediate=True)

        if self.preview_fig is not None:
            try:
                self.preview_fig.set_size_inches(self._figsize[0], self._figsize[1], forward=True)
            except Exception:
                pass

    def _on_close(self):
        return self.controller.on_close()

    def _on_value_changed(self):
        return self.controller.on_value_changed()

    def _on_step_changed(self):
        return self.controller.on_step_changed()

    def _choose_color(self, var: tk.StringVar):
        current = var.get()
        _, hex_color = colorchooser.askcolor(color=current, parent=self)
        if hex_color:
            var.set(hex_color)

    def _on_color_changed(self):
        return self.controller.on_color_changed()

    def _resolve_colormap_mode(self) -> str:
        mode_raw = self.colormap_mode_var.get().strip()
        mode_map = {
            "最小/最大の2色": "rgb",
            "虹色（iRIC風）": "jet",
            "色相回転": "hsv",
        }
        return mode_map.get(mode_raw, mode_raw or "rgb")

    def _update_colormap_dependent_controls(self):
        mode = self._resolve_colormap_mode()
        use_minmax = mode != "jet"
        state = "normal" if use_minmax else "disabled"
        try:
            self.min_color_btn.configure(state=state)
            self.max_color_btn.configure(state=state)
        except Exception:
            pass
        if use_minmax:
            try:
                self.min_color_sample.configure(background=self.min_color_var.get(), text="")
                self.max_color_sample.configure(background=self.max_color_var.get(), text="")
            except Exception:
                pass
            try:
                self.cmap_hint_label.grid_remove()
            except Exception:
                pass
        else:
            try:
                self.min_color_sample.configure(background="#dddddd", text="固定", foreground="#666666")
                self.max_color_sample.configure(background="#dddddd", text="固定", foreground="#666666")
            except Exception:
                pass
            try:
                self.cmap_hint_label.grid()
            except Exception:
                pass

    def _on_colormap_mode_changed(self):
        self._update_colormap_dependent_controls()
        return self.controller.on_output_option_changed()

    def _on_resolution_changed(self):
        return self.controller.on_resolution_changed()

    def _on_scale_mode_changed(self):
        return self.controller.on_scale_mode_changed()

    def _on_manual_scale_changed(self):
        return self.controller.on_manual_scale_changed()

    def _on_output_option_changed(self):
        return self.controller.on_output_option_changed()

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
        self._global_scale.invalidate()
        self._clear_auto_range()

    def _on_roi_changed(self):
        return self.controller.on_roi_changed()

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
        return self.controller.on_roi_entry_confirm(_event)

    def _get_scale(self) -> tuple[float, float] | None:
        if self.scale_mode.get() == "manual":
            return float(self.vmin_var.get()), float(self.vmax_var.get())
        return self._global_scale.get_scale()

    def _get_output_options(self) -> OutputOptions:
        def _safe_pad(var: tk.DoubleVar, default: float = 0.02) -> float:
            try:
                val = float(var.get())
            except Exception:
                return default
            if not np.isfinite(val) or val < 0:
                return default
            return val
        def _safe_scale(var: tk.DoubleVar, default: float = 1.0) -> float:
            try:
                val = float(var.get())
            except Exception:
                return default
            if not np.isfinite(val) or val <= 0:
                return default
            return val

        if self.preview_fig is not None:
            try:
                cur_w, cur_h = self.preview_fig.get_size_inches()
                figsize = (float(cur_w), float(cur_h))
            except Exception:
                figsize = tuple(self._figsize)
        else:
            figsize = tuple(self._figsize)

        colormap_mode = self._resolve_colormap_mode()

        return OutputOptions(
            show_title=True,
            title_text=self.title_text_var.get().strip(),
            show_ticks=bool(self.show_ticks_var.get()),
            show_frame=bool(self.show_frame_var.get()),
            show_cbar=bool(self.show_cbar_var.get()),
            cbar_label=self.cbar_label_var.get().strip(),
            pad_inches=_safe_pad(self.pad_inches_var),
            title_font_size=_safe_pad(self.title_font_size_var, DEFAULT_TITLE_FONT_SIZE),
            tick_font_size=_safe_pad(self.tick_font_size_var, DEFAULT_TICK_FONT_SIZE),
            cbar_label_font_size=_safe_pad(self.cbar_label_font_size_var, DEFAULT_CBAR_LABEL_FONT_SIZE),
            figsize=figsize,
            colormap_mode=colormap_mode,
            output_scale=_safe_scale(self.output_scale_var),
        )

    def _get_export_step_range(self) -> tuple[int, int, int]:
        if self._data_source is None:
            return 1, 1, 0
        max_step = max(1, int(getattr(self._data_source, "step_count", 1)))
        try:
            start = int(self.export_start_var.get() or 1)
        except Exception:
            start = 1
        try:
            end = int(self.export_end_var.get() or max_step)
        except Exception:
            end = max_step
        try:
            skip = int(self.export_skip_var.get() or 0)
        except Exception:
            skip = 0

        start = max(1, min(start, max_step))
        end = max(1, min(end, max_step))
        if end < start:
            end = start
        if skip < 0:
            skip = 0
        return start, end, skip

    def _set_preview_figsize(self, figsize: tuple[float, float]):
        """Update preview figure size if changed and keep the latest size."""
        try:
            cur_w, cur_h = self.preview_fig.get_size_inches()
        except Exception:
            cur_w, cur_h = None, None
        if (
            cur_w is None
            or cur_h is None
            or abs(cur_w - figsize[0]) > 1e-3
            or abs(cur_h - figsize[1]) > 1e-3
        ):
            try:
                self.preview_fig.set_size_inches(*figsize, forward=True)
            except Exception:
                pass
        self.state.preview.figsize = tuple(figsize)

    def _sync_preview_figsize_to_widget(self) -> bool:
        if self.preview_canvas is None or self.preview_fig is None:
            return False
        try:
            widget = self.preview_canvas.get_tk_widget()
            avail_w = max(widget.winfo_width(), 1)
            avail_h = max(widget.winfo_height(), 1)
            dpi = float(self.preview_fig.get_dpi()) if self.preview_fig is not None else 100.0
            try:
                tk_dpi = float(widget.winfo_fpixels("1i"))
                if tk_dpi > 0:
                    dpi = tk_dpi
                    try:
                        self.preview_fig.set_dpi(dpi)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            return False
        if avail_w < 50 or avail_h < 50:
            return False
        if self._preview_last_size == (avail_w, avail_h):
            return False
        if dpi <= 0:
            return False
        new_size = (avail_w / dpi, avail_h / dpi)
        self._set_preview_figsize(new_size)
        self.state.preview.pad_px = (0.0, 0.0)
        self._preview_last_size = (avail_w, avail_h)
        try:
            self.preview_canvas.draw_idle()
        except Exception:
            pass
        return True

    def _on_preview_configure(self):
        """ウィジェットサイズ変更時に画像を中央に寄せるため再配置"""
        return self.controller.on_preview_configure()

    def _set_manual_scale_vars(self, vmin: float, vmax: float):
        self.state.scale.var_lock = True
        try:
            self.vmin_var.set(vmin)
            self.vmax_var.set(vmax)
        finally:
            self.state.scale.var_lock = False

    def _ensure_manual_scale_defaults(self):
        if self.state.scale.auto_range is None:
            return
        auto_min, auto_max = self.state.scale.auto_range
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())
        except Exception:
            self._set_manual_scale_vars(auto_min, auto_max)
            self.state.scale.ratio = (0.0, 1.0)
            return
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin >= vmax:
            self._set_manual_scale_vars(auto_min, auto_max)
            self.state.scale.ratio = (0.0, 1.0)

    def _clamp_manual_scale(self) -> bool:
        if self.state.scale.auto_range is None:
            return False
        auto_min, auto_max = self.state.scale.auto_range
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
        if self.state.scale.slider_lock or self.state.scale.auto_range is None:
            return
        if not hasattr(self, "range_slider"):
            return
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())
        except Exception:
            return
        self.state.scale.slider_lock = True
        try:
            self.range_slider.set_values(vmin, vmax)
        finally:
            self.state.scale.slider_lock = False

    def _on_range_slider_changed(self, vmin: float, vmax: float):
        return self.controller.on_range_slider_changed(vmin, vmax)

    def _on_export_range_changed(self, vmin: float, vmax: float):
        if self._export_slider_lock or self._data_source is None:
            return
        max_step = max(1, int(getattr(self._data_source, "step_count", 1)))
        start = int(round(vmin))
        end = int(round(vmax))
        start = max(1, min(start, max_step))
        end = max(1, min(end, max_step))
        if end < start:
            start, end = end, start
        self._export_slider_lock = True
        try:
            self.export_start_var.set(start)
            self.export_end_var.set(end)
        finally:
            self._export_slider_lock = False

    def _on_export_range_var_changed(self):
        if self._export_var_lock:
            return
        self._sync_export_step_controls()

    def _sync_export_step_controls(self):
        max_step = max(1, int(getattr(self._data_source, "step_count", 1)) if self._data_source else 1)
        try:
            start = int(self.export_start_var.get() or 1)
        except Exception:
            start = 1
        try:
            end = int(self.export_end_var.get() or max_step)
        except Exception:
            end = max_step
        start = max(1, min(start, max_step))
        end = max(1, min(end, max_step))
        if end < start:
            end = start

        self._export_var_lock = True
        try:
            self.export_start_var.set(start)
            self.export_end_var.set(end)
            try:
                self.export_start_entry.configure(to=max_step)
                self.export_end_entry.configure(to=max_step)
            except Exception:
                pass
            try:
                self.export_range_slider.set_range(1, max_step, keep_values=False)
                self.export_range_slider.set_values(start, end)
            except Exception:
                pass
        finally:
            self._export_var_lock = False

    def _set_auto_range(self, vmin: float, vmax: float):
        if not np.isfinite(vmin) or not np.isfinite(vmax):
            return
        if vmin == vmax:
            vmax = vmin + 1e-12
        if vmax < vmin:
            vmin, vmax = vmax, vmin
        self.state.scale.auto_range = (float(vmin), float(vmax))
        ratio = self._clamp_ratio(*self.state.scale.ratio)
        self.state.scale.ratio = ratio
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
        self.state.scale.auto_range = None
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
        if self.state.scale.auto_range is None:
            return rmin, rmax
        auto_min, auto_max = self.state.scale.auto_range
        span = max(auto_max - auto_min, 1e-12)
        return auto_min + rmin * span, auto_min + rmax * span

    def _ratio_from_values(self, vmin: float, vmax: float) -> tuple[float, float]:
        if self.state.scale.auto_range is None:
            return self.state.scale.ratio
        auto_min, auto_max = self.state.scale.auto_range
        span = max(auto_max - auto_min, 1e-12)
        rmin = (vmin - auto_min) / span
        rmax = (vmax - auto_min) / span
        return self._clamp_ratio(rmin, rmax)

    def _update_scale_ratio_from_values(self, vmin: float, vmax: float):
        if self.state.scale.auto_range is None:
            return
        self.state.scale.ratio = self._ratio_from_values(vmin, vmax)

    def _update_scale_ratio_from_vars(self):
        if self.state.scale.auto_range is None:
            return
        try:
            vmin = float(self.vmin_var.get())
            vmax = float(self.vmax_var.get())
        except Exception:
            return
        self.state.scale.ratio = self._ratio_from_values(vmin, vmax)


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
        if self.state.preview.job:
            try:
                self.after_cancel(self.state.preview.job)
            except Exception:
                pass
        delay = 0 if immediate else 200
        self.state.preview.job = self.after(delay, self._update_views)

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
            self.state.ui.step_var_lock = True
            try:
                self.step_var.set(step)
            finally:
                self.state.ui.step_var_lock = False

        output_opts = self._get_output_options()
        self._sync_preview_figsize_to_widget()

        # global スケールの計算（非同期）
        if not self.state.preview.dragging and self.state.roi.confirmed:
            self._ensure_global_scale_async(value_col, roi, dx, dy)

        try:
            frame = self._get_preview_frame(step, value_col)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビューデータの取得に失敗しました:\n{e}")
            return

        cmap = build_colormap(
            self.min_color_var.get(),
            self.max_color_var.get(),
            mode=output_opts.colormap_mode,
        )
        if self.state.edit.map_dirty or self._edit_image_id is None:
            try:
                # Keep edit background scale tied to full-domain values (ROI independent).
                self._update_edit_view(frame, value_col, roi, cmap, None)
                self.state.edit.map_dirty = False
            except Exception as e:
                self.status_var.set("")
                messagebox.showerror("エラー", f"編集表示の描画に失敗しました:\n{e}")
                return
        else:
            self._update_edit_roi_artists(roi)

        if not self.state.roi.confirmed:
            self.status_var.set("ROI確定待ち")
            self._draw_pending_preview(roi, output_opts)
            return

        scale = self._get_scale()
        self._update_preview_view(frame, value_col, roi, dx, dy, cmap, scale, output_opts)

    def _update_preview_view(self, frame, value_col, roi: Roi, dx: float, dy: float, cmap, scale, output_opts):
        self.state.preview.last_output_opts = output_opts
        try:
            grid = slice_frame_to_roi_grid(frame, value_col=value_col, roi=roi)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビュー描画用データの準備に失敗しました:\n{e}")
            return None

        if grid is None:
            self.status_var.set("ROI内に点がありません")
            self._draw_empty_preview(roi, output_opts)
            return None

        try:
            prepared = prepare_preview_grid(
                grid,
                roi=roi,
                dx=dx,
                dy=dy,
                preview_dragging=self.state.preview.dragging,
            )
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビュー補間の準備に失敗しました:\n{e}")
            return None
        out_x, out_y, vals_resampled, mask = prepared.x, prepared.y, prepared.values, prepared.mask
        status_note = prepared.status_note

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
                if self.state.roi.confirmed:
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
        self.state.edit.context = {"step": frame.step, "time": frame.time, "value": value_col}
        edit_cmap = self._edit_colormap()
        self.state.edit.render_context = {
            "frame": frame,
            "value_col": value_col,
            "cmap": edit_cmap,
            "scale": scale,
        }
        self._render_edit_background(frame, value_col, edit_cmap, scale)
        self._update_edit_roi_artists(roi)

    def _edit_colormap(self):
        return get_edit_colormap()

    def _edit_canvas_size(self) -> tuple[int, int]:
        if self._edit_canvas_mgr is None:
            return 1, 1
        return self._edit_canvas_mgr.edit_canvas_size()

    def _fit_bounds_to_canvas(
        self, bounds: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        if self._edit_canvas_mgr is None:
            return bounds
        return self._edit_canvas_mgr.fit_bounds_to_canvas(bounds)

    def _edit_view_bounds_or_base(self) -> tuple[float, float, float, float]:
        if self._edit_canvas_mgr is None:
            return self._fit_bounds_to_canvas((0.0, 1.0, 0.0, 1.0))
        return self._edit_canvas_mgr.edit_view_bounds_or_base()

    def _roi_edit_bounds(self) -> tuple[float, float, float, float]:
        if self._edit_canvas_mgr is None:
            return self._fit_bounds_to_canvas((0.0, 1.0, 0.0, 1.0))
        return self._edit_canvas_mgr.roi_edit_bounds()

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
        if self._edit_canvas_mgr is None:
            bounds = self._fit_bounds_to_canvas((0.0, 1.0, 0.0, 1.0))
            return bounds, 1.0, 0.0, 0.0
        tr = self._edit_canvas_mgr.edit_transform()
        return tr.bounds, tr.scale, tr.offset_x, tr.offset_y

    def _edit_zoom_ratio(self) -> float:
        if self._edit_canvas_mgr is None:
            return 1.0
        return self._edit_canvas_mgr.edit_zoom_ratio()

    def _data_to_canvas(self, x: float, y: float) -> tuple[float, float] | None:
        if self._edit_canvas_mgr is None:
            return None
        return self._edit_canvas_mgr.data_to_canvas(x, y)

    def _canvas_to_data(self, cx: float, cy: float) -> tuple[float, float] | None:
        if self._edit_canvas_mgr is None:
            return None
        return self._edit_canvas_mgr.canvas_to_data(cx, cy)

    def _update_canvas_rect(
        self,
        rect_id: int | None,
        bounds: tuple[float, float, float, float],
        *,
        outline: str,
        dash: tuple[int, int] | None = None,
    ) -> int | None:
        if self._edit_canvas_mgr is None:
            return rect_id
        return self._edit_canvas_mgr.update_canvas_rect(rect_id, bounds, outline=outline, dash=dash)

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
        if self._edit_canvas_mgr is None:
            return text_id, bg_id
        return self._edit_canvas_mgr.update_canvas_text_with_bg(text_id, bg_id, text, x=x, y=y, anchor=anchor)

    def _update_edit_bounds_overlay(self):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.update_edit_bounds_overlay()

    def _update_edit_overlay_text(self):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.update_edit_overlay_text()

    def _update_edit_overlay(self):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.update_edit_overlay()

    def _compute_grid_outline(self, grid: RoiGrid) -> np.ndarray | None:
        if self._edit_canvas_mgr is None:
            return None
        return self._edit_canvas_mgr.compute_grid_outline(grid)

    def _update_edit_outline(self):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.update_edit_outline()

    def _render_edit_background(self, frame, value_col, cmap, scale):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.render_edit_background(frame, value_col, cmap, scale)

    def _schedule_edit_background_render(self, immediate: bool = False):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.schedule_edit_background_render(immediate)

    def _render_edit_background_from_context(self):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.render_edit_background_from_context()

    def _on_edit_configure(self, _event):
        return self.controller.on_edit_configure(_event)

    def _set_roi_vars(self, roi: Roi):
        angle = float(roi.angle_deg)
        while angle <= -180:
            angle += 360
        while angle > 180:
            angle -= 360
        self.state.roi.var_lock = True
        try:
            self.cx_var.set(roi.cx)
            self.cy_var.set(roi.cy)
            self.width_var.set(roi.width)
            self.height_var.set(roi.height)
            self.angle_var.set(angle)
        finally:
            self.state.roi.var_lock = False

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
            self.state.roi.confirmed = True
        elif confirm is False:
            self.state.roi.confirmed = False
        self._update_edit_roi_artists(roi)
        if invalidate_scale:
            self._invalidate_global_scale()
        if schedule_views:
            self._schedule_view_update()

    def _reset_edit_view(self):
        if self.state.edit.base_bounds is None:
            return
        self.state.edit.view_bounds = self._fit_bounds_to_canvas(self.state.edit.base_bounds)
        self.state.edit.map_dirty = True
        self._schedule_edit_background_render(immediate=True)

    def _update_edit_roi_artists(self, roi: Roi):
        if self._edit_canvas_mgr is None:
            return
        return self._edit_canvas_mgr.update_edit_roi_artists(roi)

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
        return self.controller.on_edit_press(event)

    def _on_edit_motion(self, event):
        return self.controller.on_edit_motion(event)

    def _on_edit_release(self, event):
        return self.controller.on_edit_release(event)

    def _on_edit_scroll(self, event):
        return self.controller.on_edit_scroll(event)

    def _draw_empty_preview(
        self,
        roi: Roi,
        output_opts: OutputOptions | None = None,
        *,
        title: str = "No points in ROI",
    ):
        if self._preview_renderer is None:
            return
        opts = output_opts or self.state.preview.last_output_opts
        if opts is None:
            opts = self._get_output_options()
        self._preview_renderer.draw_empty_preview(roi, output_opts=opts, title=title)
        self._sync_preview_renderer_state()

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
        output_opts: OutputOptions,
    ):
        if self._preview_renderer is None:
            return
        self._preview_renderer.draw_preview(
            x=x,
            y=y,
            vals=vals,
            roi=roi,
            value_col=value_col,
            step=step,
            t=t,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            output_opts=output_opts,
        )
        self._sync_preview_renderer_state()

    def _reset_preview_axes(self):
        """Clear preview axes and colorbar to avoid leftover artists/clipping."""
        if self._preview_renderer is None:
            return
        self._preview_renderer.reset_axes()
        self._sync_preview_renderer_state()

    def _update_tight_bbox_overlay(self, pad_inches: float = 0.02):
        """Preview 用: bbox_inches=\"tight\" 相当の領域を破線で可視化する。"""
        if self._preview_renderer is None:
            return
        self._preview_renderer.update_tight_bbox_overlay(pad_inches=pad_inches)
        self._sync_preview_renderer_state()

    def _build_plot_title(self, *, step: int, t: float, value_col: str, output_opts: OutputOptions) -> str:
        if self._preview_renderer is None:
            return ""
        return self._preview_renderer.build_plot_title(step=step, t=t, value_col=value_col, output_opts=output_opts)

    def _apply_plot_options(self, *, ax, mesh, output_opts: OutputOptions):
        if self._preview_renderer is None:
            return
        self._preview_renderer.apply_plot_options(mesh=mesh, output_opts=output_opts)
        self._sync_preview_renderer_state()

    def _sync_preview_renderer_state(self):
        if self._preview_renderer is None:
            return
        self.preview_ax = self._preview_renderer.ax
        self.mesh = self._preview_renderer.mesh
        self.cbar = self._preview_renderer.cbar
        self._tight_rect = self._preview_renderer.tight_rect


    def _get_preview_frame(self, step: int, value_col: str):
        if self._data_source is None:
            raise RuntimeError("データが読み込まれていません。")
        return self._preview_frame_cache.get_or_fetch(
            data_source=self._data_source,
            step=step,
            value_col=value_col,
        )

    def _ensure_global_scale_async(self, value_col: str, roi: Roi, dx: float, dy: float):
        if self._data_source is None:
            return

        def on_status(text: str):
            self.status_var.set(text)

        def on_empty():
            self._clear_auto_range()
            self.status_var.set("ROI内に有効な値がありません。")

        def on_error(err: Exception):
            logger.exception("globalスケール計算に失敗")
            self.status_var.set("")
            messagebox.showerror("エラー", f"globalスケール計算に失敗しました:\n{err}")

        def on_done(vmin: float, vmax: float):
            self.status_var.set("")
            self._set_auto_range(vmin, vmax)

        def on_token_mismatch():
            self._schedule_view_update(immediate=True)

        self._global_scale.ensure_async(
            data_source=self._data_source,
            value_col=value_col,
            roi=roi,
            dx=dx,
            dy=dy,
            status_text="globalスケール計算中...",
            on_status=on_status,
            on_empty=on_empty,
            on_error=on_error,
            on_done=on_done,
            on_token_mismatch=on_token_mismatch,
        )

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
        manual_scale = None
        if scale_mode == "manual":
            manual_scale = (self.vmin_var.get(), self.vmax_var.get())

        try:
            min_color = parse_color(self.min_color_var.get())
            max_color = parse_color(self.max_color_var.get())
        except Exception as e:
            messagebox.showerror("エラー", f"色の指定が不正です:\n{e}")
            return
        output_opts = self._get_output_options()
        export_start, export_end, export_skip = self._get_export_step_range()

        out_base = Path(self.output_var.get())
        out_dir = out_base / f"xy_value_map_{value_col}"

        try:
            out_dir = run_export_all(
                data_source=self._data_source,
                value_col=value_col,
                roi=roi,
                dx=dx,
                dy=dy,
                min_color=min_color,
                max_color=max_color,
                output_opts=output_opts,
                output_dir=out_dir,
                scale_mode=scale_mode,
                manual_scale=manual_scale,
                step_start=export_start,
                step_end=export_end,
                step_skip=export_skip,
                progress_factory=lambda maximum, title: _ProgressWindow(self, title=title, maximum=maximum),
                export_func=export_xy_value_maps,
            )
        except ValueError as e:
            messagebox.showerror("エラー", str(e))
            return
        except Exception as e:
            logger.exception("画像出力に失敗しました")
            messagebox.showerror("エラー", str(e))
            return

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
        manual_scale = None
        if scale_mode == "manual":
            manual_scale = (self.vmin_var.get(), self.vmax_var.get())

        try:
            min_color = parse_color(self.min_color_var.get())
            max_color = parse_color(self.max_color_var.get())
        except Exception as e:
            messagebox.showerror("エラー", f"色の指定が不正です:\n{e}")
            return
        output_opts = self._get_output_options()

        out_base = Path(self.output_var.get())
        out_dir = out_base / f"xy_value_map_{value_col}"

        try:
            out_path = run_export_single_step(
                data_source=self._data_source,
                value_col=value_col,
                step=step,
                roi=roi,
                dx=dx,
                dy=dy,
                min_color=min_color,
                max_color=max_color,
                output_opts=output_opts,
                output_dir=out_dir,
                scale_mode=scale_mode,
                manual_scale=manual_scale,
                global_scale=self._global_scale.get_scale(),
                confirm_global_fallback=lambda msg: messagebox.askyesno("確認", msg),
                get_preview_frame=self._get_preview_frame,
                compute_roi_minmax_fn=compute_roi_minmax,
                progress_factory=lambda maximum, title: _ProgressWindow(self, title=title, maximum=maximum),
                export_func=export_xy_value_map_step,
            )
        except ValueError as e:
            messagebox.showerror("エラー", str(e))
            return
        except Exception as e:
            logger.exception("このステップのみ出力に失敗しました")
            messagebox.showerror("エラー", str(e))
            return
        if out_path is None:
            return

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

