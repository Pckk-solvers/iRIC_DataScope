# 断面集計ツール 実装設計

## 1. 目的

側線SHPで指定した断面ごとに、iRIC計算結果CGNSのノード値を集計し、断面ごとの時系列とピーク時刻をCSVで出力する。

初期実装では、以下に絞る。

* 入力CGNS: `FlowSolutionN` のノード値
* 対象変数: `watersurfaceelevation(m)` / `depth(m)`
* 側線SHP: `LineString`
* 出力: CSV 3種
* 出力: 断面ごとの平均水位グラフ PNG
* UI: ランチャーから新機能ウィンドウを起動
* CLI: 実装確認とバッチ処理用に追加

## 2. 入力と出力

### 2.1 入力

```text
CGNS:
  .cgn / .ipro / プロジェクトフォルダ

側線SHP:
  .shp
  .shx
  .dbf
  .prj は任意

出力フォルダ:
  既存ランチャーの出力フォルダを使う
```

CGNS と側線SHPは同じ平面座標系である前提にする。座標変換は初期実装では行わない。

### 2.2 出力

```text
section_node_map.csv
section_timeseries.csv
section_peak_summary.csv
section_graphs/
  SEC001.png
  SEC002.png
  ...
```

CSV は当面 `utf-8-sig` で出力する。

グラフは `section_graphs` 配下に、断面ごとの PNG として出力する。

## 3. 画面設計

### 3.1 ランチャー

`iRIC_DataScope/app.py` の機能カードに「断面集計」を追加する。

追加するカード:

```text
断面集計
側線SHPに沿って水位・水深を断面別に集計します。
出力: 断面時系列 CSV / ピーク CSV
```

ランチャーから渡す値:

```text
input_path: 既存の入力パス
output_dir: 既存の出力フォルダ
```

### 3.2 断面集計ウィンドウ

新規 Toplevel として実装する。

主な入力項目:

```text
側線SHP
depth_threshold
sample_interval
断面IDフィールド
断面名フィールド
```

初期値:

```text
depth_threshold = 0.01
sample_interval = 自動
断面IDフィールド = 自動
断面名フィールド = 自動
```

ボタン:

```text
側線SHPを選択
実行
```

実行前の簡易表示:

```text
CGNS入力種別
側線 feature 数
出力予定ファイル
```

## 4. CLI設計

GUI実装と同じ `processor.py` を呼ぶ CLI を追加する。実装中のPDCAを速く回すため、最初はCLIを先に動かせる状態にする。

コマンド名は以下を想定する。

```text
iric-datascope-section
```

モジュール実行もできるようにする。

```bash
uv run python -m iRIC_DataScope.section_analyze --help
```

### 4.1 実行例

`Case1-1.cgn` と検証用側線SHPで実行する例。

```bash
uv run python -m iRIC_DataScope.section_analyze ^
  --input Case1-1.cgn ^
  --sections tests/fixtures/section_analyze/section_lines_sample.shp ^
  --output output/section_analyze_case1 ^
  --depth-threshold 0.01
```

PowerShell では以下のように実行する。

```powershell
uv run python -m iRIC_DataScope.section_analyze `
  --input Case1-1.cgn `
  --sections tests/fixtures/section_analyze/section_lines_sample.shp `
  --output output/section_analyze_case1 `
  --depth-threshold 0.01
```

### 4.2 引数

必須:

```text
--input / -i
  CGNS / .ipro / プロジェクトフォルダ

--sections / -s
  側線SHP

--output / -o
  出力フォルダ
```

任意:

```text
--depth-threshold
  有効点判定に使う水深下限。既定値 0.01

--sample-interval
  側線サンプリング間隔。未指定なら自動推定

--section-id-field
  断面IDとして使う属性フィールド。未指定なら自動検出

--section-name-field
  断面名として使う属性フィールド。未指定なら自動検出

--overwrite
  既存CSVがある場合に上書きする

--dry-run
  CGNSとSHPを読み、採用ノード数などの概要だけ表示してCSVは出さない

--limit-steps
  開発確認用。先頭Nステップだけ処理する

--column-names
  CSV列名を切り替える。standard は内部向け英語名、river は河川業務向け日本語名

--shared-y-scale
  グラフY軸を全断面で共通スケールにする。未指定時は断面ごとの最適スケール
```

### 4.3 CLIの終了コード

```text
0  正常終了
1  入力やパラメータのエラー
2  処理中の予期しないエラー
```

### 4.4 CLIの出力

