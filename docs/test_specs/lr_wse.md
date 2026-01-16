# lr_wse テスト仕様メモ（設定/読込）

## 目的
iRIC_DataScope/lr_wse の設定CSV読込とCSVパース処理の現状仕様を整理し、
pytest のテスト対象を明確化する。

## 対象モジュール
- iRIC_DataScope/lr_wse/config.py
  - load_setting(config_file)
- iRIC_DataScope/lr_wse/reader.py
  - extract_time(first_line)
  - read_iric_csv(file_path, skip_rows=2, encoding="utf-8")

## 現状仕様（コード準拠）
### 設定CSV読込: load_setting
- ファイルが存在しない場合は FileNotFoundError を送出する。
- UTF-8 で pandas.read_csv する。
- KP 列がある場合のみ数値化を試みる。
  - まず pd.to_numeric(errors="raise") で全件数値変換を試す。
  - 失敗した場合は KP を文字列化し末尾の "k"/"K" を削除してから
    pd.to_numeric(errors="coerce") で変換する。
  - 変換不能な値は NaN になる。
- LI/LJ/RI/RJ など他列の型変換や必須列検証は行わない。

### 入力CSV読込: read_iric_csv / extract_time
- 1行目に "iRIC output t =" を含む場合は "=" の右側を float に変換する。
  - float 変換に失敗した場合は None を返す。
  - 文字列が含まれていない場合も None を返す。
- CSV 本体は pandas.read_csv(file_path, skiprows=2, encoding=...) で読み込む。
  - 既定では 1行目=時刻、2行目=説明行、3行目=ヘッダを想定。

## テスト観点
### load_setting
- ファイル不存在時に FileNotFoundError。
- KP が数値のみの場合は数値型として読める。
- KP に末尾 "k"/"K" が付く場合に数値化される。
- KP に数値化できない値が混在する場合は NaN になる。

### extract_time
- 正常な形式 ("iRIC output t = 1.5") から 1.5 を取得。
- "iRIC output t = abc" など不正値は None。
- "iRIC output t =" を含まない場合は None。

### read_iric_csv
- 1行目の時刻値が extract_time と同じ結果になる。
- skiprows=2 の前提で 3行目ヘッダが正しくパースされる。

## テスト実装メモ
- テストデータは tmp_path で一時CSVを生成。
- pandas の dtype 判定は pd.api.types.is_numeric_dtype を使用。
- NaN 判定は pandas.isna を使用。
