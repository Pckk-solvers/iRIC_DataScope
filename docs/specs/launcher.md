# ランチャー（`iRIC_DataScope/app.py`）現状実装まとめ

## 目的
- 1つの GUI から、各機能（ツール）を起動できるようにする
- 入力が **プロジェクトフォルダ / `.ipro`** の場合も、各機能が **直接読み込んで**処理できるようにする

## 入力/出力
- 入力: フォルダ または `.ipro`
  - CSVフォルダ: 既に `Result_*.csv` が存在する前提（従来の iRIC 出力 CSV）
  - プロジェクトフォルダ: CGNS を直接読み込み（CSV 変換は不要）
  - `.ipro`: 内部を展開して CGNS を直接読み込み（CSV 変換は不要）
- 出力: 出力フォルダ（各機能の成果物）

## 起動できる機能
- `左右岸水位抽出`（`iRIC_DataScope/lr_wse`）
- `横断重ね合わせ図作成`（`iRIC_DataScope/cross_section`）
- `時系列データ抽出`（`iRIC_DataScope/time_series`）
- `X-Y分布画像出力`（`iRIC_DataScope/xy_value_map`）

## 入力パスの扱い
- `左右岸水位抽出` / `横断重ね合わせ図作成` / `時系列データ抽出` / `X-Y分布画像出力` の全機能が
  **プロジェクトフォルダ / CSVフォルダ / `.ipro`** を直接読み込む

## エントリポイント
- 推奨: `python -m iRIC_DataScope.app`（モジュール実行）
  - 直接実行用のパス調整処理を避けられ、PyInstaller でも安定しやすい
- 互換: リポジトリ直下の `main.py`（`iRIC_DataScope.app.main()` を呼ぶ薄いラッパ）
