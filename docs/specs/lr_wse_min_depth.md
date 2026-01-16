# lr_wse: 最小水深入力 追加検討メモ

## 目的
GUI に「最小水深」を追加し、入力データの `depth(m)` 列が
指定値と一致しているかどうかを全時系列で検出する。
一致した場合はデータを無効扱いとする。

## 用語
- 最小水深: GUI で入力する float 値
- 無効データ: 出力対象から除外、またはエラー扱いとする対象

## 現状構成（関係箇所）
- GUI: `iRIC_DataScope/lr_wse/gui.py`
  - 入力値を `run_lr_wse()` に渡す
- 処理本体: `iRIC_DataScope/lr_wse/main.py`
  - `run_lr_wse()` → `_extract_input_to_temp()` → `extract_all()` / `extract_all_from_frames()`
- CSV 読込: `iRIC_DataScope/lr_wse/reader.py`
  - `read_iric_csv()` で DataFrame を生成
- 抽出: `iRIC_DataScope/lr_wse/extractor.py`
  - `extract_all()` / `extract_all_from_frames()` で各時系列を処理

## 要件
### 入力
- GUI に「最小水深」入力欄を追加する。
- 値は float を受け付ける（空欄時は無効判定を行わない）。

### 判定
- 入力データの `depth(m)` 列を参照する。
- 全ての時系列データ（CSV フォルダの各ファイル、または frame 群）で、
  `depth(m)` が GUI 入力値と一致するかどうかを検出する。
- 判定条件:
  - **GUI入力値以下**（`depth(m) <= min_depth`）。
  - NaN は一致扱いにしない。

### 無効扱い
- 一致が検出された場合、データを「無効」として扱う。
- **左右岸別々に判定**し、該当する岸の出力のみ無効化する。
- Excel 出力では、該当行の以下の値を **"取得不可"** に置換する。
  - `L_watersurfaceelevation(m)` / `L_elevation(m)`
  - `R_watersurfaceelevation(m)` / `R_elevation(m)`

## 追加パラメータ案
- `run_lr_wse(..., min_depth: Optional[float] = None)`
- `extract_all(..., min_depth: Optional[float] = None)`
- `extract_all_from_frames(..., min_depth: Optional[float] = None)`

## 実装方針
- GUI:
  - 既存の欠損値欄の近くに「最小水深」入力欄を追加。
  - 空欄なら `None` を渡す。
- 解析:
  - `extract_all()` / `extract_all_from_frames()` のループ冒頭で
    `depth(m)` 列の一致チェックを行う。
  - 検出時は左右岸別に "取得不可" を設定する。

## エラー条件
- `depth(m)` 列が存在しない場合はエラーとする。
