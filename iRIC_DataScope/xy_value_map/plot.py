from __future__ import annotations

import logging
from typing import Literal

import numpy as np

from .style import ensure_japanese_font

logger = logging.getLogger(__name__)


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
    mx = min(max(margin_x_pct, 0.0), 50.0) / 100.0
    my = min(max(margin_y_pct, 0.0), 50.0) / 100.0
    if mx > 0.0 or my > 0.0:
        try:
            ax.figure.set_constrained_layout(False)
            ax.figure.subplots_adjust(left=mx, right=1.0 - mx, bottom=my, top=1.0 - my)
        except Exception:
            pass


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


def render_xy_value_map(
    *,
    fig,
    ax,
    x,
    y,
    vals,
    roi,
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
    """プレビュー／出力共通の描画処理"""
    ensure_japanese_font()

    width = max(float(roi.width), 1e-12)
    height = max(float(roi.height), 1e-12)

    # pcolormesh
    m = ax.pcolormesh(x, y, vals, cmap=cmap, vmin=vmin, vmax=vmax, shading="gouraud")

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
