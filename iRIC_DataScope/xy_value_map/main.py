from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import numpy as np
from matplotlib import font_manager, rcParams

from .processor import (
    DataSource,
    Roi,
    build_colormap,
    compute_global_value_range_rotated,
    frame_to_grids,
    prepare_rotated_grid,
)

logger = logging.getLogger(__name__)
_JP_FONT_SET = False


def _ensure_japanese_font():
    """Try to set a font that can render Japanese to avoid glyph warnings."""
    global _JP_FONT_SET
    if _JP_FONT_SET:
        return
    candidates = ["Yu Gothic", "Yu Gothic UI", "Meiryo", "MS Gothic", "Noto Sans CJK JP"]
    for name in candidates:
        try:
            path = font_manager.findfont(name, fallback_to_default=False)
            if path:
                rcParams["font.family"] = name
                rcParams["axes.unicode_minus"] = False
                _JP_FONT_SET = True
                return
        except Exception:
            continue
    # fallback: at least avoid minus glyph issues
    rcParams["axes.unicode_minus"] = False
    _JP_FONT_SET = True


def _build_title(
    *,
    step: int,
    t: float,
    value_col: str,
    show_title: bool,
    title_text: str = "",
) -> str:
    if not show_title:
        return ""
    if title_text:
        return title_text
    return ""


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


def _apply_plot_options(
    ax,
    *,
    show_ticks: bool,
    show_frame: bool,
    margin_x_pct: float = 0.0,
    margin_y_pct: float = 0.0,
    tick_labelsize: float | None = None,
):
    ax.tick_params(
        bottom=show_ticks,
        left=show_ticks,
        labelbottom=show_ticks,
        labelleft=show_ticks,
        labelsize=tick_labelsize,
    )
    for spine in ax.spines.values():
        spine.set_visible(show_frame)


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


def render_xy_value_map(
    *,
    fig,
    ax,
    x,
    y,
    vals,
    roi: Roi,
    cmap,
    vmin: float,
    vmax: float,
    title: str,
    show_ticks: bool,
    show_frame: bool,
    show_cbar: bool,
    margin_x_pct: float = 0.0,
    margin_y_pct: float = 0.0,
    cbar_label: str = "",
    title_font_size: float | None = None,
    tick_font_size: float | None = None,
    cbar_label_font_size: float | None = None,
):
    """
    プレビュー／出力共通の描画処理
    """
    _ensure_japanese_font()
    # クリップ
    from matplotlib.patches import Rectangle

    width = max(float(roi.width), 1e-12)
    height = max(float(roi.height), 1e-12)
    clip_rect = Rectangle((0.0, 0.0), width, height, transform=ax.transData)

    # pcolormesh
    m = ax.pcolormesh(x, y, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="gouraud")
    m.set_clip_path(clip_rect)

    # オプション適用
    _apply_plot_options(
        ax,
        show_ticks=show_ticks,
        show_frame=show_frame,
        margin_x_pct=margin_x_pct,
        margin_y_pct=margin_y_pct,
        tick_labelsize=tick_font_size,
    )

    # タイトル
    if title:
        ax.set_title(title, fontsize=title_font_size)

    # 軸範囲
    ax.set_xlim(0.0, width)
    ax.set_ylim(0.0, height)
    ax.set_aspect("equal", adjustable="box")

    # カラーバー
    if show_cbar:
        try:
            from mpl_toolkits.axes_grid1 import make_axes_locatable

            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.05)
            cb = fig.colorbar(m, cax=cax)
        except Exception:
            cb = fig.colorbar(m, ax=ax, fraction=0.04, pad=0.01)

        if cbar_label:
            try:
                cb.ax.set_ylabel(cbar_label, fontsize=cbar_label_font_size, rotation=270, labelpad=10)
            except Exception:
                pass
        if tick_font_size is not None:
            try:
                cb.ax.tick_params(labelsize=tick_font_size)
            except Exception:
                pass

    return m

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
        progress.update(current=total, total=total, text="完了")

    return output_dir
