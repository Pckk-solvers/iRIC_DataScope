"""ROI操作（ドラッグ・回転・サイズ変更）の計算をまとめる。"""

from __future__ import annotations

import math

import numpy as np

from .processor import Roi


def update_roi_from_drag(
    roi: Roi,
    *,
    mode: str,
    xdata: float,
    ydata: float,
    offset: tuple[float, float] | None = None,
    kind: str | None = None,
    sign: float | None = None,
    min_size: float = 1e-9,
) -> Roi | None:
    """ドラッグ状態に応じてROIを更新する。"""
    if mode == "move":
        if offset is None:
            return None
        return Roi(
            cx=xdata + offset[0],
            cy=ydata + offset[1],
            width=roi.width,
            height=roi.height,
            angle_deg=roi.angle_deg,
        )

    if mode != "handle" or kind is None:
        return None

    sign_val = float(sign or 0.0)
    vx = xdata - roi.cx
    vy = ydata - roi.cy

    theta = math.radians(roi.angle_deg)
    ux = np.array([math.cos(theta), math.sin(theta)])
    uy = np.array([-math.sin(theta), math.cos(theta)])

    if kind == "rotate":
        angle = math.degrees(math.atan2(vy, vx)) - 90.0
        return Roi(
            cx=roi.cx,
            cy=roi.cy,
            width=roi.width,
            height=roi.height,
            angle_deg=angle,
        )
    if kind == "width":
        half_w = 0.5 * roi.width
        opposite_edge = np.array([roi.cx, roi.cy]) - sign_val * half_w * ux
        proj = np.dot(np.array([xdata, ydata]) - opposite_edge, ux)
        if sign_val >= 0:
            proj = max(proj, min_size)
        else:
            proj = min(proj, -min_size)
        half_new = abs(proj) * 0.5
        new_center = opposite_edge + ux * (proj * 0.5)
        return Roi(
            cx=float(new_center[0]),
            cy=float(new_center[1]),
            width=float(half_new * 2.0),
            height=roi.height,
            angle_deg=roi.angle_deg,
        )
    if kind == "height":
        half_h = 0.5 * roi.height
        opposite_edge = np.array([roi.cx, roi.cy]) - sign_val * half_h * uy
        proj = np.dot(np.array([xdata, ydata]) - opposite_edge, uy)
        if sign_val >= 0:
            proj = max(proj, min_size)
        else:
            proj = min(proj, -min_size)
        half_new = abs(proj) * 0.5
        new_center = opposite_edge + uy * (proj * 0.5)
        return Roi(
            cx=float(new_center[0]),
            cy=float(new_center[1]),
            width=roi.width,
            height=float(half_new * 2.0),
            angle_deg=roi.angle_deg,
        )
    return None
