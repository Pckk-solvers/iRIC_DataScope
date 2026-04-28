# iRIC計算結果CGNSの断面集計ツールでやりたいこと

## 1. やりたいこと

iRICの計算結果CGNSを読み込み、計算結果に含まれる水位と水深を、側線SHPごとに整理したい。

対象にしたい計算結果は、主に以下の2つ。

* `watersurfaceelevation(m)`
* `depth(m)`

全格子点の結果をそのまま見るのではなく、側線SHPで指定した断面ごとに、近くの格子点を拾い、その断面の代表値として平均水位・平均水深を整理する。

最終的には、各断面について全ステップの時系列結果を出し、さらにその中から平均水位が最大になるステップを抽出したい。

あわせて、各断面ごとの平均水位の時系列グラフも出力したい。

---

## 2. 入力データ

入力は大きく2つ。

### 2.1 iRIC計算結果CGNS

計算結果が入っているCGNSファイルを使う。

ここから以下を取得する。

* 計算ステップ
* 時刻
* 格子点のI/J番号
* 格子点のX/Y座標
* `watersurfaceelevation(m)`
* `depth(m)`

#### 確認済みCGNS構造

ルート直下に置いた `Case1-1.cgn` を確認したところ、対象データは以下の構造で格納されていた。

```text
iRIC/
  BaseIterativeData/
    TimeValues                         shape=(110,)
  iRICZone/
    GridCoordinates/
      CoordinateX                      shape=(73, 813)
      CoordinateY                      shape=(73, 813)
    ZoneIterativeData/
      FlowSolutionPointers             shape=(110, 32)
      FlowCellSolutionPointers         shape=(110, 32)
    FlowSolution1 ... FlowSolution110
    FlowCellSolution1 ... FlowCellSolution110
    FlowIFaceSolution1 ... FlowIFaceSolution110
    FlowJFaceSolution1 ... FlowJFaceSolution110
```

今回の断面集計で使う水位・水深は、ノード結果 `FlowSolutionN` に入っている。

```text
FlowSolutionN
  depth(m)                             shape=(73, 813)
  watersurfaceelevation(m)             shape=(73, 813)
```

`FlowSolutionN` には明示的な `GridLocation` は入っていないが、座標 `CoordinateX/Y` と同じ shape なので、ノード値として扱う。

一方、セル中心結果は `FlowCellSolutionN` に入っている。

```text
FlowCellSolutionN
  GridLocation                         CellCenter
  cell_h[m]                            shape=(72, 812)
  cell_eta[m]                          shape=(72, 812)
```

セル中心の水深・水位を使う場合は、`depth(m)` / `watersurfaceelevation(m)` ではなく、`cell_h[m]` / `cell_eta[m]` を別途扱う必要がある。初期実装ではノード値を対象にする。

#### definition.xml との対応

`sandbox/definition.xml` では、出力変数の有効/無効を制御する計算条件として以下が確認できた。

```text
output_variables:
  jop_have  Averaged water level in the cross sections
  jop_zmin  Minimun bed elevation in the cross sections
  jop_zave  Averaged bed elevation in the cross sections
```

また、格子条件としては以下が定義されている。

```text
GridRelatedCondition:
  Elevation       position=node
  Elevation_zb    position=node
  Obstacle        position=cell
  Fix_movable     position=cell
  roughness_cell  position=cell
```

ただし、実際に計算結果として読む変数名は `definition.xml` の表示名ではなく、CGNS 内の `FlowSolutionN` / `FlowCellSolutionN` のデータセット名を優先する。

### 2.2 側線SHP

断面位置を表すラインデータ。

この側線とiRICの格子点を重ね合わせて、側線上のサンプル点ごとに最近傍の格子点を拾い、その断面の集計対象として採用する。

側線ごとに断面IDや断面名が入っていれば、それを使う。なければツール側で連番を付ける。

初期実装では、側線SHPは以下を想定する。

* ジオメトリは `LineString`
* 1 feature を 1 断面として扱う
* `MultiLineString` は初期実装では対象外
* Z/M 値は使わない
* 座標系は CGNS の `CoordinateX` / `CoordinateY` と同じ平面座標系であること

属性は必須にしない。以下の候補フィールドがあれば断面ID・断面名として使い、無ければツール側で連番を付ける。

```text
section_id
section_name
ID
Name
SecNo
断面名
```

---

## 3. 側線と格子点の考え方

側線ごとに、側線上のサンプル点から最近傍の格子点を拾って断面の対象点にする。

このとき、断面は必ずしも「Iが固定」「Jが固定」とは限らない。

例えば、Jは連続していても、側線の向きによってIが途中で変わることがある。

そのため、断面はI/Jの規則で管理するのではなく、以下のような「採用格子点のリスト」として管理する。

