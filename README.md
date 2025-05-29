# iRIC_DataScope

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
│   ├── app.py              # アプリケーションエントリーポイント
│   ├── common/             # 共通モジュール
│   │   ├── csv_reader.py   # CSVファイル読み込み処理
│   │   └── logging_config.py # ロギング設定
│   ├── cross_section/      # 横断重ね合わせ図作成功能
│   │   ├── gui.py         # GUI実装
│   │   └── plot_main.py   # プロット処理
│   ├── lr_wse/            # 左右岸最大水位整理機能
│   │   ├── gui.py         # GUI実装
│   │   ├── main.py        # メイン処理
│   │   ├── config.py      # 設定処理
│   │   ├── extractor.py   # データ抽出処理
│   │   └── writer.py      # Excel出力処理
│   └── time_series/        # 時系列データ処理
│       ├── gui_components.py # GUIコンポーネント
│       ├── main.py        # メイン処理
│       └── processor.py   # データ処理
└── requirements.txt        # 必要なパッケージリスト
```

## ロギング
アプリケーション全体で統一されたロギングシステムを実装しています。
- INFO: 重要な処理の開始/終了
- DEBUG: 詳細な実行状況
- ERROR: エラー発生時の詳細情報

## ライセンス
[MIT ライセンス](LICENSE) 
