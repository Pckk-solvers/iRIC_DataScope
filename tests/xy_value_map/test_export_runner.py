"""出力実行ロジックの分離モジュールを検証する。"""

from __future__ import annotations

from pathlib import Path

import pytest

from iRIC_DataScope.xy_value_map.export_runner import run_export_all, run_export_single_step
from iRIC_DataScope.xy_value_map.options import OutputOptions
from iRIC_DataScope.xy_value_map.processor import Roi


class DummyProgress:
    def __init__(self):
        self.closed = False
        self.updated = False

    def update(self, current: int, total: int, text: str):
        self.updated = True

    def close(self):
        self.closed = True


def _progress_factory(maximum: int, title: str):
    return DummyProgress()


def test_export_all_manual_scale_validation(tmp_path):
    def export_stub(**_kwargs):
        raise AssertionError("export should not be called for invalid scale")

    with pytest.raises(ValueError, match="vmin は vmax"):
        run_export_all(
            data_source=type("DS", (), {"step_count": 1})(),
            value_col="U",
            roi=Roi(cx=0.0, cy=0.0, width=1.0, height=1.0, angle_deg=0.0),
            dx=1.0,
            dy=1.0,
            min_color="#0000ff",
            max_color="#ff0000",
            output_opts=OutputOptions(),
            output_dir=Path(tmp_path),
            scale_mode="manual",
            manual_scale=(2.0, 1.0),
            progress_factory=_progress_factory,
            export_func=export_stub,
        )


def test_export_single_step_global_cancel(tmp_path):
    called = {"export": False}

    def export_stub(**_kwargs):
        called["export"] = True

    result = run_export_single_step(
        data_source=object(),
        value_col="U",
        step=1,
        roi=Roi(cx=0.0, cy=0.0, width=1.0, height=1.0, angle_deg=0.0),
        dx=1.0,
        dy=1.0,
        min_color="#0000ff",
        max_color="#ff0000",
        output_opts=OutputOptions(),
        output_dir=Path(tmp_path),
        scale_mode="global",
        manual_scale=None,
        global_scale=None,
        confirm_global_fallback=lambda _msg: False,
        get_preview_frame=lambda step, value_col: object(),
        compute_roi_minmax_fn=lambda *_, **__: (0.0, 1.0),
        progress_factory=_progress_factory,
        export_func=export_stub,
    )

    assert result is None
    assert called["export"] is False


def test_export_single_step_global_minmax_missing(tmp_path):
    def export_stub(**_kwargs):
        raise AssertionError("export should not be called when minmax is missing")

    with pytest.raises(ValueError, match="ROI 内の Value"):
        run_export_single_step(
            data_source=object(),
            value_col="U",
            step=1,
            roi=Roi(cx=0.0, cy=0.0, width=1.0, height=1.0, angle_deg=0.0),
            dx=1.0,
            dy=1.0,
            min_color="#0000ff",
            max_color="#ff0000",
            output_opts=OutputOptions(),
            output_dir=Path(tmp_path),
            scale_mode="global",
            manual_scale=None,
            global_scale=None,
            confirm_global_fallback=lambda _msg: True,
            get_preview_frame=lambda step, value_col: object(),
            compute_roi_minmax_fn=lambda *_, **__: None,
            progress_factory=_progress_factory,
            export_func=export_stub,
        )


def test_export_single_step_manual_scale_applied(tmp_path):
    captured = {}

    def export_stub(**kwargs):
        captured["vmin"] = kwargs["vmin"]
        captured["vmax"] = kwargs["vmax"]
        return Path(tmp_path) / "step.png"

    out_path = run_export_single_step(
        data_source=object(),
        value_col="U",
        step=1,
        roi=Roi(cx=0.0, cy=0.0, width=1.0, height=1.0, angle_deg=0.0),
        dx=1.0,
        dy=1.0,
        min_color="#0000ff",
        max_color="#ff0000",
        output_opts=OutputOptions(),
        output_dir=Path(tmp_path),
        scale_mode="manual",
        manual_scale=(0.2, 0.8),
        global_scale=None,
        confirm_global_fallback=lambda _msg: True,
        get_preview_frame=lambda step, value_col: object(),
        compute_roi_minmax_fn=lambda *_, **__: (0.0, 1.0),
        progress_factory=_progress_factory,
        export_func=export_stub,
    )

    assert out_path is not None
    assert captured["vmin"] == pytest.approx(0.2)
    assert captured["vmax"] == pytest.approx(0.8)
