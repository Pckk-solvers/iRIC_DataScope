# iRIC_DataScope/common/io_selector.py
"""
共通UIコンポーネント: 入力フォルダと出力フォルダを一組で選択するパネル
"""
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from .path_selector import PathSelector


class ProjectPathSelector(ttk.Frame):
    """
    入力: プロジェクトフォルダ / CSVフォルダ / .ipro / .cgn を選択できるセレクタ。
    """
    def __init__(self, master, label: str = "入力パス:", **kwargs):
        super().__init__(master, **kwargs)
        self.var = tk.StringVar()
        ttk.Label(self, text=label).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(self, textvariable=self.var, width=40).grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(self, text="フォルダ", command=self._select_dir).grid(row=0, column=2, padx=2)
        ttk.Button(self, text="ファイル", command=self._select_file).grid(row=0, column=3, padx=2)
        self.columnconfigure(1, weight=1)

    def _select_dir(self):
        path = filedialog.askdirectory(title="入力フォルダを選択")
        if path:
            self.var.set(path)

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="入力ファイルを選択 (.ipro / .cgn)",
            filetypes=[
                ("iRIC project", "*.ipro"),
                ("CGNS file", "*.cgn"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.var.set(path)

    def get_path(self) -> Path:
        """現在の入力パスを Path で返す（フォルダ or .ipro or .cgn）"""
        return Path(self.var.get())


class IOFolderSelector(ttk.Frame):
    """
    入力（プロジェクトフォルダ/CSVフォルダ/.ipro/.cgn）と出力フォルダを一度に選択・取得できるウィジェット。

    Attributes:
        input_selector (PathSelector): 入力フォルダ選択用
        output_selector (PathSelector): 出力フォルダ選択用
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # 入力（プロジェクトフォルダ/CSVフォルダ/.ipro/.cgn）
        self.input_selector = ProjectPathSelector(self, label="入力パス:")
        self.input_selector.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        # 出力フォルダ
        self.output_selector = PathSelector(self, label="出力フォルダ:", mode="directory")
        self.output_selector.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.columnconfigure(0, weight=1)

    def get_input_dir(self) -> Path:
        """選択された入力 Path を返す（フォルダ or .ipro or .cgn）"""
        return Path(self.input_selector.get_path())

    def get_output_dir(self) -> Path:
        """選択された出力フォルダの Path を返す"""
        return Path(self.output_selector.get_path())
