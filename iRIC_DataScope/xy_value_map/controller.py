"""GUIイベントハンドラの処理を集約し、GUI本体の肥大化を抑える。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .processor import Roi, roi_corners
from .roi_interaction import update_roi_from_drag

if TYPE_CHECKING:
    from .gui import XYValueMapGUI


class XYValueMapController:
    """イベントハンドラのロジックを集約するコントローラ。"""

    def __init__(self, gui: "XYValueMapGUI"):
        self.gui = gui

    def on_close(self):
        gui = self.gui
        try:
            if gui._data_source is not None:
                gui._data_source.close()
        finally:
            gui.destroy()

    def on_value_changed(self):
        gui = self.gui
        # 変数切替時はプレビューキャッシュとglobalスケールを無効化する。
        gui._preview_frame_cache.clear()
        gui._invalidate_global_scale()
        gui.state.edit.map_dirty = True
        gui._schedule_view_update(immediate=True)

    def on_step_changed(self):
        gui = self.gui
        if gui.state.ui.step_var_lock:
            return
        if gui._data_source is None:
            return
        try:
            step = int(gui.step_var.get())
        except Exception:
            return
        # 範囲外ステップはデータ範囲に丸める。
        step = max(1, min(step, gui._data_source.step_count))
        if step != gui.step_var.get():
            gui.state.ui.step_var_lock = True
            try:
                gui.step_var.set(step)
            finally:
                gui.state.ui.step_var_lock = False
        gui.state.edit.map_dirty = True
        gui._schedule_view_update(immediate=True)

    def on_color_changed(self):
        gui = self.gui
        gui.min_color_sample.configure(background=gui.min_color_var.get())
        gui.max_color_sample.configure(background=gui.max_color_var.get())
        gui.state.edit.map_dirty = True
        gui._schedule_view_update()

    def on_resolution_changed(self):
        gui = self.gui
        gui._invalidate_global_scale()
        gui._schedule_view_update()

    def on_scale_mode_changed(self):
        gui = self.gui
        manual = gui.scale_mode.get() == "manual"
        gui.vmin_entry.configure(state="normal" if manual else "disabled")
        gui.vmax_entry.configure(state="normal" if manual else "disabled")
        if hasattr(gui, "range_slider"):
            gui.range_slider.set_enabled(manual and gui.state.scale.auto_range is not None)
        if manual:
            gui._ensure_manual_scale_defaults()
            gui._sync_slider_from_vars()
        # スケールモード変更は編集背景も再描画する。
        gui.state.edit.map_dirty = True
        gui._schedule_view_update(immediate=True)

    def on_manual_scale_changed(self):
        gui = self.gui
        if gui.scale_mode.get() != "manual":
            return
        if gui.state.scale.var_lock:
            return
        gui._clamp_manual_scale()
        gui._update_scale_ratio_from_vars()
        gui._sync_slider_from_vars()
        gui.state.edit.map_dirty = True
        gui._schedule_view_update()

    def on_output_option_changed(self):
        gui = self.gui
        if gui.state.ui.output_opts_lock:
            return
        gui.state.edit.map_dirty = True
        gui._schedule_view_update(immediate=True)

    def on_roi_changed(self):
        gui = self.gui
        if gui.state.roi.var_lock:
            return
        gui.state.roi.confirmed = False
        gui._invalidate_global_scale()
        try:
            roi = gui._get_roi()
        except Exception:
            return
        gui._update_edit_roi_artists(roi)
        gui._schedule_view_update()

    def on_roi_entry_confirm(self, _event=None):
        gui = self.gui
        if gui._data_source is None:
            return
        try:
            roi = gui._get_roi()
        except Exception:
            return
        gui._apply_roi_update(roi, schedule_views=True, invalidate_scale=True, confirm=True)

    def on_preview_configure(self):
        gui = self.gui
        try:
            widget = gui.preview_canvas.get_tk_widget()
            avail_w = max(widget.winfo_width(), 1)
            avail_h = max(widget.winfo_height(), 1)
        except Exception:
            return
        try:
            _, height = gui.preview_fig.get_size_inches()
            dpi = gui.preview_fig.get_dpi()
            _ = height * dpi
        except Exception:
            pass
        pad_x, pad_y = gui.state.preview.pad_px
        try:
            widget.pack_configure(padx=int(pad_x), pady=int(pad_y))
        except Exception:
            pass

    def on_range_slider_changed(self, vmin: float, vmax: float):
        gui = self.gui
        if gui.scale_mode.get() != "manual":
            return
        if gui.state.scale.slider_lock:
            return
        gui._set_manual_scale_vars(vmin, vmax)
        gui._update_scale_ratio_from_values(vmin, vmax)
        gui.state.edit.map_dirty = True
        gui._schedule_view_update()

    def on_edit_configure(self, _event):
        gui = self.gui
        if gui._data_source is None:
            return
        if gui.state.edit.view_bounds is not None:
            gui.state.edit.view_bounds = gui._fit_bounds_to_canvas(gui.state.edit.view_bounds)
        elif gui.state.edit.base_bounds is not None:
            gui.state.edit.view_bounds = gui._fit_bounds_to_canvas(gui.state.edit.base_bounds)
        gui.state.edit.map_dirty = True
        gui._schedule_edit_background_render()
        try:
            roi = gui._get_roi()
        except Exception:
            return
        gui._update_edit_roi_artists(roi)

    def on_edit_press(self, event):
        gui = self.gui
        if gui._data_source is None:
            return
        if event.num != 1:
            return
        pos = gui._canvas_to_data(event.x, event.y)
        if pos is None:
            return
        try:
            roi = gui._get_roi()
        except Exception:
            return
        handle = gui._hit_test_handle(event)
        if handle:
            # ハンドル操作（回転・幅・高さ）
            gui.state.roi.drag_state = {"mode": "handle", "kind": handle.get("kind"), "sign": handle.get("sign")}
            return
        if gui._point_in_polygon(pos[0], pos[1], roi_corners(roi)):
            # ROI内クリックは移動モード
            gui.state.roi.drag_state = {
                "mode": "move",
                "offset": (roi.cx - pos[0], roi.cy - pos[1]),
            }

    def on_edit_motion(self, event):
        gui = self.gui
        if gui._data_source is None:
            return
        if gui.state.roi.drag_state is None:
            return
        pos = gui._canvas_to_data(event.x, event.y)
        if pos is None:
            return
        try:
            roi = gui._get_roi()
        except Exception:
            return
        xdata, ydata = pos

        mode = gui.state.roi.drag_state.get("mode")
        new_roi = update_roi_from_drag(
            roi,
            mode=mode,
            xdata=xdata,
            ydata=ydata,
            offset=gui.state.roi.drag_state.get("offset"),
            kind=gui.state.roi.drag_state.get("kind"),
            sign=gui.state.roi.drag_state.get("sign"),
        )
        if new_roi is None:
            return
        gui.state.roi.drag_state["roi"] = new_roi
        gui._apply_roi_update(new_roi, schedule_views=False, invalidate_scale=False, confirm=False)
        gui.state.preview.dragging = True

    def on_edit_release(self, event):
        gui = self.gui
        if gui._data_source is None:
            return
        if gui.state.roi.drag_state is None:
            return
        roi = gui.state.roi.drag_state.get("roi")
        gui.state.roi.drag_state = None
        gui.state.preview.dragging = False
        if roi is not None:
            # リリース時に確定扱いとしてスケール更新を許可。
            gui._apply_roi_update(roi, schedule_views=True, invalidate_scale=True, confirm=True)
            gui._schedule_view_update(immediate=True)

    def on_edit_scroll(self, event):
        gui = self.gui
        if gui._data_source is None:
            return
        if event.state & 0x0004 == 0:
            return
        pos = gui._canvas_to_data(event.x, event.y)
        if pos is None:
            return

        xmin, xmax, ymin, ymax = gui._edit_view_bounds_or_base()
        cur_w = xmax - xmin
        cur_h = ymax - ymin
        if cur_w <= 0 or cur_h <= 0:
            return
        delta = getattr(event, "delta", 0)
        direction = 1 if delta > 0 or getattr(event, "num", None) == 4 else -1
        zoom = 0.9 if direction > 0 else 1.1
        new_w = cur_w * zoom
        new_h = cur_h * zoom
        relx = (pos[0] - xmin) / cur_w
        rely = (pos[1] - ymin) / cur_h

        base_fit = None
        if gui.state.edit.base_bounds is not None:
            base_fit = gui._fit_bounds_to_canvas(gui.state.edit.base_bounds)
            base_w = base_fit[1] - base_fit[0]
            base_h = base_fit[3] - base_fit[2]
            new_w = min(new_w, base_w)
            new_h = min(new_h, base_h)

        new_xmin = pos[0] - new_w * relx
        new_xmax = pos[0] + new_w * (1 - relx)
        new_ymin = pos[1] - new_h * rely
        new_ymax = pos[1] + new_h * (1 - rely)

        if base_fit is not None:
            bxmin, bxmax, bymin, bymax = base_fit
            if new_w >= (bxmax - bxmin):
                new_xmin, new_xmax = bxmin, bxmax
            else:
                if new_xmin < bxmin:
                    shift = bxmin - new_xmin
                    new_xmin += shift
                    new_xmax += shift
                if new_xmax > bxmax:
                    shift = new_xmax - bxmax
                    new_xmin -= shift
                    new_xmax -= shift
            if new_h >= (bymax - bymin):
                new_ymin, new_ymax = bymin, bymax
            else:
                if new_ymin < bymin:
                    shift = bymin - new_ymin
                    new_ymin += shift
                    new_ymax += shift
                if new_ymax > bymax:
                    shift = new_ymax - bymax
                    new_ymin -= shift
                    new_ymax -= shift

        gui.state.edit.view_bounds = (new_xmin, new_xmax, new_ymin, new_ymax)
        gui.state.edit.map_dirty = True
        gui._schedule_edit_background_render()
        try:
            roi = gui._get_roi()
            gui._update_edit_roi_artists(roi)
        except Exception:
            pass
