# iric_tools/common/io_selector.py
"""
共通UIコンポーネント: 入力フォルダと出力フォルダを一組で選択するパネル
"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from .path_selector import PathSelector

class IOFolderSelector(ttk.Frame):
    """
    入力ディレクトリと出力ディレクトリを一度に選択・取得できるウィジェット。

    Attributes:
        input_selector (PathSelector): 入力フォルダ選択用
        output_selector (PathSelector): 出力フォルダ選択用
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # 入力フォルダ
        self.input_selector = PathSelector(self, label="入力フォルダ:", mode="directory")
        self.input_selector.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        # 出力フォルダ
        self.output_selector = PathSelector(self, label="出力フォルダ:", mode="directory")
        self.output_selector.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.columnconfigure(0, weight=1)

    def get_input_dir(self) -> Path:
        """選択された入力フォルダの Path を返す"""
        return Path(self.input_selector.get_path())

    def get_output_dir(self) -> Path:
        """選択された出力フォルダの Path を返す"""
        return Path(self.output_selector.get_path())
