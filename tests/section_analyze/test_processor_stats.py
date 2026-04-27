from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from iRIC_DataScope.section_analyze.models import SectionAnalyzeOptions, SectionNode
from iRIC_DataScope.section_analyze.processor import _build_peak_summary, _calculate_timeseries_rows


def _node(i: int, j: int) -> SectionNode:
    return SectionNode(
        section_id="SEC001",
        section_name="SEC001",
        source_feature_id=1,
        order_no=1,
        i=i,
        j=j,
        x=float(i),
        y=float(j),
        line_dist=float(i),
        nearest_dist=0.0,
        sample_dist=float(i),
    )


def test_calculate_timeseries_rows_filters_by_depth_threshold() -> None:
    frame = SimpleNamespace(
        step=1,
        time=10.0,
        df=pd.DataFrame(
            [
                {"I": 1, "J": 1, "watersurfaceelevation(m)": 10.0, "depth(m)": 0.02},
                {"I": 1, "J": 2, "watersurfaceelevation(m)": 20.0, "depth(m)": 0.001},
            ]
        ),
    )

    rows = _calculate_timeseries_rows(
        frame,
        {"SEC001": [_node(1, 1), _node(1, 2)]},
        SectionAnalyzeOptions(depth_threshold=0.01),
    )

    assert rows[0]["node_count"] == 2
    assert rows[0]["valid_node_count"] == 1
    assert rows[0]["mean_wse"] == 10.0
    assert rows[0]["mean_depth"] == 0.02


def test_build_peak_summary_uses_max_mean_wse_then_earliest_time() -> None:
    timeseries = pd.DataFrame(
        [
            {"section_id": "SEC001", "section_name": "SEC001", "step": 1, "time": 20.0, "node_count": 2, "depth_threshold": 0.01, "mean_wse": 5.0, "mean_depth": 1.0, "valid_node_count": 2, "valid_ratio": 1.0, "max_wse": 5.5, "min_wse": 4.5, "max_depth": 1.5, "min_depth": 0.5},
            {"section_id": "SEC001", "section_name": "SEC001", "step": 2, "time": 10.0, "node_count": 2, "depth_threshold": 0.01, "mean_wse": 5.0, "mean_depth": 2.0, "valid_node_count": 2, "valid_ratio": 1.0, "max_wse": 6.0, "min_wse": 4.0, "max_depth": 2.5, "min_depth": 1.5},
        ]
    )

    peak = _build_peak_summary(timeseries)

    assert peak.loc[0, "peak_step"] == 2
    assert peak.loc[0, "depth_at_peak_mean_wse"] == 2.0

