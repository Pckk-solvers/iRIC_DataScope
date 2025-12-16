from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import h5py
import numpy as np
import pandas as pd


DATASET_NAME = " data"  # CGNS/HDF5はノード直下の " data" に実配列が入ることが多い

def find_group_paths_by_name(f: h5py.File, target: str) -> list[str]:
    hits = []
    def visitor(name, obj):
        if isinstance(obj, h5py.Group) and Path(name).name == target:
            hits.append(name)
    f.visititems(visitor)
    return hits

def try_read_timevalues(f: h5py.File, zone_path: str) -> np.ndarray | None:
    # baseは zone_path の先頭（例: iRIC/iRICZone → iRIC）
    base = zone_path.strip("/").split("/")[0]

    cand = f"{base}/BaseIterativeData/TimeValues"
    if cand in f:
        return np.asarray(f[cand][" data"][()])

    # 念のため名前検索（ファイルによってパスが違うことがある）
    hits = find_group_paths_by_name(f, "TimeValues")
    for p in hits:
        if "BaseIterativeData" in p and p in f and " data" in f[p]:
            return np.asarray(f[p][" data"][()])

    return None

def format_iric_time(t) -> str:
    # 0 → "0" にしたい（余計な .0 を消す）
    try:
        tf = float(t)
        if abs(tf - round(tf)) < 1e-12:
            return str(int(round(tf)))
        return f"{tf:g}"
    except Exception:
        return str(t)

def decode_flowsolution_pointers_int8(a: np.ndarray) -> list[str]:
    """(nstep, strlen) int8 の文字テーブルを ['FlowSolution1', ...] にする"""
    a = np.asarray(a)
    if a.dtype != np.int8 or a.ndim != 2:
        raise TypeError(f"unexpected pointers array: shape={a.shape}, dtype={a.dtype}")
    out: list[str] = []
    for row in a:
        s = bytes(row.tolist()).decode("ascii", errors="ignore")
        out.append(s.replace("\x00", "").strip())
    return out


def read_node_data(f: h5py.File, node_path: str) -> np.ndarray:
    """CGNSノード（Group）配下の ' data' を読む。node_path は Group のパス。"""
    g = f[node_path]
    if DATASET_NAME not in g:
        raise KeyError(f"{node_path} has no '{DATASET_NAME}' dataset. keys={list(g.keys())}")
    return np.asarray(g[DATASET_NAME][()])


def pick_cgn_from_ipro(z: zipfile.ZipFile, case_name: str) -> str:
    """ipro(zip)内から取り出すCGNSを選ぶ。優先: case_name → *.cgnが1個 → 最大サイズの*.cgn"""
    names = z.namelist()

    # 1) 指定名（例: Case1.cgn）を優先
    for n in names:
        if Path(n).name.lower() == case_name.lower():
            return n

    # 2) *.cgn が1個ならそれ
    cgns = [n for n in names if n.lower().endswith(".cgn")]
    if len(cgns) == 1:
        return cgns[0]

    # 3) 複数あるなら最大サイズのもの（だいたい結果が入ってる）
    if cgns:
        size_map = {}
        for info in z.infolist():
            if info.filename in cgns:
                size_map[info.filename] = info.file_size
        return max(size_map, key=size_map.get)

    raise FileNotFoundError("No .cgn found in .ipro")


@contextmanager
def resolve_case_cgn(input_path: Path, case_name: str) -> Generator[Path, None, None]:
    """
    input:
      - *.cgn: そのまま
      - *.ipro: zipから case_name を一時展開して返す
      - dir: dir配下から case_name を探す。無ければ *.cgn が1個ならそれ
    """
    p = input_path

    if p.is_dir():
        hit = list(p.rglob(case_name))
        if hit:
            yield hit[0]
            return
        cgns = list(p.rglob("*.cgn"))
        if len(cgns) == 1:
            yield cgns[0]
            return
        raise FileNotFoundError(f"'{case_name}' not found and ambiguous *.cgn in dir: {p}")

    if p.suffix.lower() == ".cgn":
        yield p
        return

    if p.suffix.lower() == ".ipro":
        with tempfile.TemporaryDirectory(prefix="ipro_extract_") as td:
            td_path = Path(td)
            with zipfile.ZipFile(p, "r") as z:
                target = pick_cgn_from_ipro(z, case_name)
                out = td_path / Path(target).name
                with z.open(target) as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            yield out
        return

    raise ValueError(f"Unsupported input: {p} (expected .cgn, .ipro, or directory)")


