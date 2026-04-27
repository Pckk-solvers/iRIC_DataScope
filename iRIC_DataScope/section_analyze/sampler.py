from __future__ import annotations

from math import ceil, hypot

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from iRIC_DataScope.section_analyze.models import SectionLine, SectionNode


def estimate_sample_interval(grid_nodes: pd.DataFrame) -> float:
    df = grid_nodes.loc[:, ["I", "J", "X", "Y"]].copy()
    distances: list[np.ndarray] = []
    same_i = df.sort_values(["I", "J"])
    dx = same_i.groupby("I")["X"].diff()
    dy = same_i.groupby("I")["Y"].diff()
    d = np.sqrt(dx * dx + dy * dy).dropna().to_numpy()
    if d.size:
        distances.append(d[d > 0])

    same_j = df.sort_values(["J", "I"])
    dx = same_j.groupby("J")["X"].diff()
    dy = same_j.groupby("J")["Y"].diff()
    d = np.sqrt(dx * dx + dy * dy).dropna().to_numpy()
    if d.size:
        distances.append(d[d > 0])

    merged = np.concatenate([arr for arr in distances if arr.size]) if distances else np.array([])
    if not merged.size:
        raise ValueError("sample_interval を自動推定できませんでした")
    return float(np.median(merged) * 0.5)


def _cumulative_distances(points: tuple[tuple[float, float], ...]) -> list[float]:
    distances = [0.0]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        distances.append(distances[-1] + hypot(x1 - x0, y1 - y0))
    return distances


def _point_at_distance(points: tuple[tuple[float, float], ...], distances: list[float], target: float) -> tuple[float, float]:
    if target <= 0:
        return points[0]
    total = distances[-1]
    if target >= total:
        return points[-1]
    for idx in range(1, len(distances)):
        if distances[idx] >= target:
            prev_d = distances[idx - 1]
            seg_len = distances[idx] - prev_d
            ratio = 0.0 if seg_len <= 0 else (target - prev_d) / seg_len
            x0, y0 = points[idx - 1]
            x1, y1 = points[idx]
            return (x0 + (x1 - x0) * ratio, y0 + (y1 - y0) * ratio)
    return points[-1]


def _project_distance(points: tuple[tuple[float, float], ...], distances: list[float], x: float, y: float) -> float:
    best_dist = float("inf")
    best_line_dist = 0.0
    for idx, ((x0, y0), (x1, y1)) in enumerate(zip(points, points[1:])):
        vx = x1 - x0
        vy = y1 - y0
        seg_len2 = vx * vx + vy * vy
        if seg_len2 <= 0:
            continue
        t = max(0.0, min(1.0, ((x - x0) * vx + (y - y0) * vy) / seg_len2))
        px = x0 + t * vx
        py = y0 + t * vy
        dist = hypot(x - px, y - py)
        if dist < best_dist:
            best_dist = dist
            best_line_dist = distances[idx] + hypot(px - x0, py - y0)
    return best_line_dist


def map_section_nodes(
    grid_nodes: pd.DataFrame,
    section_lines: list[SectionLine],
    *,
    sample_interval: float | None,
) -> tuple[list[SectionNode], float]:
    interval = sample_interval if sample_interval and sample_interval > 0 else estimate_sample_interval(grid_nodes)
    coords = grid_nodes.loc[:, ["X", "Y"]].to_numpy(dtype=float)
    tree = cKDTree(coords)
    nodes = grid_nodes.reset_index(drop=True)

    mapped: list[SectionNode] = []
    for line in section_lines:
        distances = _cumulative_distances(line.points)
        total_length = distances[-1]
        sample_count = max(1, int(ceil(total_length / interval)))
        sample_distances = [min(total_length, n * interval) for n in range(sample_count + 1)]
        if sample_distances[-1] != total_length:
            sample_distances.append(total_length)

        seen: set[tuple[int, int]] = set()
        for sample_dist in sample_distances:
            sx, sy = _point_at_distance(line.points, distances, sample_dist)
            nearest_dist, idx = tree.query([sx, sy], k=1)
            row = nodes.iloc[int(idx)]
            i = int(row["I"])
            j = int(row["J"])
            key = (i, j)
            if key in seen:
                continue
            seen.add(key)
            x = float(row["X"])
            y = float(row["Y"])
            mapped.append(
                SectionNode(
                    section_id=line.section_id,
                    section_name=line.section_name,
                    source_feature_id=line.source_feature_id,
                    order_no=line.order_no,
                    i=i,
                    j=j,
                    x=x,
                    y=y,
                    line_dist=_project_distance(line.points, distances, x, y),
                    nearest_dist=float(nearest_dist),
                    sample_dist=float(sample_dist),
                )
            )
    return sorted(mapped, key=lambda node: (node.order_no, node.line_dist, node.i, node.j)), interval

