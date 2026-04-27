from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from iRIC_DataScope.section_analyze.models import SectionNode


NODE_MAP_NAME = "section_node_map.csv"
TIMESERIES_NAME = "section_timeseries.csv"
PEAK_NAME = "section_peak_summary.csv"

ColumnNames = Literal["standard", "river"]

RIVER_COLUMN_MAP = {
    "section_id": "断面ID",
    "section_name": "断面名",
    "source_feature_id": "側線FID",
    "order_no": "表示順",
    "i": "I番号",
    "j": "J番号",
    "x": "X座標",
    "y": "Y座標",
    "line_dist": "断面距離",
    "nearest_dist": "最近傍距離",
    "sample_dist": "サンプル距離",
    "step": "ステップ",
    "time": "時刻",
    "node_count": "採用点数",
    "valid_node_count": "有効点数",
    "invalid_node_count": "除外点数",
    "valid_ratio": "有効率",
    "depth_threshold": "有効水深下限",
    "mean_wse": "平均水位",
    "mean_depth": "平均水深",
    "max_wse": "最高水位",
    "min_wse": "最低水位",
    "max_depth": "最大水深",
    "min_depth": "最小水深",
    "peak_step": "平均水位最大ステップ",
    "peak_time": "平均水位最大時刻",
    "peak_mean_wse": "最大平均水位",
    "depth_at_peak_mean_wse": "最大平均水位時平均水深",
    "valid_node_count_at_peak": "最大平均水位時有効点数",
    "valid_ratio_at_peak": "最大平均水位時有効率",
    "max_wse_at_peak": "最大平均水位時最高水位",
    "min_wse_at_peak": "最大平均水位時最低水位",
    "max_depth_at_peak": "最大平均水位時最大水深",
    "min_depth_at_peak": "最大平均水位時最小水深",
}


def section_nodes_to_frame(nodes: list[SectionNode]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "section_id": node.section_id,
                "section_name": node.section_name,
                "source_feature_id": node.source_feature_id,
                "order_no": node.order_no,
                "i": node.i,
                "j": node.j,
                "x": node.x,
                "y": node.y,
                "line_dist": node.line_dist,
                "nearest_dist": node.nearest_dist,
                "sample_dist": node.sample_dist,
            }
            for node in nodes
        ]
    )


def ensure_output_dir(output_dir: Path, *, overwrite: bool, dry_run: bool) -> None:
    if dry_run:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        return
    existing = [output_dir / name for name in (NODE_MAP_NAME, TIMESERIES_NAME, PEAK_NAME) if (output_dir / name).exists()]
    if existing:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"出力CSVが既に存在します。上書きする場合は --overwrite を指定してください: {joined}")


def write_outputs(
    output_dir: Path,
    *,
    node_map: pd.DataFrame,
    timeseries: pd.DataFrame,
    peak: pd.DataFrame,
    column_names: ColumnNames = "standard",
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    node_map_path = output_dir / NODE_MAP_NAME
    timeseries_path = output_dir / TIMESERIES_NAME
    peak_path = output_dir / PEAK_NAME
    if column_names == "river":
        node_map = node_map.rename(columns=RIVER_COLUMN_MAP)
        timeseries = timeseries.rename(columns=RIVER_COLUMN_MAP)
        peak = peak.rename(columns=RIVER_COLUMN_MAP)
    node_map.to_csv(node_map_path, index=False, encoding="utf-8-sig")
    timeseries.to_csv(timeseries_path, index=False, encoding="utf-8-sig")
    peak.to_csv(peak_path, index=False, encoding="utf-8-sig")
    return node_map_path, timeseries_path, peak_path