def export_iric_like_csv(
    cgn_path: Path,
    out_dir: Path,
    zone_path: str = "iRIC/iRICZone",
    vars_keep: list[str] | None = None,
    step_from: int = 1,
    step_to: int | None = None,
    step_skip: int = 1,
    fortran_order: bool = True,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    zone_path = zone_path.strip("/")

    with h5py.File(cgn_path, "r") as f:
        # 1) FlowSolutionPointers
        fsp_node = f"{zone_path}/ZoneIterativeData/FlowSolutionPointers"
        sol_names = decode_flowsolution_pointers_int8(read_node_data(f, fsp_node))
        nstep = len(sol_names)

        if step_to is None:
            step_to = nstep
        step_from = max(1, step_from)
        step_to = min(nstep, step_to)

        # 2) 座標
        x = read_node_data(f, f"{zone_path}/GridCoordinates/CoordinateX")
        y = read_node_data(f, f"{zone_path}/GridCoordinates/CoordinateY")
        if x.shape != y.shape:
            raise RuntimeError(f"CoordinateX shape {x.shape} != CoordinateY shape {y.shape}")

        order = "F" if fortran_order else "C"

        # 3) I,J,X,Y
        I, J = np.indices(x.shape)
        base_cols = {
            "I": (I + 1).ravel(order=order),
            "J": (J + 1).ravel(order=order),
            "X": x.ravel(order=order),
            "Y": y.ravel(order=order),
        }

        # 変数リスト
        first_sol_path = f"{zone_path}/{sol_names[0]}"
        var_all = list(f[first_sol_path].keys())
        vars_use = [v for v in vars_keep if v in var_all] if vars_keep else var_all

        print(f"[INFO] CGNS={cgn_path}")
        print(f"[INFO] zone={zone_path}")
        print(f"[INFO] steps={nstep} export={step_from}..{step_to} skip={step_skip}")
        print(f"[INFO] vars={vars_use}")

        # 4) ステップごとCSV
        for step in range(step_from, step_to + 1, step_skip):
            sol_name = sol_names[step - 1]
            sol_path = f"{zone_path}/{sol_name}"

            cols = dict(base_cols)

            for v in vars_use:
                node = f"{sol_path}/{v}"
                if node not in f:
                    continue
                try:
                    arr = read_node_data(f, node)
                except KeyError:
                    continue

                # 座標と同shapeのものだけ（セル中心等は必要ならここで分岐）
                if arr.shape != x.shape:
                    continue

                cols[v] = arr.ravel(order=order)

            df = pd.DataFrame(cols)
            out_path = out_dir / f"Result_{step}.csv"
            imax, jmax = x.shape  # 例: (236, 41)
            t_values = try_read_timevalues(f, zone_path)  # None の可能性あり

            # ループ内（stepごと）
            t = t_values[step - 1] if (t_values is not None and len(t_values) >= step) else 0

            with out_path.open("w", encoding="utf-8-sig", newline="") as fp:
                fp.write(f"iRIC output t = {format_iric_time(t)}\n")
                fp.write(f"{imax},{jmax}\n")
                df.to_csv(fp, index=False)  # ここから下が通常のCSV（列名行+データ）

            if step == step_from or step % 10 == 0 or step == step_to:
                print(f"[OK] {out_path.name}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument(
        "--input",
        required=True,
        help="入力: Case1.cgn / project.ipro / プロジェクトフォルダ のいずれかを指定します。",
    )
    p.add_argument(
        "--out",
        required=True,
        help="出力先フォルダを指定します（例: out_csv）。存在しない場合は作成します。",
    )
    p.add_argument(
        "--case",
        default="Case1.cgn",
        help="(.ipro またはフォルダ指定時) 対象CGNSファイル名を指定します（既定: Case1.cgn）。",
    )
    p.add_argument(
        "--zone",
        default="iRIC/iRICZone",
        help="対象ゾーンのパスを指定します（既定: iRIC/iRICZone）。",
    )
    p.add_argument(
        "--vars",
        default="",
        help="出力する変数名をカンマ区切りで指定します（例: ZB,ZS,HS）。空の場合は全変数を出力します。",
    )
    p.add_argument(
        "--from-step",
        type=int,
        default=1,
        help="出力する開始ステップ番号（1始まり、既定: 1）。",
    )
    p.add_argument(
        "--to-step",
        type=int,
        default=None,
        help="出力する終了ステップ番号（1始まり）。未指定の場合は最終ステップまで出力します。",
    )
    p.add_argument(
        "--skip",
        type=int,
        default=1,
        help="出力するステップ間隔（例: 2なら1,3,5...。既定: 1）。",
    )
    p.add_argument(
        "--c-order",
        action="store_true",
        help="配列の並べ替えをC順（row-major）で行います。指定しない場合はFortran順（column-major）です。",
    )

    return p.parse_args()



if __name__ == "__main__":
    args = parse_args()
    vars_keep = [s.strip() for s in args.vars.split(",") if s.strip()] or None

    in_path = Path(args.input)

    with resolve_case_cgn(in_path, args.case) as cgn:
        export_iric_like_csv(
            cgn_path=cgn,
            out_dir=Path(args.out),
            zone_path=args.zone,
            vars_keep=vars_keep,
            step_from=args.from_step,
            step_to=args.to_step,
            step_skip=args.skip,
            fortran_order=not args.c_order,
        )
