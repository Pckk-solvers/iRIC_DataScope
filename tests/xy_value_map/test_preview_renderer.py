"""プレビュー描画の分離モジュールが期待通りに動くかを確認する。"""

from __future__ import annotations

import numpy as np
import pytest


def _make_renderer():
    pytest.importorskip("matplotlib")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    from iRIC_DataScope.xy_value_map.preview_renderer import PreviewRenderer

    fig = Figure(figsize=(3.0, 2.0), dpi=100, constrained_layout=True)
    ax = fig.add_subplot(111)
    canvas = FigureCanvasAgg(fig)
    return PreviewRenderer(fig, ax, canvas)


def test_draw_preview_title_and_colorbar():
    pytest.importorskip("matplotlib")
    from matplotlib import colormaps

    from iRIC_DataScope.xy_value_map.options import OutputOptions
    from iRIC_DataScope.xy_value_map.processor import Roi

    renderer = _make_renderer()

    xs = np.linspace(0.0, 2.0, 3)
    ys = np.linspace(0.0, 1.0, 3)
    xx, yy = np.meshgrid(xs, ys)
    vals = xx + yy
    roi = Roi(cx=1.0, cy=0.5, width=2.0, height=1.0, angle_deg=0.0)
    opts = OutputOptions(
        show_title=True,
        title_text="preview title",
        show_ticks=True,
        show_frame=True,
        show_cbar=True,
        pad_inches=0.0,
    )

    renderer.draw_preview(
        x=xx,
        y=yy,
        vals=vals,
        roi=roi,
        value_col="U",
        step=1,
        t=0.0,
        cmap=colormaps.get_cmap("viridis"),
        vmin=float(vals.min()),
        vmax=float(vals.max()),
        output_opts=opts,
    )

    assert renderer.ax.get_title() == "preview title"
    assert renderer.ax.get_xlim() == pytest.approx((0.0, 2.0))
    assert renderer.ax.get_ylim() == pytest.approx((0.0, 1.0))
    assert len(renderer.fig.axes) >= 2


def test_draw_empty_preview_hides_ticks_and_frame():
    from iRIC_DataScope.xy_value_map.options import OutputOptions
    from iRIC_DataScope.xy_value_map.processor import Roi

    renderer = _make_renderer()
    roi = Roi(cx=0.5, cy=0.5, width=1.0, height=1.0, angle_deg=0.0)
    opts = OutputOptions(
        show_title=False,
        show_ticks=False,
        show_frame=False,
        show_cbar=False,
        pad_inches=0.0,
    )

    renderer.draw_empty_preview(roi, output_opts=opts, title="hidden")

    assert renderer.ax.get_title() == ""
    assert renderer.ax.get_xlim() == pytest.approx((0.0, 1.0))
    assert renderer.ax.get_ylim() == pytest.approx((0.0, 1.0))
    assert all(not spine.get_visible() for spine in renderer.ax.spines.values())
    assert all(not label.get_visible() for label in renderer.ax.get_xticklabels())
    assert all(not label.get_visible() for label in renderer.ax.get_yticklabels())
