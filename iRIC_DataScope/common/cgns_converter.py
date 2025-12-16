from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Literal, Sequence

import h5py
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# CGNS/HDF5 ではノード直下の " data" に実配列が格納されていることが多い
DATASET_NAME = " data"


@dataclass
class ConversionOptions:
    """
    CGNS / IPRO から iRIC 互換 CSV を生成する際のオプション

    location_preference:
      - "auto"   : Vertex を優先し、無ければ CellCenter を使う
      - "vertex" : Vertex を優先（無ければ CellCenter にフォールバック）
      - "cell"   : CellCenter を優先（無ければ Vertex にフォールバック）
    include_flow_solution:
      - True の場合、FlowSolution 系のスカラーを出力（形状が座標と一致するもののみ）
      - False の場合、座標のみを出力
    """
    case_name: str = "Case1.cgn"
    zone_path: str = "iRIC/iRICZone"
    vars_keep: list[str] | None = None
    step_from: int = 1
    step_to: int | None = None
    step_skip: int = 1
    fortran_order: bool = True
    location_preference: Literal["auto", "vertex", "cell"] = "auto"
    include_flow_solution: bool = True


# --- ユーティリティ ---------------------------------------------------------

def _decode_bytes(val) -> str:
    if isinstance(val, bytes):
        try:
            return val.decode("ascii").strip()
        except Exception:
            return val.decode(errors="ignore").strip()
    if isinstance(val, np.ndarray):
        # h5py attr が array で返る場合がある
        if val.dtype.kind in {"S", "U"}:
            return str(val[()]).strip().strip("b'").strip('"')
        try:
            return bytes(val.tolist()).decode("ascii", errors="ignore").strip()
        except Exception:
            pass
    return str(val)


def _normalize_location(loc: str | None) -> str | None:
    if not loc:
        return None
    return _decode_bytes(loc).upper().replace(" ", "")


def _read_node_data(f: h5py.File, node_path: str) -> np.ndarray:
    if node_path not in f:
        raise KeyError(f"{node_path} not found in CGNS")
    g = f[node_path]
    if DATASET_NAME not in g:
        raise KeyError(f"{node_path} has no '{DATASET_NAME}' dataset. keys={list(g.keys())}")
    return np.asarray(g[DATASET_NAME][()])


def _read_dataset_or_group(node: h5py.Group | h5py.Dataset) -> np.ndarray:
    """
    FlowSolution 配下の変数を読む。
    - Dataset の場合はそのまま
    - Group の場合は内部の " data" を読む
    """
    if isinstance(node, h5py.Dataset):
        return np.asarray(node[()])
    if isinstance(node, h5py.Group):
        if DATASET_NAME not in node:
            raise KeyError(f"missing '{DATASET_NAME}' in group: {node.name}")
        return np.asarray(node[DATASET_NAME][()])
    raise TypeError(f"unsupported node type: {type(node)}")


def _find_group_paths_by_name(f: h5py.File, target: str) -> list[str]:
    hits: list[str] = []

    def visitor(name, obj):
        if isinstance(obj, h5py.Group) and Path(name).name == target:
            hits.append(name)

    f.visititems(visitor)
    return hits


def _try_read_timevalues(f: h5py.File, zone_path: str) -> np.ndarray | None:
    base = zone_path.strip("/").split("/")[0]
    cand = f"{base}/BaseIterativeData/TimeValues"
    if cand in f:
        return np.asarray(f[cand][" data"][()])

    hits = _find_group_paths_by_name(f, "TimeValues")
    for p in hits:
        if "BaseIterativeData" in p and p in f and " data" in f[p]:
            return np.asarray(f[p][" data"][()])
    return None


def _format_iric_time(t) -> str:
    try:
        tf = float(t)
        if abs(tf - round(tf)) < 1e-12:
            return str(int(round(tf)))
        return f"{tf:g}"
    except Exception:
        return str(t)


def _decode_flow_solution_pointers_int8(a: np.ndarray) -> list[str]:
    a = np.asarray(a)
    if a.dtype != np.int8 or a.ndim != 2:
        raise TypeError(f"unexpected pointers array: shape={a.shape}, dtype={a.dtype}")
    out: list[str] = []
    for row in a:
        s = bytes(row.tolist()).decode("ascii", errors="ignore")
        out.append(s.replace("\x00", "").strip())
    return out


