#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\app.py
"""iRIC_DataScope ランチャー起動用スクリプト。"""
import sys
import logging
import json
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import webbrowser
import time
from importlib import metadata

from iRIC_DataScope.common.io_selector import IOFolderSelector
from iRIC_DataScope.common.iric_project import (
    classify_input_dir,
    find_case_cgn,
    has_result_csv,
    is_valid_input_path,
    list_solution_cgns_in_dir,
    list_solution_cgns_in_ipro,
)
from iRIC_DataScope.common.logging_config import setup_logging
from iRIC_DataScope.lr_wse.launcher import launch_from_launcher as launch_lr_wse
from iRIC_DataScope.cross_section.launcher import launch_from_launcher as launch_cross_section
from iRIC_DataScope.time_series.launcher import launch_from_launcher as launch_time_series
from iRIC_DataScope.xy_value_map.launcher import launch_from_launcher as launch_xy_value_map

# pyinstallerのスプラッシュを閉じる用
try:
    import pyi_splash
except Exception:
    pyi_splash = None 

logger = logging.getLogger(__name__)

"""
重い import は起動時のスプラッシュ表示後に遅延ロードする。
"""

SPLASH_REL_PATH = Path("iRIC_DataScope") / "assets" / "splash.png"
_APP_DIR = Path(__file__).resolve().parent
APP_TITLE = "iRIC解析結果抽出・可視化アプリ"
MANUAL_URL = "https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=73"
DOCS_URL = "https://pckk-solvers.github.io/iRIC_DataScope/"
RECENT_PATH = Path.home() / ".iric_datascope" / "launcher_recent.json"
MAX_RECENT_ITEMS = 5
BUTTON_LABELS = {
    "lr_wse": "左右岸水位抽出",
    "cross_section": "横断重ね合わせ図作成",
    "time_series": "時系列データ抽出",
    "xy_value_map": "X-Y分布画像出力",
}


@dataclass(frozen=True)
class ToolSpec:
    key: str
    label: str
    description: str
    output_hint: str
    docs_path: str
    button_attr: str
    window_attr: str
    log_name: str
    close_binding: str  # "protocol" or "destroy"
    open_fn: Callable


@dataclass(frozen=True)
class InputSummary:
    label: str
    valid: bool
    details: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def get_app_version() -> str:
    try:
        return metadata.version("iric-datascope")
    except metadata.PackageNotFoundError:
        return "dev"


def summarize_input_path(input_path: Path | None) -> InputSummary:
    if input_path is None or not str(input_path):
        return InputSummary(
            label="入力未選択",
            valid=False,
            details=("入力パスを選択してください。",),
        )

    if not input_path.exists():
        return InputSummary(
            label="入力が見つかりません",
            valid=False,
            details=(str(input_path),),
        )

    if input_path.is_file():
        suffix = input_path.suffix.lower()
        if suffix == ".ipro":
            solutions = list_solution_cgns_in_ipro(input_path)
            details = [".ipro ファイル", f"Solution*.cgn: {len(solutions)} 件"]
            if not solutions:
                details.append("内部の Solution*.cgn は未検出です。")
            return InputSummary("iRIC プロジェクト", True, tuple(details))
        if suffix == ".cgn":
            return InputSummary("CGNS ファイル", True, (input_path.name,))
        return InputSummary(
            label="未対応ファイル",
            valid=False,
            details=(f"対応形式は .ipro / .cgn です: {input_path.name}",),
        )

    try:
        kind = classify_input_dir(input_path)
    except Exception as exc:
        return InputSummary(
            label="入力判定エラー",
            valid=False,
            details=(str(exc),),
        )

    if kind == "project_dir":
        case = find_case_cgn(input_path, "Case1.cgn")
        solutions = list_solution_cgns_in_dir(input_path)
        details = [
            "プロジェクトフォルダ",
            f"Case1.cgn: {'あり' if case else 'なし'}",
            f"Solution*.cgn: {len(solutions)} 件",
        ]
        warnings = ()
        if has_result_csv(input_path):
            warnings = ("Result_*.csv も検出しました。CGNS プロジェクトとして扱います。",)
        return InputSummary("プロジェクトフォルダ", True, tuple(details), warnings)

    return InputSummary(
        "CSV フォルダ",
        True,
        ("Result_*.csv を検出", "CSV 入力として扱います。"),
    )


