from __future__ import annotations

import logging
import math
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Roi:
    xmin: float
    xmax: float
    ymin: float
    ymax: float


@dataclass(frozen=True)
class RoiGrid:
    x: np.ndarray
    y: np.ndarray
    v: np.ndarray
    mask: np.ndarray


def clamp_roi_to_bounds(roi: Roi, bounds: tuple[float, float, float, float]) -> Roi:
    xmin, xmax, ymin, ymax = bounds
    lo_x, hi_x = sorted([roi.xmin, roi.xmax])
    lo_y, hi_y = sorted([roi.ymin, roi.ymax])
    return Roi(
        xmin=max(xmin, lo_x),
        xmax=min(xmax, hi_x),
        ymin=max(ymin, lo_y),
        ymax=min(ymax, hi_y),
    )


def parse_color(color: str) -> str:
    c = (color or "").strip()
    if not c:
        raise ValueError("色が空です")
    # tkinter.colorchooser は "#RRGGBB" を返す想定
    if re.fullmatch(r"#[0-9a-fA-F]{6}", c):
        return c.lower()
    return c


def build_colormap(min_color: str, max_color: str):
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("xy_value_map", [min_color, max_color])
    try:
        cmap.set_bad(color=(0, 0, 0, 0))
    except Exception:
        pass
    return cmap


