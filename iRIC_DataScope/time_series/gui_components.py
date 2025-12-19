#!/usr/bin/env python3
# iRIC_DataScope\time_series\gui_components.py
"""
iRIC_DataScope/time_series/gui_components.py:
時系列抽出ツール GUI リファクタリング版

- 入力/出力フォルダの表示（編集不可）
- 格子点 (I,J) の追加・削除
- 変数選択チェックボックス
- ヘルプメニュー（Alt+H で Notion マニュアルを開く）
- 実行ボタン押下で処理を実行し、結果を通知
"""
import os
import logging
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk, filedialog
from pathlib import Path
import pandas as pd

from iRIC_DataScope.common.path_selector import PathSelector
from iRIC_DataScope.common.ui_config import FONT_MAIN, PAD_X, PAD_Y
from .processor import aggregate_all
from .excel_writer import write_sheets

# モジュールレベルのロガーを取得
logger = logging.getLogger(__name__)


class InputDirectorySelector(PathSelector):
    """
    入力ディレクトリを表示するウィジェット（編集不可）
    初期ディレクトリを設定し、参照ボタンを削除して読み取り専用にする
    """
    def __init__(self, master, initial_dir: str | None = None):
        super().__init__(master, label="入力フォルダ:", mode="directory")
        # 初期ディレクトリをセット
        if initial_dir:
            self.var.set(initial_dir)
        # Entry を読み取り専用に変更し、参照ボタンを破棄
        for widget in self.grid_slaves(row=0, column=1):
            widget.configure(state="readonly")
        for widget in self.grid_slaves(row=0, column=2):
            widget.destroy()


class OutputDirectorySelector(PathSelector):
    """
    出力ディレクトリを表示するウィジェット（編集不可）
    同様に初期ディレクトリ設定と参照ボタン除去
    """
    def __init__(self, master, initial_dir: str | None = None):
        super().__init__(master, label="出力フォルダ:", mode="directory")
        if initial_dir:
            self.var.set(initial_dir)
        for widget in self.grid_slaves(row=0, column=1):
            widget.configure(state="readonly")
        for widget in self.grid_slaves(row=0, column=2):
            widget.destroy()