class LauncherApp(tk.Tk):
    """
    iRIC 統合ランチャー アプリケーションクラス
    - 入力/出力フォルダ選択
    - 各種ツール起動ボタン
    - ヘルプメニュー＆マニュアルボタン
    """
    def __init__(
        self,
        *,
        show_splash: bool = True,
        on_ready: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.withdraw()
        self._show_internal_splash = show_splash
        self._on_ready = on_ready
        self._splash = None
        self._splash_image = None
        if self._show_internal_splash:
            self._show_splash()
        self._safe_update()
        self._close_pyi_splash()
        self._safe_update()
        self._setup_logging()
        self._initialize_ui()
        # 既存ウィンドウを保持する変数
        self._lr_wse_win = None
        self._cross_section_win = None
        self._time_series_win = None
        self._xy_map_win = None
        # Hide splash after the event loop starts so it can be displayed.
        self.after(0, self._finish_startup)

    def _safe_update(self) -> None:
        try:
            self.update_idletasks()
            self.update()
        except Exception:
            pass

    def _close_pyi_splash(self) -> None:
        # pyinstallerのスプラッシュを閉じる用
        if not pyi_splash:
            return
        try:
            pyi_splash.close()
        except Exception:
            pass

    def _setup_logging(self) -> None:
        # Configure logging after splash is visible (import can be heavy).
        self._safe_call(setup_logging, "setup logging")

    def _initialize_ui(self) -> None:
        start = time.perf_counter()
        logger.debug("LauncherApp: Starting initialization")
        # 1. ウィンドウ設定
        self._configure_window()
        logger.debug("LauncherApp: Window configured in %.3fs", time.perf_counter() - start)
        self._configure_styles()
        # 2. メニューバー（ヘルプ）作成
        self._create_menu()
        logger.debug("LauncherApp: Menu created in %.3fs", time.perf_counter() - start)
        self._create_header()
        # 3. IO フォルダ選択パネル作成
        self._create_io_panel()
        logger.debug("LauncherApp: IO panel created in %.3fs", time.perf_counter() - start)
        self._create_recent_panel()
        self._create_input_summary_panel()
        # 4. 各機能起動ボタン作成
        self._create_launch_buttons()
        logger.debug("LauncherApp: Launch buttons created in %.3fs", time.perf_counter() - start)
        self._create_status_bar()
        # 5. イベントバインド（パス検証・ショートカットキー）
        self._bind_events()
        logger.debug("LauncherApp: Events bound in %.3fs", time.perf_counter() - start)
        # 6. 自動レイアウト調整：ウィジェットに合わせて初期サイズ＆最小サイズを設定
        self._finalize_layout()
        logger.debug("LauncherApp: Layout finalized in %.3fs", time.perf_counter() - start)
        logger.debug("LauncherApp: Initialization complete in %.3fs", time.perf_counter() - start)

    def _finish_startup(self) -> None:
        self.deiconify()
        self.update_idletasks()   # 初回描画を出す
        if self._on_ready:
            self._safe_call(self._on_ready, "signal readiness")
        if self._show_internal_splash:
            self._hide_splash()
        self.lift()

    def _safe_call(self, func: Callable, context: str) -> None:
        try:
            func()
        except Exception as exc:
            logger.debug("LauncherApp: Failed to %s: %s", context, exc)

    def _resource_path(self, relative_path: Path) -> Path:
        # Support both PyInstaller (sys._MEIPASS) and Nuitka (no _MEIPASS).
        rel = relative_path
        rel_stripped = (
            Path(*relative_path.parts[1:]) if relative_path.parts[:1] == ("iRIC_DataScope",) else relative_path
        )
        bases: list[Path] = []
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                bases.append(Path(meipass))
            exe = getattr(sys, "executable", None)
            if exe:
                bases.append(Path(exe).resolve().parent)
            bases.append(Path.cwd())
        else:
            bases.append(_APP_DIR)

        for base in bases:
            for rp in (rel, rel_stripped):
                candidate = base / rp
                if candidate.is_file():
                    return candidate

        # Fallback for dev mode
        return _APP_DIR / rel_stripped

    def _show_splash(self) -> None:
        splash_path = self._resource_path(SPLASH_REL_PATH)
        if not splash_path.is_file():
            logger.debug("LauncherApp: Splash image not found: %s", splash_path)
            return

        self.withdraw()  # main window hidden

        splash = tk.Toplevel(self)
        splash.withdraw()  # ★最初は出さない（ここが効く）
        splash.overrideredirect(True)
        splash.attributes("-topmost", True)

        try:
            image = tk.PhotoImage(file=str(splash_path))
        except Exception as exc:
            logger.warning("LauncherApp: Failed to load splash image: %s", exc)
            self.deiconify()
            return

        label = tk.Label(splash, image=image, borderwidth=0, highlightthickness=0)
        label.pack()

        # 画像サイズが確定した状態で geometry を決める
        splash.update_idletasks()
        width = image.width()
        height = image.height()
        x = (splash.winfo_screenwidth() - width) // 2
        y = (splash.winfo_screenheight() - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")

        splash.deiconify()  # ★位置が決まってから表示
        splash.lift()
        # 初期表示後は最前面を解除して他ウィンドウ操作を邪魔しない。
        def _release_topmost() -> None:
            try:
                if splash.winfo_exists():
                    splash.attributes("-topmost", False)
            except Exception:
                pass
        splash.after(500, _release_topmost)

        self._splash = splash
        self._splash_image = image  # keep reference

    def _hide_splash(self) -> None:
        if self._splash and self._splash.winfo_exists():
            self._splash.destroy()
        self._splash = None
        self._splash_image = None

    def _configure_window(self):
        """ウィンドウのタイトルと初期サイズを設定"""
        logger.debug("LauncherApp: Configuring main window")
        self.title(APP_TITLE)
        # self.geometry("600x330")

    def _configure_styles(self) -> None:
        self.configure(bg="#f6f8fb")
        style = ttk.Style(self)
        style.configure("Header.TFrame", background="#f6f8fb")
        style.configure("Title.TLabel", background="#f6f8fb", font=("TkDefaultFont", 14, "bold"))
        style.configure("Subtitle.TLabel", background="#f6f8fb", foreground="#4b5563")
        style.configure("Muted.TLabel", foreground="#6b7280")
        style.configure("Ok.TLabel", foreground="#047857")
        style.configure("Warn.TLabel", foreground="#b45309")
        style.configure("Error.TLabel", foreground="#b91c1c")
        style.configure("Tool.TLabelframe", padding=8)
        style.configure("Tool.TLabelframe.Label", font=("TkDefaultFont", 10, "bold"))

    def _finalize_layout(self):
        """
        ウィジェット配置後に必要最小サイズを計算し、
        初期ジオメトリと最小サイズとして設定する
        """
        logger.debug("LauncherApp: Finalizing layout")
        # 全配置が終わるまで待ってサイズ計算
        self.update_idletasks()
        # 必要最小幅・高さを取得
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()

        # 余白として左右 20px、上下 20px を追加
        margin_x, margin_y = 20, 20
        self.minsize(w+margin_x, h+margin_y)
        self._center_window(w + margin_x, h + margin_y)
        logger.debug(f"LauncherApp: Geometry set to {w+margin_x}x{h+margin_y}")

    def _center_window(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _create_menu(self):
        """メニューバーとヘルプメニューを追加"""
        logger.debug("LauncherApp: Creating menu bar")
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="マニュアルを開く (Notion)",
                              accelerator="Alt+H",
                              command=self.open_manual)
        help_menu.add_command(label="ユーザーマニュアルを開く (GitHub Pages)",
                              command=self.open_docs)
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)
        logger.debug("LauncherApp: Menu bar created")

    def _create_header(self) -> None:
        frame = ttk.Frame(self, style="Header.TFrame", padding=(14, 12, 14, 4))
        frame.pack(fill="x")
        ttk.Label(frame, text="iRIC_DataScope", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text=f"{APP_TITLE} / v{get_app_version()}",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self._header_summary_var = tk.StringVar(value="入力未選択")
        ttk.Label(frame, textvariable=self._header_summary_var, style="Muted.TLabel").grid(row=0, column=1, sticky="e")
        frame.columnconfigure(0, weight=1)

    def _create_io_panel(self):
        """入力／出力フォルダ選択用パネルを配置"""
        logger.debug("LauncherApp: Creating IO folder selector panel")
        container = ttk.LabelFrame(self, text="入力 / 出力", padding=8)
        container.pack(fill="x", padx=12, pady=(8, 6))
        self.io_panel = IOFolderSelector(container)
        self.io_panel.pack(fill="x")
        ttk.Label(
            container,
            text="入力は iRIC のプロジェクトフォルダ、.ipro、.cgn、または Result_*.csv を含む CSV フォルダを指定してください。",
            style="Muted.TLabel",
            wraplength=760,
        ).pack(fill="x", padx=(112, 0), pady=(2, 0))
        logger.debug("LauncherApp: IO panel created")

    def _create_recent_panel(self) -> None:
        self._recent_items = self._load_recent_items()
        frame = ttk.Frame(self, padding=(12, 0, 12, 6))
        frame.pack(fill="x")
        ttk.Label(frame, text="最近使ったパス").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._recent_var = tk.StringVar()
        self._recent_combo = ttk.Combobox(frame, textvariable=self._recent_var, state="readonly", width=80)
        self._recent_combo.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(frame, text="復元", command=self._apply_recent_selection).grid(row=0, column=2)
        frame.columnconfigure(1, weight=1)
        self._refresh_recent_options()

    def _create_input_summary_panel(self) -> None:
        frame = ttk.LabelFrame(self, text="入力診断", padding=8)
        frame.pack(fill="x", padx=12, pady=(0, 8))
        self._input_kind_var = tk.StringVar(value="入力未選択")
        self._input_detail_var = tk.StringVar(value="入力パスを選択してください。")
        self._input_warning_var = tk.StringVar(value="")
        self._output_status_var = tk.StringVar(value="出力フォルダ未選択")
        ttk.Label(frame, textvariable=self._input_kind_var, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, textvariable=self._output_status_var, style="Muted.TLabel").grid(row=0, column=1, sticky="e")
        ttk.Label(frame, textvariable=self._input_detail_var, style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(frame, textvariable=self._input_warning_var, style="Warn.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        frame.columnconfigure(0, weight=1)

    def _create_launch_buttons(self):
        """各機能の起動カードを配置"""
        logger.debug("LauncherApp: Creating launch buttons")
        self._tool_specs = self._build_tool_specs()
        self._tool_buttons = []
        self._tool_status_vars = {}
        grid = ttk.Frame(self, padding=(12, 0, 12, 8))
        grid.pack(fill="both", expand=True)
        for idx, spec in enumerate(self._tool_specs):
            card = ttk.LabelFrame(grid, text=spec.label, style="Tool.TLabelframe")
            row, col = divmod(idx, 2)
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            ttk.Label(card, text=spec.description, wraplength=280).grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=f"出力: {spec.output_hint}", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 8))
            status_var = tk.StringVar(value="入力と出力を選択してください")
            ttk.Label(card, textvariable=status_var, style="Muted.TLabel").grid(row=2, column=0, sticky="w")
            btn = ttk.Button(card, text="開始", command=lambda s=spec: self._open_tool(s), state="disabled")
            btn.grid(row=2, column=1, sticky="e")
            ttk.Button(card, text="?", width=3, command=lambda s=spec: self._open_tool_docs(s)).grid(row=0, column=1, sticky="ne")
            card.columnconfigure(0, weight=1)
            setattr(self, spec.button_attr, btn)
            self._tool_buttons.append(btn)
            self._tool_status_vars[spec.key] = status_var
        grid.columnconfigure(0, weight=1, uniform="tools")
        grid.columnconfigure(1, weight=1, uniform="tools")
        logger.debug("LauncherApp: Launch buttons created")

    def _create_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="準備中")
        ttk.Label(self, textvariable=self._status_var, anchor="w", padding=(12, 4), style="Muted.TLabel").pack(fill="x")

    def _bind_events(self):
        """入力/出力パス検証と Alt+H ショートカットをバインド"""
        logger.debug("LauncherApp: Binding events")
        # パス入力変更で有効化チェック
        self.io_panel.input_selector.var.trace_add("write", self._validate)
        self.io_panel.output_selector.var.trace_add("write", self._validate)
        # Alt+H でマニュアルオープン
        self.bind_all("<Alt-h>", lambda e: self.open_manual())
        logger.debug("LauncherApp: Events bound")

    def _validate(self, *args):
        """
        入力／出力フォルダの存在をチェックして、
        両方そろったときだけ起動ボタンを有効化、
        そうでなければ無効化する
        """
        in_dir = self.io_panel.input_selector.var.get()
        out_dir = self.io_panel.output_selector.var.get()
        in_path = Path(in_dir) if in_dir else None
        out_path = Path(out_dir) if out_dir else None
        in_ok = self._is_valid_input_path(in_path)
        out_ok = self._is_valid_output_path(out_path)
        ok = in_ok and out_ok
        self._update_summary(in_path, out_path, in_ok, out_ok)
        self._set_tool_buttons_state(ok)
        logger.debug(f"LauncherApp: Validation result: input='{in_dir}', output='{out_dir}', buttons_enabled={ok}")

    def _is_valid_input_path(self, in_path: Path | None) -> bool:
        return is_valid_input_path(in_path)

    def _is_valid_output_path(self, out_path: Path | None) -> bool:
        return bool(out_path and out_path.is_dir())

    def _set_tool_buttons_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in self._tool_buttons:
            btn.configure(state=state)
        for spec in self._tool_specs:
            win = getattr(self, spec.window_attr, None)
            running = bool(win and win.winfo_exists())
            if running:
                text = "起動中"
            elif enabled:
                text = "実行できます"
            else:
                text = "入力と出力を選択してください"
            self._tool_status_vars[spec.key].set(text)

    def _update_summary(self, in_path: Path | None, out_path: Path | None, in_ok: bool, out_ok: bool) -> None:
        summary = summarize_input_path(in_path)
        self._input_kind_var.set(summary.label)
        self._input_detail_var.set(" / ".join(summary.details))
        self._input_warning_var.set(" / ".join(summary.warnings))
        self._header_summary_var.set(summary.label if in_ok else "入力未完了")
        if out_ok:
            assert out_path is not None
            self._output_status_var.set(f"出力: {out_path}")
        elif out_path and str(out_path):
            self._output_status_var.set("出力フォルダが見つかりません")
        else:
            self._output_status_var.set("出力フォルダ未選択")
        if in_ok and out_ok:
            self._status_var.set("準備完了。起動する機能を選択してください。")
        else:
            self._status_var.set("入力パスと出力フォルダを選択してください。")

    def _build_tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                key="lr_wse",
                label=BUTTON_LABELS["lr_wse"],
                description="左右岸の水位時系列を抽出し、確認用 CSV を作成します。",
                output_hint="左右岸水位 CSV",
                docs_path="user_docs/lr_wse/",
                button_attr="btn_lr_wse",
                window_attr="_lr_wse_win",
                log_name="LrWseGUI",
                close_binding="protocol",
                open_fn=self._launch_lr_wse,
            ),
            ToolSpec(
                key="cross_section",
                label=BUTTON_LABELS["cross_section"],
                description="横断方向の重ね合わせ図を作成し、断面比較を支援します。",
                output_hint="断面図 / Excel",
                docs_path="user_docs/cross_section/",
                button_attr="btn_cross_section",
                window_attr="_cross_section_win",
                log_name="ProfilePlotGUI",
                close_binding="protocol",
                open_fn=self._launch_cross_section,
            ),
            ToolSpec(
                key="time_series",
                label=BUTTON_LABELS["time_series"],
                description="指定した格子点やセルの時系列データを抽出します。",
                output_hint="地点別 CSV",
                docs_path="user_docs/time_series/",
                button_attr="btn_time_series",
                window_attr="_time_series_win",
                log_name="TimeSeriesGUI",
                close_binding="protocol",
                open_fn=self._launch_time_series,
            ),
            ToolSpec(
                key="xy_value_map",
                label=BUTTON_LABELS["xy_value_map"],
                description="平面分布をプレビューし、画像としてまとめて出力します。",
                output_hint="PNG / 連番画像",
                docs_path="user_docs/xy_value_map/",
                button_attr="btn_xy_map",
                window_attr="_xy_map_win",
                log_name="XYValueMapGUI",
                close_binding="destroy",
                open_fn=self._launch_xy_value_map,
            ),
        ]

    def _open_tool(self, spec: ToolSpec) -> None:
        out_dir = self.io_panel.get_output_dir()
        in_path = self.io_panel.get_input_dir()
        logger.info(
            "LauncherApp: Opening %s (in_path=%s, out_dir=%s)",
            spec.log_name,
            in_path,
            out_dir,
        )
        win = getattr(self, spec.window_attr)
        if win and win.winfo_exists():
            logger.debug("LauncherApp: %s already open, lifting window", spec.log_name)
            win.lift()
            return
        new_win = spec.open_fn(self, input_path=in_path, output_dir=out_dir)
        if new_win is None:
            return
        setattr(self, spec.window_attr, new_win)
        self._record_recent_paths(in_path, out_dir)
        self._status_var.set(f"{spec.label} を起動しました。")
        if spec.close_binding == "protocol":
            new_win.protocol("WM_DELETE_WINDOW", lambda s=spec: self._on_tool_close(s))
        else:
            new_win.bind("<Destroy>", lambda event, s=spec: self._on_tool_destroy(event, s))
        self._set_tool_buttons_state(True)
        logger.debug("LauncherApp: %s window created", spec.log_name)

    def _on_tool_close(self, spec: ToolSpec) -> None:
        logger.debug("LauncherApp: Closing %s window", spec.log_name)
        win = getattr(self, spec.window_attr)
        if win:
            win.destroy()
        setattr(self, spec.window_attr, None)
        self._validate()

    def _on_tool_destroy(self, event, spec: ToolSpec) -> None:
        win = getattr(self, spec.window_attr)
        if event.widget is win:
            logger.debug("LauncherApp: %s destroyed", spec.log_name)
            setattr(self, spec.window_attr, None)
            self._validate()

    def _open_tool_docs(self, spec: ToolSpec) -> None:
        webbrowser.open(DOCS_URL.rstrip("/") + "/" + spec.docs_path)

    def _load_recent_items(self) -> list[dict[str, str]]:
        try:
            data = json.loads(RECENT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        items: list[dict[str, str]] = []
        for item in data:
            if isinstance(item, dict) and item.get("input") and item.get("output"):
                items.append({"input": str(item["input"]), "output": str(item["output"])})
        return items[:MAX_RECENT_ITEMS]

    def _save_recent_items(self) -> None:
        try:
            RECENT_PATH.parent.mkdir(parents=True, exist_ok=True)
            RECENT_PATH.write_text(json.dumps(self._recent_items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("LauncherApp: Failed to save recent paths: %s", exc)

    def _record_recent_paths(self, input_path: Path, output_dir: Path) -> None:
        item = {"input": str(input_path), "output": str(output_dir)}
        self._recent_items = [x for x in self._recent_items if x != item]
        self._recent_items.insert(0, item)
        self._recent_items = self._recent_items[:MAX_RECENT_ITEMS]
        self._save_recent_items()
        self._refresh_recent_options()

    def _recent_label(self, item: dict[str, str]) -> str:
        return f"{Path(item['input']).name}  ->  {Path(item['output']).name}"

    def _refresh_recent_options(self) -> None:
        if not hasattr(self, "_recent_combo"):
            return
        self._recent_labels = [self._recent_label(item) for item in self._recent_items]
        self._recent_combo.configure(values=self._recent_labels)
        if self._recent_labels and not self._recent_var.get():
            self._recent_var.set(self._recent_labels[0])

    def _apply_recent_selection(self) -> None:
        label = self._recent_var.get()
        if not label:
            return
        try:
            idx = self._recent_labels.index(label)
        except ValueError:
            return
        item = self._recent_items[idx]
        self.io_panel.input_selector.var.set(item["input"])
        self.io_panel.output_selector.var.set(item["output"])
        self._validate()

    def _launch_lr_wse(self, master: tk.Misc, *, input_path: Path, output_dir: Path):
        """左右岸水位抽出ツールを開く"""
        return self._safe_open_tool(
            lambda: launch_lr_wse(master, input_path=input_path, output_dir=output_dir),
            "LrWseGUI",
        )

    def _launch_cross_section(self, master: tk.Misc, *, input_path: Path, output_dir: Path):
        """横断重ね合わせ図作成ツールを開く"""
        return self._safe_open_tool(
            lambda: launch_cross_section(master, input_path=input_path, output_dir=output_dir),
            "ProfilePlotGUI",
        )

    def _launch_time_series(self, master: tk.Misc, *, input_path: Path, output_dir: Path):
        """時系列抽出ツール GUI を起動"""
        return self._safe_open_tool(
            lambda: launch_time_series(master, input_path=input_path, output_dir=output_dir),
            "TimeSeriesGUI",
        )

    def _launch_xy_value_map(self, master: tk.Misc, *, input_path: Path, output_dir: Path):
        """X-Y分布画像出力ツールを開く（プロジェクト/CSVフォルダ/.ipro/.cgn を直接読み込む）"""
        return self._safe_open_tool(
            lambda: launch_xy_value_map(master, input_path=input_path, output_dir=output_dir),
            "XYValueMapGUI",
        )

    def _safe_open_tool(self, launcher: Callable, log_name: str):
        try:
            return launcher()
        except Exception as exc:
            logger.warning("LauncherApp: Failed to open %s: %s", log_name, exc)
            return None

    def open_manual(self):
        """Notion のマニュアルを既定ブラウザで開く"""
        logger.info("LauncherApp: Opening manual URL: %s", MANUAL_URL)
        webbrowser.open(MANUAL_URL)

    def open_docs(self):
        """GitHub Pages のユーザーマニュアルを既定ブラウザで開く"""
        logger.info("LauncherApp: Opening docs URL: %s", DOCS_URL)
        webbrowser.open(DOCS_URL)

def main(
    argv: list[str] | None = None,
    *,
    show_splash: bool = True,
    on_ready: Callable[[], None] | None = None,
):
    """エントリポイント: ランチャー起動"""
    logger.info("ランチャーを開始します")
    args = sys.argv[1:] if argv is None else argv
    app = LauncherApp(show_splash=show_splash, on_ready=on_ready)
    if len(args) == 2:
        in_arg, out_arg = args
        app.io_panel.input_selector.var.set(in_arg)
        app.io_panel.output_selector.var.set(out_arg)
        app._validate()
    app.mainloop()


if __name__ == "__main__":
    main()
