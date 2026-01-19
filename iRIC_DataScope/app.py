#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\app.py
"""iRIC_DataScope ランチャー起動用スクリプト。"""
import sys
import logging
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
import tkinter as tk
import webbrowser
import time

from iRIC_DataScope.common.io_selector import IOFolderSelector
from iRIC_DataScope.common.iric_project import is_valid_input_path
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
    button_attr: str
    window_attr: str
    log_name: str
    close_binding: str  # "protocol" or "destroy"
    open_fn: Callable

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
        # 2. メニューバー（ヘルプ）作成
        self._create_menu()
        logger.debug("LauncherApp: Menu created in %.3fs", time.perf_counter() - start)
        # 3. IO フォルダ選択パネル作成
        self._create_io_panel()
        logger.debug("LauncherApp: IO panel created in %.3fs", time.perf_counter() - start)
        # 4. 各機能起動ボタン作成
        self._create_launch_buttons()
        logger.debug("LauncherApp: Launch buttons created in %.3fs", time.perf_counter() - start)
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
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
            return base / relative_path
        if relative_path.parts and relative_path.parts[0] == "iRIC_DataScope":
            relative_path = Path(*relative_path.parts[1:])
        return _APP_DIR / relative_path

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

    def _create_io_panel(self):
        """入力／出力フォルダ選択用パネルを配置"""
        logger.debug("LauncherApp: Creating IO folder selector panel")
        self.io_panel = IOFolderSelector(self)
        self.io_panel.pack(fill="x", padx=10, pady=10)
        logger.debug("LauncherApp: IO panel created")

    def _create_launch_buttons(self):
        """左右岸整理・プロファイルプロット・時系列抽出ツールの起動ボタンを配置"""
        logger.debug("LauncherApp: Creating launch buttons")
        self._tool_specs = self._build_tool_specs()
        self._tool_buttons = []
        for spec in self._tool_specs:
            btn = tk.Button(
                self,
                text=spec.label,
                command=lambda s=spec: self._open_tool(s),
                state="disabled",
            )
            setattr(self, spec.button_attr, btn)
            btn.pack(fill="x", padx=20, pady=5)
            self._tool_buttons.append(btn)
        logger.debug("LauncherApp: Launch buttons created")

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

    def _build_tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                key="lr_wse",
                label=BUTTON_LABELS["lr_wse"],
                button_attr="btn_lr_wse",
                window_attr="_lr_wse_win",
                log_name="LrWseGUI",
                close_binding="protocol",
                open_fn=self._launch_lr_wse,
            ),
            ToolSpec(
                key="cross_section",
                label=BUTTON_LABELS["cross_section"],
                button_attr="btn_cross_section",
                window_attr="_cross_section_win",
                log_name="ProfilePlotGUI",
                close_binding="protocol",
                open_fn=self._launch_cross_section,
            ),
            ToolSpec(
                key="time_series",
                label=BUTTON_LABELS["time_series"],
                button_attr="btn_time_series",
                window_attr="_time_series_win",
                log_name="TimeSeriesGUI",
                close_binding="protocol",
                open_fn=self._launch_time_series,
            ),
            ToolSpec(
                key="xy_value_map",
                label=BUTTON_LABELS["xy_value_map"],
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
        if spec.close_binding == "protocol":
            new_win.protocol("WM_DELETE_WINDOW", lambda s=spec: self._on_tool_close(s))
        else:
            new_win.bind("<Destroy>", lambda event, s=spec: self._on_tool_destroy(event, s))
        logger.debug("LauncherApp: %s window created", spec.log_name)

    def _on_tool_close(self, spec: ToolSpec) -> None:
        logger.debug("LauncherApp: Closing %s window", spec.log_name)
        win = getattr(self, spec.window_attr)
        if win:
            win.destroy()
        setattr(self, spec.window_attr, None)

    def _on_tool_destroy(self, event, spec: ToolSpec) -> None:
        win = getattr(self, spec.window_attr)
        if event.widget is win:
            logger.debug("LauncherApp: %s destroyed", spec.log_name)
            setattr(self, spec.window_attr, None)

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
        """X-Y分布画像出力ツールを開く（プロジェクト/CSVフォルダ/.ipro を直接読み込む）"""
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
