# CGNS / IPRO → CSV 変換 要件まとめ

## ゴール
- `.ipro`（iRIC プロジェクト）または `.cgn` を直接入力として受け取り、既存ツール群が期待する `Result_*.csv` 群を自動生成して渡す。
- 最初のスコープは「ノード座標系データのみ」（セル中心などは扱わない）。

## 既存スクリプトの機能（sandbox/cgns_to_csv.py）
- 入力解決:
  - 単一 `.cgn` → そのまま使用。
  - `.ipro` → ZIP 内から対象 CGNS を特定（指定名優先、単一 *.cgn、複数なら最大サイズ）し、一時展開。
  - ディレクトリ → 指定名ヒット or *.cgn が1個ならそれ。
- CGNS 読み取り:
  - HDF5 を `h5py` でオープン。
  - `ZoneIterativeData/FlowSolutionPointers` からステップ一覧。
  - 座標: `GridCoordinates/CoordinateX`, `CoordinateY`。形状が一致するもののみ対象。
  - ベース列: I, J (1 始まり), X, Y。F オーダーを既定、C オーダーもオプション。
  - 変数: FlowSolution 配下のキーから選択（未指定なら全て）。座標と同形状のみ出力。
  - 時刻: `BaseIterativeData/TimeValues` を優先的に参照。なければ 0。
- 出力:
  - ステップごと `Result_{n}.csv`。先頭2行は iRIC 互換 (`iRIC output t = ...`, `imax,jmax`)。
  - UTF-8 BOM 付き。

## これから実装する変換モジュール（案）
- 配置: `iRIC_DataScope/common/` に新規モジュール（例: `cgns_converter.py`）。
- 公開関数（イメージ）:
  ```python
  def convert_iric_project(
      input_path: Path,          # .ipro / .cgn / ディレクトリ
      output_dir: Path,          # CSV を出す先
      case_name: str = "Case1.cgn",
      zone_path: str = "iRIC/iRICZone",
      vars_keep: list[str] | None = None,
      step_from: int = 1,
      step_to: int | None = None,
      step_skip: int = 1,
      fortran_order: bool = True,
  ) -> Path:
      """
      CSV を output_dir に生成し、そのパスを返す。
      """
  ```
- 動作:
  1) 入力解決（`.ipro` 展開 or `.cgn` 直接）。`.ipro` 展開は一時ディレクトリで処理し、終了時にクリーンアップ。
  2) `export_iric_like_csv` 相当の処理を実行。サポートするのは座標と同形状のノード変数のみ。
  3) `output_dir` を作成し、`Result_{step}.csv` を出力。関数の戻り値は `output_dir`。
  4) ロギングで進行とスキップ理由を出力（座標と形状が合わない変数はスキップと明示）。
- エラーハンドリング:
  - 入力が不正、対象 CGNS が見つからない場合は例外。
  - HDF5 読み取りエラーは例外として上位に通知。

## ランチャー統合（app.py）のイメージ
- 入力 UI で `.ipro` / `.cgn` / 既存の CSV フォルダを受け付けるよう拡張（現状はフォルダのみ）。
- 各機能起動前に、入力が `.ipro` or `.cgn` の場合は変換を走らせる:
  - 変換先は `output` 下にサブフォルダを自動生成（例: `output/converted_<stem>/`）し、そのパスを各 GUI に渡す。
  - 既に同サブフォルダに CSV があれば再利用 or 上書き（ポリシー要検討）。
- 既存ツール（左右岸/横断/時系列）は「CSV フォルダ」を入力とみなすため、変換後フォルダを自動セットしてから GUI を開く。

## 依存ライブラリ
- 追加: `h5py` （HDF5 読み取り用）。`requirements.txt` / `pyproject.toml` への追記が必要。

## 方針更新（未決だった項目）
- 出力先再利用: `output_dir` に既存 CSV がある場合は上書き前に警告ダイアログを出す。
- データ対象:
  - 境界データは扱わない。
  - ノード中心/セル中心のいずれか片方しか無い場合は存在する側を出力。
  - 両方ある場合は、将来的に UI/オプションでどちらを使うか選択できるようにする（当面の実装は決め打ち or 片方のみでも可）。
- ゾーン名・ケース名: 当面デフォルト固定（Case1.cgn, iRIC/iRICZone）だが、要望があれば UI から指定可能にする余地を残す。
- 変換進捗/失敗通知: ダイアログでユーザに通知（ログも併用）。
