#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\cross_section\gui.py
"""
プロファイルプロット GUI （Toplevel版）

子ウィンドウとして起動し、入力・出力パスや各種オプションをGUIから取得して
`plot_main` を呼び出します。エラーはダイアログで通知します。
"""
import sys
import webbrowser
import logging
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ロガー設定
logger = logging.getLogger(__name__)

# スクリプト単体実行時にパッケージを認識させる
if __name__ == "__main__" and __package__ is None:
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    __package__ = "iRIC_DataScope.cross_section"

from .plot_main import plot_main

class ProfilePlotGUI(tk.Toplevel):
    def __init__(self, master, input_dir: Path, output_dir: Path):
        logger.info(f"GUI インスタンス作成: input_dir={input_dir}, output_dir={output_dir}")
        super().__init__(master)
        start = time.perf_counter()
        self.master = master
        self.input_dir = input_dir
        self.output_dir = output_dir

        self.title("横断重ね合わせ図作成")
        self.geometry("550x650")

        # ─── メニューバー（ヘルプ）作成 ───
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label="マニュアルを開く",
            accelerator="Alt+H",
            command=self._open_help
        )
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)
        self.bind_all("<Alt-h>", lambda e: self._open_help())
        # ────────────────────────────────

        self._build_ui()
        logger.debug("ProfilePlotGUI: UI built in %.3fs", time.perf_counter() - start)
        self._toggle_manual_entries()  # 初期状態を設定
        logger.debug("ProfilePlotGUI: Initialization complete in %.3fs", time.perf_counter() - start)

    def _open_help(self):
        """ヘルプページをスレッドセーフに開く"""
        def open_url():
            webbrowser.open("https://pckk-solvers.github.io/iRIC_DataScope/user_docs/cross_section/")
        
        threading.Thread(target=open_url, daemon=True).start()

    def _build_ui(self):
        logger.info("GUI ビルド開始")
        pad = {'padx': 8, 'pady': 4}
        # 入力フォルダ
        tk.Label(self, text="入力フォルダ:").grid(row=0, column=0, sticky="e", **pad)
        self.input_var = tk.StringVar(value=str(self.input_dir))
        tk.Entry(self, textvariable=self.input_var, width=40, state='readonly').grid(row=0, column=1, columnspan=2, sticky="EW", **pad)

        # 出力フォルダ
        tk.Label(self, text="出力フォルダ:").grid(row=1, column=0, sticky="e", **pad)
        self.output_var = tk.StringVar(value=str(self.output_dir))
        tk.Entry(self, textvariable=self.output_var, width=40, state='readonly').grid(row=1, column=1, columnspan=2, sticky="EW", **pad)

        # --- モード選択 ---
        tk.Label(self, text="モード:").grid(row=2, column=0, sticky="e", **pad)
        self.mode_var = tk.StringVar(value="multi")
        for i, (label, val) in enumerate([("横断図","single"), ("横断重ね図","multi")]):
            rb = ttk.Radiobutton(
                self,
                text=label,
                variable=self.mode_var,
                value=val,
                command=self._toggle_file_select
            )
            rb.grid(row=2, column=1 + i, sticky="w", **pad)
        # single モード時のファイル指定
        tk.Label(self, text="対象ファイル:").grid(row=3, column=0, sticky="e", **pad)
        self.file_var = tk.StringVar()
        self.file_entry = tk.Entry(self, textvariable=self.file_var, width=40)
        self.file_entry.grid(row=3, column=1, columnspan=2, sticky="EW", **pad)
        self.file_btn = tk.Button(self, text="選択", command=self._select_file)
        self.file_btn.grid(row=3, column=3, sticky="w", **pad)

        # Profile_ID 絞込
        tk.Label(self, text="I 絞込 (例: 1,3~5):").grid(row=4, column=0, sticky="e", **pad)
        self.include_var = tk.StringVar()
        tk.Entry(self, textvariable=self.include_var, width=40).grid(row=4, column=1, sticky="EW", **pad)

        # グラフオプション
        self.legend_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="凡例表示", variable=self.legend_var).grid(row=5, column=1, sticky="w", **pad)
        self.title_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="タイトル表示", variable=self.title_var).grid(row=6, column=1, sticky="w", **pad)
        self.grid_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="グリッド表示", variable=self.grid_var).grid(row=7, column=1, sticky="w", **pad)
        self.wse_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="WSE を描画", variable=self.wse_var).grid(row=8, column=1, sticky="w", **pad)

        # Y軸目盛
        tk.Label(self, text="Y目盛数:").grid(row=9, column=0, sticky="e", **pad)
        self.yticks_var = tk.IntVar(value=5)
        tk.Spinbox(self, from_=1, to=20, textvariable=self.yticks_var, width=5).grid(row=9, column=1, sticky="w", **pad)
        self.yint_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Y軸整数目盛", variable=self.yint_var).grid(row=10, column=1, sticky="w", **pad)

        # Y軸範囲
        tk.Label(self, text="Y軸範囲:").grid(row=11, column=0, sticky="e", **pad)
        self.yaxis_mode = tk.StringVar(value="individual")
        for i, (label, val) in enumerate([
                ("各図最適","individual"),
                ("全体最小最大","global"),
                ("代表幅固定","representative"),
                ("手動指定","manual"),
        ]):
            rb = ttk.Radiobutton(
                self,
                text=label,
                variable=self.yaxis_mode,
                value=val,
                command=self._toggle_manual_entries
            )
            rb.grid(row=11, column=1 + i, sticky="we", **pad)
        for col in (1,2,3,4):
            self.grid_columnconfigure(col, weight=1, uniform="yaxis_uniform")

        # 手動指定用の最小／最大入力欄
        self.ymin_var = tk.DoubleVar(value=230)
        self.ymax_var = tk.DoubleVar(value=260)
        tk.Label(self, text="Y最小:").grid(row=12, column=0, sticky="e", **pad)
        self.ymin_entry = tk.Entry(self, textvariable=self.ymin_var, width=10, state="disabled")
        self.ymin_entry.grid(row=12, column=1, sticky="w", **pad)
        tk.Label(self, text="Y最大:").grid(row=13, column=0, sticky="e", **pad)
        self.ymax_entry = tk.Entry(self, textvariable=self.ymax_var, width=10, state="disabled")
        self.ymax_entry.grid(row=13, column=1, sticky="w", **pad)

        # スケール
        tk.Label(self, text="Xスケール:").grid(row=14, column=0, sticky="e", **pad)
        self.xscale_var = tk.DoubleVar(value=1.0)
        tk.Entry(self, textvariable=self.xscale_var, width=10).grid(row=14, column=1, sticky="w", **pad)
        tk.Label(self, text="Yスケール:").grid(row=15, column=0, sticky="e", **pad)
        self.yscale_var = tk.DoubleVar(value=1.0)
        tk.Entry(self, textvariable=self.yscale_var, width=10).grid(row=15, column=1, sticky="w", **pad)

        # シート名接頭辞 & 出力ファイル名
        tk.Label(self, text="シート名接頭辞:").grid(row=16, column=0, sticky="e", **pad)
        self.prefix_var = tk.StringVar(value="I=")
        tk.Entry(self, textvariable=self.prefix_var, width=20).grid(row=16, column=1, sticky="EW", **pad)
        tk.Label(self, text="出力ファイル名:").grid(row=17, column=0, sticky="e", **pad)
        self.filename_var = tk.StringVar(value="cross_section.xlsx")
        tk.Entry(self, textvariable=self.filename_var, width=30).grid(row=17, column=1, columnspan=2, sticky="EW", **pad)

        # 実行ボタン
        tk.Button(self, text="実行", command=self._run).grid(row=18, column=0, columnspan=5, pady=20)
        self._toggle_file_select()

    def _toggle_file_select(self):
        state = 'normal' if self.mode_var.get() == 'single' else 'disabled'
        self.file_entry.configure(state=state)
        self.file_btn.configure(state=state)

    def _toggle_manual_entries(self):
        manual = (self.yaxis_mode.get() == "manual")
        state = 'normal' if manual else 'disabled'
        self.ymin_entry.configure(state=state)
        self.ymax_entry.configure(state=state)

    def _select_file(self):
        logger.info("ファイル選択ダイアログを開く")
        file = filedialog.askopenfilename(title="対象CSVを選択", filetypes=[("CSV ファイル","*.csv"),("All files","*.*")])
        if file:
            logger.info(f"ファイル選択: {file}")
            self.file_var.set(file)

    def _parse_include_ids(self, text: str):
        ids = set()
        for part in text.split(','):
            part = part.strip()
            if '~' in part:
                a, b = part.split('~', 1)
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

    def _run(self):
        logger.info("実行ボタン押下")
        in_dir = Path(self.input_var.get())
        out_dir = Path(self.output_var.get())
        logger.debug(f"入力フォルダ: {in_dir}, 出力フォルダ: {out_dir}")
        
        in_ok = in_dir.is_dir() or (in_dir.is_file() and in_dir.suffix.lower() == ".ipro")
        if not in_ok:
            logger.error(f"入力フォルダが無効: {in_dir}")
            messagebox.showerror("エラー", f"入力が無効です:\n{in_dir}")
            return
        if not out_dir.is_dir():
            logger.error(f"出力フォルダが無効: {out_dir}")
            messagebox.showerror("エラー", f"出力フォルダが無効です:\n{out_dir}")
            return

        mode = self.mode_var.get()
        logger.info(f"実行モード: {mode}")
        sel_file = None
        if mode == 'single' and self.file_var.get().strip():
            file_path = Path(self.file_var.get())
            logger.debug(f"選択ファイル: {file_path}")
            if file_path.is_file():
                sel_file = str(file_path)

        text = self.include_var.get().strip()
        if not text:
            messagebox.showerror("エラー", "I の絞込を入力してください。")
            return
        try:
            include_ids = self._parse_include_ids(text)
        except ValueError as ve:
            messagebox.showerror("エラー", str(ve))
            return

        show_legend = self.legend_var.get()
        show_title = self.title_var.get()
        show_grid = self.grid_var.get()
        show_wse = self.wse_var.get()
        yticks_count = self.yticks_var.get()
        yticks_integer = self.yint_var.get()
        yaxis_mode = self.yaxis_mode.get()
        if yaxis_mode == 'manual':
            yaxis_manual = (self.ymin_var.get(), self.ymax_var.get())
        else:
            yaxis_manual = None

        x_scale = self.xscale_var.get()
        y_scale = self.yscale_var.get()
        sheet_prefix = self.prefix_var.get()
        excel_name = self.filename_var.get()

        try:
            out_path = plot_main(
                input_dir=str(in_dir),
                output_dir=str(out_dir),
                mode=mode,
                selected_file=sel_file,
                include_ids=include_ids,
                show_legend=show_legend,
                show_title=show_title,
                show_grid=show_grid,
                yticks_count=yticks_count,
                yticks_integer=yticks_integer,
                yaxis_mode=yaxis_mode,
                yaxis_manual=yaxis_manual,
                show_wse=show_wse,
                x_scale=x_scale,
                y_scale=y_scale,
                excel_filename=excel_name,
                sheet_prefix=sheet_prefix
            )
            if messagebox.showinfo("完了", f"Excelを出力しました:\n{out_path}") == "ok":
                self.destroy()
        except FileNotFoundError as fnf_err:
            messagebox.showerror("ファイルエラー", str(fnf_err))
        except Exception as err:
            messagebox.showerror("予期せぬエラー", str(err))

# 直接実行用
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    in_dir = Path(filedialog.askdirectory(title="入力フォルダを選択"))
    out_dir = Path(filedialog.askdirectory(title="出力フォルダを選択"))
    root.destroy()
    ProfilePlotGUI(None, in_dir, out_dir)
    tk.mainloop()
