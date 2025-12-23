from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import numpy as np

from .processor import (
    DataSource,
    Roi,
    build_colormap,
    compute_global_value_range_rotated,
    frame_to_grids,
    prepare_rotated_grid,
)

logger = logging.getLogger(__name__)


def _build_title(
    *,
    step: int,
    t: float,
    value_col: str,
    show_title: bool,
    show_step: bool,
    show_time: bool,
    show_value: bool,
) -> str:
    if not show_title:
        return ""
    parts: list[str] = []
    if show_step:
        parts.append(f"step={step}")
    if show_time:
        parts.append(f"t={t:g}")
    if show_value:
        parts.append(f"value={value_col}")
    return "  ".join(parts)


def _apply_plot_options(ax, *, show_ticks: bool, show_frame: bool):
    ax.tick_params(
        bottom=show_ticks,
        left=show_ticks,
        labelbottom=show_ticks,
        labelleft=show_ticks,
    )
    for spine in ax.spines.values():
        spine.set_visible(show_frame)

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
    dx: float = 1.0,
    dy: float = 1.0,
    dpi: int = 150,
    show_title: bool = True,
    show_step: bool = True,
    show_time: bool = True,
    show_value: bool = True,
    show_ticks: bool = True,
    show_frame: bool = True,
    show_cbar: bool = True,
) -> Path:
    """
    指定した 1 ステップ分の X-Y 分布画像を出力する。

    ROI の角度と dx/dy を反映して I/J 補間後に描画する。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = data_source.get_frame(step=step, value_col=value_col)
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
        raise ValueError("ROI 内に点がありません。")

    out_x, out_y, vals, mask = prepared
    finite = vals[np.isfinite(vals) & mask]
    if finite.size == 0:
        raise ValueError("ROI 内の Value が全て NaN/Inf です。")

    cmap = build_colormap(min_color, max_color)

    # ROI の縦横比に合わせて figsize を固定
    width = max(float(roi.width), 1e-12)
    height = max(float(roi.height), 1e-12)
    base_w = 8.0
    base_h = base_w * (height / width)
    base_h = min(max(base_h, 3.5), 12.0)
    figsize = (base_w, base_h)

    from matplotlib.figure import Figure

    fig = Figure(figsize=figsize, dpi=dpi, constrained_layout=True)
    ax = fig.add_subplot(111)
    m = ax.pcolormesh(out_x, out_y, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="gouraud")
    from matplotlib.patches import Rectangle

    clip_rect = Rectangle((0.0, 0.0), width, height, transform=ax.transData)
    m.set_clip_path(clip_rect)
    if show_cbar:
        fig.colorbar(m, ax=ax)
    title = _build_title(
        step=frame.step,
        t=frame.time,
        value_col=value_col,
        show_title=show_title,
        show_step=show_step,
        show_time=show_time,
        show_value=show_value,
    )
    ax.set_title(title)
    _apply_plot_options(ax, show_ticks=show_ticks, show_frame=show_frame)
    ax.set_xlim(0.0, width)
    ax.set_ylim(0.0, height)
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
    dx: float = 1.0,
    dy: float = 1.0,
    progress=None,
    dpi: int = 150,
    show_title: bool = True,
    show_step: bool = True,
    show_time: bool = True,
    show_value: bool = True,
    show_ticks: bool = True,
    show_frame: bool = True,
    show_cbar: bool = True,
) -> Path:
    """
    全ステップ分の X-Y 分布画像を出力する。

    ROI 内が空の場合はそのステップをスキップし、ログに残す。
    ROI の角度と dx/dy を反映して I/J 補間後に描画する。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cmap = build_colormap(min_color, max_color)

    if scale_mode == "manual":
        if manual_scale is None:
            raise ValueError("manual_scale が必要です")
        vmin, vmax = manual_scale
    else:
        vmin, vmax = compute_global_value_range_rotated(
            data_source,
            value_col=value_col,
            roi=roi,
            dx=dx,
            dy=dy,
        )

    total = data_source.step_count
    digits = max(4, len(str(total)))

    # ROI の縦横比に合わせて figsize を固定（全ステップ同一）
    width = max(float(roi.width), 1e-12)
    height = max(float(roi.height), 1e-12)
    base_w = 8.0
    base_h = base_w * (height / width)
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
                logger.info("Skip step=%s: ROI内に点がありません", frame.step)
                continue
            out_x, out_y, vals, mask = prepared
        except Exception:
            logger.exception("Skip step=%s: 描画用データ準備に失敗", frame.step)
            continue
        finite = vals[np.isfinite(vals) & mask]
        if finite.size == 0:
            logger.info("Skip step=%s: ROI内のValueが全てNaN/Infです", frame.step)
            continue

        fig = Figure(figsize=figsize, dpi=dpi, constrained_layout=True)
        ax = fig.add_subplot(111)
        m = ax.pcolormesh(out_x, out_y, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="gouraud")
        from matplotlib.patches import Rectangle

        clip_rect = Rectangle((0.0, 0.0), width, height, transform=ax.transData)
        m.set_clip_path(clip_rect)
        if show_cbar:
            fig.colorbar(m, ax=ax)
        title = _build_title(
            step=frame.step,
            t=frame.time,
            value_col=value_col,
            show_title=show_title,
            show_step=show_step,
            show_time=show_time,
            show_value=show_value,
        )
        ax.set_title(title)
        _apply_plot_options(ax, show_ticks=show_ticks, show_frame=show_frame)
        ax.set_xlim(0.0, width)
        ax.set_ylim(0.0, height)
        ax.set_aspect("equal", adjustable="box")

        out_path = output_dir / f"step_{frame.step:0{digits}d}.png"
        fig.savefig(out_path)

    if progress is not None:
        progress.update(current=total, total=total, text="完了")

    return output_dir
