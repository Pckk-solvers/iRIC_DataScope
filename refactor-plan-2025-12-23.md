# xy_value_map リファクタリングメモ（2025-12-23）  

現状: `gui.py` が肥大化。`plot.py` へ描画処理を分離済み。  
目的: 責務分離と可読性向上。機能変更は極力なし。

## 優先度高
- ~~出力オプションのデータクラス化 (`options.py`)~~ 完了
  - タイトル文字列・カラーバー名・pad_inches・タイトル/目盛/CBラベルのフォントサイズ・表示フラグ類をまとめる。
  - GUI ↔ 描画/出力の受け渡しをこの型に一本化。

- ~~GUI構築とイベント処理の分離（UIレイアウトの切り出し）~~ 一部完了
  - フレーム/ウィジェット生成のうち「出力オプション」を `ui.py` に分離（実装完了）。
  - ~~イベントハンドラ・状態更新は引き続き `gui.py` に残っており、さらなる分離余地あり。~~ 完了
  - 実装内容：
    - `iRIC_DataScope/xy_value_map/controller.py` を追加
    - `XYValueMapController` に `_on_*` 系（ROI操作・ステップ変更・出力オプション変更・プレビュー更新・スケール計算トリガ）を集約
    - `gui.py` はイベントバインドのみ保持し、`self.controller = XYValueMapController(self)` から各ハンドラへ委譲
    - キャッシュ/非同期処理（プレビューキャッシュ・グローバルスケール計算）は引き続き `gui.py` に残存

## 優先度中
- ~~データ準備ロジックの分離 (`data.py`/`model.py`)~~ 完了
  - `iRIC_DataScope/xy_value_map/data_prep.py` を追加。
  - ROI 切り出し・プレビュー用解像度調整・編集用グリッド作成・ROI min/max 計算を集約。
  - GUI は data_prep の関数を呼ぶだけに整理。

- ~~キャッシュと非同期処理の分離 (`cache.py`/`tasks.py`)~~ 完了
  - `iRIC_DataScope/xy_value_map/cache.py` に `PreviewFrameCache` を追加。
  - `iRIC_DataScope/xy_value_map/tasks.py` に `GlobalScaleWorker` を追加。
  - GUI は cache/tasks を利用してプレビューキャッシュと global スケール計算を管理。

- ~~スタイル・フォント設定 (`style.py`)~~ 完了
  - `iRIC_DataScope/xy_value_map/style.py` を追加。
  - 日本語フォント設定、デフォルトフォントサイズ、編集用カラーマップを集約。
  - `plot.py`/`gui.py`/`options.py`/テストで共通定義を参照。

## 次の分割候補
1. `preview_renderer.py`
   - ~~プレビュー描画一式（`_draw_preview` / `_draw_empty_preview` / `_apply_plot_options` など）を分離。~~ 完了
   - ~~分割前に pytest 追加（描画関数の入出力・Axes設定・タイトル/カラーバー反映の確認）。~~ 実装済み
   - 実装: `iRIC_DataScope/xy_value_map/preview_renderer.py` と `tests/xy_value_map/test_preview_renderer.py`
2. `edit_canvas.py`
   - ~~編集キャンバス描画・座標変換（`_render_edit_background` / `_update_edit_roi_artists` / `_edit_*` 系）を分離。~~ 完了
   - ~~分割前に pytest 追加（座標変換・ROIハンドル位置計算のスナップショット的検証）。~~ 実装済み
   - 実装: `iRIC_DataScope/xy_value_map/edit_canvas.py` と `tests/xy_value_map/test_edit_canvas.py`
3. `roi_interaction.py`
   - ~~ROIドラッグ/回転/サイズ変更のロジックを集約（controller からさらに切り出し）。~~ 完了
   - ~~分割前に pytest 追加（ドラッグ入力に対するROI更新の数値検証）。~~ 実装済み
   - 実装: `iRIC_DataScope/xy_value_map/roi_interaction.py` と `tests/xy_value_map/test_roi_interaction.py`
4. `export_runner.py`
   - ~~`_run` / `_run_single_step` のバリデーション・進捗・出力処理を分離。~~ 完了
   - ~~分割前に pytest 追加（引数バリデーション、global/ manual 分岐、エラー時メッセージ分岐）。~~ 実装済み
   - 実装: `iRIC_DataScope/xy_value_map/export_runner.py` と `tests/xy_value_map/test_export_runner.py`
5. `state.py`
   - ~~GUI状態（ROI/スケール/解像度/プレビュー状態など）をデータクラス化して集約。~~ 完了
   - ~~分割前に pytest 追加（初期値・更新時の整合性を確認）。~~ 実装済み
   - 実装: `iRIC_DataScope/xy_value_map/state.py` と `tests/xy_value_map/test_state.py`

## pytest テスト計画（追加）
- pytest土台: `tests/` + `conftest.py`（Tk rootフィクスチャ、matplotlib未導入時はskip対応）
- GUI起動スモーク: `XYValueMapGUI._start_initial_load` をmonkeypatchで無効化し、生成→update→破棄で落ちないことを確認
- 出力オプション既定値: `_get_output_options()` の値が期待通りか簡易検証
- 最小描画テスト: `render_xy_value_map` にダミーグリッドを渡し、例外が出ないことを確認（matplotlibがなければskip）
  - 実装済み: `tests/conftest.py`, `tests/test_gui_smoke.py`, `tests/test_plot_render.py`
- 状態管理データクラス: 初期値と更新反映を検証
  - 実装済み: `tests/xy_value_map/test_state.py`

## メモ
- ドキュメント更新も上記分割後に対応する。
