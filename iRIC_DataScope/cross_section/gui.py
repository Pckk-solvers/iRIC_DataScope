#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\cross_section\gui.py
"""
プロファイルプロット GUI（Toplevel 版）

子ウィンドウとして起動し、入力・出力パスや各種オプションを GUI から取得して
`plot_main` を呼び出します。エラーはダイアログで通知します。
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

logger = logging.getLogger(__name__)

try:
    from iRIC_DataScope.cross_section.plot_main import plot_main
except ModuleNotFoundError:
    if __name__ == "__main__" and __package__ is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(project_root))
        __package__ = "iRIC_DataScope.cross_section"
        from iRIC_DataScope.cross_section.plot_main import plot_main

DOCS_URL = "https://pckk-solvers.github.io/iRIC_DataScope/user_docs/cross_section/"


class ProfilePlotGUI(tk.Toplevel):
    """横断重ね合わせ図作成ツール GUI"""

    def __init__(self, master, input_dir: Path, output_dir: Path):
        logger.info("ProfilePlotGUI: init input_dir=%s, output_dir=%s", input_dir, output_dir)
        super().__init__(master)
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        # --- tkinter variables ---
        self.input_var = tk.StringVar(value=str(self.input_dir))
        self.output_var = tk.StringVar(value=str(self.output_dir))
        self.mode_var = tk.StringVar(value="multi")
        self.file_var = tk.StringVar()
        self.include_var = tk.StringVar()
        self.legend_var = tk.BooleanVar(value=True)
        self.title_var = tk.BooleanVar(value=True)
        self.grid_var = tk.BooleanVar(value=True)
        self.wse_var = tk.BooleanVar(value=True)
        self.yticks_var = tk.IntVar(value=5)
        self.yint_var = tk.BooleanVar(value=True)
        self.yaxis_mode = tk.StringVar(value="individual")
        self.ymin_var = tk.DoubleVar(value=230)
        self.ymax_var = tk.DoubleVar(value=260)
        self.xscale_var = tk.DoubleVar(value=1.0)
        self.yscale_var = tk.DoubleVar(value=1.0)
        self.prefix_var = tk.StringVar(value="I=")
        self.filename_var = tk.StringVar(value="cross_section.xlsx")

        self._status_var = tk.StringVar(value="I 絞込を入力してください。")
        self._status_detail_var = tk.StringVar(value="")

        self.title("横断重ね合わせ図作成")
        self._configure_styles()
        self._build_ui()
        self._bind_events()
        self._refresh_state()
        self._finalize_layout()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------
    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("CS.Heading.TLabel", font=("TkDefaultFont", 13, "bold"))
        style.configure("CS.Desc.TLabel", foreground="#4b5563")
        style.configure("CS.Muted.TLabel", foreground="#6b7280")
        style.configure("CS.Status.TLabel", foreground="#6b7280", font=("TkDefaultFont", 9))
        style.configure("CS.Section.TLabelframe", padding=10)
        style.configure("CS.Section.TLabelframe.Label", font=("TkDefaultFont", 9, "bold"))
        style.configure("CS.Run.TButton", font=("TkDefaultFont", 10, "bold"))
        style.configure("CS.Key.TLabel", foreground="#374151", font=("TkDefaultFont", 9))
        style.configure("CS.Val.TLabel", foreground="#1f2937", font=("TkDefaultFont", 9, "bold"))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _finalize_layout(self) -> None:
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 640)
        h = max(self.winfo_reqheight(), 560)
        self.geometry(f"{w}x{h}")
        self.minsize(600, 520)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)

        self._build_header(root)
        self._build_input_section(root)
        self._build_graph_section(root)
        self._build_output_section(root)
        self._build_action_section(root)
        self._build_status_bar(root)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="横断重ね合わせ図作成", style="CS.Heading.TLabel").grid(
            row=0, column=0, sticky="w",
        )
        ttk.Label(
            header,
            text="横断方向の重ね合わせ図を作成し、断面比較を支援します。",
            style="CS.Desc.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        meta = ttk.Frame(header)
        meta.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        meta.columnconfigure(1, weight=1)
        meta.columnconfigure(3, weight=2)

        ttk.Label(meta, text="入力:", style="CS.Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(meta, text=self.input_dir.name, style="CS.Val.TLabel").grid(
            row=0, column=1, sticky="w", padx=(4, 0),
        )
        ttk.Label(meta, text="出力:", style="CS.Muted.TLabel").grid(
            row=0, column=2, sticky="w", padx=(16, 0),
        )
        out_display = str(self.output_dir)
        if len(out_display) > 50:
            out_display = "…" + out_display[-48:]
        ttk.Label(meta, text=out_display, style="CS.Val.TLabel").grid(
            row=0, column=3, sticky="w", padx=(4, 0),
        )

    # ------------------------------------------------------------------
    # Input section (mode + file + I filtering)
    # ------------------------------------------------------------------
    def _build_input_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="入力", style="CS.Section.TLabelframe")
        section.pack(fill="x", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        # Mode
        ttk.Label(section, text="モード", style="CS.Key.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        mode_frame = ttk.Frame(section)
        mode_frame.grid(row=0, column=1, columnspan=2, sticky="w", pady=3)
        for label, val in [("横断図", "single"), ("横断重ね図", "multi")]:
            ttk.Radiobutton(
                mode_frame, text=label, variable=self.mode_var, value=val,
                command=self._toggle_file_select,
            ).pack(side="left", padx=(0, 16))

        # Target file (single mode)
        ttk.Label(section, text="対象ファイル", style="CS.Key.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        self.file_entry = ttk.Entry(section, textvariable=self.file_var)
        self.file_entry.grid(row=1, column=1, sticky="ew", pady=3)
        self.file_btn = ttk.Button(section, text="選択…", width=8, command=self._select_file)
        self.file_btn.grid(row=1, column=2, sticky="e", padx=(6, 0), pady=3)

        # I filter
        ttk.Label(section, text="I 絞込", style="CS.Key.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Entry(section, textvariable=self.include_var, width=30).grid(
            row=2, column=1, sticky="ew", pady=3,
        )
        ttk.Label(section, text="例: 1,3~5", style="CS.Muted.TLabel").grid(
            row=2, column=2, sticky="w", padx=(8, 0), pady=3,
        )

        self._toggle_file_select()

    # ------------------------------------------------------------------
    # Graph settings section
    # ------------------------------------------------------------------
    def _build_graph_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="グラフ設定", style="CS.Section.TLabelframe")
        section.pack(fill="x", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        # Checkboxes row
        chk_frame = ttk.Frame(section)
        chk_frame.grid(row=0, column=0, columnspan=3, sticky="w", pady=3)
        for text, var in [
            ("凡例", self.legend_var),
            ("タイトル", self.title_var),
            ("グリッド", self.grid_var),
            ("WSE描画", self.wse_var),
        ]:
            ttk.Checkbutton(chk_frame, text=text, variable=var).pack(side="left", padx=(0, 16))

        # Y ticks
        ttk.Label(section, text="Y目盛数", style="CS.Key.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Spinbox(section, from_=1, to=20, textvariable=self.yticks_var, width=6).grid(
            row=1, column=1, sticky="w", pady=3,
        )
        ttk.Checkbutton(section, text="Y軸整数目盛", variable=self.yint_var).grid(
            row=1, column=2, sticky="w", padx=(8, 0), pady=3,
        )

        # Y-axis range mode
        ttk.Label(section, text="Y軸範囲", style="CS.Key.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ymode_frame = ttk.Frame(section)
        ymode_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=3)
        for label, val in [
            ("各図最適", "individual"),
            ("全体最小最大", "global"),
            ("代表幅固定", "representative"),
            ("手動指定", "manual"),
        ]:
            ttk.Radiobutton(
                ymode_frame, text=label, variable=self.yaxis_mode, value=val,
                command=self._toggle_manual_entries,
            ).pack(side="left", padx=(0, 12))

        # Manual Y range
        manual_frame = ttk.Frame(section)
        manual_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Label(manual_frame, text="Y最小:", style="CS.Key.TLabel").pack(side="left", padx=(0, 4))
        self.ymin_entry = ttk.Entry(manual_frame, textvariable=self.ymin_var, width=10, state="disabled")
        self.ymin_entry.pack(side="left", padx=(0, 16))
        ttk.Label(manual_frame, text="Y最大:", style="CS.Key.TLabel").pack(side="left", padx=(0, 4))
        self.ymax_entry = ttk.Entry(manual_frame, textvariable=self.ymax_var, width=10, state="disabled")
        self.ymax_entry.pack(side="left")

        ttk.Separator(section).grid(row=4, column=0, columnspan=3, sticky="ew", pady=6)

        # Scales
        scale_frame = ttk.Frame(section)
        scale_frame.grid(row=5, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Label(scale_frame, text="Xスケール:", style="CS.Key.TLabel").pack(side="left", padx=(0, 4))
        ttk.Entry(scale_frame, textvariable=self.xscale_var, width=8).pack(side="left", padx=(0, 16))
        ttk.Label(scale_frame, text="Yスケール:", style="CS.Key.TLabel").pack(side="left", padx=(0, 4))
        ttk.Entry(scale_frame, textvariable=self.yscale_var, width=8).pack(side="left")

    # ------------------------------------------------------------------
    # Output section
    # ------------------------------------------------------------------
    def _build_output_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="出力", style="CS.Section.TLabelframe")
        section.pack(fill="x", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        ttk.Label(section, text="シート名接頭辞", style="CS.Key.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Entry(section, textvariable=self.prefix_var, width=20).grid(
            row=0, column=1, sticky="w", pady=3,
        )

        ttk.Label(section, text="出力ファイル名", style="CS.Key.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Entry(section, textvariable=self.filename_var, width=30).grid(
            row=1, column=1, sticky="ew", pady=3,
        )

    # ------------------------------------------------------------------
    # Action section
    # ------------------------------------------------------------------
    def _build_action_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent)
        section.pack(fill="x", pady=(4, 0))
        section.columnconfigure(0, weight=1)

        self.run_btn = ttk.Button(
            section, text="▶ 実行", style="CS.Run.TButton",
            command=self._run,
        )
        self.run_btn.grid(row=0, column=0, sticky="ew", ipady=4)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _build_status_bar(self, parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(8, 0))
        bar.columnconfigure(0, weight=1)
        ttk.Separator(bar).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Label(bar, textvariable=self._status_var, style="CS.Status.TLabel", anchor="w").grid(
            row=1, column=0, sticky="w",
        )
        ttk.Label(bar, textvariable=self._status_detail_var, style="CS.Muted.TLabel", anchor="e").grid(
            row=1, column=1, sticky="e",
        )

    # ------------------------------------------------------------------
    # Events & state
    # ------------------------------------------------------------------
    def _bind_events(self) -> None:
        self.bind_all("<Alt-h>", lambda e: self._open_help())
        self.include_var.trace_add("write", lambda *_: self._refresh_state())
        # Menu
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="マニュアルを開く", accelerator="Alt+H", command=self._open_help)
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)

    def _refresh_state(self) -> None:
        text = self.include_var.get().strip()
        if text:
            self._status_var.set("実行できます。")
            self._status_detail_var.set(f"I 絞込: {text}")
            self.run_btn.configure(state="normal")
        else:
            self._status_var.set("I 絞込を入力してください。")
            self._status_detail_var.set("")
            self.run_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    # Toggle helpers
    # ------------------------------------------------------------------
    def _toggle_file_select(self) -> None:
        state = "normal" if self.mode_var.get() == "single" else "disabled"
        self.file_entry.configure(state=state)
        self.file_btn.configure(state=state)

    def _toggle_manual_entries(self) -> None:
        manual = self.yaxis_mode.get() == "manual"
        state = "normal" if manual else "disabled"
        self.ymin_entry.configure(state=state)
        self.ymax_entry.configure(state=state)

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def _select_file(self) -> None:
        file = filedialog.askopenfilename(
            title="対象CSVを選択",
            filetypes=[("CSV ファイル", "*.csv"), ("All files", "*.*")],
            parent=self,
        )
        if file:
            self.file_var.set(file)

    def _open_help(self) -> None:
        webbrowser.open(DOCS_URL)

    # ------------------------------------------------------------------
    # Parse include IDs
    # ------------------------------------------------------------------
    def _parse_include_ids(self, text: str) -> list[int]:
        ids: set[int] = set()
        for part in text.split(","):
            part = part.strip()
            if "~" in part:
                a, b = part.split("~", 1)
                try:
                    ids.update(range(int(a), int(b) + 1))
                except ValueError:
                    raise ValueError(f"範囲指定が無効です: {part}")
            else:
                try:
                    ids.add(int(part))
                except ValueError:
                    raise ValueError(f"指定の I が無効です: {part}")
        return sorted(ids)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def _run(self) -> None:
        logger.info("実行ボタン押下")
        in_dir = Path(self.input_var.get())
        out_dir = Path(self.output_var.get())

        in_ok = in_dir.is_dir() or (in_dir.is_file() and in_dir.suffix.lower() in {".ipro", ".cgn"})
        if not in_ok:
            messagebox.showerror("エラー", f"入力が無効です:\n{in_dir}", parent=self)
            return
        if not out_dir.is_dir():
            messagebox.showerror("エラー", f"出力フォルダが無効です:\n{out_dir}", parent=self)
            return

        text = self.include_var.get().strip()
        if not text:
            messagebox.showerror("エラー", "I の絞込を入力してください。", parent=self)
            return
        try:
            include_ids = self._parse_include_ids(text)
        except ValueError as ve:
            messagebox.showerror("エラー", str(ve), parent=self)
            return

        mode = self.mode_var.get()
        sel_file = None
        if mode == "single" and self.file_var.get().strip():
            file_path = Path(self.file_var.get())
            if file_path.is_file():
                sel_file = str(file_path)

        yaxis_manual = None
        if self.yaxis_mode.get() == "manual":
            yaxis_manual = (self.ymin_var.get(), self.ymax_var.get())

        self.run_btn.configure(state="disabled")
        self._status_var.set("処理中...")
        self._status_detail_var.set("横断図を作成中です。")

        def worker() -> None:
            try:
                out_path = plot_main(
                    input_dir=str(in_dir),
                    output_dir=str(out_dir),
                    mode=mode,
                    selected_file=sel_file,
                    include_ids=include_ids,
                    show_legend=self.legend_var.get(),
                    show_title=self.title_var.get(),
                    show_grid=self.grid_var.get(),
                    yticks_count=self.yticks_var.get(),
                    yticks_integer=self.yint_var.get(),
                    yaxis_mode=self.yaxis_mode.get(),
                    yaxis_manual=yaxis_manual,
                    show_wse=self.wse_var.get(),
                    x_scale=self.xscale_var.get(),
                    y_scale=self.yscale_var.get(),
                    excel_filename=self.filename_var.get(),
                    sheet_prefix=self.prefix_var.get(),
                )
            except Exception as exc:
                self.after(0, lambda err=exc: self._finish_error(err))
                return
            self.after(0, lambda: self._finish_success(out_path))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_error(self, exc: Exception) -> None:
        self.run_btn.configure(state="normal")
        self._status_var.set("エラー")
        self._status_detail_var.set(str(exc))
        messagebox.showerror("エラー", f"処理に失敗しました:\n{exc}", parent=self)

    def _finish_success(self, out_path) -> None:
        self.run_btn.configure(state="normal")
        self._status_var.set("完了")
        self._status_detail_var.set(f"出力: {out_path}")
        messagebox.showinfo("完了", f"Excelを出力しました:\n{out_path}", parent=self)


# 直接実行用
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    in_dir = Path(filedialog.askdirectory(title="入力フォルダを選択"))
    out_dir = Path(filedialog.askdirectory(title="出力フォルダを選択"))
    root.destroy()
    root = tk.Tk()
    root.withdraw()
    ProfilePlotGUI(root, in_dir, out_dir)
    root.mainloop()