標準出力には、PDCAで必要な概要だけを出す。

```text
Input: Case1-1.cgn
Sections: sandbox/section_lines_sample.shp
Sections loaded: 5
Sample interval: auto -> 12.34
Mapped nodes: 365
Steps: 110
Wrote:
  output/section_analyze_case1/section_node_map.csv
  output/section_analyze_case1/section_timeseries.csv
  output/section_analyze_case1/section_peak_summary.csv
```

エラー詳細は例外メッセージを表示し、将来的にはログファイル出力を追加する。

## 5. ソース追加場所

新規パッケージを追加する。

```text
iRIC_DataScope/
  section_analyze/
    __init__.py
    __main__.py
    cli.py
    launcher.py
    gui.py
    models.py
    cgn_loader.py
    shp_reader.py
    sampler.py
    processor.py
    writer.py
    plotter.py
```

### 5.1 __main__.py

`python -m iRIC_DataScope.section_analyze` の入口。

```python
from .cli import main

raise SystemExit(main())
```

### 5.2 cli.py

`argparse` でCLI引数を受け取り、`processor.run_section_analysis()` を呼ぶ。

責務:

* 引数のパース
* Path の解決
* options の構築
* dry-run / limit-steps の反映
* 終了コードの制御

`processor.py` にCLI依存を入れない。

### 5.3 launcher.py

ランチャーから呼ぶ薄い入口。

```python
def launch_from_launcher(master, *, input_path: Path, output_dir: Path):
    return SectionAnalyzeGUI(master, input_path=input_path, output_dir=output_dir)
```

### 5.4 gui.py

Tkinter/ttk の Toplevel。

責務:

* 側線SHP選択
* パラメータ入力
* 実行ボタン
* エラー表示
* 完了表示

処理本体は `processor.py` に寄せ、GUIには集計ロジックを書かない。

### 5.5 models.py

処理内のデータ構造をまとめる。

候補:

```python
SectionLine
SectionNode
SectionStats
SectionAnalyzeOptions
SectionAnalyzeResult
```

`SectionAnalyzeOptions` には CLI / GUI 共通の設定を持たせる。

```python
depth_threshold: float
sample_interval: float | None
section_id_field: str | None
section_name_field: str | None
overwrite: bool
limit_steps: int | None
dry_run: bool
column_names: Literal["standard", "river"]
shared_y_scale: bool
```

### 5.6 cgn_loader.py

CGNSから断面集計に必要なデータを取り出す。

既存の `DataSource` を優先利用する。

使用方針:

```text
DataSource.from_input(input_path, grid_location="node")
iter_frames_with_columns(["watersurfaceelevation(m)", "depth(m)"])
```

初期実装ではセル中心値を読まない。

### 5.7 shp_reader.py

側線SHPを読む。

依存候補:

```text
pyshp >= 2.3
```

理由:

* pure Python で軽い
* LineString SHP の読み取りには十分
* GeoPandas / Fiona より配布影響が小さい

初期実装では `LineString` のみ受け付ける。`MultiLineString` はエラーにする。

属性フィールドは以下の順で自動検出する。

```text
section_id: section_id, ID, id, SecNo, sec_no
section_name: section_name, Name, name, 断面名
```

見つからない場合:

```text
section_id = SEC001, SEC002, ...
section_name = section_id
```

### 5.8 sampler.py

側線と格子ノードの対応付けを行う。

処理:

```text
1. CGNSノード座標から KDTree を作る
2. 側線を sample_interval ごとにサンプリングする
3. 各サンプル点に対して最近傍ノードを検索する
4. 同一 section 内で重複 I/J を除外する
5. 採用ノードを line_dist 順に並べる
```

KDTree は既存依存の `scipy.spatial.cKDTree` を使う。

`sample_interval` が未指定の場合は、CGNSノードの代表格子間隔から自動推定する。

初期案:

```text
隣接ノード距離の中央値 * 0.5
```

### 5.9 processor.py

処理全体をまとめる。

公開関数候補:

```python
def run_section_analysis(
    input_path: Path,
    section_shp_path: Path,
    output_dir: Path,
    options: SectionAnalyzeOptions,
) -> SectionAnalyzeResult:
    ...
```

処理順:

```text
1. CGNSノード座標を読む
2. 側線SHPを読む
3. 側線ごとの採用ノードを作る
4. section_node_map.csv を作る
5. 全ステップを走査する
6. 断面ごとに depth_threshold 以上の点だけで統計する
7. section_timeseries.csv を作る
8. mean_wse 最大ステップを抽出する
9. section_peak_summary.csv を作る
```

