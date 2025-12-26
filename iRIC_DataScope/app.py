#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\app.py
"""iRIC_DataScope ランチャー起動用スクリプト。"""
import sys
import logging
from pathlib import Path
import tkinter as tk
import webbrowser

# ログ設定を初期化
from iRIC_DataScope.common.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# GUI コンポーネントの読み込み
from iRIC_DataScope.common.io_selector import IOFolderSelector
from iRIC_DataScope.common.iric_project import classify_input_dir
from iRIC_DataScope.lr_wse.launcher import launch_from_launcher as launch_lr_wse
from iRIC_DataScope.cross_section.launcher import launch_from_launcher as launch_cross_section
from iRIC_DataScope.time_series.launcher import launch_from_launcher as launch_time_series
from iRIC_DataScope.xy_value_map.launcher import launch_from_launcher as launch_xy_value_map

class LauncherApp(tk.Tk):
    """
    iRIC 統合ランチャー アプリケーションクラス
    - 入力/出力フォルダ選択
    - 各種ツール起動ボタン
    - ヘルプメニュー＆マニュアルボタン
    """
    def __init__(self):
        super().__init__()
        logger.debug("LauncherApp: Starting initialization")
        # 1. ウィンドウ設定
        self._configure_window()
        # 2. メニューバー（ヘルプ）作成
        self._create_menu()
        # 3. IO フォルダ選択パネル作成
        self._create_io_panel()
        # 4. 各機能起動ボタン作成
        self._create_launch_buttons()
        # 5. イベントバインド（パス検証・ショートカットキー）
        self._bind_events()
        # 6. 自動レイアウト調整：ウィジェットに合わせて初期サイズ＆最小サイズを設定
        self._finalize_layout()
        # 既存ウィンドウを保持する変数
        self._lr_wse_win = None
        self._cross_section_win = None
        self._time_series_win = None
        self._xy_map_win = None
        logger.debug("LauncherApp: Initialization complete")

    def _configure_window(self):
        """ウィンドウのタイトルと初期サイズを設定"""
        logger.debug("LauncherApp: Configuring main window")
        self.title("iRIC解析結果抽出・可視化アプリ")
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
        self.geometry(f"{w+margin_x}x{h+margin_y}")
        self.minsize(w+margin_x, h+margin_y)
        logger.debug(f"LauncherApp: Geometry set to {w+margin_x}x{h+margin_y}")

    def _create_menu(self):
        """メニューバーとヘルプメニューを追加"""
        logger.debug("LauncherApp: Creating menu bar")
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="マニュアルを開く",
                              accelerator="Alt+H",
                              command=self.open_manual)
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
        self.btn_lr_wse = tk.Button(self, text="左右岸水位抽出",
                                    command=self.open_lr_wse, state="disabled")
        self.btn_cross_section = tk.Button(self, text="横断重ね合わせ図作成",
                                           command=self.open_cross_section, state="disabled")
        self.btn_time_series = tk.Button(self, text="時系列データ抽出",
                                         command=self.open_time_series, state="disabled")
        self.btn_xy_map = tk.Button(self, text="X-Y分布画像出力",
                                    command=self.open_xy_value_map, state="disabled")
        for btn in (self.btn_lr_wse, self.btn_cross_section, self.btn_time_series, self.btn_xy_map):
            btn.pack(fill="x", padx=20, pady=5)
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
        in_ok = False
        if in_path and in_path.is_dir():
            try:
                classify_input_dir(in_path)
                in_ok = True
            except Exception:
                in_ok = False
        elif in_path and in_path.is_file() and in_path.suffix.lower() == ".ipro":
            in_ok = True
        out_ok = bool(out_path and out_path.is_dir())
        ok = in_ok and out_ok
        state = "normal" if ok else "disabled"
        for btn in (self.btn_lr_wse, self.btn_cross_section, self.btn_time_series, self.btn_xy_map):
            btn.configure(state=state)
        logger.debug(f"LauncherApp: Validation result: input='{in_dir}', output='{out_dir}', buttons_enabled={ok}")

    def open_lr_wse(self):
        """左右岸水位抽出ツールを開く"""
        out_dir = self.io_panel.get_output_dir()
        in_path = self.io_panel.get_input_dir()
        logger.info(f"LauncherApp: Opening LrWseGUI (in_path={in_path}, out_dir={out_dir})")
        if self._lr_wse_win and self._lr_wse_win.winfo_exists():
            logger.debug("LauncherApp: LrWseGUI already open, lifting window")
            self._lr_wse_win.lift()
            return
        self._lr_wse_win = launch_lr_wse(self, input_path=in_path, output_dir=out_dir)
        self._lr_wse_win.protocol("WM_DELETE_WINDOW", self._on_close_lr_wse)
        logger.debug("LauncherApp: LrWseGUI window created")

    def _on_close_lr_wse(self):
        """左右岸水位抽出ウィンドウが閉じられたときに参照を破棄"""
        logger.debug("LauncherApp: Closing LrWseGUI window")
        if self._lr_wse_win:
            self._lr_wse_win.destroy()
        self._lr_wse_win = None

    def open_cross_section(self):
        """横断重ね合わせ図作成ツールを開く"""
        out_dir = self.io_panel.get_output_dir()
        in_path = self.io_panel.get_input_dir()
        logger.info(f"LauncherApp: Opening ProfilePlotGUI (in_path={in_path}, out_dir={out_dir})")
        if self._cross_section_win and self._cross_section_win.winfo_exists():
            logger.debug("LauncherApp: ProfilePlotGUI already open, lifting window")
            self._cross_section_win.lift()
            return
        self._cross_section_win = launch_cross_section(self, input_path=in_path, output_dir=out_dir)
        self._cross_section_win.protocol("WM_DELETE_WINDOW", self._on_close_cross_section)
        logger.debug("LauncherApp: ProfilePlotGUI window created")

    def _on_close_cross_section(self):
        """横断重ね合わせ図作成ウィンドウが閉じられたときに参照を破棄"""
        logger.debug("LauncherApp: Closing ProfilePlotGUI window")
        if self._cross_section_win:
            self._cross_section_win.destroy()
        self._cross_section_win = None

    def open_time_series(self):
        """時系列抽出ツール GUI を起動"""
        out_dir = self.io_panel.get_output_dir()
        in_path = self.io_panel.get_input_dir()
        logger.info(f"LauncherApp: Opening TimeSeriesGUI (in_path={in_path}, out_dir={out_dir})")
        if self._time_series_win and self._time_series_win.winfo_exists():
            logger.debug("LauncherApp: TimeSeriesGUI already open, lifting window")
            self._time_series_win.lift()
            return
        self._time_series_win = launch_time_series(self, input_path=in_path, output_dir=out_dir)
        self._time_series_win.protocol("WM_DELETE_WINDOW", self._on_close_time_series)
        logger.debug("LauncherApp: TimeSeriesGUI window created")

    def _on_close_time_series(self):
        """時系列ウィンドウが閉じられたときに参照を破棄"""
        logger.debug("LauncherApp: Closing TimeSeriesGUI window")
        if self._time_series_win:
            self._time_series_win.destroy()
            self._time_series_win = None

    def open_xy_value_map(self):
        """X-Y分布画像出力ツールを開く（プロジェクト/CSVフォルダ/.ipro を直接読み込む）"""
        in_path = self.io_panel.get_input_dir()
        out_dir = self.io_panel.get_output_dir()
        logger.info(f"LauncherApp: Opening XYValueMapGUI (input={in_path}, out_dir={out_dir})")
        if self._xy_map_win and self._xy_map_win.winfo_exists():
            logger.debug("LauncherApp: XYValueMapGUI already open, lifting window")
            self._xy_map_win.lift()
            return
        self._xy_map_win = launch_xy_value_map(self, input_path=in_path, output_dir=out_dir)
        self._xy_map_win.bind("<Destroy>", self._on_destroy_xy_map)

    def _on_destroy_xy_map(self, event):
        if event.widget is self._xy_map_win:
            logger.debug("LauncherApp: XYValueMapGUI destroyed")
            self._xy_map_win = None

    def open_manual(self):
        """Notion のマニュアルを既定ブラウザで開く"""
        url = "https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=73"
        logger.info(f"LauncherApp: Opening manual URL: {url}")
        webbrowser.open(url)

def main(argv: list[str] | None = None):
    """エントリポイント: ランチャー起動"""
    logger.info("ランチャーを開始します")
    args = sys.argv[1:] if argv is None else argv
    app = LauncherApp()
    if len(args) == 2:
        in_arg, out_arg = args
        app.io_panel.input_selector.var.set(in_arg)
        app.io_panel.output_selector.var.set(out_arg)
        app._validate()
    app.mainloop()


if __name__ == "__main__":
    main()
