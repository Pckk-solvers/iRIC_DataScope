"""GUI状態の初期値と更新が整合することを確認する。"""

from __future__ import annotations

from iRIC_DataScope.xy_value_map.state import GuiState


def test_state_defaults():
    state = GuiState()
    assert state.preview.dragging is False
    assert state.preview.figsize == (6.0, 4.0)
    assert state.preview.last_output_opts is None
    assert state.edit.map_dirty is True
    assert state.edit.base_bounds is None
    assert state.edit.view_bounds is None
    assert state.edit.context["step"] is None
    assert state.scale.auto_range is None
    assert state.scale.ratio == (0.0, 1.0)
    assert state.roi.confirmed is False
    assert state.roi.drag_state is None
    assert state.ui.output_opts_lock is False


def test_state_updates():
    state = GuiState()
    state.scale.auto_range = (0.0, 1.0)
    state.scale.ratio = (0.2, 0.8)
    state.roi.confirmed = True
    state.preview.dragging = True

    assert state.scale.auto_range == (0.0, 1.0)
    assert state.scale.ratio == (0.2, 0.8)
    assert state.roi.confirmed is True
    assert state.preview.dragging is True
