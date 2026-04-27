from __future__ import annotations

from pathlib import Path

import pandas as pd

from iRIC_DataScope.section_analyze.cgn_loader import SectionDataSource
from iRIC_DataScope.section_analyze.models import (
    DEPTH_COLUMN,
    WSE_COLUMN,
    SectionAnalyzeOptions,
    SectionAnalyzeResult,
    SectionNode,
)
from iRIC_DataScope.section_analyze.sampler import map_section_nodes
from iRIC_DataScope.section_analyze.shp_reader import read_section_lines
from iRIC_DataScope.section_analyze.writer import ensure_output_dir, section_nodes_to_frame, write_outputs


def _calculate_timeseries_rows(frame, nodes_by_section: dict[str, list[SectionNode]], options: SectionAnalyzeOptions) -> list[dict]:
    df = frame.df.loc[:, ["I", "J", WSE_COLUMN, DEPTH_COLUMN]].copy()
    rows: list[dict] = []
    for section_id, nodes in nodes_by_section.items():
        section_name = nodes[0].section_name
        keys = pd.DataFrame([{"I": node.i, "J": node.j} for node in nodes])
        values = keys.merge(df, on=["I", "J"], how="left")
        depth = values[DEPTH_COLUMN]
        valid = values[depth >= options.depth_threshold]
        node_count = int(len(values))
        valid_count = int(len(valid))
        invalid_count = node_count - valid_count
        row = {
            "section_id": section_id,
            "section_name": section_name,
            "step": frame.step,
            "time": frame.time,
            "node_count": node_count,
            "valid_node_count": valid_count,
            "invalid_node_count": invalid_count,
            "valid_ratio": valid_count / node_count if node_count else 0.0,
            "depth_threshold": options.depth_threshold,
            "mean_wse": pd.NA,
            "mean_depth": pd.NA,
            "max_wse": pd.NA,
            "min_wse": pd.NA,
            "max_depth": pd.NA,
            "min_depth": pd.NA,
        }
        if valid_count:
            row.update(
                {
                    "mean_wse": float(valid[WSE_COLUMN].mean()),
                    "mean_depth": float(valid[DEPTH_COLUMN].mean()),
                    "max_wse": float(valid[WSE_COLUMN].max()),
                    "min_wse": float(valid[WSE_COLUMN].min()),
                    "max_depth": float(valid[DEPTH_COLUMN].max()),
                    "min_depth": float(valid[DEPTH_COLUMN].min()),
                }
            )
        rows.append(row)
    return rows


def _build_peak_summary(timeseries: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for section_id, group in timeseries.groupby("section_id", sort=False):
        valid = group.dropna(subset=["mean_wse"]).sort_values(["mean_wse", "time"], ascending=[False, True])
        if valid.empty:
            first = group.iloc[0]
            rows.append(
                {
                    "section_id": section_id,
                    "section_name": first["section_name"],
                    "node_count": first["node_count"],
                    "depth_threshold": first["depth_threshold"],
                    "peak_step": pd.NA,
                    "peak_time": pd.NA,
                    "peak_mean_wse": pd.NA,
                    "depth_at_peak_mean_wse": pd.NA,
                    "valid_node_count_at_peak": 0,
                    "valid_ratio_at_peak": 0.0,
                    "max_wse_at_peak": pd.NA,
                    "min_wse_at_peak": pd.NA,
                    "max_depth_at_peak": pd.NA,
                    "min_depth_at_peak": pd.NA,
                }
            )
            continue
        peak = valid.iloc[0]
        rows.append(
            {
                "section_id": section_id,
                "section_name": peak["section_name"],
                "node_count": peak["node_count"],
                "depth_threshold": peak["depth_threshold"],
                "peak_step": peak["step"],
                "peak_time": peak["time"],
                "peak_mean_wse": peak["mean_wse"],
                "depth_at_peak_mean_wse": peak["mean_depth"],
                "valid_node_count_at_peak": peak["valid_node_count"],
                "valid_ratio_at_peak": peak["valid_ratio"],
                "max_wse_at_peak": peak["max_wse"],
                "min_wse_at_peak": peak["min_wse"],
                "max_depth_at_peak": peak["max_depth"],
                "min_depth_at_peak": peak["min_depth"],
            }
        )
    return pd.DataFrame(rows)


def run_section_analysis(
    input_path: Path,
    section_shp_path: Path,
    output_dir: Path,
    options: SectionAnalyzeOptions,
) -> SectionAnalyzeResult:
    input_path = Path(input_path)
    section_shp_path = Path(section_shp_path)
    output_dir = Path(output_dir)
    ensure_output_dir(output_dir, overwrite=options.overwrite, dry_run=options.dry_run)

    data_source = SectionDataSource(input_path)
    try:
        grid_nodes = data_source.load_grid_nodes()
        section_lines = read_section_lines(section_shp_path, options)
        section_nodes, actual_sample_interval = map_section_nodes(
            grid_nodes,
            section_lines,
            sample_interval=options.sample_interval,
        )
        node_map = section_nodes_to_frame(section_nodes)
        nodes_by_section: dict[str, list[SectionNode]] = {}
        for node in section_nodes:
            nodes_by_section.setdefault(node.section_id, []).append(node)

        output_files: tuple[Path, ...] = ()
        step_count = min(data_source.step_count, options.limit_steps) if options.limit_steps else data_source.step_count
        if not options.dry_run:
            timeseries_rows: list[dict] = []
            for frame in data_source.iter_result_frames(limit_steps=options.limit_steps):
                timeseries_rows.extend(_calculate_timeseries_rows(frame, nodes_by_section, options))
            timeseries = pd.DataFrame(timeseries_rows)
            peak = _build_peak_summary(timeseries)
            output_files = write_outputs(
                output_dir,
                node_map=node_map,
                timeseries=timeseries,
                peak=peak,
                column_names=options.column_names,
            )

        return SectionAnalyzeResult(
            input_path=input_path,
            section_shp_path=section_shp_path,
            output_dir=output_dir,
            section_count=len(section_lines),
            mapped_node_count=len(section_nodes),
            step_count=int(step_count),
            sample_interval=float(actual_sample_interval),
            output_files=output_files,
            dry_run=options.dry_run,
        )
    finally:
        data_source.close()
