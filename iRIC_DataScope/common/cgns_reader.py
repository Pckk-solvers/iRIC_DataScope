from __future__ import annotations

import logging
import re
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


@dataclass(frozen=True)
class IricStepFrame:
    """
    iRIC の Result_*.csv 相当の 1 ステップ分データ。

    df は少なくとも I,J,X,Y を含む。
    """
    step: int
    time: float
    imax: int
    jmax: int
    location: str | None
    df: pd.DataFrame


def _decode_bytes(val) -> str:
    if isinstance(val, bytes):
        try:
            return val.decode("ascii").strip()
        except Exception:
            return val.decode(errors="ignore").strip()
    if isinstance(val, np.ndarray):
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


def try_read_timevalues(f: h5py.File, zone_path: str) -> np.ndarray | None:
    base = zone_path.strip("/").split("/")[0]
    cand = f"{base}/BaseIterativeData/TimeValues"
    if cand in f:
        return np.asarray(f[cand][DATASET_NAME][()])

    hits = _find_group_paths_by_name(f, "TimeValues")
    for p in hits:
        if "BaseIterativeData" in p and p in f and DATASET_NAME in f[p]:
            return np.asarray(f[p][DATASET_NAME][()])
    return None


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
    if "GridLocation" in sol_group.attrs:
        return _normalize_location(sol_group.attrs["GridLocation"])
    if "GridLocation" in sol_group:
        try:
            return _normalize_location(sol_group["GridLocation"][()])
        except Exception:
            return None
    return None


def _load_flow_solutions(
    f: h5py.File, zone_path: str
) -> tuple[list[str], list[str | None], set[str]]:
    pointers_path = f"{zone_path}/ZoneIterativeData/FlowSolutionPointers"
    pointers: list[str] = []
    if pointers_path in f:
        try:
            pointers = _decode_flow_solution_pointers_int8(_read_node_data(f, pointers_path))
        except Exception as e:
            logger.debug("Failed to read FlowSolutionPointers: %s", e)

    if not pointers:
        pointers = _list_flow_solution_groups(f, zone_path)

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


def _list_flow_solution_groups(f: h5py.File, zone_path: str) -> list[str]:
    if zone_path not in f:
        return []
    zone = f[zone_path]
    names: list[str] = []
    for name, obj in zone.items():
        if isinstance(obj, h5py.Group) and name.lower().startswith("flowsolution"):
            names.append(name)
    if not names:
        return []

    def sort_key(n: str):
        m = re.search(r"(\d+)$", n)
        if m:
            return (0, int(m.group(1)))
        return (1, n.lower())

    return sorted(names, key=sort_key)


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

    if available & vertex_labels:
        return next(iter(vertex_labels & available))
    if available & cell_labels:
        return next(iter(cell_labels & available))
    return None


def _pick_cgn_from_ipro(z: zipfile.ZipFile, case_name: str) -> str:
    names = z.namelist()

    for n in names:
        if Path(n).name.lower() == case_name.lower():
            return n

    cgns = [n for n in names if n.lower().endswith(".cgn")]
    if len(cgns) == 1:
        return cgns[0]

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


def iter_iric_step_frames(
    cgn_path: Path,
    *,
    zone_path: str = "iRIC/iRICZone",
    vars_keep: list[str] | None = None,
    step_from: int = 1,
    step_to: int | None = None,
    step_skip: int = 1,
    fortran_order: bool = True,
    location_preference: Literal["auto", "vertex", "cell"] = "auto",
    include_flow_solution: bool = True,
) -> Generator[IricStepFrame, None, None]:
    """
    CGNS を読み込み、iRIC 互換 CSV 相当の DataFrame をステップ単位で返す。
    """
    zone_path = zone_path.strip("/")

    with h5py.File(cgn_path, "r") as f:
        x = _read_node_data(f, f"{zone_path}/GridCoordinates/CoordinateX")
        y = _read_node_data(f, f"{zone_path}/GridCoordinates/CoordinateY")
        if x.shape != y.shape:
            raise RuntimeError(f"CoordinateX shape {x.shape} != CoordinateY shape {y.shape}")

        order = "F" if fortran_order else "C"
        ii, jj = np.indices(x.shape)
        base_cols = {
            "I": (ii + 1).ravel(order=order),
            "J": (jj + 1).ravel(order=order),
            "X": x.ravel(order=order),
            "Y": y.ravel(order=order),
        }

        time_values = try_read_timevalues(f, zone_path)

        if include_flow_solution:
            sol_names, sol_locations, location_set = _load_flow_solutions(f, zone_path)
            preferred = _pick_preferred_location(location_set, location_preference)
            if preferred:
                logger.info("Preferred GridLocation: %s", preferred)

            nstep = len(sol_names)
            if nstep < 1:
                raise RuntimeError("No FlowSolution found")

            first_sol_path = f"{zone_path}/{sol_names[0]}"
            if first_sol_path not in f:
                raise FileNotFoundError(f"{first_sol_path} not found in CGNS")
            var_all = [k for k in f[first_sol_path].keys() if k != "GridLocation"]
            vars_selected: Sequence[str] = (
                [v for v in vars_keep if v in var_all] if vars_keep else var_all
            )
        else:
            sol_names = []
            sol_locations = []
            preferred = None
            nstep = 1
            vars_selected = []

        if step_to is None:
            step_to = nstep
        step_from = max(1, step_from)
        step_to = min(nstep, step_to)

        for step in range(step_from, step_to + 1, step_skip):
            cols = dict(base_cols)
            loc_norm: str | None = None

            if include_flow_solution:
                sol_name = sol_names[step - 1]
                sol_path = f"{zone_path}/{sol_name}"
                if sol_path not in f:
                    raise FileNotFoundError(f"{sol_path} not found in CGNS")

                loc_norm = _normalize_location(sol_locations[step - 1])
                sol_group = f[sol_path]

                for v in vars_selected:
                    if v not in sol_group:
                        continue
                    try:
                        arr = _read_dataset_or_group(sol_group[v])
                    except Exception as ex:
                        logger.debug("Skip var %s: read error: %s", v, ex)
                        continue

                    if arr.shape != x.shape:
                        logger.debug("Skip var %s: shape %s != %s", v, arr.shape, x.shape)
                        continue
                    cols[v] = arr.ravel(order=order)

            t_val = 0.0
            if include_flow_solution and time_values is not None and len(time_values) >= step:
                try:
                    t_val = float(time_values[step - 1])
                except Exception:
                    t_val = 0.0

            df = pd.DataFrame(cols)
            imax, jmax = x.shape
            yield IricStepFrame(
                step=step,
                time=t_val,
                imax=int(imax),
                jmax=int(jmax),
                location=loc_norm or preferred,
                df=df,
            )


def iter_iric_step_frames_from_input(
    input_path: Path,
    *,
    case_name: str = "Case1.cgn",
    **kwargs,
) -> Generator[IricStepFrame, None, None]:
    """入力(.cgn/.ipro/dir)から CGNS を解決して iter_iric_step_frames を返す。"""
    with resolve_case_cgn(input_path, case_name) as cgn:
        yield from iter_iric_step_frames(cgn, **kwargs)