`dry_run=True` の場合は、SHP読み込み、CGNS座標読み込み、採用ノード作成まで行い、CSVは出力しない。

`limit_steps` が指定された場合は、時系列処理を先頭Nステップに制限する。`section_node_map.csv` は制限に関係なく出力する。

### 5.10 writer.py

CSV出力を担当する。

GUIや processor に `to_csv` の細かい設定を書かない。

CSV列名は `column_names` に応じて writer でだけ変換する。内部処理のDataFrame列名は英語名のまま維持する。

`river` 指定時の主な列名は以下。

```text
section_id -> 断面ID
section_name -> 断面名
source_feature_id -> 側線FID
line_dist -> 断面距離
nearest_dist -> 最近傍距離
step -> ステップ
time -> 時刻
node_count -> 採用点数
valid_node_count -> 有効点数
depth_threshold -> 有効水深下限
mean_wse -> 平均水位
mean_depth -> 平均水深
peak_step -> 平均水位最大ステップ
peak_time -> 平均水位最大時刻
peak_mean_wse -> 最大平均水位
depth_at_peak_mean_wse -> 最大平均水位時平均水深
```

### 5.11 plotter.py

断面ごとの平均水位グラフ画像を作る。

責務:

* `section_timeseries.csv` 相当の時系列データから PNG を出力する
* 断面ごとに1枚ずつ描画する
* 既定は断面ごとの Y 軸範囲で描画する
* オプションで全断面共通の Y 軸範囲へ切り替えられるようにする
* `mean_wse` の最大点を強調表示する
* 時刻の目盛りは整数表示に整える
* 欠損値は線をつながず、その区間は空ける
* 折れ線の平滑化はしない。計算結果をそのまま描く

CSV の出力と同じく、グラフの保存先や命名規則はここでまとめる。

## 6. 集計仕様

### 6.1 採用ノード

側線SHPごとに採用ノード一覧を作る。

採用条件:

```text
側線上のサンプル点に最も近いノード
```

`search_distance` は初期実装では設けない。

確認用に `nearest_dist` を出す。

### 6.2 統計量

各断面・各ステップで以下を計算する。

```text
node_count
valid_node_count
invalid_node_count
valid_ratio
mean_wse
mean_depth
max_wse
min_wse
max_depth
min_depth
```

有効点:

```text
depth(m) >= depth_threshold
```

有効点が 0 の場合、平均・最大・最小は空欄にする。

### 6.3 ピーク

断面ごとに `mean_wse` が最大のステップを採用する。

同値の場合は早い時刻を採用する。

### 6.4 グラフ出力

各断面について、`mean_wse` の時系列グラフを1枚ずつ出力する。

見た目の方針は以下。

```text
ファイル形式:
  PNG

ファイル名:
  断面IDベース。例: SEC001.png

描画対象:
  全ステップの mean_wse を折れ線で描く

見た目:
  折れ線は 1 本、落ち着いた単色で描く
  線上の最大点だけマーカー付きで強調する
  背景は白、補助線は薄いグレーにする
  断面ごとに色を変えない
  凡例は1要素のみ。最大点の説明が不要なら省略してよい
  余白は詰めすぎず、タイトルと軸ラベルが読み切れるサイズにする
  文字サイズはタイトル、軸ラベル、目盛りで役割を分けて固定する
  軸の枠線は強く出しすぎない
  画像は横長で、時系列の変化を追いやすい比率にする
  既定ではY軸を断面ごとに最適化する
  比較時のみ全断面共通のY軸スケールを使う

強調表示:
  mean_wse 最大点を丸印などで目立たせる
  必要なら注記で最大時刻と最大値を添える
  注記はグラフを隠さない位置に置く

軸:
  X軸 = 時刻
  Y軸 = 平均水位

Y軸スケール:
  既定は断面ごとの mean_wse から最小値と最大値を求める
  断面ごとの範囲に余白を足して描画する
  --shared-y-scale 指定時は全断面・全ステップの範囲へ切り替える
  外れ値がある場合に備えて、将来は分位点ベースへ切り替えられる余地を残す

時刻表示:
  実データの時刻値は保持しつつ、表示は整数目盛りに整える
  目盛りラベルの重なりが起きないように間引く
  必要なら主目盛りと副目盛りを分ける
  表示上の整数化は四捨五入ではなく、原則としてそのままの時刻系列に対する整数表記にする

レイアウト:
  断面名をタイトルに入れる
  補助線は薄く入れる
  凡例は1つにまとめる
  タイトルには断面IDも入れ、同じ断面名があっても識別できるようにする
  y軸は選択したスケールに余白を持たせ、最大点が枠に張り付かないようにする
  x軸の表示範囲は全ステップを含める
  ティックや注記が重なる場合は、ラベル数を減らして読みやすさを優先する
```

