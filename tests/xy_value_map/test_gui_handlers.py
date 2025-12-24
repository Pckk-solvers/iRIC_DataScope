"""GUIハンドラの副作用とオプション正規化の挙動を確認する。"""

# 本ファイルでは `XYValueMapGUI` の内部イベントハンドラをスタブ化した GUI インスタンスで動かし、
# 値変更・ステップ変更・出力オプションの切り替えに伴う dirty フラグ、スケール調整、更新予約の振る舞いと、
# 入力が空・負・NaN のケースで `_get_output_options` が安全なデフォルトに置き換えること、正規化比率と実数値の間のラウンドトリップを確認します。

from __future__ import annotations

from pathlib import Path
import types

import pytest

try:
    import tkinter as tk
except Exception:  # pragma: no cover - optional GUI dependency
    tk = None


@pytest.fixture
def gui_instance(tk_root, monkeypatch, tmp_path):
    from iRIC_DataScope.xy_value_map import gui as gui_module

    monkeypatch.setattr(gui_module.XYValueMapGUI, "_start_initial_load", lambda self: None)
    win = gui_module.XYValueMapGUI(
        master=tk_root,
        input_path=Path(tmp_path) / "dummy.ipro",
        output_dir=Path(tmp_path),
    )
    yield win
    win.destroy()


def _record_updates(win):
    calls = []

    def _record(self, immediate: bool = False):
        calls.append(bool(immediate))

    win._schedule_view_update = types.MethodType(_record, win)
    return calls


def test_on_value_changed_sets_dirty_and_schedules(gui_instance):
    win = gui_instance
    win._preview_frame_cache._cache[(1, "dummy")] = object()
    win._global_scale.vmin = 1.0
    win._global_scale.vmax = 2.0
    win.state.edit.map_dirty = False
    before_token = win._global_scale.token
    calls = _record_updates(win)

    win._on_value_changed()

    assert len(win._preview_frame_cache) == 0
    assert win._global_scale.vmin is None
    assert win._global_scale.vmax is None
    assert win._global_scale.token == before_token + 1
    assert win.state.edit.map_dirty is True
    assert calls == [True]


def test_on_step_changed_clamps_and_schedules(gui_instance):
    win = gui_instance

    class DummyData:
        step_count = 5

    win._data_source = DummyData()
    win.step_var.set(99)
    win.state.edit.map_dirty = False
    calls = _record_updates(win)

    win._on_step_changed()

    assert win.step_var.get() == 5
    assert win.state.edit.map_dirty is True
    assert calls == [True]


def test_on_output_option_changed_sets_dirty_and_schedules(gui_instance):
    win = gui_instance
    win.state.ui.output_opts_lock = False
    win.state.edit.map_dirty = False
    calls = _record_updates(win)

    win._on_output_option_changed()

    assert win.state.edit.map_dirty is True
    assert calls == [True]


def test_output_options_sanitize_invalid_values(gui_instance):
    if tk is None:
        pytest.skip("tkinter not available")
    win = gui_instance
    win.pad_inches_var = tk.StringVar(value="")
    win.title_font_size_var = tk.StringVar(value="-1")
    win.tick_font_size_var = tk.StringVar(value="nan")
    win.cbar_label_font_size_var = tk.StringVar(value="")

    opts = win._get_output_options()

    assert opts.pad_inches == pytest.approx(0.02)
    from iRIC_DataScope.xy_value_map.style import (
        DEFAULT_CBAR_LABEL_FONT_SIZE,
        DEFAULT_TICK_FONT_SIZE,
        DEFAULT_TITLE_FONT_SIZE,
    )

    assert opts.title_font_size == pytest.approx(DEFAULT_TITLE_FONT_SIZE)
    assert opts.tick_font_size == pytest.approx(DEFAULT_TICK_FONT_SIZE)
    assert opts.cbar_label_font_size == pytest.approx(DEFAULT_CBAR_LABEL_FONT_SIZE)


def test_scale_ratio_round_trip(gui_instance):
    win = gui_instance
    win.state.scale.auto_range = (10.0, 20.0)

    rmin, rmax = win._ratio_from_values(12.5, 17.5)
    assert rmin == pytest.approx(0.25)
    assert rmax == pytest.approx(0.75)

    vmin, vmax = win._values_from_ratio(rmin, rmax)
    assert vmin == pytest.approx(12.5)
    assert vmax == pytest.approx(17.5)

    clamped = win._clamp_ratio(1.2, -0.1)
    assert clamped == (0.0, 1.0)
