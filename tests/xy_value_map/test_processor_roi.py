"""ROIが境界内に収まるようクランプされることを確認する。"""

# 本ファイルでは `Roi` を画面外・サイズ過大の状態から構築し、`clamp_roi_to_bounds` が
# 与えられたバウンダリ内に幅・高さ・中心を収めて角度を維持することを確認します。

from __future__ import annotations

from iRIC_DataScope.xy_value_map.processor import Roi, clamp_roi_to_bounds


def test_clamp_roi_to_bounds_limits_size_and_center():
    roi = Roi(cx=-5.0, cy=10.0, width=20.0, height=10.0, angle_deg=15.0)
    bounds = (0.0, 10.0, 0.0, 5.0)

    clamped = clamp_roi_to_bounds(roi, bounds)

    assert clamped.width == 10.0
    assert clamped.height == 5.0
    assert clamped.cx == 0.0
    assert clamped.cy == 5.0
    assert clamped.angle_deg == 15.0