def frame_to_grids(frame, *, value_col: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    df = frame.df
    required = {"I", "J", "X", "Y", value_col}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise KeyError(f"必要な列が不足しています: {sorted(missing)}")

    imax = int(getattr(frame, "imax", 0) or 0)
    jmax = int(getattr(frame, "jmax", 0) or 0)
    if imax <= 0 or jmax <= 0:
        imax = int(pd.to_numeric(df["I"], errors="coerce").max())
        jmax = int(pd.to_numeric(df["J"], errors="coerce").max())

    sub = df.loc[:, ["I", "J", "X", "Y", value_col]].copy()
    sub["I"] = pd.to_numeric(sub["I"], errors="coerce")
    sub["J"] = pd.to_numeric(sub["J"], errors="coerce")
    sub["X"] = pd.to_numeric(sub["X"], errors="coerce")
    sub["Y"] = pd.to_numeric(sub["Y"], errors="coerce")
    sub[value_col] = pd.to_numeric(sub[value_col], errors="coerce")
    sub = sub.dropna(subset=["I", "J", "X", "Y"])

    sub["I"] = sub["I"].astype(int)
    sub["J"] = sub["J"].astype(int)
    sub = sub.sort_values(["J", "I"])

    expected = imax * jmax
    if expected > 0 and len(sub) == expected:
        x = sub["X"].to_numpy().reshape((jmax, imax))
        y = sub["Y"].to_numpy().reshape((jmax, imax))
        v = sub[value_col].to_numpy().reshape((jmax, imax))
        return x, y, v

    x_piv = sub.pivot(index="J", columns="I", values="X")
    y_piv = sub.pivot(index="J", columns="I", values="Y")
    v_piv = sub.pivot(index="J", columns="I", values=value_col)
    x = x_piv.to_numpy()
    y = y_piv.to_numpy()
    v = v_piv.to_numpy()
    return x, y, v


def slice_grids_to_roi(x: np.ndarray, y: np.ndarray, v: np.ndarray, *, roi: Roi) -> RoiGrid | None:
    if x.shape != y.shape or x.shape != v.shape:
        raise ValueError(f"X/Y/V shape mismatch: x={x.shape}, y={y.shape}, v={v.shape}")

    mask = (roi.xmin <= x) & (x <= roi.xmax) & (roi.ymin <= y) & (y <= roi.ymax)
    if not np.any(mask):
        return None

    jj, ii = np.where(mask)
    j0, j1 = int(jj.min()), int(jj.max())
    i0, i1 = int(ii.min()), int(ii.max())

    # pcolormesh 用に 1セル分だけ余裕を持たせる
    j0 = max(0, j0 - 1)
    i0 = max(0, i0 - 1)
    j1 = min(x.shape[0] - 1, j1 + 1)
    i1 = min(x.shape[1] - 1, i1 + 1)

    xs = x[j0 : j1 + 1, i0 : i1 + 1]
    ys = y[j0 : j1 + 1, i0 : i1 + 1]
    vs = v[j0 : j1 + 1, i0 : i1 + 1]
    ms = mask[j0 : j1 + 1, i0 : i1 + 1]
    return RoiGrid(x=xs, y=ys, v=vs, mask=ms)


def apply_mask_to_values(v: np.ndarray, mask: np.ndarray) -> np.ndarray:
    vv = np.asarray(v, dtype=float).copy()
    vv[~mask] = np.nan
    return vv


def downsample_grid_for_preview(
    grid: RoiGrid, *, max_points: int = 40000
) -> RoiGrid:
    n = int(grid.x.size)
    if n <= max_points:
        return grid
    factor = math.sqrt(n / max_points)
    stride = max(1, int(math.floor(factor)))
    return RoiGrid(
        x=grid.x[::stride, ::stride],
        y=grid.y[::stride, ::stride],
        v=grid.v[::stride, ::stride],
        mask=grid.mask[::stride, ::stride],
    )


def _sanitize_name(name: str) -> str:
    return re.sub(r"[\\\\/:*?\"<>|]+", "_", name)


def _parse_step_number(path: Path) -> int | None:
    m = re.search(r"Result_(\d+)", path.stem, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


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
    入力（.cgn/.ipro/CSVフォルダ）を統一的に扱うための薄いアダプタ。
    - CGNS は session 中に一度だけ展開して使い回す（.ipro でも毎回展開しない）
    """

    input_path: Path
    kind: Literal["cgns", "csv_dir"]
    cgn_path: Path | None = None
    _tmpdir: tempfile.TemporaryDirectory | None = None
    zone_path: str = "iRIC/iRICZone"
    case_name: str = "Case1.cgn"
    step_count: int = 1
    steps: list[int] = None  # type: ignore[assignment]
    domain_bounds: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0)
    _csv_files: list[Path] | None = None

    @classmethod
    def from_input(cls, input_path: Path) -> "DataSource":
        p = Path(input_path)
        if p.is_dir():
            ds = cls(input_path=p, kind="csv_dir")
            ds._init_csv_dir()
            return ds
        if p.suffix.lower() in {".cgn", ".ipro"}:
            ds = cls(input_path=p, kind="cgns")
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

        if self.input_path.suffix.lower() == ".cgn":
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
            ptr = f[f"{zone}/ZoneIterativeData/FlowSolutionPointers"][(" data")]
            a = _np.asarray(ptr[()])
            self.step_count = int(a.shape[0])
            self.steps = list(range(1, self.step_count + 1))

            x = _np.asarray(f[f"{zone}/GridCoordinates/CoordinateX"][" data"][()])
            y = _np.asarray(f[f"{zone}/GridCoordinates/CoordinateY"][" data"][()])
            self.domain_bounds = (float(x.min()), float(x.max()), float(y.min()), float(y.max()))

    def list_value_columns(self) -> list[str]:
        if self.kind == "csv_dir":
            return self._list_csv_value_columns()
        return self._list_cgns_value_columns()

    def _list_cgns_value_columns(self) -> list[str]:
        if not self.cgn_path:
            raise RuntimeError("CGNS が初期化されていません")
        import h5py
        import numpy as _np

        zone = self.zone_path.strip("/")

        with h5py.File(self.cgn_path, "r") as f:
            x = f[f"{zone}/GridCoordinates/CoordinateX"][" data"]
            coord_shape = tuple(x.shape)
            ptr = _np.asarray(f[f"{zone}/ZoneIterativeData/FlowSolutionPointers"][" data"][()])
            if ptr.ndim != 2 or ptr.shape[0] < 1:
                return []
            first_name = bytes(ptr[0].tolist()).decode("ascii", errors="ignore").replace("\x00", "").strip()
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
        if self.kind == "csv_dir":
            yield from self._iter_csv_frames(value_col=value_col)
            return
        yield from self._iter_cgns_frames(value_col=value_col)

    def get_frame(self, *, step: int, value_col: str):
        if self.kind == "csv_dir":
            return self._get_csv_frame(step=step, value_col=value_col)
        return self._get_cgns_frame(step=step, value_col=value_col)

    def _iter_cgns_frames(self, *, value_col: str):
        from iRIC_DataScope.common.cgns_reader import iter_iric_step_frames

        if not self.cgn_path:
            raise RuntimeError("CGNS が初期化されていません")
        yield from iter_iric_step_frames(
            self.cgn_path,
            zone_path=self.zone_path,
            vars_keep=[value_col],
            step_from=1,
            step_to=self.step_count,
            step_skip=1,
            fortran_order=True,
            include_flow_solution=True,
        )

    def _get_cgns_frame(self, *, step: int, value_col: str):
        from iRIC_DataScope.common.cgns_reader import iter_iric_step_frames

        if not self.cgn_path:
            raise RuntimeError("CGNS が初期化されていません")
        gen = iter_iric_step_frames(
            self.cgn_path,
            zone_path=self.zone_path,
            vars_keep=[value_col],
            step_from=step,
            step_to=step,
            step_skip=1,
            fortran_order=True,
            include_flow_solution=True,
        )
        return next(gen)

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

    def _iter_csv_frames(self, *, value_col: str):
        from iRIC_DataScope.common.cgns_reader import IricStepFrame

        if not self._csv_files:
            return
        for idx, p in enumerate(self._csv_files):
            step = self.steps[idx]
            t, imax, jmax, df = _read_iric_result_csv(p, usecols=["I", "J", "X", "Y", value_col])
            yield IricStepFrame(step=step, time=t, imax=imax, jmax=jmax, location=None, df=df)

    def _get_csv_frame(self, *, step: int, value_col: str):
        from iRIC_DataScope.common.cgns_reader import IricStepFrame

        if not self._csv_files:
            raise FileNotFoundError("CSVがありません")
        # step が存在すればそのファイル、無ければ index として扱う
        if step in self.steps:
            idx = self.steps.index(step)
        else:
            idx = max(0, min(step - 1, len(self._csv_files) - 1))
        p = self._csv_files[idx]
        t, imax, jmax, df = _read_iric_result_csv(p, usecols=["I", "J", "X", "Y", value_col])
        return IricStepFrame(step=self.steps[idx], time=t, imax=imax, jmax=jmax, location=None, df=df)


def compute_global_value_range(data_source: DataSource, *, value_col: str, roi: Roi) -> tuple[float, float]:
    vmin = float("inf")
    vmax = float("-inf")
    found = False
    for frame in data_source.iter_frames(value_col=value_col):
        df = frame.df
        sub = df[(roi.xmin <= df["X"]) & (df["X"] <= roi.xmax) & (roi.ymin <= df["Y"]) & (df["Y"] <= roi.ymax)]
        if sub.empty:
            continue
        vals = pd.to_numeric(sub[value_col], errors="coerce").to_numpy()
        finite = vals[np.isfinite(vals)]
        if finite.size == 0:
            continue
        found = True
        vmin = min(vmin, float(finite.min()))
        vmax = max(vmax, float(finite.max()))
    if not found:
        raise ValueError("ROI 内に有効な値が見つかりませんでした。")
    if vmin == vmax:
        vmax = vmin + 1e-12
    return vmin, vmax
