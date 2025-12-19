from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from iRIC_DataScope.common.iric_data_source import DataSource

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
