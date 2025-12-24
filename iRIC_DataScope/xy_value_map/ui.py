from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class UIBuilder:
    """GUIレイアウト構築専用クラス。イベント・ロジックは呼び出し側で紐づける。"""

    def __init__(self, master: tk.Misc):
        self.master = master

    def build_output_options(self, parent: tk.Misc, *, vars: dict[str, tk.Variable]) -> dict[str, ttk.Entry | ttk.Checkbutton]:
        """
        出力オプションのウィジェットを生成し、主要ウィジェットを返す。
        vars: {
          title_text_var, show_ticks_var, show_frame_var, show_cbar_var,
          cbar_label_var, pad_inches_var,
          title_font_size_var, tick_font_size_var, cbar_label_font_size_var,
          export_start_var, export_end_var, export_skip_var
        }
        """
        widgets: dict[str, object] = {}
        opt_frame = ttk.LabelFrame(parent, text="出力オプション")
        opt_frame.grid(row=7, column=0, columnspan=7, sticky="ew", padx=8, pady=6)
        opt_frame.columnconfigure(0, weight=1)
        opt_frame.columnconfigure(1, weight=1)
        opt_frame.columnconfigure(2, weight=1)
        opt_frame.columnconfigure(3, weight=1)
        opt_frame.columnconfigure(4, weight=1)

        ttk.Label(opt_frame, text="タイトル文字列").grid(row=0, column=0, sticky="e", padx=6, pady=2)
        title_entry = ttk.Entry(opt_frame, textvariable=vars["title_text_var"], width=30)
        title_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=2, pady=2)
        widgets["title_entry"] = title_entry

        ttk.Label(opt_frame, text="カラーマップ").grid(row=0, column=3, sticky="e", padx=6, pady=2)
        widgets["cmap_combo"] = ttk.Combobox(
            opt_frame,
            textvariable=vars["colormap_mode_var"],
            state="readonly",
            width=10,
            values=["rgb", "jet", "hsv"],
        )
        widgets["cmap_combo"].grid(row=0, column=4, sticky="w", padx=2, pady=2)

        widgets["show_ticks_chk"] = ttk.Checkbutton(opt_frame, text="目盛り", variable=vars["show_ticks_var"])
        widgets["show_ticks_chk"].grid(row=1, column=0, sticky="w", padx=6, pady=2)
        widgets["show_frame_chk"] = ttk.Checkbutton(opt_frame, text="枠線", variable=vars["show_frame_var"])
        widgets["show_frame_chk"].grid(row=1, column=1, sticky="w", padx=6, pady=2)
        widgets["show_cbar_chk"] = ttk.Checkbutton(opt_frame, text="カラーバー", variable=vars["show_cbar_var"])
        widgets["show_cbar_chk"].grid(row=1, column=2, sticky="w", padx=6, pady=2)

        ttk.Label(opt_frame, text="pad[in]").grid(row=2, column=0, sticky="e", padx=6, pady=2)
        widgets["pad_entry"] = ttk.Entry(opt_frame, textvariable=vars["pad_inches_var"], width=8)
        widgets["pad_entry"].grid(row=2, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(opt_frame, text="カラーバー名").grid(row=3, column=0, sticky="e", padx=6, pady=2)
        widgets["cbar_label_entry"] = ttk.Entry(opt_frame, textvariable=vars["cbar_label_var"], width=30)
        widgets["cbar_label_entry"].grid(row=3, column=1, columnspan=3, sticky="ew", padx=2, pady=2)

        ttk.Label(opt_frame, text="タイトルFont").grid(row=4, column=0, sticky="e", padx=6, pady=2)
        widgets["title_font_entry"] = ttk.Entry(opt_frame, textvariable=vars["title_font_size_var"], width=8)
        widgets["title_font_entry"].grid(row=4, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(opt_frame, text="目盛Font").grid(row=4, column=2, sticky="e", padx=6, pady=2)
        widgets["tick_font_entry"] = ttk.Entry(opt_frame, textvariable=vars["tick_font_size_var"], width=8)
        widgets["tick_font_entry"].grid(row=4, column=3, sticky="w", padx=2, pady=2)

        ttk.Label(opt_frame, text="CBラベルFont").grid(row=5, column=0, sticky="e", padx=6, pady=2)
        widgets["cbar_label_font_entry"] = ttk.Entry(opt_frame, textvariable=vars["cbar_label_font_size_var"], width=8)
        widgets["cbar_label_font_entry"].grid(row=5, column=1, sticky="w", padx=2, pady=2)

        ttk.Label(opt_frame, text="出力ステップ").grid(row=6, column=0, sticky="e", padx=6, pady=2)
        widgets["export_start_entry"] = ttk.Entry(opt_frame, textvariable=vars["export_start_var"], width=8)
        widgets["export_start_entry"].grid(row=6, column=1, sticky="w", padx=2, pady=2)
        ttk.Label(opt_frame, text="〜").grid(row=6, column=2, sticky="w", padx=2, pady=2)
        widgets["export_end_entry"] = ttk.Entry(opt_frame, textvariable=vars["export_end_var"], width=8)
        widgets["export_end_entry"].grid(row=6, column=3, sticky="w", padx=2, pady=2)

        ttk.Label(opt_frame, text="間引き数").grid(row=7, column=0, sticky="e", padx=6, pady=2)
        widgets["export_skip_entry"] = ttk.Entry(opt_frame, textvariable=vars["export_skip_var"], width=8)
        widgets["export_skip_entry"].grid(row=7, column=1, sticky="w", padx=2, pady=2)

        return widgets