```text
断面 SEC001
  1点目: i=25, j=101
  2点目: i=25, j=102
  3点目: i=26, j=103
  ...
```

この対応関係は後で確認できるように、`section_node_map.csv` として出力する。

初期実装では、採用距離の閾値 `search_distance` は設けない。

理由は、側線SHPが断面位置として作成されている前提では、「一定距離以内の点を全て拾う」よりも、「側線上をたどりながら代表する格子点列を作る」方が断面として扱いやすいため。

採用ルールは以下とする。

```text
1. 側線を sample_interval ごとにサンプリングする
2. 各サンプル点に最も近いノードを1点拾う
3. 同じ I/J が複数回選ばれた場合は重複除外する
4. 採用点を側線上の距離 line_dist 順に並べる
5. nearest_dist は採用条件ではなく確認用に出力する
```

`sample_interval` は、未指定の場合は CGNS の格子間隔から自動推定する。初期案として、代表的な隣接ノード間距離の半分程度を使う。

`nearest_dist` が大きい点は処理から除外せず、`section_node_map.csv` で確認できるようにする。必要になれば後で警告閾値を追加する。

---

## 4. 平均を計算するときのルール

断面平均を計算するときは、すべての格子点を使うのではなく、`depth` に閾値を設ける。

例えば、閾値を `0.01` とした場合は、以下のように扱う。

```text
depth >= 0.01 の格子点だけを平均計算に使う
depth <  0.01 の格子点は平均計算から外す
```

つまり、水深がほとんどない点は、平均水位や平均水深の計算母数から除外する。

このルールで、各断面・各ステップごとに以下を計算する。

* 有効な格子点数
* 除外された格子点数
* 有効格子点率
* 平均水位 `mean_wse`（`watersurfaceelevation(m)` から計算）
* 平均水深 `mean_depth`（`depth(m)` から計算）
* 最大水位
* 最大水深
* 最小水位
* 最小水深

有効な格子点が1つもない場合は、そのステップの平均値は空欄またはNaNとして扱う。

---

## 5. 最大ステップの考え方

各断面について、全ステップの中から `mean_wse` が最大になるステップを採用する。

つまり、最大値の基準は水深ではなく、平均水位。

```text
各断面のピーク = mean_wse が最大のステップ
```

そのピーク時刻について、以下の情報を整理する。

* ピークステップ
* ピーク時刻
* 最大となった平均水位
* その時の平均水深
* その時の有効格子点数
* その時の有効格子点率
* その時の最大水位
* その時の最大水深

同じ平均水位が複数ステップで出た場合は、ひとまず早い時刻のステップを採用する。

---

## 6. 出力したいCSV

初期段階では、以下の3つのCSVを出力したい。

```text
output/
  section_node_map.csv
  section_timeseries.csv
  section_peak_summary.csv
```

---

## 6.1 section_node_map.csv

側線ごとに、どの格子点を採用したかを確認するためのCSV。

主なカラムは以下。

```text
section_id
section_name
source_line_id
order_no
i
j
x
y
line_dist
nearest_dist
sample_dist
```

`sample_dist` は側線上のサンプル位置、`line_dist` は採用ノードを側線へ投影した位置を表す。通常は `line_dist` を断面内の並び順に使う。

このCSVを見ることで、以下を確認できる。

* 側線ごとに採用された格子点
* I/Jの並び
* 側線から格子点までの距離
* 不自然に遠い格子点を拾っていないか
* どのサンプル位置から採用された点か

---

## 6.2 section_timeseries.csv

断面ごと・ステップごとの集計結果を出すCSV。

主なカラムは以下。

```text
section_id
section_name
step
time
node_count
valid_node_count
invalid_node_count
valid_ratio
depth_threshold
mean_wse
mean_depth
max_wse
min_wse
max_depth
min_depth
```

このCSVが、時系列確認用のメイン出力になる。

---

## 6.3 section_peak_summary.csv

各断面について、`mean_wse` が最大になるステップだけをまとめたCSV。

主なカラムは以下。

```text
section_id
section_name
node_count
depth_threshold
peak_step
peak_time
peak_mean_wse
depth_at_peak_mean_wse
valid_node_count_at_peak
valid_ratio_at_peak
max_wse_at_peak
min_wse_at_peak
max_depth_at_peak
min_depth_at_peak
```

このCSVを見れば、各断面の最大水位時の状態を一覧で確認できる。

---

## 7. 処理の流れ

全体の流れは以下のイメージ。

```text
1. iRIC計算結果CGNSを読み込む
2. 格子点の座標、I/J、ステップ、時刻、水位、水深を取得する
3. 側線SHPを読み込む
4. 側線ごとに sample_interval 間隔でサンプリングする
5. 各サンプル点の最近傍ノードを採用し、重複 I/J を除外する
6. 採用格子点一覧を section_node_map.csv に出力する
7. 各断面・各ステップで depth 閾値以上の点だけを使って平均を計算する
8. 断面別の時系列結果を section_timeseries.csv に出力する
9. 各断面で mean_wse が最大のステップを抽出する
10. 最大時の一覧を section_peak_summary.csv に出力する
```