def _grid_location(sol_group: h5py.Group) -> str | None:
    # attrs 優先
    if "GridLocation" in sol_group.attrs:
        return _normalize_location(sol_group.attrs["GridLocation"])
    # データセットとして持っている場合
    if "GridLocation" in sol_group:
        try:
            return _normalize_location(sol_group["GridLocation"][()])
        except Exception:
            return None
    return None


def _pick_cgn_from_ipro(z: zipfile.ZipFile, case_name: str) -> str:
    names = z.namelist()
    # 1) 指定名を優先
    for n in names:
        if Path(n).name.lower() == case_name.lower():
            return n
    # 2) *.cgn が1個ならそれ
    cgns = [n for n in names if n.lower().endswith(".cgn")]
    if len(cgns) == 1:
        return cgns[0]
    # 3) 複数なら最大サイズ
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
    input_path:
      - *.cgn: そのまま
      - *.ipro: zip から case_name を一時展開
      - dir: dir 配下から case_name を探す。無ければ *.cgn が1個ならそれ。
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
                target = _pick_cgn_from_ipro(z, case_name)
                out = td_path / Path(target).name
                with z.open(target) as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            yield out
        return

    raise ValueError(f"Unsupported input: {p} (expected .cgn, .ipro, or directory)")


# --- 変換本体 ---------------------------------------------------------------

def _load_flow_solutions(
    f: h5py.File, zone_path: str
) -> tuple[list[str], list[str | None], set[str]]:
    pointers_path = f"{zone_path}/ZoneIterativeData/FlowSolutionPointers"
    pointers = _decode_flow_solution_pointers_int8(_read_node_data(f, pointers_path))
    locations: list[str | None] = []
    location_set: set[str] = set()
    for name in pointers:
        sol_path = f"{zone_path}/{name}"
        loc = _grid_location(f[sol_path]) if sol_path in f else None
        norm = _normalize_location(loc)
        locations.append(norm)
        if norm:
            location_set.add(norm)
    return pointers, locations, location_set


def _pick_preferred_location(
    available: set[str], preference: Literal["auto", "vertex", "cell"]
) -> str | None:
    vertex_labels = {"VERTEX", "NODE", "NODAL"}
    cell_labels = {"CELLCENTER", "CELL_CENTER"}

    if preference == "vertex":
        if available & vertex_labels:
            return next(iter(vertex_labels & available))
        if available & cell_labels:
            return next(iter(cell_labels & available))
        return None

    if preference == "cell":
        if available & cell_labels:
            return next(iter(cell_labels & available))
        if available & vertex_labels:
            return next(iter(vertex_labels & available))
        return None

    # auto: Vertex を優先
    if available & vertex_labels:
        return next(iter(vertex_labels & available))
    if available & cell_labels:
        return next(iter(cell_labels & available))
    return None


