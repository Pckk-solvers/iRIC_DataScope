# xy_value_map リファクタリングメモ（2025-12-23）  

現状: `gui.py` が肥大化。`plot.py` へ描画処理を分離済み。  
目的: 責務分離と可読性向上。機能変更は極力なし。

## 優先度高
- ~~出力オプションのデータクラス化 (`options.py`)~~ 完了
  - タイトル文字列・カラーバー名・pad_inches・タイトル/目盛/CBラベルのフォントサイズ・表示フラグ類をまとめる。
  - GUI ↔ 描画/出力の受け渡しをこの型に一本化。

- ~~GUI構築とイベント処理の分離（UIレイアウトの切り出し）~~ 一部完了
  - フレーム/ウィジェット生成のうち「出力オプション」を `ui.py` に分離（実装完了）。
  - イベントハンドラ・状態更新は引き続き `gui.py` に残っており、さらなる分離余地あり。
  - 次の詳細案：
    - `iRIC_DataScope/xy_value_map/controller.py` を追加
    - `XYValueMapController` を作り、`_on_*` 系（ROI操作・ステップ変更・出力オプション変更・プレビュー更新・スケール計算トリガ）を集約
    - `gui.py` はイベントバインドのみ保持し、`self.controller = XYValueMapController(self)` を持たせて各ハンドラを委譲
    - キャッシュ/非同期処理（プレビューキャッシュ・グローバルスケール計算）は Controller 側で管理

## 優先度中
- データ準備ロジックの分離 (`data.py`/`model.py`)
  - DataSource とのやりとり、ROI 補間、スケール計算、プレビュー用ダウンサンプリングを集約。
  - GUI は「描画用データを取得する」だけにする。

- キャッシュと非同期処理の分離 (`cache.py`/`tasks.py`)
  - `_preview_frame_cache` やグローバルスケール計算スレッド管理を別モジュールに。

- スタイル・フォント設定 (`style.py`)
  - 日本語フォント設定、デフォルトフォントサイズ、カラーマップなどを共有設定としてまとめる。

## pytest テスト計画（追加）
- pytest土台: `tests/` + `conftest.py`（Tk rootフィクスチャ、matplotlib未導入時はskip対応）
- GUI起動スモーク: `XYValueMapGUI._start_initial_load` をmonkeypatchで無効化し、生成→update→破棄で落ちないことを確認
- 出力オプション既定値: `_get_output_options()` の値が期待通りか簡易検証
- 最小描画テスト: `render_xy_value_map` にダミーグリッドを渡し、例外が出ないことを確認（matplotlibがなければskip）
  - 実装済み: `tests/conftest.py`, `tests/test_gui_smoke.py`, `tests/test_plot_render.py`

## メモ
- カラーバーラベルが出力に出ない現象は原因調査中。リファクタ完了後に再度切り分け。
- ドキュメント更新も上記分割後に対応する。
