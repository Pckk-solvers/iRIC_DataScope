"""GUI起動のスモークテストと出力オプション既定値の確認を行う。"""

from __future__ import annotations

from pathlib import Path

import pytest


def _skip_initial_load(monkeypatch):
    from iRIC_DataScope.xy_value_map import gui as gui_module

    monkeypatch.setattr(gui_module.XYValueMapGUI, "_start_initial_load", lambda self: None)
    return gui_module


def test_gui_smoke(tk_root, monkeypatch, tmp_path):
    gui_module = _skip_initial_load(monkeypatch)

    win = gui_module.XYValueMapGUI(
        master=tk_root,
        input_path=Path(tmp_path) / "dummy.ipro",
        output_dir=Path(tmp_path),
    )
    win.update_idletasks()
    win.destroy()


def test_output_options_defaults(tk_root, monkeypatch, tmp_path):
    gui_module = _skip_initial_load(monkeypatch)

    win = gui_module.XYValueMapGUI(
        master=tk_root,
        input_path=Path(tmp_path) / "dummy.ipro",
        output_dir=Path(tmp_path),
    )
    opts = win._get_output_options()
    assert opts.show_title is True
    assert opts.show_ticks is True
    assert opts.show_frame is True
    assert opts.show_cbar is True
    assert opts.pad_inches == pytest.approx(0.02)
    assert opts.title_text.startswith("title")
    assert opts.cbar_label.startswith("colorbar")
    assert opts.title_font_size == pytest.approx(12.0)
    assert opts.tick_font_size == pytest.approx(10.0)
    assert opts.cbar_label_font_size == pytest.approx(10.0)
    assert opts.figsize == (6.0, 4.0)
    win.destroy()
