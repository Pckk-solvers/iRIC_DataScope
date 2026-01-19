# リファクタリング方針メモ（2026-01-19 / ruff 対応）

## 目的
- `ruff` の指摘を整理し、影響の小さいものから段階的に修正する。
- **E402（遅延 import）** は動作影響があるため、方針を明確にしたうえで扱う。

## 対象範囲
- `iRIC_DataScope/` 配下のみを対象とする。
- `sandbox/` は解析対象外（検証用スクリプトのため）。

## 方針
1. **安全に直せるものは修正**
   - 未使用変数/未使用 import（`F841/F401`）は削除で対応。
   - 変数名の曖昧さ（`E741`）は `I/J` → `ii/jj` などに変更。

2. **E402（遅延 import）は解消**
   - 起動速度よりも安定性を優先し、**遅延 import はなくす方針**とする。
   - すべての import をファイル先頭へ移動して `E402` を解消する。
   - PyInstaller の同梱漏れリスクを下げる目的。

3. **--unsafe-fixes は使わない**
   - 動作影響のリスクが高いため。
   - 必要なら個別に修正方針を決めて手で対応。

## 具体対応（予定）
- `iRIC_DataScope/common/cgns_reader.py`
  - `I, J` の変数名を `ii, jj` に変更（列名 `"I"`, `"J"` は維持）。
- `iRIC_DataScope/time_series/excel_writer.py`
  - `workbook` の未使用変数を削除。
- `iRIC_DataScope/xy_value_map/edit_canvas.py`
  - `ux`, `half_w` の未使用変数を削除。
- `iRIC_DataScope/xy_value_map/gui.py`
  - `width` の未使用変数を削除。
- `iRIC_DataScope/cross_section/gui.py`, `iRIC_DataScope/lr_wse/gui.py`
  - import を先頭へ移動して E402 を解消。

## 進め方
- まず `uv run ruff check iRIC_DataScope` を基準にして差分修正。
- その後、必要なら `ruff` 設定（`pyproject.toml`）に対象/除外を明記する。
