"""ROIドラッグ操作の数値更新ロジックを検証する。"""

from __future__ import annotations

import pytest

from iRIC_DataScope.xy_value_map.processor import Roi
from iRIC_DataScope.xy_value_map.roi_interaction import update_roi_from_drag


def test_move_updates_center():
    roi = Roi(cx=5.0, cy=5.0, width=4.0, height=2.0, angle_deg=0.0)
    offset = (1.0, -2.0)

    new_roi = update_roi_from_drag(
        roi,
        mode="move",
        xdata=6.0,
        ydata=9.0,
        offset=offset,
    )

    assert new_roi is not None
    assert new_roi.cx == pytest.approx(7.0)
    assert new_roi.cy == pytest.approx(7.0)
    assert new_roi.width == pytest.approx(4.0)
    assert new_roi.height == pytest.approx(2.0)


def test_handle_width_updates_center_and_size():
    roi = Roi(cx=0.0, cy=0.0, width=4.0, height=2.0, angle_deg=0.0)

    new_roi = update_roi_from_drag(
        roi,
        mode="handle",
        xdata=4.0,
        ydata=0.0,
        kind="width",
        sign=1.0,
    )

    assert new_roi is not None
    assert new_roi.width == pytest.approx(6.0)
    assert new_roi.cx == pytest.approx(1.0)
    assert new_roi.cy == pytest.approx(0.0)


def test_handle_height_updates_center_and_size():
    roi = Roi(cx=0.0, cy=0.0, width=4.0, height=2.0, angle_deg=0.0)

    new_roi = update_roi_from_drag(
        roi,
        mode="handle",
        xdata=0.0,
        ydata=4.0,
        kind="height",
        sign=1.0,
    )

    assert new_roi is not None
    assert new_roi.height == pytest.approx(5.0)
    assert new_roi.cy == pytest.approx(1.5)


def test_handle_rotate_updates_angle():
    roi = Roi(cx=2.0, cy=1.0, width=4.0, height=2.0, angle_deg=0.0)

    new_roi = update_roi_from_drag(
        roi,
        mode="handle",
        xdata=roi.cx + 1.0,
        ydata=roi.cy,
        kind="rotate",
        sign=0.0,
    )

    assert new_roi is not None
    assert new_roi.angle_deg == pytest.approx(-90.0)
