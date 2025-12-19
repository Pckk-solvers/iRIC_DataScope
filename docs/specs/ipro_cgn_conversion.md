# CGNS / IPRO → CSV 変換（現状実装まとめ）

## ゴール
- **プロジェクトフォルダ / `.ipro`**（iRIC の出力一式）を入力として受け取り、既存ツール群が期待する `Result_*.csv` 群を自動生成して渡す。
- 最初のスコープは「ノード座標系データのみ」（セル中心などは扱わない）。

## 現状の実装
### モジュール構成
- `iRIC_DataScope/common/cgns_reader.py`
  - `.ipro`/フォルダ入力から CGNS を解決（`.ipro` は ZIP から一時展開）
  - CGNS(HDF5) を読み込み、ステップ単位で `pandas.DataFrame` を生成
  - 公開 API:
    - `resolve_case_cgn(input_path, case_name)`
    - `iter_iric_step_frames(cgn_path, ...)`
    - `iter_iric_step_frames_from_input(input_path, case_name=..., ...)`
- `iRIC_DataScope/common/iric_project.py`
  - 入力フォルダが「プロジェクトフォルダ」か「CSVフォルダ」かを判定
  - `Solution*.cgn` の列挙・並び替えロジックを共通化
- `iRIC_DataScope/common/iric_csv_writer.py`
  - `IricStepFrame` を iRIC 互換の `Result_*.csv` に書き出し
  - 公開 API:
    - `write_iric_result_csv(frame, out_path)`
    - `export_iric_result_csv(frames, out_dir, filename_template=...)`
- `iRIC_DataScope/common/cgns_converter.py`
  - 従来の「入力→CSV出力」の入口を維持するラッパ
  - `ConversionOptions` と `convert_iric_project()` を提供

### 変換の仕様（CSV出力）
- ステップは `ZoneIterativeData/FlowSolutionPointers` を基準に `Result_{step}.csv` を生成。
- `Solution*.cgn` が存在する場合は **1ファイル=1ステップ** として扱い、ファイル名の番号を `Result_{step}.csv` に反映する。
- 時刻は `BaseIterativeData/TimeValues` を優先して読み込み（無い場合は 0）。
- 座標は `GridCoordinates/CoordinateX` / `CoordinateY` を使用。
- 変数は FlowSolution 配下のキーを走査し、以下のみ出力:
  - Dataset 直下に配列があるもの
  - Group 配下の `" data"` に配列があるもの
  - かつ座標と同形状（ノード座標と同shape）のもの
- 出力 CSV は iRIC 互換フォーマット:
  - 1行目: `iRIC output t = ...`
  - 2行目: `imax,jmax`
  - 3行目以降: ヘッダ + データ（I,J,X,Y,+スカラー）

## ランチャー統合（app.py）のイメージ
（現在は実装済み）
- 入力 UI は「フォルダ / `.ipro`」を受け付ける。
- 各機能起動前に、入力が **プロジェクトフォルダ / `.ipro`** の場合は CSV 変換を実行し、変換後フォルダを各 GUI の入力として渡す。
  - 変換先: 出力フォルダ配下の `converted_<入力名>/`
  - 既存 CSV がある場合: 上書き確認ダイアログ（いいえ→既存を再利用）
  - 変換中: 進捗ウィンドウ表示、完了/失敗: ダイアログ表示

## 依存ライブラリ
- `h5py` （HDF5 読み取り用）
- `numpy`, `pandas`（データ処理）

## 制限と今後の拡張
- 境界データは扱わない（FlowSolution 以外は対象外）。
- セル中心データ（CellCenter）は現状「座標と同shapeのもののみ出力」なので、セル中心で shape が異なる変数はスキップされる。
  - 将来的に「CellCenter の座標生成」「Vertex/Cell の選択 UI」を追加して対応する。
- ゾーン名・ケース名は当面デフォルト固定（Case1.cgn, iRIC/iRICZone）。要望があれば UI から指定できるようにする余地を残す。

## 参考（試作スクリプト）
- `sandbox/cgns_to_csv.py` は試験用のスクリプト。現行アプリでは `common/` 配下のモジュールを使用する。