時刻を整数表示にする理由は、現状の時刻値が小数で長く、断面ごとの比較時に読みづらいため。

### 6.5 グラフの整え方の方針

見た目を崩さないための前提を、あらかじめ決めておく。

* 色は増やさない。基本は単一の折れ線と1つの強調点だけにする
* 文字は増やしすぎない。断面名、軸ラベル、必要なら最大点の注記に絞る
* 余白は削りすぎない。タイトル、軸ラベル、目盛りが詰まる図は避ける
* 時刻は小数表示を避ける。比較しやすさを優先して整数表記に寄せる
* 最大点の注記は毎回必須ではなく、図が混む場合は丸印だけでもよい
* 欠損がある場合は線を無理につながない
* 断面ごとに同じレイアウトを使い、図の見た目を揃える
* 既定は断面ごとにY軸最適化し、比較が必要な場合だけ共通Y軸を使う

## 7. テスト方針

追加場所:

```text
tests/section_analyze/
  test_cli.py
  test_shp_reader.py
  test_sampler.py
  test_processor_stats.py
```

優先してテストすること:

* 属性なしSHPで `SEC001` が付く
* CLIで必須引数が不足した場合に終了コード 1 になる
* CLIの `--dry-run` でCSVが出力されない
* 側線サンプリングで重複ノードが除外される
* `depth_threshold` 未満の点が統計から除外される
* `mean_wse` 最大ステップが抽出される

## 8. 依存追加

`pyproject.toml` の dependencies に以下を追加する想定。

```toml
"pyshp>=2.3.1"
```

`scipy` は既存依存に含まれるため、KDTree 用の追加は不要。

CLIコマンドをインストール後にも使えるように、`pyproject.toml` に script entry point を追加する。

```toml
[project.scripts]
iric-datascope-section = "iRIC_DataScope.section_analyze.cli:main"
```

## 9. 初期実装の対象外

* セル中心値 `cell_eta[m]` / `cell_h[m]` の集計
* `MultiLineString`
* 座標変換
* Excel出力
* GUIでの地図プレビュー
* `nearest_dist` による除外

## 10. グラフ仕様更新とUI拡張（2026-04-28）

次の改修で、`plotter.py` と `gui.py` / `cli.py` に以下を反映する。

### 10.1 `plotter.py` の更新方針

* Y軸:
  下端は開始側の値が読みやすい範囲にし、上端は最上位目盛で閉じる
* 外枠:
  上下左右のスパインを表示する
* グリッド:
  点線（`linestyle='--'`）に変更し、色は現状より濃くする
* 軸ラベル:
  `xlabel='時間[h]'`、`ylabel='水位[T.P.m]'` に固定
* 時刻変換:
  描画用データで `time_sec -> time_hour = time_sec / 3600.0`
* 最大点注記:
  文言は `Max` を使う（例: `Max 12.34 (t=1.5h)`）
* 横軸目盛:
  `x_tick_interval_hour` が指定された場合は固定刻みで主目盛を配置
  未指定時は自動目盛

### 10.2 オプション追加

`SectionAnalyzeOptions` に次を追加する想定。

* `x_tick_interval_hour: float | None`
  * `None`: 自動目盛
  * 指定値あり: 指定時間刻みで主目盛

### 10.3 GUI拡張方針

`section_analyze/gui.py` の設定欄に次を追加する。

* `横軸目盛間隔[h]` 入力欄（空欄で自動）
* `断面IDフィールド` / `断面名フィールド` は
  SHP読み込み後の属性候補を選択できるUIへ拡張
* タイトル調整欄（次段実装）
  * 表示ON/OFF
  * テンプレート文字列
  * ID/名称の表示モード

### 10.4 CLI拡張方針

`section_analyze/cli.py` に以下を追加する。

* `--x-tick-interval-hour`
  * 例: `--x-tick-interval-hour 0.5`

### 10.5 後方互換

* 既定挙動は現行と同じく自動目盛を維持する
* 時刻の元データ（秒）は保持し、表示変換のみグラフ描画で行う
