#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\app.py
"""
iRIC_DataScope\app.py 直接実行用スクリプト
"""
import sys
import logging
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import webbrowser

# スクリプト単体実行時にパッケージを認識させる
if __name__ == '__main__':
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

# ログ設定を初期化
from iRIC_DataScope.common.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# GUI コンポーネントの読み込み
from iRIC_DataScope.common.io_selector import IOFolderSelector
from iRIC_DataScope.common.cgns_converter import ConversionOptions, convert_iric_project
from iRIC_DataScope.common.iric_project import classify_input_dir
from iRIC_DataScope.lr_wse.gui import P5GUI
from iRIC_DataScope.cross_section.gui import ProfilePlotGUI
from iRIC_DataScope.time_series.gui_components import TimeSeriesGUI
from iRIC_DataScope.xy_value_map.gui import XYValueMapGUI

class App2(tk.Tk):
    """
    iRIC 統合ランチャー アプリケーションクラス
    - 入力/出力フォルダ選択
    - 各種ツール起動ボタン
    - ヘルプメニュー＆マニュアルボタン
    """
    def __init__(self):
        super().__init__()
        logger.debug("App2: Starting initialization")
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
        self._p5_win   = None
        self._plot_win = None
        self._ts_win   = None
        self._xy_win   = None
        logger.debug("App2: Initialization complete")

    def _configure_window(self):
        """ウィンドウのタイトルと初期サイズを設定"""
        logger.debug("App2: Configuring main window")
        self.title("iRIC解析結果抽出・可視化アプリ")
        # self.geometry("600x330")

    def _finalize_layout(self):
        """
        ウィジェット配置後に必要最小サイズを計算し、
        初期ジオメトリと最小サイズとして設定する
        """
        logger.debug("App2: Finalizing layout")
        # 全配置が終わるまで待ってサイズ計算
        self.update_idletasks()
        # 必要最小幅・高さを取得
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()

        # 余白として左右 20px、上下 20px を追加
        margin_x, margin_y = 20, 20
        self.geometry(f"{w+margin_x}x{h+margin_y}")
        self.minsize(w+margin_x, h+margin_y)
        logger.debug(f"App2: Geometry set to {w+margin_x}x{h+margin_y}")

    def _create_menu(self):
        """メニューバーとヘルプメニューを追加"""
        logger.debug("App2: Creating menu bar")
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="マニュアルを開く",
                              accelerator="Alt+H",
                              command=self.open_manual)
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)
        logger.debug("App2: Menu bar created")

    def _create_io_panel(self):
        """入力／出力フォルダ選択用パネルを配置"""
        logger.debug("App2: Creating IO folder selector panel")
        self.io_panel = IOFolderSelector(self)
        self.io_panel.pack(fill="x", padx=10, pady=10)
        logger.debug("App2: IO panel created")

    def _create_launch_buttons(self):
        """左右岸整理・プロファイルプロット・時系列抽出ツールの起動ボタンを配置"""
        logger.debug("App2: Creating launch buttons")
        self.btn_p5   = tk.Button(self, text="左右岸水位抽出",
                                  command=self.open_p5, state="disabled")
        self.btn_plot = tk.Button(self, text="横断重ね合わせ図作成",
                                  command=self.open_plot, state="disabled")
        self.btn_ts   = tk.Button(self, text="時系列データ抽出",
                                  command=self.open_ts, state="disabled")
        self.btn_xy = tk.Button(self, text="X-Y分布画像出力",
                                command=self.open_xy, state="disabled")
        for btn in (self.btn_p5, self.btn_plot, self.btn_ts, self.btn_xy):
            btn.pack(fill="x", padx=20, pady=5)
        logger.debug("App2: Launch buttons created")

    def _bind_events(self):
        """入力/出力パス検証と Alt+H ショートカットをバインド"""
        logger.debug("App2: Binding events")
        # パス入力変更で有効化チェック
        self.io_panel.input_selector.var.trace_add("write", self._validate)
        self.io_panel.output_selector.var.trace_add("write", self._validate)
        # Alt+H でマニュアルオープン
        self.bind_all("<Alt-h>", lambda e: self.open_manual())
        logger.debug("App2: Events bound")

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
        for btn in (self.btn_p5, self.btn_plot, self.btn_ts, self.btn_xy):
            btn.configure(state=state)
        logger.debug(f"App2: Validation result: input='{in_dir}', output='{out_dir}', buttons_enabled={ok}")

    def _show_progress(self, text: str) -> tk.Toplevel:
        """簡易プログレス表示用の小ウィンドウを出す"""
        win = tk.Toplevel(self)
        win.title("変換中")
        win.transient(self)
        win.resizable(False, False)
        tk.Label(win, text=text, padx=20, pady=15).pack()
        win.update_idletasks()
        self.update_idletasks()
        return win

    def _prepare_input_for_tool(self) -> Path | None:
        """
        入力がプロジェクトフォルダの場合は CSV 変換して変換先フォルダを返す。
        既存CSVがある場合は上書き確認を出し、キャンセルなら再利用。
        エラー時は None。
        """
        in_path = self.io_panel.get_input_dir()
        out_dir = self.io_panel.get_output_dir()

        if in_path.is_file():
            if in_path.suffix.lower() != ".ipro":
                messagebox.showerror(
                    "入力エラー",
                    "入力にはプロジェクトフォルダ、CSVフォルダ、または .ipro を指定してください。",
                )
                return None
            input_kind = "ipro"
            conv_dir = out_dir / f"converted_{in_path.stem}"
        else:
            try:
                kind = classify_input_dir(in_path)
            except Exception as exc:
                logger.exception("入力フォルダの判定に失敗しました")
                messagebox.showerror("入力エラー", str(exc))
                return None
            if kind == "csv_dir":
                return in_path
            input_kind = "project_dir"
            conv_dir = out_dir / f"converted_{in_path.name}"

        conv_dir.mkdir(parents=True, exist_ok=True)

        existing_csv = list(conv_dir.glob("*.csv"))
        if existing_csv:
            overwrite = messagebox.askyesno(
                "確認",
                f"{conv_dir} に既存の CSV が見つかりました。\n"
                "上書きして再変換しますか？\n"
                "（いいえ を選ぶと既存CSVを再利用します）"
            )
            if not overwrite:
                # 再利用するのでパスだけ返す
                self.io_panel.input_selector.var.set(str(conv_dir))
                return conv_dir

        progress = None
        try:
            if input_kind == "ipro":
                progress = self._show_progress("ipro を展開して CSV へ変換中です...")
            else:
                progress = self._show_progress("プロジェクトフォルダから CSV へ変換中です...")
            # すぐに描画する
            if progress:
                progress.update()
                self.update()

            convert_iric_project(
                in_path,
                conv_dir,
                options=ConversionOptions(
                    include_flow_solution=True,
                    location_preference="auto",
                ),
            )
            # 先にプログレスを閉じてから完了ダイアログ
            if progress and progress.winfo_exists():
                progress.destroy()
                progress = None
            self.io_panel.input_selector.var.set(str(conv_dir))
            messagebox.showinfo("変換完了", f"CSV 変換が完了しました。\n出力先: {conv_dir}")
            return conv_dir
        except Exception:
            logger.exception("CSV 変換に失敗しました")
            if progress and progress.winfo_exists():
                progress.destroy()
                progress = None
            messagebox.showerror(
                "変換エラー",
                "CSV 変換に失敗しました。詳細はログを確認してください。"
            )
            return None

    def open_p5(self):
        """左右岸水位抽出ツールを開く"""
        out_dir = self.io_panel.get_output_dir()
        in_dir = self._prepare_input_for_tool()
        if not in_dir:
            return
        logger.info(f"App2: Opening P5GUI (in_dir={in_dir}, out_dir={out_dir})")
        if self._p5_win and self._p5_win.winfo_exists():
            logger.debug("App2: P5GUI already open, lifting window")
            self._p5_win.lift()
            return
        self._p5_win = P5GUI(self, in_dir, out_dir)
        self._p5_win.protocol("WM_DELETE_WINDOW", self._on_close_p5)
        logger.debug("App2: P5GUI window created")

    def _on_close_p5(self):
        """P5GUI が閉じられたときに参照を破棄"""
        logger.debug("App2: Closing P5GUI window")
        if self._p5_win:
            self._p5_win.destroy()
        self._p5_win = None

    def open_plot(self):
        """プロファイルプロットツールを開く"""
        out_dir = self.io_panel.get_output_dir()
        in_dir = self._prepare_input_for_tool()
        if not in_dir:
            return
        logger.info(f"App2: Opening ProfilePlotGUI (in_dir={in_dir}, out_dir={out_dir})")
        if self._plot_win and self._plot_win.winfo_exists():
            logger.debug("App2: ProfilePlotGUI already open, lifting window")
            self._plot_win.lift()
            return
        self._plot_win = ProfilePlotGUI(self, in_dir, out_dir)
        self._plot_win.protocol("WM_DELETE_WINDOW", self._on_close_plot)
        logger.debug("App2: ProfilePlotGUI window created")

    def _on_close_plot(self):
        """ProfilePlotGUI が閉じられたときに参照を破棄"""
        logger.debug("App2: Closing ProfilePlotGUI window")
        if self._plot_win:
            self._plot_win.destroy()
        self._plot_win = None

    def open_ts(self):
        """時系列抽出ツール GUI を起動"""
        out_dir = self.io_panel.get_output_dir()
        in_dir = self._prepare_input_for_tool()
        if not in_dir:
            return
        logger.info(f"App2: Opening TimeSeriesGUI (in_dir={in_dir}, out_dir={out_dir})")
        if self._ts_win and self._ts_win.winfo_exists():
            logger.debug("App2: TimeSeriesGUI already open, lifting window")
            self._ts_win.lift()
            return
        self._ts_win = TimeSeriesGUI(master=self, initial_input_dir=in_dir, initial_output_dir=out_dir)
        self._ts_win.protocol("WM_DELETE_WINDOW", self._on_close_ts)
        logger.debug("App2: TimeSeriesGUI window created")

    def _on_close_ts(self):
        """時系列ウィンドウが閉じられたときに参照を破棄"""
        logger.debug("App2: Closing TimeSeriesGUI window")
        if self._ts_win:
            self._ts_win.destroy()
            self._ts_win = None

    def open_xy(self):
        """X-Y分布画像出力ツールを開く（プロジェクト/CSVフォルダ/.ipro を直接読み込む）"""
        in_path = self.io_panel.get_input_dir()
        out_dir = self.io_panel.get_output_dir()
        logger.info(f"App2: Opening XYValueMapGUI (input={in_path}, out_dir={out_dir})")
        if self._xy_win and self._xy_win.winfo_exists():
            logger.debug("App2: XYValueMapGUI already open, lifting window")
            self._xy_win.lift()
            return
        self._xy_win = XYValueMapGUI(self, input_path=in_path, output_dir=out_dir)
        self._xy_win.bind("<Destroy>", self._on_destroy_xy)

    def _on_destroy_xy(self, event):
        if event.widget is self._xy_win:
            logger.debug("App2: XYValueMapGUI destroyed")
            self._xy_win = None

    def open_manual(self):
        """Notion のマニュアルを既定ブラウザで開く"""
        url = "https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=73"
        logger.info(f"App2: Opening manual URL: {url}")
        webbrowser.open(url)

def main(argv: list[str] | None = None):
    """エントリポイント: ランチャー起動"""
    logger.info("app2ランチャーを開始します")
    args = sys.argv[1:] if argv is None else argv
    app = App2()
    if len(args) == 2:
        in_arg, out_arg = args
        app.io_panel.input_selector.var.set(in_arg)
        app.io_panel.output_selector.var.set(out_arg)
        app._validate()
    app.mainloop()


if __name__ == "__main__":
    main()
