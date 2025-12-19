# 時系列データ抽出（`iRIC_DataScope/time_series`）現状実装まとめ

## 目的
プロジェクトフォルダ / `.ipro` / iRIC 出力 CSV（`Result_*.csv`）を全ステップ走査し、指定した格子点（`I,J`）における指定変数の時系列を抽出して Excel に出力する。

## 入力/出力
- 入力: プロジェクトフォルダ / `.ipro` / `Result_*.csv` が格納されたフォルダ
- 入力（GUIで指定）:
  - 抽出対象の格子点（`I,J` の組）
  - 抽出対象の変数名（列名）
- 出力: Excel（GUI から指定）

## 処理の流れ（概要）
- `iRIC_DataScope/time_series/processor.py`
  - CSVフォルダ: `Result_*.csv` を列挙して時系列 DataFrame を作成
  - プロジェクトフォルダ / `.ipro`: CGNS を直接読み込んで時系列 DataFrame を作成
- `iRIC_DataScope/time_series/excel_writer.py`
  - 時系列 DataFrame を Excel に出力

## エントリポイント
- GUI: `iRIC_DataScope/time_series/gui_components.py`（ランチャーから起動）
- まとめ起動: `iRIC_DataScope/time_series/main.py`
