# iRIC_DataScope\common\path_selector.py
"""
汎用パス選択UIコンポーネント

- mode="directory": フォルダ選択ダイアログ
- mode="file_open": 単一ファイル選択ダイアログ
- mode="files_open": 複数ファイル選択ダイアログ
- mode="file_save": ファイル保存先指定ダイアログ
"""
import os
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .ui_config import FONT_MAIN, PAD_X, PAD_Y

logger = logging.getLogger(__name__)

class PathSelector(ttk.Frame):
    """
    汎用パス選択UI

    Args:
        master: 親ウィジェット
        label (str): ラベル表示テキスト
        mode (str): 'directory', 'file_open', 'files_open', or 'file_save'
        filetypes (list[tuple[str,str]] | None): ファイル選択時のフィルタ
        default_ext (str): ファイル保存時のデフォルト拡張子
    """
    def __init__(self, master, label: str, mode: str = "directory",
                 filetypes=None, default_ext: str = ""):
        super().__init__(master, padding=(PAD_X, PAD_Y))
        self.mode = mode
        self.var = tk.StringVar()
        # ラベルとエントリ
        ttk.Label(self, text=label, font=FONT_MAIN).grid(row=0, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.var, width=40, font=FONT_MAIN).grid(row=0, column=1, sticky="ew")
        # ボタンテキスト設定
        btn_text_map = {
            "directory": "参照",
            "file_open": "開く",
            "files_open": "複数選択",
            "file_save": "保存先選択",
        }
        btn_text = btn_text_map.get(mode, "参照")
        ttk.Button(self, text=btn_text, command=self._select).grid(row=0, column=2)
        self.filetypes = filetypes
        self.default_ext = default_ext
        self.columnconfigure(1, weight=1)

    def _select(self):
        if self.mode == "directory":
            path = filedialog.askdirectory(title=self.var.get() or None)
        elif self.mode == "file_open":
            path = filedialog.askopenfilename(
                title=self.var.get() or None,
                filetypes=self.filetypes or [("All files", "*.*")]
            )
        elif self.mode == "files_open":
            paths = filedialog.askopenfilenames(
                title=self.var.get() or None,
                filetypes=self.filetypes or [("All files", "*.*")]
            )
            path = ";".join(paths) if paths else ""
        else:  # file_save
            path = filedialog.asksaveasfilename(
                title=self.var.get() or None,
                defaultextension=self.default_ext,
                filetypes=self.filetypes or [("All files", "*.*")]
            )
        if path:
            self.var.set(path)
            logger.info(f"{self.mode} 選択: {path}")

    def get_path(self):
        """
        選択されたパスを返す

        Returns:
            str or list[str]: mode=='files_open' の場合は list[str]、それ以外は str

        Raises:
            ValueError: 無効なパスが選択されている場合
        """
        p = self.var.get()
        if not p:
            messagebox.showerror("エラー", "パスを選択してください。")
            raise ValueError("パス未選択")
        if self.mode == "directory":
            if not os.path.isdir(p):
                messagebox.showerror("エラー", "有効なフォルダを選択してください。")
                raise ValueError(f"無効なフォルダパス: {p}")
            return p
        if self.mode in ("file_open", "file_save"):
            if not os.path.isfile(p) and self.mode == "file_open":
                messagebox.showerror("エラー", "有効なファイルを選択してください。")
                raise ValueError(f"無効なファイルパス: {p}")
            return p
        if self.mode == "files_open":
            paths = p.split(";")
            valid = [x for x in paths if x]
            if not valid or not all(os.path.isfile(x) for x in valid):
                messagebox.showerror("エラー", "有効なファイルを選択してください。")
                raise ValueError(f"無効なファイルが含まれています: {p}")
            return valid
        # fallback
        return p
