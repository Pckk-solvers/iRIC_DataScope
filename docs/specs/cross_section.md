# 横断重ね合わせ図作成（`iRIC_DataScope/cross_section`）現状実装まとめ

## 目的
iRIC 出力 CSV（`Result_*.csv`）から、横断データを読み込み、標高/水位等の重ね合わせ図を Excel に出力する。

## 入力/出力
- 入力: `Result_*.csv` が格納されたフォルダ
- 出力: Excel（既定 `profile_charts.xlsx`）

## 前提（入力 CSV の列）
現行の実装は `iRIC_DataScope/common/csv_reader.py:read_iric_csv()` を通して CSV を読み込み、
以下の列が存在する想定です（名称は iRIC 側の出力に依存します）。

- `elevation(m)`
- `watersurfaceelevation(m)`

## 処理の流れ（概要）
- `iRIC_DataScope/cross_section/data_loader.py`
  - CSV を読み込み、Profile ID（`I`）とソートキー（`J`）でグループ化
  - 座標差分から累積距離を計算して、グラフ用の最小 DataFrame を作成
- `iRIC_DataScope/cross_section/excel_utils.py`
  - 複数断面/複数時刻の折れ線グラフを Excel に出力
- `iRIC_DataScope/cross_section/plot_core.py`
  - 読み込み〜出力をまとめて実行する薄いオーケストレーション

## エントリポイント
- GUI: `iRIC_DataScope/cross_section/gui.py`（ランチャーから `ProfilePlotGUI` を起動）
- 処理本体: `iRIC_DataScope/cross_section/plot_main.py:plot_main()`

