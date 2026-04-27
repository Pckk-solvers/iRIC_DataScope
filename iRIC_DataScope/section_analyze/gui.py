from __future__ import annotations

from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from iRIC_DataScope.section_analyze.models import SectionAnalyzeOptions
from iRIC_DataScope.section_analyze.processor import run_section_analysis


class SectionAnalyzeGUI(tk.Toplevel):
    def __init__(self, master: tk.Misc, *, input_path: Path, output_dir: Path):
        super().__init__(master)
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.title("断面集計")
        self.geometry("720x360")
        self.section_shp_var = tk.StringVar()
        self.depth_threshold_var = tk.StringVar(value="0.01")
        self.sample_interval_var = tk.StringVar(value="")
        self.section_id_field_var = tk.StringVar(value="")
        self.section_name_field_var = tk.StringVar(value="")
        self.column_names_var = tk.StringVar(value="standard")
        self.overwrite_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="側線SHPを選択してください。")
        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 5}
        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        ttk.Label(body, text="入力").grid(row=0, column=0, sticky="e", **pad)
        ttk.Label(body, text=str(self.input_path)).grid(row=0, column=1, columnspan=2, sticky="w", **pad)
        ttk.Label(body, text="出力").grid(row=1, column=0, sticky="e", **pad)
        ttk.Label(body, text=str(self.output_dir)).grid(row=1, column=1, columnspan=2, sticky="w", **pad)

        ttk.Label(body, text="側線SHP").grid(row=2, column=0, sticky="e", **pad)
        ttk.Entry(body, textvariable=self.section_shp_var).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Button(body, text="参照", command=self._select_shp).grid(row=2, column=2, sticky="ew", **pad)

        ttk.Label(body, text="有効水深下限").grid(row=3, column=0, sticky="e", **pad)
        ttk.Entry(body, textvariable=self.depth_threshold_var, width=12).grid(row=3, column=1, sticky="w", **pad)
        ttk.Checkbutton(body, text="既存CSVを上書き", variable=self.overwrite_var).grid(row=3, column=2, sticky="w", **pad)

        ttk.Label(body, text="sample_interval").grid(row=4, column=0, sticky="e", **pad)
        ttk.Entry(body, textvariable=self.sample_interval_var, width=12).grid(row=4, column=1, sticky="w", **pad)
        ttk.Label(body, text="空欄なら自動推定").grid(row=4, column=2, sticky="w", **pad)

        ttk.Label(body, text="断面IDフィールド").grid(row=5, column=0, sticky="e", **pad)
        ttk.Entry(body, textvariable=self.section_id_field_var, width=20).grid(row=5, column=1, sticky="w", **pad)
        ttk.Label(body, text="空欄なら自動検出").grid(row=5, column=2, sticky="w", **pad)

        ttk.Label(body, text="断面名フィールド").grid(row=6, column=0, sticky="e", **pad)
        ttk.Entry(body, textvariable=self.section_name_field_var, width=20).grid(row=6, column=1, sticky="w", **pad)
        ttk.Label(body, text="空欄なら自動検出").grid(row=6, column=2, sticky="w", **pad)

        ttk.Label(body, text="CSV列名").grid(row=7, column=0, sticky="e", **pad)
        ttk.Combobox(
            body,
            textvariable=self.column_names_var,
            values=("standard", "river"),
            state="readonly",
            width=12,
        ).grid(row=7, column=1, sticky="w", **pad)
        ttk.Label(body, text="river: 河川業務向け日本語列名").grid(row=7, column=2, sticky="w", **pad)

        ttk.Label(body, textvariable=self.status_var).grid(row=8, column=0, columnspan=3, sticky="w", **pad)
        self.run_btn = ttk.Button(body, text="実行", command=self._run)
        self.run_btn.grid(row=9, column=0, columnspan=3, pady=(12, 4))

    def _select_shp(self) -> None:
        path = filedialog.askopenfilename(
            title="側線SHPを選択",
            filetypes=[("Shapefile", "*.shp"), ("All files", "*.*")],
            parent=self,
        )
        if path:
            self.section_shp_var.set(path)

    def _build_options(self) -> SectionAnalyzeOptions:
        depth_threshold = float(self.depth_threshold_var.get())
        interval_text = self.sample_interval_var.get().strip()
        sample_interval = float(interval_text) if interval_text else None
        return SectionAnalyzeOptions(
            depth_threshold=depth_threshold,
            sample_interval=sample_interval,
            section_id_field=self.section_id_field_var.get().strip() or None,
            section_name_field=self.section_name_field_var.get().strip() or None,
            overwrite=self.overwrite_var.get(),
            column_names=self.column_names_var.get(),
        )

    def _run(self) -> None:
        shp_path = self.section_shp_var.get().strip()
        if not shp_path:
            messagebox.showerror("エラー", "側線SHPを選択してください。", parent=self)
            return
        try:
            options = self._build_options()
        except Exception as exc:
            messagebox.showerror("エラー", f"設定値が不正です:\n{exc}", parent=self)
            return
        self.run_btn.configure(state="disabled")
        self.status_var.set("処理中...")

        def worker() -> None:
            try:
                result = run_section_analysis(
                    input_path=self.input_path,
                    section_shp_path=Path(shp_path),
                    output_dir=self.output_dir,
                    options=options,
                )
            except Exception as exc:
                error = exc
                self.after(0, lambda: self._finish_error(error))
                return
            self.after(0, lambda: self._finish_success(result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_error(self, exc: Exception) -> None:
        self.run_btn.configure(state="normal")
        self.status_var.set("エラー")
        messagebox.showerror("エラー", f"断面集計に失敗しました:\n{exc}", parent=self)

    def _finish_success(self, result) -> None:
        self.run_btn.configure(state="normal")
        self.status_var.set(f"完了: {result.mapped_node_count} ノード / {result.step_count} ステップ")
        files = "\n".join(str(path) for path in result.output_files)
        messagebox.showinfo("完了", f"断面集計が完了しました。\n\n{files}", parent=self)
