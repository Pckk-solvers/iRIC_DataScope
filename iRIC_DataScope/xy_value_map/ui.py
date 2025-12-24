from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class UIBuilder:
    """GUIレイアウト構築専用クラス。イベント・ロジックは呼び出し側で紐づける。"""

    def __init__(self, master: tk.Misc):
        self.master = master

    def build_display_options(self, parent: tk.Misc, *, vars: dict[str, tk.Variable]) -> dict[str, ttk.Entry | ttk.Checkbutton]:
        """
        表示オプションのウィジェットを生成し、主要ウィジェットを返す。
        vars: {
          title_text_var, show_ticks_var, show_frame_var, show_cbar_var,
          cbar_label_var
        }
        """
        widgets: dict[str, object] = {}
        frame = ttk.LabelFrame(parent, text="表示")
        frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        widgets["show_ticks_chk"] = ttk.Checkbutton(frame, text="目盛り", variable=vars["show_ticks_var"])
        widgets["show_ticks_chk"].grid(row=0, column=1, sticky="w", padx=6, pady=2)
        widgets["show_frame_chk"] = ttk.Checkbutton(frame, text="枠線", variable=vars["show_frame_var"])
        widgets["show_frame_chk"].grid(row=0, column=2, sticky="w", padx=6, pady=2)
        widgets["show_cbar_chk"] = ttk.Checkbutton(frame, text="カラーバー", variable=vars["show_cbar_var"])
        widgets["show_cbar_chk"].grid(row=0, column=3, sticky="w", padx=6, pady=2)

        ttk.Label(frame, text="タイトル").grid(row=1, column=0, sticky="e", padx=6, pady=2)
        title_entry = ttk.Entry(frame, textvariable=vars["title_text_var"], width=30)
        title_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=2, pady=2)
        widgets["title_entry"] = title_entry

        ttk.Label(frame, text="カラーバー名").grid(row=2, column=0, sticky="e", padx=6, pady=2)
        widgets["cbar_label_entry"] = ttk.Entry(frame, textvariable=vars["cbar_label_var"], width=30)
        widgets["cbar_label_entry"].grid(row=2, column=1, columnspan=3, sticky="ew", padx=2, pady=2)

        return widgets

    def build_font_options(self, parent: tk.Misc, *, vars: dict[str, tk.Variable]) -> dict[str, tk.Spinbox]:
        """
        フォント設定のウィジェットを生成し、主要ウィジェットを返す。
        vars: { title_font_size_var, tick_font_size_var, cbar_label_font_size_var }
        """
        widgets: dict[str, object] = {}
        frame = ttk.LabelFrame(parent, text="フォントサイズ")
        frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="タイトル").grid(row=0, column=0, sticky="e", padx=6, pady=2)
        widgets["title_font_entry"] = tk.Spinbox(frame, from_=1, to=64, increment=1, textvariable=vars["title_font_size_var"], width=8)
        widgets["title_font_entry"].grid(row=0, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(frame, text="目盛").grid(row=1, column=0, sticky="e", padx=6, pady=2)
        widgets["tick_font_entry"] = tk.Spinbox(frame, from_=1, to=64, increment=1, textvariable=vars["tick_font_size_var"], width=8)
        widgets["tick_font_entry"].grid(row=1, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(frame, text="CBラベル").grid(row=2, column=0, sticky="e", padx=6, pady=2)
        widgets["cbar_label_font_entry"] = tk.Spinbox(frame, from_=1, to=64, increment=1, textvariable=vars["cbar_label_font_size_var"], width=8)
        widgets["cbar_label_font_entry"].grid(row=2, column=1, sticky="w", padx=2, pady=2)

        return widgets

    def build_export_options(self, parent: tk.Misc, *, vars: dict[str, tk.Variable]) -> dict[str, tk.Spinbox | ttk.Entry]:
        """
        出力設定のウィジェットを生成し、主要ウィジェットを返す。
        vars: { pad_inches_var, output_scale_var, export_start_var, export_end_var, export_skip_var }
        """
        widgets: dict[str, object] = {}
        frame = ttk.LabelFrame(parent, text="出力")
        frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=1)

        ttk.Label(frame, text="余白(in)").grid(row=0, column=0, sticky="e", padx=6, pady=2)
        widgets["pad_entry"] = tk.Spinbox(frame, from_=0.0, to=1.0, increment=0.01, textvariable=vars["pad_inches_var"], width=8)
        widgets["pad_entry"].grid(row=0, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(frame, text="出力倍率").grid(row=1, column=0, sticky="e", padx=6, pady=2)
        widgets["output_scale_entry"] = tk.Spinbox(frame, from_=0.1, to=10.0, increment=0.1, textvariable=vars["output_scale_var"], width=8)
        widgets["output_scale_entry"].grid(row=1, column=1, sticky="w", padx=2, pady=2)
        ttk.Label(
            frame,
            text="プレビューの大きさを基準に、数値を上げると画像サイズ/解像度が上がります。",
            style="Hint.TLabel",
        ).grid(row=1, column=2, sticky="w", padx=2, pady=2)

        ttk.Label(frame, text="出力ステップ").grid(row=2, column=0, sticky="e", padx=6, pady=2)

        ttk.Label(frame, text="開始").grid(row=3, column=0, sticky="e", padx=6, pady=2)
        widgets["export_start_entry"] = tk.Spinbox(frame, from_=1, to=1, increment=1, textvariable=vars["export_start_var"], width=8)
        widgets["export_start_entry"].grid(row=3, column=1, sticky="w", padx=2, pady=2)
        ttk.Label(frame, text="終了").grid(row=3, column=2, sticky="e", padx=6, pady=2)
        widgets["export_end_entry"] = tk.Spinbox(frame, from_=1, to=1, increment=1, textvariable=vars["export_end_var"], width=8)
        widgets["export_end_entry"].grid(row=3, column=3, sticky="w", padx=2, pady=2)

        ttk.Label(frame, text="間引き数").grid(row=4, column=0, sticky="e", padx=6, pady=2)
        widgets["export_skip_entry"] = tk.Spinbox(frame, from_=0, to=9999, increment=1, textvariable=vars["export_skip_var"], width=8)
        widgets["export_skip_entry"].grid(row=4, column=1, sticky="w", padx=2, pady=2)

        return widgets
