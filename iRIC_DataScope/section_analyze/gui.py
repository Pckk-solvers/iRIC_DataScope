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
        self.output_root_dir = Path(output_dir)
        self.output_dir = self.output_root_dir / "section_analyze"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.title("断面集計")

        # --- tkinter variables ---
        self.section_shp_var = tk.StringVar()
        self.depth_threshold_var = tk.StringVar(value="0.01")
        self.sample_interval_var = tk.StringVar()
        self.section_id_field_var = tk.StringVar()
        self.section_name_field_var = tk.StringVar()
        self.column_names_var = tk.StringVar(value="standard")
        self.shared_y_scale_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=True)

        self._status_var = tk.StringVar(value="側線SHPを選択してください。")
        self._status_detail_var = tk.StringVar(value="")

        self._configure_styles()
        self._build_ui()
        self._bind_variable_traces()
        self._refresh_summary()
        self._finalize_layout()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------
    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("SA.Heading.TLabel", font=("TkDefaultFont", 13, "bold"))
        style.configure("SA.Desc.TLabel", foreground="#4b5563")
        style.configure("SA.Muted.TLabel", foreground="#6b7280")
        style.configure("SA.Status.TLabel", foreground="#6b7280", font=("TkDefaultFont", 9))
        style.configure("SA.Ready.TLabel", foreground="#047857", font=("TkDefaultFont", 9, "bold"))
        style.configure("SA.Error.TLabel", foreground="#b91c1c", font=("TkDefaultFont", 9))
        style.configure("SA.Section.TLabelframe", padding=10)
        style.configure("SA.Section.TLabelframe.Label", font=("TkDefaultFont", 9, "bold"))
        style.configure("SA.Run.TButton", font=("TkDefaultFont", 10, "bold"))
        style.configure("SA.PreviewKey.TLabel", foreground="#374151", font=("TkDefaultFont", 9))
        style.configure("SA.PreviewVal.TLabel", foreground="#1f2937", font=("TkDefaultFont", 9, "bold"))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _finalize_layout(self) -> None:
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 780)
        h = max(self.winfo_reqheight(), 540)
        self.geometry(f"{w}x{h}")
        self.minsize(720, 500)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(1, weight=1)

        self._build_header(root)

        # --- Left column: inputs & settings ---
        left = ttk.Frame(root)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        self._build_input_section(left)
        self._build_settings_section(left)

        # --- Right column: preview & action ---
        right = ttk.Frame(root)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self._build_preview_section(right)
        self._build_action_section(right)

        # --- Bottom status bar ---
        status_frame = ttk.Frame(root)
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        status_frame.columnconfigure(0, weight=1)
        ttk.Separator(status_frame).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Label(
            status_frame,
            textvariable=self._status_var,
            style="SA.Status.TLabel",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew")
        ttk.Label(
            status_frame,
            textvariable=self._status_detail_var,
            style="SA.Muted.TLabel",
            anchor="e",
        ).grid(row=1, column=1, sticky="e", padx=(8, 0))

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header, text="断面集計", style="SA.Heading.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="側線SHPに沿って平均水位と水深を断面別に集計し、CSV と PNG を出力します。",
            style="SA.Desc.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        meta = ttk.Frame(header)
        meta.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        meta.columnconfigure(1, weight=1)
        meta.columnconfigure(3, weight=2)

        ttk.Label(meta, text="入力:", style="SA.Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            meta,
            text=self.input_path.name if self.input_path else "-",
            style="SA.PreviewVal.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(meta, text="出力:", style="SA.Muted.TLabel").grid(row=0, column=2, sticky="w", padx=(16, 0))
        # Truncate long output paths for display
        out_display = str(self.output_dir)
        if len(out_display) > 50:
            out_display = "…" + out_display[-48:]
        ttk.Label(meta, text=out_display, style="SA.PreviewVal.TLabel").grid(row=0, column=3, sticky="w", padx=(4, 0))

    # ------------------------------------------------------------------
    # Input section (SHP file picker)
    # ------------------------------------------------------------------
    def _build_input_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="入力", style="SA.Section.TLabelframe")
        section.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        ttk.Label(section, text="側線SHP", style="SA.PreviewKey.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 4),
        )
        shp_entry = ttk.Entry(section, textvariable=self.section_shp_var)
        shp_entry.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        ttk.Button(section, text="参照…", width=8, command=self._select_shp).grid(
            row=0, column=2, sticky="e", padx=(6, 0), pady=(0, 4),
        )
        ttk.Label(
            section,
            text="LineString の .shp を選択します。1 feature = 1 断面。",
            style="SA.Muted.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w")

    # ------------------------------------------------------------------
    # Settings section
    # ------------------------------------------------------------------
    def _build_settings_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="集計設定", style="SA.Section.TLabelframe")
        section.grid(row=1, column=0, sticky="nsew")
        section.columnconfigure(1, weight=1)

        # Entry-based settings  (label, var, hint)
        entries = [
            ("有効水深下限", self.depth_threshold_var, "depth ≥ この値の点のみ有効"),
            ("sample_interval", self.sample_interval_var, "空欄 = 自動推定"),
            ("断面IDフィールド", self.section_id_field_var, "空欄 = 自動検出"),
            ("断面名フィールド", self.section_name_field_var, "空欄 = 自動検出"),
        ]
        for row, (label, var, hint) in enumerate(entries):
            ttk.Label(section, text=label, style="SA.PreviewKey.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 8), pady=3,
            )
            e = ttk.Entry(section, textvariable=var, width=18)
            e.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=3)
            ttk.Label(section, text=hint, style="SA.Muted.TLabel").grid(
                row=row, column=2, sticky="w", pady=3,
            )

        sep_row = len(entries)
        ttk.Separator(section).grid(
            row=sep_row, column=0, columnspan=3, sticky="ew", pady=6,
        )

        # Combobox: CSV column names
        r = sep_row + 1
        ttk.Label(section, text="CSV列名", style="SA.PreviewKey.TLabel").grid(
            row=r, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        cb = ttk.Combobox(
            section,
            textvariable=self.column_names_var,
            values=("standard", "river"),
            state="readonly",
            width=14,
        )
        cb.grid(row=r, column=1, sticky="w", pady=3)
        ttk.Label(
            section, text="river = 河川業務向け日本語列名", style="SA.Muted.TLabel",
        ).grid(row=r, column=2, sticky="w", pady=3)

        # Checkboxes
        r += 1
        ttk.Label(section, text="グラフY軸", style="SA.PreviewKey.TLabel").grid(
            row=r, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Checkbutton(
            section,
            text="全断面で共通スケールを使う",
            variable=self.shared_y_scale_var,
        ).grid(row=r, column=1, columnspan=2, sticky="w", pady=3)

        r += 1
        ttk.Label(section, text="既存CSV", style="SA.PreviewKey.TLabel").grid(
            row=r, column=0, sticky="w", padx=(0, 8), pady=3,
        )
        ttk.Checkbutton(
            section,
            text="既存の出力を上書きする",
            variable=self.overwrite_var,
        ).grid(row=r, column=1, columnspan=2, sticky="w", pady=3)

    # ------------------------------------------------------------------
    # Preview section (right column – summary + output list)
    # ------------------------------------------------------------------
    def _build_preview_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="出力プレビュー", style="SA.Section.TLabelframe")
        section.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        # Summary rows (key: value on the same line)
        self._preview_vars: dict[str, tk.StringVar] = {}
        preview_items = [
            ("入力状態", "ready"),
            ("側線SHP", "shp"),
            ("Y軸", "yaxis"),
            ("列名", "colname"),
            ("上書き", "overwrite"),
            ("水深下限", "threshold"),
            ("sample_interval", "interval"),
        ]
        for idx, (label, key) in enumerate(preview_items):
            var = tk.StringVar(value="—")
            self._preview_vars[key] = var
            ttk.Label(section, text=label, style="SA.PreviewKey.TLabel").grid(
                row=idx, column=0, sticky="w", padx=(0, 10), pady=2,
            )
            ttk.Label(section, textvariable=var, style="SA.PreviewVal.TLabel").grid(
                row=idx, column=1, sticky="w", pady=2,
            )

        sep_row = len(preview_items)
        ttk.Separator(section).grid(
            row=sep_row, column=0, columnspan=2, sticky="ew", pady=6,
        )

        # Output file list
        r = sep_row + 1
        ttk.Label(section, text="出力されるもの", style="SA.PreviewKey.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(0, 4),
        )
        outputs = [
            "section_node_map.csv",
            "section_timeseries.csv",
            "section_peak_summary.csv",
            "section_graphs/SEC001.png …",
        ]
        for i, text in enumerate(outputs, start=r + 1):
            ttk.Label(section, text=f"  • {text}", style="SA.Muted.TLabel").grid(
                row=i, column=0, columnspan=2, sticky="w", pady=1,
            )

    # ------------------------------------------------------------------
    # Action section (run button + graph note)
    # ------------------------------------------------------------------
    def _build_action_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="実行", style="SA.Section.TLabelframe")
        section.grid(row=1, column=0, sticky="sew")
        section.columnconfigure(0, weight=1)

        # Graph note
        ttk.Label(
            section,
            text="断面ごとに1枚ずつ、平均水位の時系列 PNG を出力します。\n"
                 "最大点は注記で強調し、時刻は整数表示にしています。",
            style="SA.Muted.TLabel",
            wraplength=300,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.run_btn = ttk.Button(
            section,
            text="▶ 断面集計を実行",
            style="SA.Run.TButton",
            command=self._run,
        )
        self.run_btn.grid(row=1, column=0, sticky="ew", ipady=4)

        ttk.Label(
            section,
            text="output_dir/section_graphs/ に断面ごとの PNG を出力します。",
            style="SA.Muted.TLabel",
            wraplength=300,
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(6, 0))

    # ------------------------------------------------------------------
    # Variable traces
    # ------------------------------------------------------------------
    def _bind_variable_traces(self) -> None:
        for var in (
            self.section_shp_var,
            self.depth_threshold_var,
            self.sample_interval_var,
            self.section_id_field_var,
            self.section_name_field_var,
            self.column_names_var,
            self.shared_y_scale_var,
            self.overwrite_var,
        ):
            var.trace_add("write", lambda *_: self._refresh_summary())

    def _run_enabled(self) -> bool:
        shp_path = self.section_shp_var.get().strip()
        return bool(shp_path and Path(shp_path).is_file())

    def _set_run_button_state(self, enabled: bool) -> None:
        self.run_btn.configure(state="normal" if enabled else "disabled")

    def _refresh_summary(self) -> None:
        shp_path = self.section_shp_var.get().strip()
        shp = Path(shp_path) if shp_path else None

        # SHP state
        if not shp_path:
            self._preview_vars["shp"].set("未選択")
        elif shp.exists():
            self._preview_vars["shp"].set(shp.name)
        else:
            self._preview_vars["shp"].set("⚠ 見つかりません")

        # Other preview fields
        self._preview_vars["yaxis"].set(
            "全断面共通" if self.shared_y_scale_var.get() else "断面ごと最適"
        )
        self._preview_vars["colname"].set(self.column_names_var.get())
        self._preview_vars["overwrite"].set(
            "上書きする" if self.overwrite_var.get() else "上書きしない"
        )
        self._preview_vars["threshold"].set(
            self.depth_threshold_var.get().strip() or "未入力"
        )
        interval_text = self.sample_interval_var.get().strip()
        self._preview_vars["interval"].set(interval_text if interval_text else "自動推定")

        # Ready state & status bar
        if self._run_enabled():
            self._preview_vars["ready"].set("✔ 準備完了")
            self._status_var.set("断面集計を実行できます。")
            self._status_detail_var.set("設定を確認して「実行」を押してください。")
            self._set_run_button_state(True)
        else:
            self._preview_vars["ready"].set("未準備")
            if not shp_path:
                self._status_var.set("側線SHPを選択してください。")
                self._status_detail_var.set("")
            else:
                self._status_var.set("側線SHPが見つかりません。")
                self._status_detail_var.set(shp_path)
            self._set_run_button_state(False)

    # ------------------------------------------------------------------
    # File dialog
    # ------------------------------------------------------------------
    def _select_shp(self) -> None:
        path = filedialog.askopenfilename(
            title="側線SHPを選択",
            filetypes=[("Shapefile", "*.shp"), ("All files", "*.*")],
            parent=self,
        )
        if path:
            self.section_shp_var.set(path)

    # ------------------------------------------------------------------
    # Build options
    # ------------------------------------------------------------------
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
            shared_y_scale=self.shared_y_scale_var.get(),
        )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def _run(self) -> None:
        if not self._run_enabled():
            self._refresh_summary()
            return
        try:
            options = self._build_options()
        except Exception as exc:
            messagebox.showerror("エラー", f"設定値が不正です:\n{exc}", parent=self)
            return

        self._set_run_button_state(False)
        self._status_var.set("処理中...")
        self._status_detail_var.set("CGNS と側線SHPを読み込み中です。")

        def worker() -> None:
            try:
                result = run_section_analysis(
                    input_path=self.input_path,
                    section_shp_path=Path(self.section_shp_var.get().strip()),
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
        self._set_run_button_state(True)
        self._status_var.set("エラー")
        self._status_detail_var.set(str(exc))
        messagebox.showerror("エラー", f"断面集計に失敗しました:\n{exc}", parent=self)

    def _finish_success(self, result) -> None:
        self._set_run_button_state(True)
        self._status_var.set(f"完了: {result.mapped_node_count} ノード / {result.step_count} ステップ")
        self._status_detail_var.set(f"出力先: {result.output_dir}")
        files = "\n".join(str(path) for path in result.output_files)
        messagebox.showinfo("完了", f"断面集計が完了しました。\n\n{files}", parent=self)
