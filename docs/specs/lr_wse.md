# 左右岸最大水位整理（`iRIC_DataScope/lr_wse`）現状実装まとめ

## 目的
プロジェクトフォルダ / `.ipro` / iRIC 出力 CSV（`Result_*.csv`）から、設定に基づいて左右岸等の集計を行い、Excel に整理して出力する。

## 入力/出力
- 入力: プロジェクトフォルダ / `.ipro` / `Result_*.csv` が格納されたフォルダ
- 設定: 設定 CSV（GUI から選択）
- 出力: Excel（既定 `summary.xlsx`）

## 処理の流れ（概要）
- `iRIC_DataScope/lr_wse/config.py`
  - `load_setting()` で設定 CSV を読み込み
- `iRIC_DataScope/lr_wse/extractor.py`
  - CSVフォルダ入力: `extract_all()` で中間 CSV を生成
  - プロジェクトフォルダ / `.ipro`: CGNS を直接読み込んで中間 CSV を生成
  - **時刻 `t=0` のデータは抽出対象から除外**
- `iRIC_DataScope/lr_wse/writer.py`
  - `combine_to_excel()` で中間 CSV を統合して Excel を出力

## エントリポイント
- GUI: `iRIC_DataScope/lr_wse/gui.py`（ランチャーから `LrWseGUI` を起動）
- 処理本体: `iRIC_DataScope/lr_wse/main.py:run_lr_wse()`
