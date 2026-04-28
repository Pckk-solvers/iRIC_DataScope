from __future__ import annotations

from pathlib import Path

import pandas as pd

from iRIC_DataScope.section_analyze import plotter


def _sample_timeseries() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"section_id": "SEC001", "section_name": "A", "time": 0.0, "mean_wse": 1.0},
            {"section_id": "SEC001", "section_name": "A", "time": 1.0, "mean_wse": 2.0},
            {"section_id": "SEC002", "section_name": "B", "time": 0.0, "mean_wse": 10.0},
            {"section_id": "SEC002", "section_name": "B", "time": 1.0, "mean_wse": 20.0},
        ]
    )


def test_write_section_graphs_default_uses_per_section_y_limits(monkeypatch, tmp_path: Path) -> None:
    timeseries = _sample_timeseries()
    captured: list[tuple[float, float]] = []

    def fake_render(
        path: Path,
        section_id: str,
        section_name: str,
        group: pd.DataFrame,
        *,
        x_limits,
        y_limits,
        x_tick_interval_hour,
        title_template,
        graph_width_inch,
        graph_height_inch,
        graph_dpi,
    ) -> None:
        captured.append(y_limits)
        path.write_bytes(b"png")

    monkeypatch.setattr(plotter, "_render_section_graph", fake_render)
    output_files = plotter.write_section_graphs(tmp_path, timeseries, overwrite=True)

    assert len(output_files) == 2
    assert captured[0] != captured[1]


def test_write_section_graphs_shared_y_limits(monkeypatch, tmp_path: Path) -> None:
    timeseries = pd.DataFrame(
        _sample_timeseries()
    )

    captured: list[tuple[float, float]] = []

    def fake_render(
        path: Path,
        section_id: str,
        section_name: str,
        group: pd.DataFrame,
        *,
        x_limits,
        y_limits,
        x_tick_interval_hour,
        title_template,
        graph_width_inch,
        graph_height_inch,
        graph_dpi,
    ) -> None:
        captured.append(y_limits)
        path.write_bytes(b"png")

    monkeypatch.setattr(plotter, "_render_section_graph", fake_render)

    output_files = plotter.write_section_graphs(tmp_path, timeseries, overwrite=True, shared_y_scale=True)

    assert len(output_files) == 2
    assert captured[0] == captured[1]
    assert captured[0][0] < 1.0
    assert captured[0][1] > 20.0
