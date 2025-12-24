"""最小データで描画が例外なく完了することを確認する。"""

from __future__ import annotations

import numpy as np
import pytest


def test_render_xy_value_map_minimal():
    pytest.importorskip("matplotlib")
    from matplotlib import colormaps
    from matplotlib.figure import Figure

    from iRIC_DataScope.xy_value_map.plot import render_xy_value_map
    from iRIC_DataScope.xy_value_map.processor import Roi

    xs = np.linspace(0.0, 1.0, 3)
    ys = np.linspace(0.0, 1.0, 3)
    xx, yy = np.meshgrid(xs, ys)
    vals = xx + yy

    roi = Roi(cx=0.5, cy=0.5, width=1.0, height=1.0, angle_deg=0.0)
    fig = Figure(figsize=(3.0, 2.0), dpi=100, constrained_layout=True)
    ax = fig.add_subplot(111)

    mappable = render_xy_value_map(
        fig=fig,
        ax=ax,
        x=xx,
        y=yy,
        vals=vals,
        roi=roi,
        cmap=colormaps.get_cmap("viridis"),
        vmin=float(vals.min()),
        vmax=float(vals.max()),
        title="",
        show_ticks=True,
        show_frame=True,
        show_cbar=False,
    )
    assert mappable is not None
