# iRIC_DataScope/common/io_selector.py
"""
共通UIコンポーネント: 入力フォルダと出力フォルダを一組で選択するパネル
"""
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path


class ProjectPathSelector(ttk.Frame):
    """
    入力: プロジェクトフォルダ / CSVフォルダ / .ipro / .cgn / project.xml を選択できるセレクタ。
    """
    def __init__(self, master, label: str = "入力パス:", label_width: int = 14, **kwargs):
        super().__init__(master, **kwargs)
        self.var = tk.StringVar()
        ttk.Label(self, text=label, width=label_width, anchor="e").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Entry(self, textvariable=self.var, width=56).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(self, text="フォルダ", width=8, command=self._select_dir).grid(row=0, column=2, padx=(0, 4), pady=4)
        ttk.Button(self, text="ファイル", width=8, command=self._select_file).grid(row=0, column=3, pady=4)
        self.columnconfigure(1, weight=1)

    def _select_dir(self):
        path = filedialog.askdirectory(title="入力フォルダを選択")
        if path:
            self.var.set(path)

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="入力ファイルを選択 (.ipro / .cgn / project.xml)",
            filetypes=[
                ("iRIC project", "*.ipro"),
                ("CGNS file", "*.cgn"),
                ("Project metadata", "project.xml"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.var.set(path)

    def get_path(self) -> Path:
        """現在の入力パスを Path で返す（フォルダ or .ipro or .cgn or project.xml）"""
        return Path(self.var.get())


class OutputFolderSelector(ttk.Frame):
    """出力フォルダを選択するセレクタ。入力行と同じ列幅で配置する。"""

    def __init__(self, master, label: str = "出力フォルダ:", label_width: int = 14, **kwargs):
        super().__init__(master, **kwargs)
        self.var = tk.StringVar()
        ttk.Label(self, text=label, width=label_width, anchor="e").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Entry(self, textvariable=self.var, width=56).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(self, text="参照", width=8, command=self._select_dir).grid(row=0, column=2, padx=(0, 4), pady=4)
        ttk.Label(self, text="", width=8).grid(row=0, column=3, pady=4)
        self.columnconfigure(1, weight=1)

    def _select_dir(self):
        path = filedialog.askdirectory(title="出力フォルダを選択")
        if path:
            self.var.set(path)

    def get_path(self) -> Path:
        """現在の出力フォルダを Path で返す。"""
        return Path(self.var.get())


class _SelectorProxy:
    """IOFolderSelector の統一グリッド化後も .input_selector.var 等のAPIを維持するプロキシ。"""

    def __init__(self, var: tk.StringVar):
        self.var = var

    def get_path(self) -> Path:
        return Path(self.var.get())


class IOFolderSelector(ttk.Frame):
    """
    入力（プロジェクトフォルダ/CSVフォルダ/.ipro/.cgn/project.xml）と出力フォルダを
    一度に選択・取得できるウィジェット。

    統一グリッドで配置し、ラベル列・Entry列・ボタン列の幅を揃える。

    Attributes:
        input_selector: 入力パス選択用 (.var でアクセス)
        output_selector: 出力フォルダ選択用 (.var でアクセス)
    """

    _LABEL_WIDTH = 14
    _BTN_WIDTH = 8

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.columnconfigure(1, weight=1)

        # --- Row 0: 入力パス ---
        self._input_var = tk.StringVar()
        ttk.Label(self, text="入力パス:", width=self._LABEL_WIDTH, anchor="e").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=4,
        )
        ttk.Entry(self, textvariable=self._input_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=4,
        )
        ttk.Button(self, text="フォルダ", width=self._BTN_WIDTH, command=self._select_input_dir).grid(
            row=0, column=2, padx=(0, 4), pady=4,
        )
        ttk.Button(self, text="ファイル", width=self._BTN_WIDTH, command=self._select_input_file).grid(
            row=0, column=3, pady=4,
        )

        # --- Row 1: 出力フォルダ ---
        self._output_var = tk.StringVar()
        ttk.Label(self, text="出力フォルダ:", width=self._LABEL_WIDTH, anchor="e").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=4,
        )
        ttk.Entry(self, textvariable=self._output_var).grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=4,
        )
        ttk.Button(self, text="参照", width=self._BTN_WIDTH, command=self._select_output_dir).grid(
            row=1, column=2, padx=(0, 4), pady=4,
        )
        # col 3 は row 0 のボタンが幅を決めるのでスペーサ不要

        # --- 後方互換のプロキシ ---
        self.input_selector = _SelectorProxy(self._input_var)
        self.output_selector = _SelectorProxy(self._output_var)

        # 最近のパス行（add_recent_row で遅延追加）
        self._recent_var: tk.StringVar | None = None
        self._recent_combo: ttk.Combobox | None = None

    def add_recent_row(self, *, style: str = "") -> tuple[tk.StringVar, ttk.Combobox]:
        """Row 2: 最近のパス を統一グリッドに追加し、(var, combobox) を返す。"""
        self._recent_var = tk.StringVar()
        label_kwargs = {"style": style} if style else {}
        ttk.Label(
            self, text="最近のパス:", width=self._LABEL_WIDTH, anchor="e", **label_kwargs,
        ).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        self._recent_combo = ttk.Combobox(
            self, textvariable=self._recent_var, state="readonly",
        )
        self._recent_combo.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._recent_btn = ttk.Button(self, text="復元", width=self._BTN_WIDTH)
        self._recent_btn.grid(row=2, column=2, padx=(0, 4), pady=4)
        # col 3 は row 0 のボタンが幅を決めるのでスペーサ不要
        return self._recent_var, self._recent_combo

    def get_recent_button(self) -> ttk.Button:
        """復元ボタンを返す（command のバインド用）。"""
        return self._recent_btn

    # --- Input dialogs ---
    def _select_input_dir(self):
        path = filedialog.askdirectory(title="入力フォルダを選択")
        if path:
            self._input_var.set(path)

    def _select_input_file(self):
        path = filedialog.askopenfilename(
            title="入力ファイルを選択 (.ipro / .cgn / project.xml)",
            filetypes=[
                ("iRIC project", "*.ipro"),
                ("CGNS file", "*.cgn"),
                ("Project metadata", "project.xml"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._input_var.set(path)

    def _select_output_dir(self):
        path = filedialog.askdirectory(title="出力フォルダを選択")
        if path:
            self._output_var.set(path)

    # --- Public API ---
    def get_input_dir(self) -> Path:
        """選択された入力 Path を返す（フォルダ or .ipro or .cgn or project.xml）"""
        return Path(self._input_var.get())

    def get_output_dir(self) -> Path:
        """選択された出力フォルダの Path を返す"""
        return Path(self._output_var.get())
