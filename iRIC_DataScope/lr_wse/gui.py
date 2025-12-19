#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\lr_wse\gui.py
"""
lr_wse GUI: iRIC 左右岸最大水位整理ツール
このウィンドウは Toplevel で生成され、ランチャーの Tk を master に持ちます。
"""
import sys
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser

# ロガー設定
logger = logging.getLogger(__name__)

# スクリプト単体実行時にパッケージを認識させる
if __name__ == "__main__" and __package__ is None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo_root))
    __package__ = "iRIC_DataScope.lr_wse"

from .main import run_lr_wse

class LrWseGUI(tk.Toplevel):
    """
    iRIC 左右岸最大水位整理ツール GUI
    - 入力/出力フォルダ
    - 設定ファイル選択
    - 各種オプション設定
    - 実行/ヘルプメニュー
    """
    def __init__(self, master, input_dir: Path, output_dir: Path):
        logger.info(f"GUI インスタンス作成: input_dir={input_dir}, output_dir={output_dir}")
        super().__init__(master)
        self.master = master
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.config_file = None

        # 1. ウィンドウ設定
        self._configure_window()
        # 2. メニューバー（ヘルプ）作成
        self._create_menu()
        # 3. ウィジェット作成
        self._create_widgets()
        # 4. イベントバインド
        self._bind_events()
        # 5. 自動レイアウト調整：ウィジェットに合わせて初期サイズ＆最小サイズを設定
        self._finalize_layout()

    def _configure_window(self):
        """ウィンドウタイトルとサイズを設定"""
        logger.info("ウィンドウ設定開始")
        self.title("左右岸水位抽出")
        #self.geometry("600x330")
        
    def _finalize_layout(self):
        """
        ウィジェット配置後に必要最小サイズを計算し、
        初期ジオメトリと最小サイズとして設定する
        """
        logger.info("ウィンドウサイズ調整開始")
        # 全配置が終わるまで待ってサイズ計算
        self.update_idletasks()
        # 必要最小幅・高さを取得
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        logger.debug(f"ウィンドウサイズ: width={w}, height={h}")

        # 余白として左右 0px、上下 0px を追加
        margin_x, margin_y = 0, 0  
        self.geometry(f"{w+margin_x}x{h+margin_y}")
        self.minsize(w+margin_x, h+margin_y)

    def _create_menu(self):
        """メニューバーにヘルプメニューを追加"""
        menubar = tk.Menu(self)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label="マニュアルを開く",
            accelerator="Alt+H",
            command=self.open_manual
        )
        menubar.add_cascade(label="ヘルプ(H)", menu=help_menu)
        self.config(menu=menubar)

    def _create_widgets(self):
        """入力フィールド、オプション、ボタンなどのウィジェットを配置"""
        pad = {'padx': 8, 'pady': 4}

        # 入力フォルダ
        tk.Label(self, text="入力フォルダ:").grid(row=0, column=0, sticky="e", **pad)
        self.input_var = tk.StringVar(value=str(self.input_dir))
        tk.Entry(self, textvariable=self.input_var, width=40, state='readonly').grid(row=0, column=1, **pad)

        # 設定ファイル
        tk.Label(self, text="設定ファイル:").grid(row=1, column=0, sticky="e", **pad)
        self.config_var = tk.StringVar(value="(未選択)")
        tk.Entry(self, textvariable=self.config_var, width=40, state='readonly').grid(row=1, column=1, **pad)
        tk.Button(self, text="参照", command=self._choose_config_file).grid(row=1, column=2, **pad)

        # 出力フォルダ
        tk.Label(self, text="出力フォルダ:").grid(row=2, column=0, sticky="e", **pad)
        self.output_var = tk.StringVar(value=str(self.output_dir))
        tk.Entry(self, textvariable=self.output_var, width=40, state='readonly').grid(row=2, column=1, **pad)

        # 中間CSV出力オン/オフ
        self.use_temp = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self,
            text="中間CSVを出力する",
            variable=self.use_temp,
            command=self._toggle_temp_ui
        ).grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        tk.Label(self, text="中間フォルダ:").grid(row=4, column=0, sticky="e", **pad)
        self.temp_var = tk.StringVar()
        self.temp_entry = tk.Entry(self, textvariable=self.temp_var, width=40, state='disabled')
        self.temp_entry.grid(row=4, column=1, **pad)
        self.temp_btn = tk.Button(self, text="参照", state='disabled', command=self._choose_temp_dir)
        self.temp_btn.grid(row=4, column=2, **pad)

        # 出力ファイル名
        tk.Label(self, text="出力ファイル名:").grid(row=5, column=0, sticky="e", **pad)
        self.filename_var = tk.StringVar(value="LR_WSE.xlsx")
        tk.Entry(self, textvariable=self.filename_var, width=40).grid(row=5, column=1, **pad)

        # 欠損値置換
        tk.Label(self, text="欠損値置換:").grid(row=6, column=0, sticky="e", **pad)
        self.missing_var = tk.StringVar(value="")
        tk.Entry(self, textvariable=self.missing_var, width=40).grid(row=6, column=1, **pad)
        tk.Label(self, text="(空白→空セル)").grid(row=6, column=2, sticky="w", **pad)

        # 実行ボタン
        tk.Button(self, text="実行", command=self._run).grid(row=7, column=0, columnspan=3, pady=15)

    def _bind_events(self):
        """各種イベントのバインド: Alt+H など"""
        self.bind_all("<Alt-h>", lambda e: self.open_manual())

    def _toggle_temp_ui(self):
        """中間フォルダ選択 UI の有効/無効切り替え"""
        state = 'normal' if self.use_temp.get() else 'disabled'
        self.temp_entry.configure(state=state)
        self.temp_btn.configure(state=state)

    def _choose_temp_dir(self):
        """中間フォルダを選択し、変数にセット"""
        path = filedialog.askdirectory(title="中間フォルダを選択")
        if path:
            self.temp_var.set(path)

    def _choose_config_file(self):
        """設定ファイルを選択し、変数にセット"""
        logger.info("設定ファイル選択ダイアログを開く")
        file = filedialog.askopenfilename(
            title="設定ファイルを選択",
            filetypes=[("CSVファイル", "*.csv"), ("All files", "*")]
        )
        if file:
            self.config_file = Path(file)
            logger.info(f"設定ファイル選択: {file}")
            self.config_var.set(str(file))

    def _run(self):
        """左右岸水位抽出の実行処理を呼び出し、完了/エラーを通知"""
        logger.info("実行ボタン押下")
        try:
            in_dir = Path(self.input_var.get())
            out_dir = Path(self.output_var.get())
            cfg = self.config_file
            logger.debug(f"入力フォルダ: {in_dir}, 出力フォルダ: {out_dir}, 設定ファイル: {cfg}")
            
            in_ok = in_dir.is_dir() or (in_dir.is_file() and in_dir.suffix.lower() == ".ipro")
            if not (in_ok and out_dir.is_dir() and cfg and cfg.is_file()):
                logger.error("入力フォルダ、設定ファイル、出力フォルダのいずれかが無効です")
                messagebox.showerror(
                    "エラー",
                    "入力（プロジェクトフォルダ/CSVフォルダ/.ipro）、設定ファイル、出力フォルダを正しく指定してください。",
                )
                return
            
            missing = None if self.missing_var.get() == "" else self.missing_var.get()
            temp_dir = Path(self.temp_var.get()) if self.use_temp.get() else None
            logger.debug(f"実行パラメータ: missing_elev={missing}, temp_dir={temp_dir}")
            
            out_path = run_lr_wse(
                input_path=in_dir,
                config_file=cfg,
                output_dir=out_dir,
                excel_filename=self.filename_var.get(),
                missing_elev=missing,
                temp_dir=temp_dir
            )
            logger.info(f"処理完了: 出力ファイル={out_path}")
            # 完了ダイアログを表示し、OK が押されたら Toplevel を閉じる
            if messagebox.showinfo("完了", f"Excelを出力しました:\n{out_path}") == "ok":
                self.destroy()
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def open_manual(self):
        """Notion マニュアルを既定ブラウザで開く"""
        logger.info("マニュアルを開く")
        webbrowser.open("https://trite-entrance-e6b.notion.site/iRIC_tools-1f4ed1e8e79f8084bf81e7cf1b960727?pvs=25#1f4ed1e8e79f80fba2c3c518b62fc898")

if __name__ == "__main__":
    # コマンドライン引数: 入力フォルダ, 出力フォルダ
    args = sys.argv[1:]
    if len(args) == 2:
        in_dir, out_dir = map(Path, args)
    else:
        root = tk.Tk()
        root.withdraw()
        in_dir = Path(filedialog.askdirectory(title="入力フォルダを選択"))
        out_dir = Path(filedialog.askdirectory(title="出力フォルダを選択"))
        root.destroy()
    # Toplevel を生成するためにルートウィンドウを用意
    root = tk.Tk()
    root.withdraw()
    app = LrWseGUI(root, in_dir, out_dir)
    root.mainloop()
