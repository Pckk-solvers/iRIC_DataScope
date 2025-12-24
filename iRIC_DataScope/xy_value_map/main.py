from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import numpy as np

from .plot import _build_title, render_xy_value_map
from .processor import (
    DataSource,
    Roi,
    build_colormap,
    compute_global_value_range_rotated,
    frame_to_grids,
    prepare_rotated_grid,
)

logger = logging.getLogger(__name__)


def figure_size_from_roi(
    roi: Roi,
    *,
    base_short: float = 6.0,
    min_side: float = 3.5,
    max_side: float = 12.0,
) -> tuple[float, float]:
    width = max(float(roi.width), 1e-12)
    height = max(float(roi.height), 1e-12)
    aspect = height / width if width > 0 else 1.0
    if not np.isfinite(aspect) or aspect <= 0:
        aspect = 1.0
    if aspect >= 1.0:
        w = base_short
        h = base_short * aspect
    else:
        h = base_short
        w = base_short / aspect
    w = min(max(w, min_side), max_side)
    h = min(max(h, min_side), max_side)
    return (w, h)


def compute_figure_size(
    *,
    roi: Roi,
    base_short: float = 6.0,
    min_side: float = 3.5,
    max_side: float = 12.0,
    pad_x_inch: float = 0.4,
    pad_y_inch: float = 0.4,
    title_inch: float = 0.3,
    cbar_width_inch: float = 0.3,
    cbar_pad_inch: float = 0.1,
) -> tuple[float, float]:
    """
    ROI のアスペクトと飾りの固定インチから figsize を計算する
    """
    w_data, h_data = figure_size_from_roi(
        roi,
        base_short=base_short,
        min_side=min_side,
        max_side=max_side,
    )
    # 左右・上下マージンを足し込む
    w_total = w_data + 2 * pad_x_inch + cbar_pad_inch + cbar_width_inch
    h_total = h_data + 2 * pad_y_inch + title_inch
    return (w_total, h_total)


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
    dpi: int = 100,
    show_title: bool = True,
    title_text: str = "",
    show_ticks: bool = True,
    show_frame: bool = True,
    show_cbar: bool = True,
    cbar_label: str = "",
    title_font_size: float | None = None,
    tick_font_size: float | None = None,
    cbar_label_font_size: float | None = None,
    margin_x_pct: float = 0.0,
    margin_y_pct: float = 0.0,
    pad_inches: float = 0.02,
    figsize: tuple[float, float] | None = None,
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

    # ベース figsize（指定なければ固定）に pad_inches を足し込んだ実寸で描画
    if figsize is None:
        base_figsize = (6.0, 4.0)
    else:
        base_figsize = figsize
    eff_figsize = (
        max(base_figsize[0] + 2.0 * max(pad_inches, 0.0), 1e-6),
        max(base_figsize[1] + 2.0 * max(pad_inches, 0.0), 1e-6),
    )

    from matplotlib.figure import Figure

    fig = Figure(figsize=eff_figsize, dpi=dpi, constrained_layout=True)
    ax = fig.add_subplot(111)
    title = _build_title(
        step=frame.step,
        t=frame.time,
        value_col=value_col,
        show_title=show_title,
        title_text=title_text,
    )
    render_xy_value_map(
        fig=fig,
        ax=ax,
        x=out_x,
        y=out_y,
        vals=vals,
        roi=roi,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        title=title,
        show_ticks=show_ticks,
        show_frame=show_frame,
        show_cbar=show_cbar,
        margin_x_pct=margin_x_pct,
        margin_y_pct=margin_y_pct,
        cbar_label=cbar_label,
        title_font_size=title_font_size,
        tick_font_size=tick_font_size,
        cbar_label_font_size=cbar_label_font_size,
    )

    digits = max(4, len(str(data_source.step_count)))
    out_path = output_dir / f"step_{frame.step:0{digits}d}.png"
    fig.savefig(out_path, bbox_inches="tight", pad_inches=pad_inches)
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
    dpi: int = 100,
    show_title: bool = True,
    title_text: str = "",
    show_ticks: bool = True,
    show_frame: bool = True,
    show_cbar: bool = True,
    cbar_label: str = "",
    title_font_size: float | None = None,
    tick_font_size: float | None = None,
    cbar_label_font_size: float | None = None,
    margin_x_pct: float = 0.0,
    margin_y_pct: float = 0.0,
    pad_inches: float = 0.02,
    figsize: tuple[float, float] | None = None,
    step_start: int | None = None,
    step_end: int | None = None,
    step_skip: int = 0,
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

    total_steps = max(1, int(getattr(data_source, "step_count", 1)))
    digits = max(4, len(str(total_steps)))

    try:
        start = int(step_start or 1)
    except Exception:
        start = 1
    try:
        end = int(step_end or total_steps)
    except Exception:
        end = total_steps
    start = max(1, min(start, total_steps))
    end = max(1, min(end, total_steps))
    if end < start:
        end = start
    if step_skip < 0:
        step_skip = 0
    stride = int(step_skip) + 1
    target_total = len(range(start, end + 1, stride))

    # ベース figsize（指定なければ固定）に pad_inches を足し込んだ実寸で描画
    if figsize is None:
        base_figsize = (6.0, 4.0)
    else:
        base_figsize = figsize
    eff_figsize = (
        max(base_figsize[0] + 2.0 * max(pad_inches, 0.0), 1e-6),
        max(base_figsize[1] + 2.0 * max(pad_inches, 0.0), 1e-6),
    )

    from matplotlib.figure import Figure

    current = 0
    for frame in data_source.iter_frames(value_col=value_col):
        if frame.step < start or frame.step > end:
            continue
        if (frame.step - start) % stride != 0:
            continue
        current += 1
        if progress is not None:
            progress.update(
                current=current,
                total=target_total,
                text=f"出力中: {current}/{target_total} (step={frame.step})",
            )

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

        fig = Figure(figsize=eff_figsize, dpi=dpi, constrained_layout=True)
        ax = fig.add_subplot(111)
        title = _build_title(
            step=frame.step,
            t=frame.time,
            value_col=value_col,
            show_title=show_title,
            title_text=title_text,
        )
        render_xy_value_map(
            fig=fig,
            ax=ax,
            x=out_x,
            y=out_y,
            vals=vals,
            roi=roi,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            title=title,
            show_ticks=show_ticks,
            show_frame=show_frame,
            show_cbar=show_cbar,
            margin_x_pct=margin_x_pct,
            margin_y_pct=margin_y_pct,
            title_font_size=title_font_size,
            tick_font_size=tick_font_size,
            cbar_label_font_size=cbar_label_font_size,
            cbar_label=cbar_label,
        )

        out_path = output_dir / f"step_{frame.step:0{digits}d}.png"
        fig.savefig(out_path, bbox_inches="tight", pad_inches=pad_inches)

    if progress is not None:
        progress.update(current=target_total, total=target_total, text="完了")

    return output_dir
