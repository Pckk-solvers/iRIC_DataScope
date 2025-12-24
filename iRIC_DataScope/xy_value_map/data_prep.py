"""GUIから呼ばれるデータ準備（ROI切り出し・補間・最小最大）をまとめる。"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .processor import (
    Roi,
    RoiGrid,
    estimate_grid_spacing,
    frame_to_grids,
    prepare_rotated_grid,
    prepare_rotated_grid_from_grid,
    roi_bounds,
    slice_grids_to_bounds,
    downsample_grid_for_preview,
)


@dataclass(frozen=True)
class PreviewGridResult:
    x: np.ndarray
    y: np.ndarray
    values: np.ndarray
    mask: np.ndarray
    status_note: str


def estimate_base_spacing_from_frame(frame, *, value_col: str) -> tuple[float, float]:
    x, y, _ = frame_to_grids(frame, value_col=value_col)
    return estimate_grid_spacing(x, y)


def slice_frame_to_roi_grid(frame, *, value_col: str, roi: Roi) -> RoiGrid | None:
    # ROIの軸平行外接矩形で粗く切り出してから補間へ渡す。
    x, y, v = frame_to_grids(frame, value_col=value_col)
    bounds = roi_bounds(roi)
    return slice_grids_to_bounds(x, y, v, bounds=bounds)


def build_edit_grid(frame, *, value_col: str, max_points: int = 40000) -> RoiGrid:
    # 編集キャンバス用に点数を落として負荷を抑える。
    x, y, v = frame_to_grids(frame, value_col=value_col)
    grid = RoiGrid(x=x, y=y, v=v, mask=np.ones_like(v, dtype=bool))
    return downsample_grid_for_preview(grid, max_points=max_points)


def adjust_preview_resolution(grid: RoiGrid, dx: float, dy: float, *, preview_max: int) -> tuple[float, float, str]:
    # 予測点数が多い場合は解像度を下げてプレビューの負荷を軽減する。
    dx_p, dy_p = dx, dy
    base_dx, base_dy = estimate_grid_spacing(grid.x, grid.y)
    fx = base_dx / dx if dx > 0 else 1.0
    fy = base_dy / dy if dy > 0 else 1.0
    if not np.isfinite(fx) or fx <= 0:
        fx = 1.0
    if not np.isfinite(fy) or fy <= 0:
        fy = 1.0
    est_points = grid.x.size * fx * fy
    if est_points <= preview_max:
        return dx_p, dy_p, ""
    scale_factor = math.sqrt(est_points / preview_max)
    dx_p = dx * scale_factor
    dy_p = dy * scale_factor
    scale_preview = (base_dx / dx_p) if dx_p > 0 else 0.0
    if scale_preview > 0:
        note = f"プレビュー軽量化のため解像度倍率を {scale_preview:.3g} に調整しました"
    else:
        note = "プレビュー軽量化のため解像度を調整しました"
    return dx_p, dy_p, note


def prepare_preview_grid(
    grid: RoiGrid,
    *,
    roi: Roi,
    dx: float,
    dy: float,
    preview_dragging: bool,
    preview_max: int = 60000,
) -> PreviewGridResult:
    # ドラッグ中のみ解像度を落とし、通常時は指定解像度で補間する。
    if preview_dragging:
        dx_p, dy_p, status_note = adjust_preview_resolution(grid, dx, dy, preview_max=preview_max)
    else:
        dx_p, dy_p, status_note = dx, dy, ""
    out_x, out_y, vals_resampled, mask = prepare_rotated_grid_from_grid(
        grid,
        roi=roi,
        dx=dx_p,
        dy=dy_p,
        local_origin=True,
    )
    return PreviewGridResult(
        x=out_x,
        y=out_y,
        values=vals_resampled,
        mask=mask,
        status_note=status_note,
    )


def compute_roi_minmax(
    frame,
    *,
    value_col: str,
    roi: Roi,
    dx: float,
    dy: float,
) -> tuple[float, float] | None:
    # 1ステップ分のROI内でmin/maxを算出する。
    x, y, v = frame_to_grids(frame, value_col=value_col)
    prepared = prepare_rotated_grid(
        x,
        y,
        v,
        roi=roi,
        dx=dx,
        dy=dy,
        local_origin=True,
    )
    if prepared is None:
        return None
    _, _, vals, mask = prepared
    finite = vals[np.isfinite(vals) & mask]
    if finite.size == 0:
        return None
    vmin = float(finite.min())
    vmax = float(finite.max())
    if vmin == vmax:
        vmax = vmin + 1e-12
    return vmin, vmax
