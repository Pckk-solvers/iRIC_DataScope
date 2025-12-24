"""編集キャンバスの座標変換とROIハンドル計算を検証する。"""

from __future__ import annotations

import pytest

from iRIC_DataScope.xy_value_map.edit_canvas import (
    canvas_to_data,
    compute_edit_transform,
    compute_roi_handle_positions,
    data_to_canvas,
)
from iRIC_DataScope.xy_value_map.processor import Roi


def test_edit_transform_round_trip():
    bounds = (0.0, 10.0, 0.0, 5.0)
    transform = compute_edit_transform(bounds, (200, 100))

    pt = data_to_canvas(2.0, 1.0, transform)
    assert pt is not None
    x, y = canvas_to_data(pt[0], pt[1], transform)
    assert x == pytest.approx(2.0)
    assert y == pytest.approx(1.0)


def test_roi_handle_positions_snapshot():
    bounds = (0.0, 10.0, 0.0, 5.0)
    transform = compute_edit_transform(bounds, (200, 100))
    roi = Roi(cx=5.0, cy=2.5, width=4.0, height=2.0, angle_deg=0.0)

    handles = compute_roi_handle_positions(roi, transform)
    assert len(handles) == 5

    handle_map = {(h["kind"], h["sign"]): (h["cx"], h["cy"]) for h in handles}
    assert handle_map[("width", 1)] == pytest.approx((140.0, 50.0))
    assert handle_map[("width", -1)] == pytest.approx((60.0, 50.0))
    assert handle_map[("height", 1)] == pytest.approx((100.0, 30.0))
    assert handle_map[("height", -1)] == pytest.approx((100.0, 70.0))
    # rotate handle should be above the top edge (y smaller in canvas coordinates)
    assert handle_map[("rotate", 0)][1] < handle_map[("height", 1)][1]
