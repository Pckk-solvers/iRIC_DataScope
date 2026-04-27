#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\lr_wse\gui.py
"""
lr_wse GUI: iRIC 左右岸最大水位整理ツール
このウィンドウは Toplevel で生成され、ランチャーの Tk を master に持ちます。
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
    from iRIC_DataScope.lr_wse.main import run_lr_wse
except ModuleNotFoundError:
    if __name__ == "__main__" and __package__ is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(repo_root))
        __package__ = "iRIC_DataScope.lr_wse"
        from iRIC_DataScope.lr_wse.main import run_lr_wse

DOCS_URL = "https://pckk-solvers.github.io/iRIC_DataScope/user_docs/lr_wse/"


class LrWseGUI(tk.Toplevel):
    """iRIC 左右岸最大水位整理ツール GUI"""

    def __init__(self, master, input_dir: Path, output_dir: Path):
        logger.info("LrWseGUI: init input_dir=%s, output_dir=%s", input_dir, output_dir)
        super().__init__(master)
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.config_file: Path | None = None
        self._swap_warned = False

        # --- tkinter variables ---
        self.input_var = tk.StringVar(value=str(self.input_dir))
        self.config_var = tk.StringVar(value="(未選択)")
        self.output_var = tk.StringVar(value=str(self.output_dir))
        self.use_temp = tk.BooleanVar(value=False)
        self.temp_var = tk.StringVar()
        self.filename_var = tk.StringVar(value="LR_WSE.xlsx")
        self.missing_var = tk.StringVar(value="")
        self.min_depth_var = tk.StringVar(value="")

        self._status_var = tk.StringVar(value="設定ファイルを選択してください。")
        self._status_detail_var = tk.StringVar(value="")

        self.title("左右岸水位抽出")
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
        style.configure("LW.Heading.TLabel", font=("TkDefaultFont", 13, "bold"))
        style.configure("LW.Desc.TLabel", foreground="#4b5563")
        style.configure("LW.Muted.TLabel", foreground="#6b7280")
        style.configure("LW.Status.TLabel", foreground="#6b7280", font=("TkDefaultFont", 9))
        style.configure("LW.Ready.TLabel", foreground="#047857", font=("TkDefaultFont", 9, "bold"))
        style.configure("LW.Section.TLabelframe", padding=10)
        style.configure("LW.Section.TLabelframe.Label", font=("TkDefaultFont", 9, "bold"))
        style.configure("LW.Run.TButton", font=("TkDefaultFont", 10, "bold"))
        style.configure("LW.Key.TLabel", foreground="#374151", font=("TkDefaultFont", 9))
        style.configure("LW.Val.TLabel", foreground="#1f2937", font=("TkDefaultFont", 9, "bold"))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _finalize_layout(self) -> None:
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 620)
        h = max(self.winfo_reqheight(), 420)
        self.geometry(f"{w}x{h}")
        self.minsize(580, 400)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)

        self._build_header(root)
        self._build_input_section(root)
        self._build_settings_section(root)
        self._build_action_section(root)
        self._build_status_bar(root)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="左右岸水位抽出", style="LW.Heading.TLabel").grid(
            row=0, column=0, sticky="w",
        )
        ttk.Label(
            header,
            text="左右岸の水位時系列を抽出し、Excel ファイルを作成します。",
            style="LW.Desc.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        meta = ttk.Frame(header)
        meta.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        meta.columnconfigure(1, weight=1)
        meta.columnconfigure(3, weight=2)

        ttk.Label(meta, text="入力:", style="LW.Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(meta, text=self.input_dir.name, style="LW.Val.TLabel").grid(
            row=0, column=1, sticky="w", padx=(4, 0),
        )
        ttk.Label(meta, text="出力:", style="LW.Muted.TLabel").grid(
            row=0, column=2, sticky="w", padx=(16, 0),
        )
        out_display = str(self.output_dir)
        if len(out_display) > 50:
            out_display = "…" + out_display[-48:]
        ttk.Label(meta, text=out_display, style="LW.Val.TLabel").grid(
            row=0, column=3, sticky="w", padx=(4, 0),
        )

    # ------------------------------------------------------------------
    # Input section (config file picker)
    # ------------------------------------------------------------------
    def _build_input_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="入力", style="LW.Section.TLabelframe")
        section.pack(fill="x", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        ttk.Label(section, text="設定ファイル", style="LW.Key.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Entry(section, textvariable=self.config_var, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=3,
        )
        ttk.Button(section, text="参照…", width=8, command=self._choose_config_file).grid(
            row=0, column=2, sticky="e", padx=(6, 0), pady=3,
        )
        ttk.Label(
            section,
            text="左右岸の地点情報を含む CSV ファイルを指定してください。",
            style="LW.Muted.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w")

    # ------------------------------------------------------------------
    # Settings section
    # ------------------------------------------------------------------
    def _build_settings_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="出力設定", style="LW.Section.TLabelframe")
        section.pack(fill="x", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        # Output filename
        ttk.Label(section, text="出力ファイル名", style="LW.Key.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Entry(section, textvariable=self.filename_var, width=30).grid(
            row=0, column=1, sticky="ew", pady=3,
        )

        # Missing value
        ttk.Label(section, text="欠損値置換", style="LW.Key.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Entry(section, textvariable=self.missing_var, width=20).grid(
            row=1, column=1, sticky="w", pady=3,
        )
        ttk.Label(section, text="空欄 → 空セル", style="LW.Muted.TLabel").grid(
            row=1, column=2, sticky="w", padx=(8, 0), pady=3,
        )

        # Min depth
        ttk.Label(section, text="最小水深", style="LW.Key.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Entry(section, textvariable=self.min_depth_var, width=20).grid(
            row=2, column=1, sticky="w", pady=3,
        )
        ttk.Label(section, text="空欄 → 無効判定なし", style="LW.Muted.TLabel").grid(
            row=2, column=2, sticky="w", padx=(8, 0), pady=3,
        )

        ttk.Separator(section).grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)

        # Intermediate CSV
        ttk.Checkbutton(
            section, text="中間CSVを出力する", variable=self.use_temp,
            command=self._toggle_temp_ui,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=3)

        ttk.Label(section, text="中間フォルダ", style="LW.Key.TLabel").grid(
            row=5, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        self.temp_entry = ttk.Entry(section, textvariable=self.temp_var, state="disabled")
        self.temp_entry.grid(row=5, column=1, sticky="ew", pady=3)
        self.temp_btn = ttk.Button(
            section, text="参照…", width=8, command=self._choose_temp_dir, state="disabled",
        )
        self.temp_btn.grid(row=5, column=2, sticky="e", padx=(6, 0), pady=3)

    # ------------------------------------------------------------------
    # Action section
    # ------------------------------------------------------------------
    def _build_action_section(self, parent: ttk.Frame) -> None:
        section = ttk.Frame(parent)
        section.pack(fill="x", pady=(4, 0))
        section.columnconfigure(0, weight=1)

        self.run_btn = ttk.Button(
            section, text="▶ 実行", style="LW.Run.TButton",
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
        ttk.Label(bar, textvariable=self._status_var, style="LW.Status.TLabel", anchor="w").grid(
            row=1, column=0, sticky="w",
        )
        ttk.Label(bar, textvariable=self._status_detail_var, style="LW.Muted.TLabel", anchor="e").grid(
            row=1, column=1, sticky="e",
        )

    # ------------------------------------------------------------------
    # Events & state
    # ------------------------------------------------------------------
    def _bind_events(self) -> None:
        self.bind_all("<Alt-h>", lambda e: self.open_manual())
        self.config_var.trace_add("write", lambda *_: self._refresh_state())
        # Menu
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="マニュアルを開く", accelerator="Alt+H", command=self.open_manual)
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)

    def _refresh_state(self) -> None:
        cfg_ok = self.config_file is not None and self.config_file.is_file()
        if cfg_ok:
            self._status_var.set("実行できます。")
            self._status_detail_var.set(f"設定: {self.config_file.name}")
            self.run_btn.configure(state="normal")
        else:
            self._status_var.set("設定ファイルを選択してください。")
            self._status_detail_var.set("")
            self.run_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def _choose_config_file(self) -> None:
        logger.info("設定ファイル選択ダイアログを開く")
        file = filedialog.askopenfilename(
            title="設定ファイルを選択",
            filetypes=[("CSVファイル", "*.csv"), ("All files", "*")],
            parent=self,
        )
        if file:
            self.config_file = Path(file)
            logger.info("設定ファイル選択: %s", file)
            self.config_var.set(str(file))

    def _choose_temp_dir(self) -> None:
        path = filedialog.askdirectory(title="中間フォルダを選択", parent=self)
        if path:
            self.temp_var.set(path)

    def _toggle_temp_ui(self) -> None:
        if self.use_temp.get():
            out_dir = Path(self.output_var.get())
            temp_dir = self._resolve_temp_dir(out_dir, self.filename_var.get())
            self.temp_var.set(str(temp_dir))
            self.temp_entry.configure(state="disabled")
            self.temp_btn.configure(state="disabled")
        else:
            self.temp_var.set("")
            self.temp_entry.configure(state="disabled")
            self.temp_btn.configure(state="disabled")

    def _resolve_temp_dir(self, output_dir: Path, excel_name: str) -> Path:
        name = Path(excel_name).stem if excel_name else "LR_WSE"
        return output_dir / name

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def _run(self) -> None:
        logger.info("実行ボタン押下")
        try:
            in_dir = Path(self.input_var.get())
            out_dir = Path(self.output_var.get())
            cfg = self.config_file

            in_ok = in_dir.is_dir() or (in_dir.is_file() and in_dir.suffix.lower() in {".ipro", ".cgn"})
            if not (in_ok and out_dir.is_dir() and cfg and cfg.is_file()):
                messagebox.showerror(
                    "エラー",
                    "入力（プロジェクトフォルダ/CSVフォルダ/.ipro/.cgn）、設定ファイル、出力フォルダを正しく指定してください。",
                    parent=self,
                )
                return

            missing = None if self.missing_var.get() == "" else self.missing_var.get()
            min_depth = None
            if self.min_depth_var.get() != "":
                try:
                    min_depth = float(self.min_depth_var.get())
                except ValueError:
                    messagebox.showerror("エラー", "最小水深は数値で入力してください。", parent=self)
                    return

            temp_dir = None
            if self.use_temp.get():
                temp_dir = self._resolve_temp_dir(out_dir, self.filename_var.get())
                self.temp_var.set(str(temp_dir))

            self.run_btn.configure(state="disabled")
            self._status_var.set("処理中...")
            self._status_detail_var.set("CGNS を読み込み中です。")

            def worker() -> None:
                try:
                    out_path = run_lr_wse(
                        input_path=in_dir,
                        config_file=cfg,
                        output_dir=out_dir,
                        excel_filename=self.filename_var.get(),
                        missing_elev=missing,
                        min_depth=min_depth,
                        temp_dir=temp_dir,
                        on_swap_warning=self._warn_setting_mismatch,
                    )
                except Exception as exc:
                    self.after(0, lambda err=exc: self._finish_error(err))
                    return
                self.after(0, lambda: self._finish_success(out_path))

            threading.Thread(target=worker, daemon=True).start()

        except Exception as e:
            messagebox.showerror("エラー", str(e), parent=self)

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

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def open_manual(self) -> None:
        logger.info("マニュアルを開く")
        webbrowser.open(DOCS_URL)

    def _warn_setting_mismatch(self, message: str) -> None:
        if self._swap_warned:
            return
        self._swap_warned = True
        messagebox.showwarning("警告", message, parent=self)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2:
        in_dir, out_dir = map(Path, args)
    else:
        root = tk.Tk()
        root.withdraw()
        in_dir = Path(filedialog.askdirectory(title="入力フォルダを選択"))
        out_dir = Path(filedialog.askdirectory(title="出力フォルダを選択"))
        root.destroy()
    root = tk.Tk()
    root.withdraw()
    app = LrWseGUI(root, in_dir, out_dir)
    root.mainloop()
