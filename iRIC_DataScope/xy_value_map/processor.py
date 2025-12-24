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
    cx: float
    cy: float
    width: float
    height: float
    angle_deg: float = 0.0


@dataclass(frozen=True)
class Bounds:
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
    width = abs(float(roi.width))
    height = abs(float(roi.height))
    max_width = max(xmax - xmin, 1e-12)
    max_height = max(ymax - ymin, 1e-12)
    width = min(width, max_width)
    height = min(height, max_height)
    cx = min(max(float(roi.cx), xmin), xmax)
    cy = min(max(float(roi.cy), ymin), ymax)
    return Roi(cx=cx, cy=cy, width=width, height=height, angle_deg=float(roi.angle_deg))


def roi_axis_bounds(roi: Roi) -> Bounds:
    half_w = roi.width / 2.0
    half_h = roi.height / 2.0
    return Bounds(
        xmin=roi.cx - half_w,
        xmax=roi.cx + half_w,
        ymin=roi.cy - half_h,
        ymax=roi.cy + half_h,
    )


def roi_corners(roi: Roi) -> np.ndarray:
    theta = math.radians(roi.angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    ux = np.array([cos_t, sin_t])
    uy = np.array([-sin_t, cos_t])
    dx = 0.5 * roi.width * ux
    dy = 0.5 * roi.height * uy
    c = np.array([roi.cx, roi.cy])
    return np.vstack(
        [
            c - dx - dy,
            c + dx - dy,
            c + dx + dy,
            c - dx + dy,
        ]
    )


def roi_bounds(roi: Roi) -> Bounds:
    corners = roi_corners(roi)
    return Bounds(
        xmin=float(np.min(corners[:, 0])),
        xmax=float(np.max(corners[:, 0])),
        ymin=float(np.min(corners[:, 1])),
        ymax=float(np.max(corners[:, 1])),
    )


def parse_color(color: str) -> str:
    c = (color or "").strip()
    if not c:
        raise ValueError("色が空です")
    # tkinter.colorchooser は "#RRGGBB" を返す想定
    if re.fullmatch(r"#[0-9a-fA-F]{6}", c):
        return c.lower()
    return c


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


def slice_grids_to_bounds(
    x: np.ndarray, y: np.ndarray, v: np.ndarray, *, bounds: Bounds
) -> RoiGrid | None:
    if x.shape != y.shape or x.shape != v.shape:
        raise ValueError(f"X/Y/V shape mismatch: x={x.shape}, y={y.shape}, v={v.shape}")

    mask = (bounds.xmin <= x) & (x <= bounds.xmax) & (bounds.ymin <= y) & (y <= bounds.ymax)
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


def estimate_grid_spacing(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    def _median_spacing(dx: np.ndarray, dy: np.ndarray) -> float | None:
        dist = np.hypot(dx, dy).ravel()
        dist = dist[np.isfinite(dist) & (dist > 0)]
        if dist.size == 0:
            return None
        return float(np.median(dist))

    dx = _median_spacing(np.diff(x, axis=1), np.diff(y, axis=1))
    dy = _median_spacing(np.diff(x, axis=0), np.diff(y, axis=0))

    if dx is None:
        dx = float((np.nanmax(x) - np.nanmin(x)) / max(x.shape[1] - 1, 1))
    if dy is None:
        dy = float((np.nanmax(y) - np.nanmin(y)) / max(y.shape[0] - 1, 1))
    if dx <= 0 or not np.isfinite(dx):
        dx = 1.0
    if dy <= 0 or not np.isfinite(dy):
        dy = 1.0
    return dx, dy


def rotate_xy(
    x: np.ndarray, y: np.ndarray, *, center: tuple[float, float], angle_deg: float
) -> tuple[np.ndarray, np.ndarray]:
    cx, cy = center
    theta = math.radians(angle_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    x0 = x - cx
    y0 = y - cy
    xr = cos_t * x0 - sin_t * y0 + cx
    yr = sin_t * x0 + cos_t * y0 + cy
    return xr, yr


def resample_grid_ij(
    grid: RoiGrid,
    *,
    dx: float,
    dy: float,
    method: str = "linear",
    mask: np.ndarray | None = None,
) -> RoiGrid:
    if dx <= 0 or dy <= 0:
        raise ValueError("dx/dy は正の値である必要があります。")
    base_dx, base_dy = estimate_grid_spacing(grid.x, grid.y)
    fx = base_dx / dx if dx > 0 else 1.0
    fy = base_dy / dy if dy > 0 else 1.0
    if not np.isfinite(fx) or fx <= 0:
        fx = 1.0
    if not np.isfinite(fy) or fy <= 0:
        fy = 1.0
    if abs(fx - 1.0) < 1e-3 and abs(fy - 1.0) < 1e-3:
        if mask is None:
            return RoiGrid(x=grid.x, y=grid.y, v=grid.v, mask=np.ones_like(grid.v, dtype=bool))
        m = np.asarray(mask, dtype=bool)
        v2 = np.asarray(grid.v, dtype=float).copy()
        v2[~m] = np.nan
        return RoiGrid(x=grid.x, y=grid.y, v=v2, mask=m)

    from scipy.ndimage import zoom

    order = 1 if method == "linear" else 3
    x2 = zoom(grid.x, zoom=(fy, fx), order=order)
    y2 = zoom(grid.y, zoom=(fy, fx), order=order)
    v = np.asarray(grid.v, dtype=float)
    if mask is None:
        v2 = zoom(v, zoom=(fy, fx), order=order)
        return RoiGrid(x=x2, y=y2, v=v2, mask=np.ones_like(v2, dtype=bool))

    m = np.asarray(mask, dtype=float)
    m = np.where(np.isfinite(v) & (m > 0), 1.0, 0.0)
    v_weighted = np.where(m > 0, v, 0.0)
    v2 = zoom(v_weighted, zoom=(fy, fx), order=order)
    w2 = zoom(m, zoom=(fy, fx), order=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        v2 = v2 / w2
    mask2 = w2 > 1e-6
    v2[~mask2] = np.nan
    return RoiGrid(x=x2, y=y2, v=v2, mask=mask2)


def prepare_rotated_grid_from_grid(
    grid: RoiGrid,
    *,
    roi: Roi,
    dx: float,
    dy: float,
    local_origin: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    center = (roi.cx, roi.cy)
    bounds = roi_axis_bounds(roi)
    x_rot0, y_rot0 = rotate_xy(grid.x, grid.y, center=center, angle_deg=-roi.angle_deg)
    mask0 = (
        (bounds.xmin <= x_rot0)
        & (x_rot0 <= bounds.xmax)
        & (bounds.ymin <= y_rot0)
        & (y_rot0 <= bounds.ymax)
    )
    if grid.mask is not None:
        mask0 &= grid.mask
    mask0 &= np.isfinite(grid.v)

    grid = resample_grid_ij(grid, dx=dx, dy=dy, mask=mask0)
    x_rot, y_rot = rotate_xy(grid.x, grid.y, center=center, angle_deg=-roi.angle_deg)
    mask = (bounds.xmin <= x_rot) & (x_rot <= bounds.xmax) & (bounds.ymin <= y_rot) & (y_rot <= bounds.ymax)
    mask &= grid.mask
    vals = np.asarray(grid.v, dtype=float)
    if local_origin:
        x_rot = x_rot - bounds.xmin
        y_rot = y_rot - bounds.ymin
    return x_rot, y_rot, vals, mask


def prepare_rotated_grid(
    x: np.ndarray,
    y: np.ndarray,
    v: np.ndarray,
    *,
    roi: Roi,
    dx: float,
    dy: float,
    local_origin: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    bounds = roi_bounds(roi)
    grid = slice_grids_to_bounds(x, y, v, bounds=bounds)
    if grid is None:
        return None
    return prepare_rotated_grid_from_grid(
        grid,
        roi=roi,
        dx=dx,
        dy=dy,
        local_origin=local_origin,
    )


def compute_global_value_range_rotated(
    data_source: DataSource,
    *,
    value_col: str,
    roi: Roi,
    dx: float,
    dy: float,
) -> tuple[float, float]:
    vmin = float("inf")
    vmax = float("-inf")
    found = False
    bounds = roi_bounds(roi)

    for frame in data_source.iter_frames(value_col=value_col):
        try:
            x, y, v = frame_to_grids(frame, value_col=value_col)
            grid = slice_grids_to_bounds(x, y, v, bounds=bounds)
            if grid is None:
                continue
            _, _, vals, mask = prepare_rotated_grid_from_grid(
                grid,
                roi=roi,
                dx=dx,
                dy=dy,
            )
        except Exception:
            logger.exception("globalスケール計算に失敗: step=%s", frame.step)
            continue

        finite = vals[np.isfinite(vals) & mask]
        if finite.size == 0:
            continue
        found = True
        vmin = min(vmin, float(finite.min()))
        vmax = max(vmax, float(finite.max()))

    if not found:
        raise ValueError("No valid values found in ROI.")
    if vmin == vmax:
        vmax = vmin + 1e-12
    return vmin, vmax
