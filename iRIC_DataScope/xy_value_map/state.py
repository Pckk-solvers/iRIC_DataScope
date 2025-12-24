"""GUIの状態をまとめて管理するデータクラス。"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .options import OutputOptions


@dataclass
class PreviewState:
    dragging: bool = False
    job: object | None = None
    pad_px: tuple[float, float] = (0.0, 0.0)
    figsize: tuple[float, float] = (6.0, 4.0)
    last_output_opts: OutputOptions | None = None


@dataclass
class EditState:
    base_bounds: tuple[float, float, float, float] | None = None
    view_bounds: tuple[float, float, float, float] | None = None
    map_dirty: bool = True
    render_job: object | None = None
    render_context: dict[str, object] | None = None
    outline_points: np.ndarray | None = None
    context: dict[str, object] = field(
        default_factory=lambda: {"step": None, "time": None, "value": ""}
    )


@dataclass
class RoiState:
    confirmed: bool = False
    var_lock: bool = False
    drag_state: dict[str, object] | None = None


@dataclass
class ScaleState:
    auto_range: tuple[float, float] | None = None
    ratio: tuple[float, float] = (0.0, 1.0)
    var_lock: bool = False
    slider_lock: bool = False


@dataclass
class UiState:
    step_var_lock: bool = False
    output_opts_lock: bool = False


@dataclass
class GuiState:
    preview: PreviewState = field(default_factory=PreviewState)
    edit: EditState = field(default_factory=EditState)
    roi: RoiState = field(default_factory=RoiState)
    scale: ScaleState = field(default_factory=ScaleState)
    ui: UiState = field(default_factory=UiState)
