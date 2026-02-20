from __future__ import annotations

import logging
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, TYPE_CHECKING

import pandas as pd

from iRIC_DataScope.common.iric_project import (
    classify_input_dir,
    discover_project_cgns,
    list_solution_cgns_in_dir,
    list_solution_cgns_in_ipro,
    parse_solution_step,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from iRIC_DataScope.common.cgns_reader import IricStepFrame


def _dedupe_columns(cols: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for c in cols:
        if c and c not in seen:
            out.append(c)
            seen.add(c)
    return out


def _parse_step_number(path: Path) -> int | None:
    m = re.search(r"Result_(\d+)", path.stem, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _list_flow_solution_names(f, zone_path: str) -> list[str]:
    return _list_solution_names_by_prefix(f, zone_path, prefix="flowsolution")


def _list_flow_cell_solution_names(f, zone_path: str) -> list[str]:
    return _list_solution_names_by_prefix(f, zone_path, prefix="flowcellsolution")


def _list_solution_names_by_prefix(f, zone_path: str, *, prefix: str) -> list[str]:
    if zone_path not in f:
        return []
    zone = f[zone_path]
    names: list[str] = []
    for name, obj in zone.items():
        if hasattr(obj, "keys") and name.lower().startswith(prefix):
            names.append(name)
    if not names:
        return []

    def sort_key(n: str):
        m = re.search(r"(\d+)$", n)
        if m:
            return (0, int(m.group(1)))
        return (1, n.lower())

    return sorted(names, key=sort_key)


def _compute_cell_centers(a):
    import numpy as _np

    arr = _np.asarray(a)
    if arr.ndim != 2:
        raise RuntimeError(f"Expected 2D grid for cell-center conversion, got shape={arr.shape}")
    if arr.shape[0] < 2 or arr.shape[1] < 2:
        raise RuntimeError(f"Grid is too small for cell-center conversion: shape={arr.shape}")
    return 0.25 * (arr[:-1, :-1] + arr[:-1, 1:] + arr[1:, :-1] + arr[1:, 1:])


def _list_result_csv_files(input_dir: Path) -> list[Path]:
    files = sorted(input_dir.rglob("Result_*.csv"))
    if not files:
        raise FileNotFoundError(f"Result_*.csv が見つかりません: {input_dir}")
    # step番号が取れるものを優先してソート
    with_steps = []
    without_steps = []
    for p in files:
        n = _parse_step_number(p)
        if n is None:
            without_steps.append(p)
        else:
            with_steps.append((n, p))
    with_steps.sort(key=lambda x: x[0])
    without_steps.sort(key=lambda p: p.name)
    return [p for _, p in with_steps] + without_steps


def _read_iric_result_csv(
    csv_path: Path, *, usecols: list[str] | None = None
) -> tuple[float, int, int, pd.DataFrame]:
    with csv_path.open("r", encoding="utf-8-sig") as f:
        first = f.readline().strip()
        second = f.readline().strip()

    try:
        time_val = float(first.split("=", 1)[1].strip())
    except Exception as e:
        raise ValueError(f"時刻取得エラー: {first}") from e

    try:
        imax_s, jmax_s = second.split(",", 1)
        imax, jmax = int(imax_s), int(jmax_s)
    except Exception:
        imax, jmax = 0, 0

    df = pd.read_csv(csv_path, skiprows=2, encoding="utf-8-sig", usecols=usecols)
    return time_val, imax, jmax, df


@dataclass
class DataSource:
    """
    入力（プロジェクトフォルダ/.ipro/.cgn/CSVフォルダ）を統一的に扱うための薄いアダプタ。
    - CGNS は session 中に一度だけ展開して使い回す（.ipro でも毎回展開しない）
    - ipro 内に Solution*.cgn が存在する場合は、それらをステップ系列として扱う
    """

    input_path: Path
    kind: Literal["cgns", "cgns_series", "csv_dir"]
    grid_location: Literal["node", "cell"] = "node"
    cgn_path: Path | None = None
    cgn_paths: list[Path] | None = None
    _tmpdir: tempfile.TemporaryDirectory | None = None
    zone_path: str = "iRIC/iRICZone"
    case_name: str = "Case1.cgn"
    step_count: int = 1
    steps: list[int] = None  # type: ignore[assignment]
    domain_bounds: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0)
    _csv_files: list[Path] | None = None

    @classmethod
    def from_input(
        cls,
        input_path: Path,
        *,
        grid_location: Literal["node", "cell"] = "node",
    ) -> "DataSource":
        p = Path(input_path)
        if p.is_dir():
            kind = classify_input_dir(p)
            if kind == "csv_dir":
                ds = cls(input_path=p, kind="csv_dir", grid_location=grid_location)
                ds._init_csv_dir()
                return ds
            if list_solution_cgns_in_dir(p):
                ds = cls(input_path=p, kind="cgns_series", grid_location=grid_location)
                ds._init_cgns_series()
            else:
                ds = cls(input_path=p, kind="cgns", grid_location=grid_location)
                ds._init_cgns()
            return ds
        if p.suffix.lower() == ".ipro":
            if list_solution_cgns_in_ipro(p):
                ds = cls(input_path=p, kind="cgns_series", grid_location=grid_location)
                ds._init_cgns_series()
            else:
                ds = cls(input_path=p, kind="cgns", grid_location=grid_location)
                ds._init_cgns()
            return ds
        if p.suffix.lower() == ".cgn":
            ds = cls(input_path=p, kind="cgns", grid_location=grid_location)
            ds._init_cgns()
            return ds
        raise ValueError(f"未対応の入力です: {p}")

    def close(self) -> None:
        if self._tmpdir is not None:
            try:
                self._tmpdir.cleanup()
            finally:
                self._tmpdir = None

    # --- CGNS -------------------------------------------------------------

    def _init_cgns(self) -> None:
        from iRIC_DataScope.common.cgns_reader import resolve_case_cgn
        import h5py
        import numpy as _np

        if self.input_path.is_dir():
            info = discover_project_cgns(self.input_path, case_name=self.case_name)
            if info.kind != "single":
                raise RuntimeError("Solution*.cgn が見つかりました。series モードで初期化してください。")
            self.cgn_path = info.paths[0]
        elif self.input_path.suffix.lower() == ".cgn":
            self.cgn_path = self.input_path
        else:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="ipro_session_")
            td_path = Path(self._tmpdir.name)
            with resolve_case_cgn(self.input_path, self.case_name) as cgn_tmp:
                out = td_path / Path(cgn_tmp).name
                shutil.copyfile(cgn_tmp, out)
                self.cgn_path = out

        if not self.cgn_path:
            raise RuntimeError("cgn_path の初期化に失敗しました")

        with h5py.File(self.cgn_path, "r") as f:
            zone = self.zone_path.strip("/")
            self.step_count = 0
            if self.grid_location == "node":
                ptr_path = f"{zone}/ZoneIterativeData/FlowSolutionPointers"
                if ptr_path in f:
                    try:
                        ptr = f[ptr_path][(" data")]
                        a = _np.asarray(ptr[()])
                        self.step_count = int(a.shape[0])
                    except Exception as e:
                        logger.info("FlowSolutionPointers の読み込みに失敗したためフォールバックします: %s", e)
                        self.step_count = 0

            if self.step_count <= 0:
                if self.grid_location == "cell":
                    sol_names = _list_flow_cell_solution_names(f, zone)
                else:
                    sol_names = _list_flow_solution_names(f, zone)
                if sol_names:
                    self.step_count = len(sol_names)
                else:
                    logger.info("FlowSolution が見つからないため step=1 として扱います")
                    self.step_count = 1
            self.steps = list(range(1, self.step_count + 1))

            x = _np.asarray(f[f"{zone}/GridCoordinates/CoordinateX"][" data"][()])
            y = _np.asarray(f[f"{zone}/GridCoordinates/CoordinateY"][" data"][()])
            if self.grid_location == "cell":
                x = _compute_cell_centers(x)
                y = _compute_cell_centers(y)
            self.domain_bounds = (float(x.min()), float(x.max()), float(y.min()), float(y.max()))

    def _init_cgns_series(self) -> None:
        import h5py
        import numpy as _np

        if self.input_path.is_dir():
            extracted = list_solution_cgns_in_dir(self.input_path)
            if not extracted:
                raise RuntimeError("プロジェクトフォルダ内に Solution*.cgn が見つかりませんでした")
            steps = []
            for idx, p in enumerate(extracted, start=1):
                n = parse_solution_step(p.name)
                steps.append(n if n is not None else idx)
            self.cgn_paths = extracted
            self.steps = steps
            self.step_count = len(extracted)
        else:
            sol_names = list_solution_cgns_in_ipro(self.input_path)
            if not sol_names:
                raise RuntimeError("ipro 内に Solution*.cgn が見つかりませんでした")

            self._tmpdir = tempfile.TemporaryDirectory(prefix="ipro_solution_")
            td_path = Path(self._tmpdir.name)
            extracted = []
            steps: list[int] = []

            with zipfile.ZipFile(self.input_path, "r") as z:
                for idx, name in enumerate(sol_names, start=1):
                    out = td_path / Path(name).name
                    with z.open(name) as src, out.open("wb") as dst:
                        dst.write(src.read())
                    extracted.append(out)
                    n = parse_solution_step(Path(name).name)
                    steps.append(n if n is not None else idx)

            if not extracted:
                raise RuntimeError("Solution*.cgn の展開に失敗しました")

            self.cgn_paths = extracted
            self.steps = steps
            self.step_count = len(extracted)

        zone = self.zone_path.strip("/")
        with h5py.File(extracted[0], "r") as f:
            if zone not in f:
                raise KeyError(f"{zone} が見つかりません: {extracted[0]}")
            x = _np.asarray(f[f"{zone}/GridCoordinates/CoordinateX"][" data"][()])
            y = _np.asarray(f[f"{zone}/GridCoordinates/CoordinateY"][" data"][()])
            if self.grid_location == "cell":
                x = _compute_cell_centers(x)
                y = _compute_cell_centers(y)
            self.domain_bounds = (float(x.min()), float(x.max()), float(y.min()), float(y.max()))

    def list_value_columns(self) -> list[str]:
        if self.kind == "csv_dir":
            return self._list_csv_value_columns()
        return self._list_cgns_value_columns()

    def _list_cgns_value_columns(self) -> list[str]:
        if self.kind == "cgns_series":
            if not self.cgn_paths:
                return []
            cgn_path = self.cgn_paths[0]
        else:
            if not self.cgn_path:
                raise RuntimeError("CGNS が初期化されていません")
            cgn_path = self.cgn_path
        import h5py
        import numpy as _np

        zone = self.zone_path.strip("/")

        with h5py.File(cgn_path, "r") as f:
            x = f[f"{zone}/GridCoordinates/CoordinateX"][" data"]
            if self.grid_location == "cell":
                coord_shape = (int(x.shape[0]) - 1, int(x.shape[1]) - 1)
            else:
                coord_shape = tuple(x.shape)
            first_name = ""
            if self.grid_location == "node":
                ptr_path = f"{zone}/ZoneIterativeData/FlowSolutionPointers"
                if ptr_path in f:
                    try:
                        ptr = _np.asarray(f[ptr_path][" data"][()])
                        if ptr.ndim == 2 and ptr.shape[0] >= 1:
                            first_name = bytes(ptr[0].tolist()).decode("ascii", errors="ignore").replace("\x00", "").strip()
                    except Exception:
                        first_name = ""
            if not first_name:
                if self.grid_location == "cell":
                    sol_names = _list_flow_cell_solution_names(f, zone)
                else:
                    sol_names = _list_flow_solution_names(f, zone)
                if not sol_names:
                    return []
                first_name = sol_names[0]

            sol_path = f"{zone}/{first_name}"
            if sol_path not in f:
                return []
            g = f[sol_path]
            out: list[str] = []
            for k, node in g.items():
                if k == "GridLocation":
                    continue
                if isinstance(node, h5py.Group):
                    if " data" not in node:
                        continue
                    shape = tuple(node[" data"].shape)
                else:
                    shape = tuple(node.shape)
                if shape == coord_shape:
                    out.append(k)
            return sorted(out)

    def iter_frames(self, *, value_col: str) -> Iterable["IricStepFrame"]:
        yield from self.iter_frames_with_columns(value_cols=[value_col])

    def get_frame(self, *, step: int, value_col: str):
        return self.get_frame_with_columns(step=step, value_cols=[value_col])

    def iter_frames_with_columns(self, *, value_cols: list[str]) -> Iterable["IricStepFrame"]:
        cols = _dedupe_columns(value_cols)
        if self.kind == "csv_dir":
            yield from self._iter_csv_frames(value_cols=cols)
            return
        if self.kind == "cgns_series":
            yield from self._iter_cgns_series_frames(value_cols=cols)
            return
        yield from self._iter_cgns_frames(value_cols=cols)

    def get_frame_with_columns(self, *, step: int, value_cols: list[str]):
        cols = _dedupe_columns(value_cols)
        if self.kind == "csv_dir":
            return self._get_csv_frame(step=step, value_cols=cols)
        if self.kind == "cgns_series":
            return self._get_cgns_series_frame(step=step, value_cols=cols)
        return self._get_cgns_frame(step=step, value_cols=cols)

    def _iter_cgns_frames(self, *, value_cols: list[str]):
        from iRIC_DataScope.common.cgns_reader import iter_iric_step_frames

        if not self.cgn_path:
            raise RuntimeError("CGNS が初期化されていません")
        yield from iter_iric_step_frames(
            self.cgn_path,
            zone_path=self.zone_path,
            grid_location=self.grid_location,
            vars_keep=value_cols,
            step_from=1,
            step_to=self.step_count,
            step_skip=1,
            fortran_order=True,
            include_flow_solution=True,
        )

    def _get_cgns_frame(self, *, step: int, value_cols: list[str]):
        from iRIC_DataScope.common.cgns_reader import iter_iric_step_frames

        if not self.cgn_path:
            raise RuntimeError("CGNS が初期化されていません")
        gen = iter_iric_step_frames(
            self.cgn_path,
            zone_path=self.zone_path,
            grid_location=self.grid_location,
            vars_keep=value_cols,
            step_from=step,
            step_to=step,
            step_skip=1,
            fortran_order=True,
            include_flow_solution=True,
        )
        return next(gen)

    def _iter_cgns_series_frames(self, *, value_cols: list[str]):
        from iRIC_DataScope.common.cgns_reader import IricStepFrame, iter_iric_step_frames

        if not self.cgn_paths:
            return
        for idx, cgn_path in enumerate(self.cgn_paths):
            step = self.steps[idx]
            gen = iter_iric_step_frames(
                cgn_path,
                zone_path=self.zone_path,
                grid_location=self.grid_location,
                vars_keep=value_cols,
                step_from=1,
                step_to=1,
                step_skip=1,
                fortran_order=True,
                include_flow_solution=True,
            )
            try:
                frame = next(gen)
            except StopIteration:
                continue
            yield IricStepFrame(
                step=step,
                time=frame.time,
                imax=frame.imax,
                jmax=frame.jmax,
                location=frame.location,
                df=frame.df,
            )

    def _get_cgns_series_frame(self, *, step: int, value_cols: list[str]):
        from iRIC_DataScope.common.cgns_reader import IricStepFrame, iter_iric_step_frames

        if not self.cgn_paths:
            raise FileNotFoundError("Solution CGNS がありません")

        if step in self.steps:
            idx = self.steps.index(step)
        else:
            idx = max(0, min(step - 1, len(self.cgn_paths) - 1))
        cgn_path = self.cgn_paths[idx]

        gen = iter_iric_step_frames(
            cgn_path,
            zone_path=self.zone_path,
            grid_location=self.grid_location,
            vars_keep=value_cols,
            step_from=1,
            step_to=1,
            step_skip=1,
            fortran_order=True,
            include_flow_solution=True,
        )
        frame = next(gen)
        return IricStepFrame(
            step=self.steps[idx],
            time=frame.time,
            imax=frame.imax,
            jmax=frame.jmax,
            location=frame.location,
            df=frame.df,
        )

    # --- CSV dir -----------------------------------------------------------

    def _init_csv_dir(self) -> None:
        files = _list_result_csv_files(self.input_path)
        self._csv_files = files

        steps: list[int] = []
        for i, p in enumerate(files, start=1):
            n = _parse_step_number(p)
            steps.append(n if n is not None else i)
        self.steps = steps
        self.step_count = len(steps)

        # bounds は1ファイル目から推定
        t, imax, jmax, df0 = _read_iric_result_csv(files[0], usecols=["X", "Y"])
        self.domain_bounds = (
            float(df0["X"].min()),
            float(df0["X"].max()),
            float(df0["Y"].min()),
            float(df0["Y"].max()),
        )

    def _list_csv_value_columns(self) -> list[str]:
        if not self._csv_files:
            return []
        p0 = self._csv_files[0]
        df_head = pd.read_csv(p0, skiprows=2, encoding="utf-8-sig", nrows=0)
        cols = [c for c in df_head.columns if c not in {"I", "J", "X", "Y"}]
        return cols

    def _iter_csv_frames(self, *, value_cols: list[str]):
        from iRIC_DataScope.common.cgns_reader import IricStepFrame

        if not self._csv_files:
            return
        for idx, p in enumerate(self._csv_files):
            step = self.steps[idx]
            cols = _dedupe_columns(["I", "J", "X", "Y", *value_cols])
            t, imax, jmax, df = _read_iric_result_csv(p, usecols=cols)
            yield IricStepFrame(step=step, time=t, imax=imax, jmax=jmax, location=None, df=df)

    def _get_csv_frame(self, *, step: int, value_cols: list[str]):
        from iRIC_DataScope.common.cgns_reader import IricStepFrame

        if not self._csv_files:
            raise FileNotFoundError("CSVがありません")
        # step が存在すればそのファイル、無ければ index として扱う
        if step in self.steps:
            idx = self.steps.index(step)
        else:
            idx = max(0, min(step - 1, len(self._csv_files) - 1))
        p = self._csv_files[idx]
        cols = _dedupe_columns(["I", "J", "X", "Y", *value_cols])
        t, imax, jmax, df = _read_iric_result_csv(p, usecols=cols)
        return IricStepFrame(step=self.steps[idx], time=t, imax=imax, jmax=jmax, location=None, df=df)