def export_iric_like_csv(
    cgn_path: Path,
    out_dir: Path,
    *,
    zone_path: str = "iRIC/iRICZone",
    vars_keep: list[str] | None = None,
    step_from: int = 1,
    step_to: int | None = None,
    step_skip: int = 1,
    fortran_order: bool = True,
    location_preference: Literal["auto", "vertex", "cell"] = "auto",
    include_flow_solution: bool = True,
) -> None:
    """
    CGNS を読み込み iRIC 互換の Result_*.csv を out_dir に出力する。
    - ノード/セルどちらかしか無い場合は存在する方を使用
    - 両方ある場合は location_preference に従い Vertex 優先（auto）
    - 境界データは扱わない（FlowSolution 配下のみを対象）
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    zone_path = zone_path.strip("/")

    with h5py.File(cgn_path, "r") as f:
        # 座標
        x = _read_node_data(f, f"{zone_path}/GridCoordinates/CoordinateX")
        y = _read_node_data(f, f"{zone_path}/GridCoordinates/CoordinateY")
        if x.shape != y.shape:
            raise RuntimeError(f"CoordinateX shape {x.shape} != CoordinateY shape {y.shape}")

        order = "F" if fortran_order else "C"
        I, J = np.indices(x.shape)
        base_cols = {
            "I": (I + 1).ravel(order=order),
            "J": (J + 1).ravel(order=order),
            "X": x.ravel(order=order),
            "Y": y.ravel(order=order),
        }

        time_values = _try_read_timevalues(f, zone_path)

        if include_flow_solution:
            sol_names, sol_locations, location_set = _load_flow_solutions(f, zone_path)
            nstep = len(sol_names)
            preferred = _pick_preferred_location(location_set, location_preference)
            logger.info(
                "FlowSolutions: %s, preferred location=%s (available=%s)",
                sol_names,
                preferred,
                location_set,
            )
        else:
            sol_names = []
            sol_locations = []
            preferred = None
            nstep = 1  # 座標だけでも1本出力する

        if step_to is None:
            step_to = nstep
        step_from = max(1, step_from)
        step_to = min(nstep, step_to)

        vars_selected: Sequence[str] | None = None
        if include_flow_solution:
            first_sol_path = f"{zone_path}/{sol_names[0]}"
            if first_sol_path in f:
                vars_all = [k for k in f[first_sol_path].keys() if k not in {"GridLocation"}]
                vars_selected = [v for v in vars_keep if v in vars_all] if vars_keep else vars_all
            else:
                raise FileNotFoundError(f"{first_sol_path} not found in CGNS")

        for step in range(step_from, step_to + 1, step_skip):
            cols = dict(base_cols)

            if include_flow_solution:
                sol_name = sol_names[step - 1]
                sol_path = f"{zone_path}/{sol_name}"
                if sol_path not in f:
                    raise FileNotFoundError(f"{sol_path} not found in CGNS")

                loc_norm = _normalize_location(sol_locations[step - 1])
                if preferred and loc_norm and loc_norm != preferred:
                    # 希望ロケーションとは違うが、このステップにはこの FlowSolution しか無いので採用する
                    logger.info(
                        "FlowSolution '%s' uses location %s (preferred %s) at step %d",
                        sol_name,
                        loc_norm,
                        preferred,
                        step,
                    )

                sol_group = f[sol_path]
                for v in vars_selected or []:
                    if v not in sol_group:
                        continue
                    node = sol_group[v]
                    try:
                        arr = _read_dataset_or_group(node)
                    except Exception as ex:
                        logger.debug("Skip var %s: read error: %s", v, ex)
                        continue
                    if arr.shape != x.shape:
                        # ノード/セルどちらかしか無い場合、座標と一致しないものはスキップ
                        logger.debug("Skip var %s: shape %s != %s", v, arr.shape, x.shape)
                        continue
                    cols[v] = arr.ravel(order=order)

            out_path = out_dir / f"Result_{step}.csv"
            imax, jmax = x.shape
            if include_flow_solution and time_values is not None and len(time_values) >= step:
                t_val = time_values[step - 1]
            else:
                t_val = 0

            with out_path.open("w", encoding="utf-8-sig", newline="") as fp:
                fp.write(f"iRIC output t = {_format_iric_time(t_val)}\n")
                fp.write(f"{imax},{jmax}\n")
                pd.DataFrame(cols).to_csv(fp, index=False)

            if step == step_from or step % 10 == 0 or step == step_to:
                logger.info("[CSV] %s", out_path.name)


def convert_iric_project(
    input_path: Path,
    output_dir: Path,
    *,
    options: ConversionOptions | None = None,
) -> Path:
    """
    .ipro / .cgn / フォルダを受け取り、Result_*.csv を output_dir に生成する。
    戻り値は output_dir。
    """
    opts = options or ConversionOptions()
    input_path = input_path.expanduser()
    output_dir = output_dir.expanduser()
    logger.info("Start CGNS→CSV: input=%s output=%s", input_path, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with resolve_case_cgn(input_path, opts.case_name) as cgn:
        export_iric_like_csv(
            cgn_path=cgn,
            out_dir=output_dir,
            zone_path=opts.zone_path,
            vars_keep=opts.vars_keep,
            step_from=opts.step_from,
            step_to=opts.step_to,
            step_skip=opts.step_skip,
            fortran_order=opts.fortran_order,
            location_preference=opts.location_preference,
            include_flow_solution=opts.include_flow_solution,
        )
    logger.info("Done CGNS→CSV: %s", output_dir)
    return output_dir