---

## 8. いったん決めておくこと

初期実装では、以下の方針で進めたい。

* 対象変数はノード値の `watersurfaceelevation(m)` と `depth(m)`
* `FlowSolution1 ... FlowSolutionN` と `BaseIterativeData/TimeValues` を使って時系列を読む
* セル中心値の `cell_eta[m]` / `cell_h[m]` は初期実装では対象外にする
* 側線SHPは `LineString` のみを対象にする
* 側線上のサンプル点ごとに最近傍ノードを採用する
* 採用距離の閾値 `search_distance` は初期実装では設けない
* 断面平均は `depth` が閾値以上の格子点だけで計算する
* ピーク判定は `mean_wse` 最大ステップで行う
* 側線と格子点の対応は `section_node_map.csv` に出す
* 出力はまずCSVでよい
* GUIやExcel出力は最初は考えない
* 座標系は、CGNSと側線SHPで一致している前提にする

---

## 9. あとで決めればよいこと

以下は、実装しながら確認すればよい。

* `depth_threshold` の標準値
* CGNS内の変数名は当面 `watersurfaceelevation(m)` / `depth(m)` 固定でよいか
* 将来的にセル中心値 `cell_eta[m]` / `cell_h[m]` も選べるようにするか
* 側線SHPの断面IDフィールド名
* `sample_interval` の自動推定方法を、格子間隔の中央値・最小値・ユーザー指定のどれに寄せるか
* `nearest_dist` がどれくらい大きい場合に警告するか
* 出力CSVのNaN表現を空欄にするか `NaN` にするか
* CSV文字コードを `utf-8-sig` にするか
* 将来的にExcel出力も必要か

---

## 10. 最初のゴール

最初のゴールは、以下の3つのCSVを安定して出せる状態にすること。

```text
section_node_map.csv
section_timeseries.csv
section_peak_summary.csv
```

まずはこの3つが出れば、側線ごとの採用格子点、断面ごとの時系列変化、平均水位最大時の一覧を確認できる。

---

## 6.4 断面ごとのグラフ出力

各断面について、平均水位の時系列グラフを1枚ずつ出力したい。

要件は以下。

* 1断面につき1枚のグラフを出力する
* 横軸は時刻
* 縦軸は平均水位
* 既定では、Y軸は断面ごとに最適な範囲を使う
* 断面間比較が必要な場合だけ、全断面共通のY軸スケールを選べるようにする
* 時刻の表示は小数点以下を付けず、整数値で表示する
* その断面で `mean_wse` が最大になった点をグラフ上で分かるようにする
* グラフは時系列確認用として、CSVとは別に画像ファイルで出力する

このグラフを見ることで、断面ごとの平均水位変化と、平均水位最大時刻をひと目で追えるようにしたい。

---

## 11. グラフ表示とUIの追加要件（2026-04-28）

次の実装では、断面グラフの見た目とGUI設定項目を以下に更新する。

### 11.1 グラフ見た目

* Y軸は、下端が系列の開始側で視認しやすい範囲になるようにする
* Y軸上端は「最上位の目盛」で閉じる表示にする
* グラフ外枠（上下左右のスパイン）を表示する
* グリッドは点線にし、現状より濃い色にする
* 縦軸ラベルは `水位[T.P.m]` に固定する
* 横軸ラベルは `時間[h]` に固定する
* 最大点注記の文言は `最大` ではなく `Max` を使う

### 11.2 時刻の扱い

* 元データの時刻は秒なので、グラフ表示時は時間[h]へ変換して扱う
* 変換は `time_hour = time_sec / 3600.0` を基本とする
* CSVの時刻列は従来どおり秒を保持し、表示用途の変換はグラフ側で行う

### 11.3 横軸目盛の指定

* 横軸目盛の刻みをユーザー指定できるようにする
* 指定がある場合は、その刻みで主目盛を配置する
* 未指定時は自動目盛を使う
* 単位は `時間[h]` で統一する

### 11.4 断面ID・断面名フィールドの選択UI

* SHP属性の `section_id` / `section_name` をハードコード前提にしない
* ユーザーが属性フィールドを選べるUIを用意する
* 候補が無い場合は従来どおり自動採番へフォールバックする

### 11.5 タイトル調整UI（実装準備）

次段の実装で、タイトル表記を細かく調整できるUIを用意する。  
初期要件として、以下を設定対象にする。

* タイトル表示のON/OFF
* タイトル文字列テンプレート（例: `{section_id} {section_name} / 平均水位時系列`）
* 断面IDのみ / 断面名のみ / 両方 の表示モード
