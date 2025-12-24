from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .ui import UIBuilder


class LeftPanelBuilder:
    """左側パネルのUI構築をまとめる。"""

    def __init__(self, master: tk.Misc):
        self.master = master

    def build(self, parent: tk.Misc, *, gui) -> dict[str, ttk.Entry | ttk.Button | ttk.Checkbutton | ttk.Combobox | tk.Canvas]:
        widgets: dict[str, object] = {}
        pad = {"padx": 6, "pady": 4}

        parent.grid_columnconfigure(0, weight=1)

        row = 0

        # 入力/出力
        io_frame = ttk.LabelFrame(parent, text="入力/出力")
        io_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        io_frame.columnconfigure(0, weight=0)
        io_frame.columnconfigure(1, weight=1)
        ttk.Label(io_frame, text="入力:").grid(row=0, column=0, sticky="e", **pad)
        widgets["input_entry"] = ttk.Entry(io_frame, textvariable=gui.input_var, width=60, state="readonly")
        widgets["input_entry"].grid(row=0, column=1, sticky="ew", **pad)
        ttk.Label(io_frame, text="出力:").grid(row=1, column=0, sticky="e", **pad)
        widgets["output_entry"] = ttk.Entry(io_frame, textvariable=gui.output_var, width=60, state="readonly")
        widgets["output_entry"].grid(row=1, column=1, sticky="ew", **pad)
        row += 1

        # プレビュー対象
        preview_frame = ttk.LabelFrame(parent, text="プレビュー対象")
        preview_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        preview_frame.columnconfigure(0, weight=0)
        preview_frame.columnconfigure(1, weight=1)
        ttk.Label(preview_frame, text="Value:").grid(row=0, column=0, sticky="e", **pad)
        widgets["value_combo"] = ttk.Combobox(preview_frame, textvariable=gui.value_var, state="readonly", width=24)
        widgets["value_combo"].grid(row=0, column=1, sticky="ew", **pad)
        ttk.Label(preview_frame, text="step:").grid(row=1, column=0, sticky="e", **pad)
        widgets["step_spin"] = tk.Spinbox(preview_frame, from_=1, to=max(1, gui._step_count), textvariable=gui.step_var, width=8, command=gui._on_step_changed)
        widgets["step_spin"].grid(row=1, column=1, sticky="w", **pad)
        row += 1

        # 色/スケール
        color_frame = ttk.LabelFrame(parent, text="色/スケール")
        color_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        color_frame.columnconfigure(0, weight=0)
        color_frame.columnconfigure(1, weight=1)
        color_frame.columnconfigure(2, weight=0)
        color_frame.columnconfigure(3, weight=1)
        ttk.Label(color_frame, text="カラーマップ:").grid(row=0, column=0, sticky="e", **pad)
        widgets["cmap_combo"] = ttk.Combobox(
            color_frame,
            textvariable=gui.colormap_mode_var,
            state="readonly",
            width=14,
            values=["最小/最大の2色", "虹色（iRIC風）", "色相回転"],
        )
        widgets["cmap_combo"].grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(color_frame, text="最小色:").grid(row=1, column=0, sticky="e", **pad)
        widgets["min_color_btn"] = ttk.Button(color_frame, text="選択", command=lambda: gui._choose_color(gui.min_color_var))
        widgets["min_color_btn"].grid(row=1, column=1, sticky="w", **pad)
        widgets["min_color_sample"] = tk.Label(color_frame, width=6, background=gui.min_color_var.get())
        widgets["min_color_sample"].grid(row=1, column=2, sticky="w", **pad)
        ttk.Label(color_frame, text="最大色:").grid(row=2, column=0, sticky="e", **pad)
        widgets["max_color_btn"] = ttk.Button(color_frame, text="選択", command=lambda: gui._choose_color(gui.max_color_var))
        widgets["max_color_btn"].grid(row=2, column=1, sticky="w", **pad)
        widgets["max_color_sample"] = tk.Label(color_frame, width=6, background=gui.max_color_var.get())
        widgets["max_color_sample"].grid(row=2, column=2, sticky="w", **pad)
        widgets["cmap_hint"] = ttk.Label(color_frame, text="※虹色（iRIC風）は最小/最大色を使用しません")
        widgets["cmap_hint"].grid(row=3, column=1, columnspan=3, sticky="w", padx=6, pady=(2, 4))
        ttk.Label(color_frame, text="スケール設定:").grid(row=4, column=0, sticky="w", **pad)
        widgets["scale_global"] = ttk.Radiobutton(color_frame, text="自動（全ステップ）", value="global", variable=gui.scale_mode, command=gui._on_scale_mode_changed)
        widgets["scale_manual"] = ttk.Radiobutton(color_frame, text="手動（数値入力）", value="manual", variable=gui.scale_mode, command=gui._on_scale_mode_changed)
        widgets["scale_global"].grid(row=4, column=1, sticky="w", **pad)
        widgets["scale_manual"].grid(row=4, column=2, sticky="w", **pad)
        ttk.Label(color_frame, text="範囲スライダー:").grid(row=5, column=0, sticky="w", **pad)
        widgets["range_slider"] = gui.range_slider
        widgets["range_slider"].grid(in_=color_frame, row=5, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(color_frame, text="表示下限:").grid(row=6, column=0, sticky="e", **pad)
        widgets["vmin_entry"] = ttk.Entry(color_frame, textvariable=gui.vmin_var, width=8, state="disabled")
        widgets["vmin_entry"].grid(row=6, column=1, sticky="w", **pad)
        ttk.Label(color_frame, text="表示上限:").grid(row=6, column=2, sticky="e", **pad)
        widgets["vmax_entry"] = ttk.Entry(color_frame, textvariable=gui.vmax_var, width=8, state="disabled")
        widgets["vmax_entry"].grid(row=6, column=3, sticky="w", **pad)
        row += 1

        # 解像度
        res_frame = ttk.LabelFrame(parent, text="解像度")
        row += 1
        res_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        res_frame.columnconfigure(0, weight=0)
        res_frame.columnconfigure(1, weight=1)
        res_frame.columnconfigure(2, weight=1)
        ttk.Label(res_frame, text="倍率:").grid(row=0, column=0, sticky="e", **pad)
        widgets["resolution_spin"] = tk.Spinbox(res_frame, from_=0.5, to=8.0, increment=0.5, textvariable=gui.resolution_var, width=8)
        widgets["resolution_spin"].grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(
            res_frame,
            text="ROIの境界が欠ける場合に倍率を上げると、見た目がなめらかになります。",
            style="Hint.TLabel",
        ).grid(row=0, column=2, sticky="w", padx=2, pady=2)
        row += 1

        ui_builder = UIBuilder(self.master)

        display_widgets = ui_builder.build_display_options(parent, vars={
            "title_text_var": gui.title_text_var,
            "show_ticks_var": gui.show_ticks_var,
            "show_frame_var": gui.show_frame_var,
            "show_cbar_var": gui.show_cbar_var,
            "cbar_label_var": gui.cbar_label_var,
        })
        display_frame = display_widgets["title_entry"].master
        display_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        widgets.update(display_widgets)
        row += 1

        font_widgets = ui_builder.build_font_options(parent, vars={
            "title_font_size_var": gui.title_font_size_var,
            "tick_font_size_var": gui.tick_font_size_var,
            "cbar_label_font_size_var": gui.cbar_label_font_size_var,
        })
        font_frame = font_widgets["title_font_entry"].master
        font_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        widgets.update(font_widgets)
        row += 1

        export_widgets = ui_builder.build_export_options(parent, vars={
            "pad_inches_var": gui.pad_inches_var,
            "output_scale_var": gui.output_scale_var,
            "export_start_var": gui.export_start_var,
            "export_end_var": gui.export_end_var,
            "export_skip_var": gui.export_skip_var,
        })
        export_frame = export_widgets["pad_entry"].master
        export_widgets["export_range_slider"] = gui.export_range_slider
        export_widgets["export_range_slider"].grid(
            in_=export_frame,
            row=2,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=6,
            pady=4,
        )
        export_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        widgets.update(export_widgets)
        row += 1

        # 出力ボタン
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        widgets["run_step_btn"] = ttk.Button(btn_frame, text="現在のステップを出力", command=gui._run_single_step)
        widgets["run_btn"] = ttk.Button(btn_frame, text="指定ステップをまとめて出力", command=gui._run)
        widgets["run_step_btn"].grid(row=0, column=0, sticky="ew", padx=(0, 6))
        widgets["run_btn"].grid(row=0, column=1, sticky="ew", padx=(6, 0))
        row += 1

        # ステータス
        ttk.Label(parent, textvariable=gui.status_var).grid(row=row, column=0, sticky="w", padx=6, pady=(2, 6))

        return widgets
