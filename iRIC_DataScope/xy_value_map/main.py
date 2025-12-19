from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import numpy as np

from .processor import (
    DataSource,
    Roi,
    apply_mask_to_values,
    build_colormap,
    compute_global_value_range,
    frame_to_grids,
    slice_grids_to_roi,
)

logger = logging.getLogger(__name__)


def export_xy_value_map_step(
    *,
    data_source: DataSource,
    output_dir: Path,
    step: int,
    value_col: str,
    roi: Roi,
    min_color: str,
    max_color: str,
    vmin: float,
    vmax: float,
    dpi: int = 150,
) -> Path:
    """
    指定した 1 ステップ分の X-Y 分布画像を出力する。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = data_source.get_frame(step=step, value_col=value_col)
    x, y, v = frame_to_grids(frame, value_col=value_col)
    grid = slice_grids_to_roi(x, y, v, roi=roi)
    if grid is None:
        raise ValueError("ROI 内に点がありません。")

    vals = apply_mask_to_values(grid.v, grid.mask)
    finite = vals[np.isfinite(vals)]
    if finite.size == 0:
        raise ValueError("ROI 内の Value が全て NaN/Inf です。")

    cmap = build_colormap(min_color, max_color)

    # ROI の縦横比に合わせて figsize を固定
    x_span = max(roi.xmax - roi.xmin, 1e-12)
    y_span = max(roi.ymax - roi.ymin, 1e-12)
    base_w = 8.0
    base_h = base_w * (y_span / x_span)
    base_h = min(max(base_h, 3.5), 12.0)
    figsize = (base_w, base_h)

    from matplotlib.figure import Figure

    fig = Figure(figsize=figsize, dpi=dpi, constrained_layout=True)
    ax = fig.add_subplot(111)
    m = ax.pcolormesh(grid.x, grid.y, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="gouraud")
    fig.colorbar(m, ax=ax)
    ax.set_title(f"step={frame.step}  t={frame.time:g}  value={value_col}")
    ax.set_xlim(roi.xmin, roi.xmax)
    ax.set_ylim(roi.ymin, roi.ymax)
    ax.set_aspect("equal", adjustable="box")

    digits = max(4, len(str(data_source.step_count)))
    out_path = output_dir / f"step_{frame.step:0{digits}d}.png"
    fig.savefig(out_path)
    return out_path


def export_xy_value_maps(
    *,
    data_source: DataSource,
    output_dir: Path,
    value_col: str,
    roi: Roi,
    min_color: str,
    max_color: str,
    scale_mode: Literal["global", "manual"] = "global",
    manual_scale: tuple[float, float] | None = None,
    progress=None,
    dpi: int = 150,
) -> Path:
    """
    全ステップ分の X-Y 分布画像を出力する。

    ROI 内が空の場合はそのステップをスキップし、ログに残す。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cmap = build_colormap(min_color, max_color)

    if scale_mode == "manual":
        if manual_scale is None:
            raise ValueError("manual_scale が必要です")
        vmin, vmax = manual_scale
    else:
        vmin, vmax = compute_global_value_range(data_source, value_col=value_col, roi=roi)

    total = data_source.step_count
    digits = max(4, len(str(total)))

    # ROI の縦横比に合わせて figsize を固定（全ステップ同一）
    x_span = max(roi.xmax - roi.xmin, 1e-12)
    y_span = max(roi.ymax - roi.ymin, 1e-12)
    base_w = 8.0
    base_h = base_w * (y_span / x_span)
    base_h = min(max(base_h, 3.5), 12.0)
    figsize = (base_w, base_h)

    from matplotlib.figure import Figure

    current = 0
    for frame in data_source.iter_frames(value_col=value_col):
        current += 1
        if progress is not None:
            progress.update(current=current, total=total, text=f"出力中: {current}/{total} (step={frame.step})")

        try:
            x, y, v = frame_to_grids(frame, value_col=value_col)
            grid = slice_grids_to_roi(x, y, v, roi=roi)
        except Exception:
            logger.exception("Skip step=%s: 描画用データ準備に失敗", frame.step)
            continue

        if grid is None:
            logger.info("Skip step=%s: ROI内に点がありません", frame.step)
            continue

        vals = apply_mask_to_values(grid.v, grid.mask)
        finite = vals[np.isfinite(vals)]
        if finite.size == 0:
            logger.info("Skip step=%s: ROI内のValueが全てNaN/Infです", frame.step)
            continue

        fig = Figure(figsize=figsize, dpi=dpi, constrained_layout=True)
        ax = fig.add_subplot(111)
        m = ax.pcolormesh(grid.x, grid.y, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="gouraud")
        fig.colorbar(m, ax=ax)
        ax.set_title(f"step={frame.step}  t={frame.time:g}  value={value_col}")
        ax.set_xlim(roi.xmin, roi.xmax)
        ax.set_ylim(roi.ymin, roi.ymax)
        ax.set_aspect("equal", adjustable="box")

        out_path = output_dir / f"step_{frame.step:0{digits}d}.png"
        fig.savefig(out_path)

    if progress is not None:
        progress.update(current=total, total=total, text="完了")

    return output_dir
