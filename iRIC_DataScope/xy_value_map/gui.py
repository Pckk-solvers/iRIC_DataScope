from __future__ import annotations

import logging
import math
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk

import numpy as np

from .main import export_xy_value_maps
from .processor import (
    DataSource,
    Roi,
    build_colormap,
    clamp_roi_to_bounds,
    apply_mask_to_values,
    compute_global_value_range,
    downsample_grid_for_preview,
    frame_to_grids,
    interpolate_grid,
    parse_color,
    slice_grids_to_roi,
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

        self._global_scale = _GlobalScaleState()
        self._preview_frame_cache: dict[tuple[int, str], object] = {}

        self._data_source = DataSource.from_input(input_path)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_menu()
        self._build_ui()
        self._init_defaults()

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
        self.step_spin = tk.Spinbox(self, from_=1, to=max(1, self._data_source.step_count), textvariable=self.step_var, width=8, command=self._on_step_changed)
        self.step_spin.grid(row=2, column=3, sticky="w", **pad)

        # ROI
        ttk.Label(self, text="ROI (Xmin/Xmax/Ymin/Ymax):").grid(row=3, column=0, sticky="e", **pad)
        self.xmin_var = tk.DoubleVar()
        self.xmax_var = tk.DoubleVar()
        self.ymin_var = tk.DoubleVar()
        self.ymax_var = tk.DoubleVar()
        self.xmin_entry = ttk.Entry(self, textvariable=self.xmin_var, width=10)
        self.xmax_entry = ttk.Entry(self, textvariable=self.xmax_var, width=10)
        self.ymin_entry = ttk.Entry(self, textvariable=self.ymin_var, width=10)
        self.ymax_entry = ttk.Entry(self, textvariable=self.ymax_var, width=10)
        self.xmin_entry.grid(row=3, column=1, sticky="w", **pad)
        self.xmax_entry.grid(row=3, column=2, sticky="w", **pad)
        self.ymin_entry.grid(row=3, column=3, sticky="w", **pad)
        self.ymax_entry.grid(row=3, column=4, sticky="w", **pad)
        ttk.Button(self, text="全体表示", command=self._reset_roi_to_full).grid(row=3, column=5, sticky="w", **pad)

        for var in (self.xmin_var, self.xmax_var, self.ymin_var, self.ymax_var):
            var.trace_add("write", lambda *_: self._on_roi_changed())

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
        ttk.Radiobutton(self, text="global", value="global", variable=self.scale_mode, command=self._on_scale_mode_changed).grid(row=5, column=1, sticky="w", **pad)
        ttk.Radiobutton(self, text="manual", value="manual", variable=self.scale_mode, command=self._on_scale_mode_changed).grid(row=5, column=2, sticky="w", **pad)

        ttk.Label(self, text="vmin/vmax:").grid(row=5, column=3, sticky="e", **pad)
        self.vmin_var = tk.DoubleVar()
        self.vmax_var = tk.DoubleVar()
        self.vmin_entry = ttk.Entry(self, textvariable=self.vmin_var, width=10, state="disabled")
        self.vmax_entry = ttk.Entry(self, textvariable=self.vmax_var, width=10, state="disabled")
        self.vmin_entry.grid(row=5, column=4, sticky="w", **pad)
        self.vmax_entry.grid(row=5, column=5, sticky="w", **pad)
        self.vmin_var.trace_add("write", lambda *_: self._schedule_preview_update())
        self.vmax_var.trace_add("write", lambda *_: self._schedule_preview_update())

        # 描画
        ttk.Label(self, text="描画:").grid(row=6, column=0, sticky="e", **pad)
        self.render_mode = tk.StringVar(value="interp")
        ttk.Radiobutton(self, text="メッシュ", value="mesh", variable=self.render_mode, command=self._on_render_mode_changed).grid(row=6, column=1, sticky="w", **pad)
        ttk.Radiobutton(self, text="補間", value="interp", variable=self.render_mode, command=self._on_render_mode_changed).grid(row=6, column=2, sticky="w", **pad)

        ttk.Label(self, text="倍率:").grid(row=6, column=3, sticky="e", **pad)
        self.interp_factor_var = tk.IntVar(value=2)
        self.interp_factor_spin = tk.Spinbox(self, from_=1, to=8, textvariable=self.interp_factor_var, width=8)
        self.interp_factor_spin.grid(row=6, column=4, sticky="w", **pad)

        self.interp_method_var = tk.StringVar(value="cubic")
        self.interp_method_combo = ttk.Combobox(self, textvariable=self.interp_method_var, values=["linear", "cubic"], state="readonly", width=8)
        self.interp_method_combo.grid(row=6, column=5, sticky="w", **pad)

        self.interp_factor_var.trace_add("write", lambda *_: self._schedule_preview_update())
        self.interp_method_var.trace_add("write", lambda *_: self._schedule_preview_update())

        # ステータス
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var).grid(row=7, column=0, columnspan=6, sticky="w", padx=8, pady=(2, 6))

        # プレビュー
        preview_frame = ttk.LabelFrame(self, text="プレビュー（ROIはドラッグで指定）")
        preview_frame.grid(row=8, column=0, columnspan=6, sticky="nsew", padx=8, pady=8)
        self._build_preview(preview_frame)

        # 実行
        ttk.Button(self, text="実行（全ステップ出力）", command=self._run).grid(row=9, column=0, columnspan=6, pady=10)

        # layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(4, weight=1)
        self.grid_rowconfigure(8, weight=1)

    def _build_preview(self, parent):
        # Matplotlib は重いので遅延 import
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        from matplotlib.widgets import RectangleSelector

        self._mpl_Figure = Figure
        self._RectangleSelector = RectangleSelector

        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.mesh = None
        self.cbar = None

        self.selector = RectangleSelector(
            self.ax,
            self._on_roi_selected,
            useblit=True,
            button=[1],
            interactive=True,
            spancoords="data",
        )

    def _init_defaults(self):
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

        self.value_combo["values"] = vars_
        self.value_var.set(vars_[0])

        xmin, xmax, ymin, ymax = self._data_source.domain_bounds
        self.xmin_var.set(xmin)
        self.xmax_var.set(xmax)
        self.ymin_var.set(ymin)
        self.ymax_var.set(ymax)

        self._on_scale_mode_changed()
        self._on_render_mode_changed()
        self._schedule_preview_update(immediate=True)

    def _on_close(self):
        try:
            self._data_source.close()
        finally:
            self.destroy()

    def _on_value_changed(self):
        self._preview_frame_cache.clear()
        self._invalidate_global_scale()
        self._schedule_preview_update(immediate=True)

    def _on_step_changed(self):
        self._schedule_preview_update(immediate=True)

    def _choose_color(self, var: tk.StringVar):
        current = var.get()
        _, hex_color = colorchooser.askcolor(color=current, parent=self)
        if hex_color:
            var.set(hex_color)

    def _on_color_changed(self):
        self.min_color_sample.configure(background=self.min_color_var.get())
        self.max_color_sample.configure(background=self.max_color_var.get())
        self._schedule_preview_update()

    def _on_scale_mode_changed(self):
        manual = self.scale_mode.get() == "manual"
        self.vmin_entry.configure(state="normal" if manual else "disabled")
        self.vmax_entry.configure(state="normal" if manual else "disabled")
        self._schedule_preview_update(immediate=True)

    def _on_render_mode_changed(self):
        interp = self.render_mode.get() == "interp"
        state = "normal" if interp else "disabled"
        self.interp_factor_spin.configure(state=state)
        self.interp_method_combo.configure(state="readonly" if interp else "disabled")
        self._schedule_preview_update(immediate=True)

    def _reset_roi_to_full(self):
        xmin, xmax, ymin, ymax = self._data_source.domain_bounds
        self.xmin_var.set(xmin)
        self.xmax_var.set(xmax)
        self.ymin_var.set(ymin)
        self.ymax_var.set(ymax)
        self._hide_selector_overlay()
        self._schedule_preview_update(immediate=True)

    def _invalidate_global_scale(self):
        self._global_scale.token += 1
        self._global_scale.vmin = None
        self._global_scale.vmax = None

    def _on_roi_changed(self):
        self._invalidate_global_scale()
        self._schedule_preview_update()

    def _get_roi(self) -> Roi:
        roi = Roi(
            xmin=float(self.xmin_var.get()),
            xmax=float(self.xmax_var.get()),
            ymin=float(self.ymin_var.get()),
            ymax=float(self.ymax_var.get()),
        )
        return clamp_roi_to_bounds(roi, self._data_source.domain_bounds)

    def _get_scale(self) -> tuple[float, float] | None:
        if self.scale_mode.get() == "manual":
            return float(self.vmin_var.get()), float(self.vmax_var.get())
        if self._global_scale.vmin is not None and self._global_scale.vmax is not None:
            return self._global_scale.vmin, self._global_scale.vmax
        return None

    def _schedule_preview_update(self, immediate: bool = False):
        if hasattr(self, "_preview_job") and self._preview_job:
            try:
                self.after_cancel(self._preview_job)
            except Exception:
                pass
        delay = 0 if immediate else 200
        self._preview_job = self.after(delay, self._update_preview)

    def _on_roi_selected(self, eclick, erelease):
        if eclick.xdata is None or eclick.ydata is None or erelease.xdata is None or erelease.ydata is None:
            return
        xmin = min(eclick.xdata, erelease.xdata)
        xmax = max(eclick.xdata, erelease.xdata)
        ymin = min(eclick.ydata, erelease.ydata)
        ymax = max(eclick.ydata, erelease.ydata)
        self.xmin_var.set(xmin)
        self.xmax_var.set(xmax)
        self.ymin_var.set(ymin)
        self.ymax_var.set(ymax)
        # そのままだとROIの半透明矩形が残り続け、見た目が邪魔になるため消す
        self._hide_selector_overlay()

    def _hide_selector_overlay(self):
        sel = getattr(self, "selector", None)
        if sel is None:
            return
        try:
            for artist in getattr(sel, "artists", ()):
                try:
                    artist.set_visible(False)
                except Exception:
                    pass
            for artist in getattr(sel, "_handles_artists", ()):
                try:
                    artist.set_visible(False)
                except Exception:
                    pass
        except Exception:
            return
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def _update_preview(self):
        value_col = self.value_var.get().strip()
        if not value_col:
            return

        try:
            roi = self._get_roi()
        except Exception:
            return

        step = int(self.step_var.get() or 1)
        step = max(1, min(step, self._data_source.step_count))
        self.step_var.set(step)

        # global スケールの計算（非同期）
        if self.scale_mode.get() == "global":
            self._ensure_global_scale_async(value_col, roi)

        try:
            frame = self._get_preview_frame(step, value_col)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビューデータの取得に失敗しました:\n{e}")
            return

        try:
            x, y, v = frame_to_grids(frame, value_col=value_col)
            grid = slice_grids_to_roi(x, y, v, roi=roi)
        except Exception as e:
            self.status_var.set("")
            messagebox.showerror("エラー", f"プレビュー描画用データの準備に失敗しました:\n{e}")
            return

        if grid is None:
            self.status_var.set("ROI 内に点がありません（プレビュー）")
            self._draw_empty_preview(roi)
            return

        if self.render_mode.get() == "interp":
            try:
                factor = int(self.interp_factor_var.get() or 2)
            except Exception:
                factor = 2
            method = (self.interp_method_var.get() or "cubic").strip()
            grid = downsample_grid_for_preview(grid, max_points=20000)
            factor = max(1, factor)
            est = int(grid.x.size) * factor * factor
            if est > 60000 and grid.x.size > 0:
                factor = max(1, int(math.floor(math.sqrt(60000 / grid.x.size))))
            if factor != int(self.interp_factor_var.get() or 2):
                self.status_var.set(f"プレビュー軽量化のため倍率を {factor} に調整しました")
            grid = interpolate_grid(
                grid,
                roi=roi,
                factor=factor,
                method="linear" if method == "linear" else "cubic",
            )
        else:
            grid = downsample_grid_for_preview(grid, max_points=40000)
        vals_masked = apply_mask_to_values(grid.v, grid.mask)

        cmap = build_colormap(self.min_color_var.get(), self.max_color_var.get())
        scale = self._get_scale()
        if scale is None:
            finite = vals_masked[np.isfinite(vals_masked)]
            if finite.size:
                vmin, vmax = float(finite.min()), float(finite.max())
                self.status_var.set("globalスケール計算中（暫定表示）" if self.scale_mode.get() == "global" else "")
            else:
                vmin, vmax = 0.0, 1.0
        else:
            vmin, vmax = scale
            self.status_var.set("")

        self._draw_preview(
            x=grid.x,
            y=grid.y,
            vals=vals_masked,
            roi=roi,
            value_col=value_col,
            step=frame.step,
            t=frame.time,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )

    def _draw_empty_preview(self, roi: Roi):
        if self.mesh is not None:
            try:
                self.mesh.remove()
            except Exception:
                pass
            self.mesh = None
        if self.cbar is not None:
            try:
                self.cbar.ax.set_visible(False)
            except Exception:
                pass
        self.ax.set_title("ROI 内に点がありません")
        self.ax.set_xlim(roi.xmin, roi.xmax)
        self.ax.set_ylim(roi.ymin, roi.ymax)
        self.ax.set_aspect("equal", adjustable="box")
        self.canvas.draw_idle()

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
    ):
        if self.mesh is not None:
            try:
                self.mesh.remove()
            except Exception:
                pass
            self.mesh = None
        self.mesh = self.ax.pcolormesh(x, y, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="gouraud")
        if self.cbar is None:
            self.cbar = self.fig.colorbar(self.mesh, ax=self.ax)
        else:
            try:
                self.cbar.ax.set_visible(True)
            except Exception:
                pass
            self.cbar.update_normal(self.mesh)

        self.ax.set_title(f"step={step}  t={t:g}  value={value_col}")
        self.ax.set_xlim(roi.xmin, roi.xmax)
        self.ax.set_ylim(roi.ymin, roi.ymax)
        self.ax.set_aspect("equal", adjustable="box")
        self.canvas.draw_idle()

    def _get_preview_frame(self, step: int, value_col: str):
        key = (step, value_col)
        if key in self._preview_frame_cache:
            return self._preview_frame_cache[key]
        frame = self._data_source.get_frame(step=step, value_col=value_col)
        self._preview_frame_cache[key] = frame
        return frame

    def _ensure_global_scale_async(self, value_col: str, roi: Roi):
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
                vmin, vmax = compute_global_value_range(self._data_source, value_col=value_col, roi=roi)
            except Exception as e:
                logger.exception("globalスケール計算に失敗")

                def on_err():
                    token_matches = token == self._global_scale.token
                    self._global_scale.running = False
                    self.status_var.set("")
                    # 既にパラメータが変わっている場合は無視して再計算に任せる
                    if not token_matches:
                        self._schedule_preview_update(immediate=True)
                        return
                    messagebox.showerror("エラー", f"globalスケール計算に失敗しました:\n{e}")

                self.after(0, on_err)
                return

            def on_done():
                token_matches = token == self._global_scale.token
                self._global_scale.running = False
                self.status_var.set("")
                if token_matches:
                    self._global_scale.vmin = vmin
                    self._global_scale.vmax = vmax
                # token 不一致の場合は最新のROI/Valueで再計算する
                self._schedule_preview_update(immediate=True)

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

        out_base = Path(self.output_var.get())
        out_dir = out_base / f"xy_value_map_{value_col}"

        render_mode = "interp" if self.render_mode.get() == "interp" else "mesh"
        if render_mode == "interp":
            try:
                interp_factor = int(self.interp_factor_var.get())
            except Exception:
                messagebox.showerror("エラー", "補間の倍率は整数で入力してください。")
                return
            interp_factor = max(1, min(8, interp_factor))
        else:
            interp_factor = 1
        interp_method = "linear" if (self.interp_method_var.get() or "cubic") == "linear" else "cubic"

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
                render_mode=render_mode,
                interp_factor=interp_factor,
                interp_method=interp_method,
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
