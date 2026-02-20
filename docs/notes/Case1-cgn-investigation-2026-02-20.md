# Case1.cgn 調査メモ (2026-02-20)

## 対象
- 入力ファイル: `C:\Users\yuuta.ochiai\Downloads\Case1.cgn`
- 発生エラー: `Unable to synchronously open object (addr overflow, addr = 10725326, size = 80, eoa = 10725086)`

## 結論
- `Case1.cgn` は **HDF5 ヘッダ整合性不良**（EOF/EOA 不一致）を含む。
- EOF を修正すると一部読めるが、iRIC_DataScope が必要とする結果構造（`GridCoordinates` / `FlowSolutionPointers` など）は欠落しており、通常解析は不可。
- 取得できたのは `iRIC/iRICZone` 直下の 4 配列のみ（時系列ではない）。

## 主要事実
- 実ファイルサイズ: `2,389,546,051 bytes`
- HDF5 superblock (v0) の `eof_addr`: `10,725,086`
- `eof_addr != 実ファイルサイズ` のため、HDF5 が「有効なファイル終端」を誤認し `addr overflow` を起こす。

## 実施した検証
1. `h5py` で `Case1.cgn` を開く
- root は列挙可能（`format`, `hdf5version`, `CGNSLibraryVersion`, `iRIC`）
- `iRIC` グループを開く段階で `addr overflow`

2. EOF パッチ版作成 (`Case1_eofpatch.cgn`)
- superblock の `eof_addr` を実ファイルサイズへ合わせる
- これにより `iRIC` / `iRICZone` へ到達可能

3. 構造確認（パッチ版）
- `iRIC/iRICZone` 直下: `term_advc_x`, `term_fric_x`, `qq_iface`, `ebcx_height` のみ
- 欠落: `iRIC/iRICZone/GridCoordinates/CoordinateX`, `CoordinateY`, `ZoneIterativeData/FlowSolutionPointers`, `FlowSolution*`
- `iRIC/BaseIterativeData/ data` は `[0]` のみ（時刻系列情報として不十分）

## 抽出できた配列
出力先: `sandbox/zone_export_case1_eofpatch`
- `ebcx_height` (`72 x 813`)
- `qq_iface` (`72 x 813`)
- `term_advc_x` (`72 x 813`)
- `term_fric_x` (`72 x 813`)

## 「容量は正常なのに壊れる」理由
- HDF5/CGNS は「サイズ」だけでなく「内部参照テーブル（メタデータ）」で読む。
- 容量が正常でも、EOF/参照情報が壊れると読み込み不能になる。
- 今回はまさにそのパターン（実サイズとヘッダ終端値が乖離）。

## 先方説明用の要約案
- 「iRIC の出力 CGNS に対し、HDF5 レベルで内部終端情報（EOF/EOA）の不整合が検出されました。容量は正常に見えるものの、内部参照が壊れているため `addr overflow` で読み込めません。EOF 修正で一部読める状態にはなりましたが、解析に必要な `GridCoordinates` / `FlowSolution` 系ノードが欠落しており、時系列結果としては利用できません。」

## 再現・補助スクリプト
- 整合性診断: `sandbox/analyze_cgn_integrity.py`
- 配列書き出し: `sandbox/export_zone_arrays.py`

例:
```powershell
uv run python sandbox/analyze_cgn_integrity.py "C:\Users\yuuta.ochiai\Downloads\Case1.cgn" --extract-zone --out "sandbox\Case1.integrity.with_zone.json"
uv run python sandbox/export_zone_arrays.py "C:\Users\yuuta.ochiai\Downloads\Case1_eofpatch.cgn" --out-dir "sandbox\zone_export_case1_eofpatch"
```

## 生成済みレポート
- `sandbox/Case1.integrity.json`
- `sandbox/Case1.integrity.with_zone.json`
- `sandbox/Case1_eofpatch.integrity.with_zone.json`
- `sandbox/zone_export_case1_eofpatch/manifest.json`
