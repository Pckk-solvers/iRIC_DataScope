# iRIC_DataScope
本リポジトリではツール利用者とiRICの計算結果整理ツールの開発者へ向けたものとなっております。


利用者は**iRIC_DataScope-[バージョン番号].exe**をダウンロードしてダブルクリックで実行してください。


開発者は[Releases](https://github.com/Pckk-solvers/iRIC_DataScope/releases)でバージョン管理をしているためそちらも合わせてご確認ください。


## 概要
iRIC_DataScopeは、iRIC（International River Interface Cooperative）のシミュレーション結果を解析・抽出・可視化するためのツールです。GUIインターフェースを提供し、以下の機能を実装しています：

- 時系列データの抽出と可視化
- 横断断面の重ね合わせプロット
- 左右岸最大水位の抽出と整理

## 機能詳細

### 1. 時系列データ処理
- iRICの出力CSVファイルから時系列データを抽出
- 複数ファイルのデータを統合して時系列DataFrameを作成
- グラフ表示とExcel出力機能を提供

### 2. 横断重ね合わせ図作成
- iRICの横断断面データを読み込み
- 複数断面の重ね合わせプロットを生成
- グラフのカスタマイズ（凡例、グリッド、スケール等）
- Excelへの出力機能

### 3. 左右岸最大水位整理
- 左右岸の最大水位データを抽出
- 設定ファイルに基づくデータの整理
- 中間CSVファイルの生成
- 最終的なExcelファイルへの出力

## 技術スタック
- Python 3.13.1
- Pandas: データ処理
- Matplotlib: グラフ描画
- Tkinter: GUIフレームワーク
- logging: ロギング

## インストール
必要なパッケージは `requirements.txt` に記載されています。
以下のコマンドでインストールできます：
```bash
pip install -r requirements.txt
```

## 使い方

### 1. インポートモジュールとして実行
```bash
python -m iRIC_DataScope.app
```

### 2. 直接実行
```bash
python iRIC_DataScope/app.py
```

## プロジェクト構造
```
iRIC_DataScope/
├── iRIC_DataScope/          # メインパッケージ
│   ├── app.py               # アプリケーションエントリーポイント
│   ├── common/              # 共通モジュール
│   │   ├── csv_reader.py    # CSVファイル読み込み処理
│   │   ├── io_selector.py   # 入力ダイアログ
│   │   ├── logging_config.py# ロギング設定
│   │   ├── path_selector.py # ファイル選択補助
│   │   └── ui_config.py     # GUI設定
│   ├── cross_section/       # 横断重ね合わせ図作成機能
│   │   ├── data_loader.py   # データ読み込み
│   │   ├── excel_utils.py   # Excel 書き出し
│   │   ├── gui.py           # GUI実装
│   │   ├── plot_core.py     # プロット処理コア
│   │   └── plot_main.py     # 実行用モジュール
│   ├── lr_wse/              # 左右岸最大水位整理機能
│   │   ├── config.py        # 設定処理
│   │   ├── extractor.py     # データ抽出処理
│   │   ├── file_utils.py    # ファイル操作
│   │   ├── gui.py           # GUI実装
│   │   ├── main.py          # メイン処理
│   │   ├── reader.py        # 読み込み処理
│   │   └── writer.py        # Excel出力処理
│   └── time_series/         # 時系列データ処理
│       ├── excel_writer.py  # Excel出力処理
│       ├── gui_components.py# GUIコンポーネント
│       ├── main.py          # メイン処理
│       └── processor.py     # データ処理
├── requirements.txt         # 必要なパッケージリスト
├── sample_config/           # 設定サンプル
│   ├── setting.csv
│   └── 格子設定サンプル.csv
│
├── iRIC_DataScope-[バージョン番号].exe    # 利用者向けツール実行ファイル

```

## ロギング
アプリケーション全体で統一されたロギングシステムを実装しています。
- INFO: 重要な処理の開始/終了
- DEBUG: 詳細な実行状況
- ERROR: エラー発生時の詳細情報

## ライセンス
[MIT ライセンス](LICENSE) 
