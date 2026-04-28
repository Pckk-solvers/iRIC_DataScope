from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


WSE_COLUMN = "watersurfaceelevation(m)"
DEPTH_COLUMN = "depth(m)"


@dataclass(frozen=True)
class SectionAnalyzeOptions:
    depth_threshold: float = 0.01
    sample_interval: float | None = None
    section_id_field: str | None = None
    section_name_field: str | None = None
    overwrite: bool = False
    limit_steps: int | None = None
    dry_run: bool = False
    column_names: Literal["standard", "river"] = "standard"
    shared_y_scale: bool = False
    x_tick_interval_hour: float | None = None
    title_template: str = "{section_id} {section_name} / 平均水位時系列"
    graph_width_inch: float = 12.0
    graph_height_inch: float = 4.8
    graph_dpi: int = 180
    section_limit: int | None = None


@dataclass(frozen=True)
class SectionLine:
    section_id: str
    section_name: str
    source_feature_id: int
    order_no: int
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class SectionNode:
    section_id: str
    section_name: str
    source_feature_id: int
    order_no: int
    i: int
    j: int
    x: float
    y: float
    line_dist: float
    nearest_dist: float
    sample_dist: float


@dataclass(frozen=True)
class SectionAnalyzeResult:
    input_path: Path
    section_shp_path: Path
    output_dir: Path
    section_count: int
    mapped_node_count: int
    step_count: int
    sample_interval: float
    output_files: tuple[Path, ...]
    dry_run: bool = False