class GridSelector(ttk.Frame):
    """
    格子点 (I,J) を追加・削除できるテーブルUI。設定CSV一括読み込み、全消去機能付き。
    """
    def __init__(self, master):
        super().__init__(master, padding=(PAD_X, PAD_Y))
        # Treeview の設定
        self.tree = ttk.Treeview(self, columns=("I", "J"), show="headings", height=6)
        self.tree.heading("I", text="I index")
        self.tree.heading("J", text="J index")
        # 縦スクロールバー
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        # Grid に配置
        self.tree.grid(row=0, column=0, columnspan=8, sticky='nsew')
        vsb.grid  (row=0, column=8, sticky='ns', padx=(0, PAD_X))

        # --- 一行目の入力フィールド＆ボタン配置 ---
        pad = {'padx': 8, 'pady': 4}
        # 設定CSV一括読み込み・全クリアをまとめて配置
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(btn_frame, text="インポート", command=self.import_points).pack(side="left")
        ttk.Button(btn_frame, text="クリア", command=self.clear_points).pack(side="left", padx=4)

        # 個別 I,J 入力と追加・ソート・削除
        ttk.Label(self, text="I :", font=10).grid(row=1, column=2, sticky="e", **pad)
        self.i_entry = ttk.Entry(self, width=5, font=FONT_MAIN)
        self.i_entry.grid(row=1, column=3, sticky="w", **pad)
        ttk.Label(self, text="J :", font=10).grid(row=1, column=4, sticky="e", **pad)
        self.j_entry = ttk.Entry(self, width=5, font=FONT_MAIN)
        self.j_entry.grid(row=1, column=5, sticky="w", **pad)
        ttk.Button(self, text="追加", command=self.add_point).grid(row=1, column=6, sticky="w", pady=4)
        ttk.Button(self, text="ソート", command=self.sort_points).grid(row=1, column=7, sticky="w", pady=4)
        ttk.Button(self, text="削除", command=self.remove_point).grid(row=1, column=8, sticky="w", pady=4)


        # --- この行だけ幅をそろえる設定 ---
        for col in range(9):
            self.grid_columnconfigure(
                col,
                uniform="row1_equal",
                weight=0
            )
        # -------------------------------------------------
        # グリッド伸縮設定
        self.grid_columnconfigure(0, weight=1)  # Treeview 列
        # vsb は固定なので weight=0 のまま
        self.grid_rowconfigure(0, weight=1)     # Treeview 行

    def add_point(self):
        """I,J を整数として追加し、フォームをクリア"""
        try:
            i = int(self.i_entry.get())
            j = int(self.j_entry.get())
        except ValueError:
            messagebox.showerror("入力エラー", "I, J は整数で入力してください。")
            return
        self.tree.insert("", "end", values=(i, j))
        self.i_entry.delete(0, "end")
        self.j_entry.delete(0, "end")
        logger.info(f"格子点追加: ({i},{j})")

    def remove_point(self):
        """選択中の格子点を削除"""
        for item in self.tree.selection():
            vals = self.tree.item(item, 'values')
            self.tree.delete(item)
            logger.info(f"格子点削除: {vals}")

    def import_points(self):
        """設定CSVから I,J 列を読み込み、一括追加"""
        file_path = filedialog.askopenfilename(
            title="設定CSVを選択",
            filetypes=[("CSV files", "*.csv"), ("All files", "*")]
        )
        if not file_path:
            return
        try:
            df = pd.read_csv(file_path, usecols=["I", "J"] )
            for _, row in df.iterrows():
                i_val = int(row["I"])
                j_val = int(row["J"])
                self.tree.insert("", "end", values=(i_val, j_val))
                logger.info(f"CSV から格子点追加: ({i_val},{j_val})")
        except Exception as e:
            messagebox.showerror("読み込みエラー", f"CSV 読み込みに失敗しました:\n{e}")
            logger.error(f"CSV 読み込みエラー: {e}", exc_info=True)

    def clear_points(self):
        """テーブル内すべての格子点をクリア"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        logger.info("格子点全削除完了")
        
    def sort_points(self):
        """I,J のペアで昇順ソートして Treeview を並び替え"""
        # (I, J, item_id) のタプルリストを作成
        data = [
            (int(self.tree.set(item, 'I')), int(self.tree.set(item, 'J')), item)
            for item in self.tree.get_children('')
        ]
        # I→J の昇順でソート
        data.sort()
        # ソート順に move で並べ替え
        for idx, (_, _, item) in enumerate(data):
            self.tree.move(item, '', idx)

    def get_points(self) -> list[tuple[int, int]]:
        """現在の格子点リストを返却"""
        return [tuple(map(int, self.tree.item(r, "values"))) for r in self.tree.get_children()]



class VariableSelector(ttk.Frame):
    """
    ディレクトリ内 CSV のヘッダーから変数選択用チェックボックスUI
    """
    def __init__(self, master, initial_dir: str | None = None):
        super().__init__(master, padding=(PAD_X, PAD_Y))
        self.checks: dict[str, tk.BooleanVar] = {}
        self.sample_dir = initial_dir or ""
        self._build_ui()
        self._bind_dir_change(master)

    def _bind_dir_change(self, master):
        """ディレクトリ変更時に UI を再構築"""
        for w in master.winfo_children():
            if isinstance(w, PathSelector) and w.mode == "directory":
                w.var.trace_add("write", lambda *a: self.refresh(w.var.get()))
                break

    def _build_ui(self):
        """チェックボックス群を生成"""
        for widget in self.winfo_children():
            widget.destroy()
        self.checks.clear()
        columns: list[str] = []

        # サンプル CSV からカラム一覧を取得
        if self.sample_dir and os.path.isdir(self.sample_dir):
            try:
                from iRIC_DataScope.common.csv_reader import list_csv_files, read_iric_csv
                files = list_csv_files(self.sample_dir)
                if files:
                    _, df = read_iric_csv(files[0])
                    columns = [c for c in df.columns if c not in ('I', 'J')]
            except Exception as e:
                logger.error(f"VariableSelector: {e}")

        ttk.Label(self, text="抽出変数:", font=FONT_MAIN).grid(row=0, column=0, sticky='w')
        for idx, col in enumerate(columns):
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(self, text=col, variable=var)
            cb.grid(row=idx//4 + 1, column=idx%4, sticky='w')
            self.checks[col] = var

    def refresh(self, sample_dir: str):
        """ディレクトリ変更時に再構築"""
        self.sample_dir = sample_dir
        self._build_ui()

    def get_variables(self) -> list[str]:
        """選択中の変数リストを返却、無選択ならエラー"""
        selected = [c for c, v in self.checks.items() if v.get()]
        if not selected:
            messagebox.showerror("エラー", "変数を選択してください。")
            raise ValueError("変数未選択")
        logger.info(f"抽出変数: {selected}")
        return selected


class TimeSeriesGUI(tk.Toplevel):
    """
    時系列抽出ツールのメインGUIクラス
    - メニューバー（ヘルプ）
    - 入力/出力ディレクトリ選択
    - 出力ファイル名入力
    - 格子点選択
    - 変数選択
    - 実行ボタン
    - レイアウト自動調整
    """
    def __init__(self, master=None, initial_input_dir=None, initial_output_dir=None):
        super().__init__(master)
        self.input_dir = initial_input_dir
        self.output_dir = initial_output_dir
        self.file_name_var = tk.StringVar(value="time_series.xlsx")

        # ウィンドウ初期設定
        self._configure_window()
        # ヘルプメニュー作成
        self._create_menu()
        # ウィジェット生成・配置
        self._create_widgets()
        # ショートカットバインド
        self._bind_events()
        # 最小サイズ設定
        self._finalize_layout()

    def _configure_window(self):
        """タイトルとリサイズ可否設定"""
        self.title("時系列データ抽出")
        self.resizable(True, True)

    def _create_menu(self):
        """メニューバーにヘルプを追加"""
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label="マニュアルを開く",
            accelerator="Alt+H",
            command=lambda: webbrowser.open(
                "https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=25#1f4ed1e8e79f8074a3d6eda343d6a550"
            )
        )
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)

    def _create_widgets(self):
        """入出力セレクタ、ファイル名、Grid/Variable Selector、実行ボタンを配置"""
        # ディレクトリセレクタ
        self.input_sel = InputDirectorySelector(self, initial_dir=self.input_dir)
        self.input_sel.pack(fill="x", padx=PAD_X, pady=PAD_Y)
        self.output_sel = OutputDirectorySelector(self, initial_dir=self.output_dir)
        self.output_sel.pack(fill="x", padx=PAD_X, pady=PAD_Y)

        # 出力ファイル名
        # 1) Frame を作る
        row = tk.Frame(self)
        row.pack(fill="x", padx=PAD_X, pady=PAD_Y)

        # 2) その中で左右並びに pack
        tk.Label(row, text="出力ファイル名:", font=FONT_MAIN).pack(side="left")
        tk.Entry(row, textvariable=self.file_name_var, width=30).pack(
            side="left", fill="x"
        )

        # 格子点セレクタ
        self.grid_sel = GridSelector(self)
        # both=縦横、expand=True=余白も埋める
        self.grid_sel.pack(fill="both", expand=True, padx=PAD_X, pady=PAD_Y)

        # 変数選択セレクタ
        self.var_sel = VariableSelector(self, initial_dir=self.input_dir)
        self.var_sel.pack(fill="x", padx=PAD_X, pady=PAD_Y)


        # 実行ボタン
        tk.Button(self, text="実行", font=FONT_MAIN, command=self._on_run).pack(pady=PAD_Y, anchor="center")

    def _bind_events(self):
        """Alt+H でマニュアルを開くショートカットを設定"""
        self.bind_all("<Alt-h>", lambda e: webbrowser.open(
            "https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=25#1f4ed1e8e79f8074a3d6eda343d6a550"
        ))

    def _on_run(self):
        """実行処理：入力/出力パス取得→集計→Excel出力→完了通知"""
        try:
            in_dir = Path(self.input_sel.get_path())
            out_dir = Path(self.output_sel.get_path())
            out_file = out_dir / self.file_name_var.get()
            points = self.grid_sel.get_points()
            variables = self.var_sel.get_variables()
            # データ集計とシート出力
            data = aggregate_all(in_dir, points, variables)
            write_sheets(data, str(out_file))
            if messagebox.showinfo("完了", f"出力ファイル: {out_file}\n処理完了しました。")== "ok":
                self.destroy()
        except Exception as e:
            logger.error(f"エラー: {e}", exc_info=True)
            messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{e}")

    def _finalize_layout(self):
        """ウィジェット配置後に最小ウィンドウサイズを設定"""
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}")
        self.minsize(w, h)


def launch_time_series_gui(master=None, initial_input_dir=None, initial_output_dir=None):
    """
    TimeSeriesGUI を生成して返す
    （LauncherApp が保持して lift/WM_DELETE_WINDOW を管理します）
    """
    gui = TimeSeriesGUI(master, initial_input_dir, initial_output_dir)
    return gui
