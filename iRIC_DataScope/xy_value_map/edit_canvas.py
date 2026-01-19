"""編集キャンバスの描画と座標変換ロジックをまとめる。"""

from __future__ import annotations

import base64
import io
import math

import numpy as np
import tkinter as tk

from .data_prep import build_edit_grid
from .processor import Roi, RoiGrid, roi_corners


class EditTransform:
    def __init__(self, bounds: tuple[float, float, float, float], scale: float, offset_x: float, offset_y: float):
        self.bounds = bounds
        self.scale = scale
        self.offset_x = offset_x
        self.offset_y = offset_y


def compute_edit_transform(
    bounds: tuple[float, float, float, float],
    canvas_size: tuple[int, int],
) -> EditTransform:
    xmin, xmax, ymin, ymax = bounds
    width, _ = canvas_size
    span_x = max(xmax - xmin, 1e-12)
    scale = width / span_x
    return EditTransform(bounds, scale, 0.0, 0.0)


def data_to_canvas(x: float, y: float, transform: EditTransform) -> tuple[float, float] | None:
    xmin, xmax, ymin, ymax = transform.bounds
    if transform.scale <= 0:
        return None
    cx = transform.offset_x + (x - xmin) * transform.scale
    cy = transform.offset_y + (ymax - y) * transform.scale
    return cx, cy


def canvas_to_data(cx: float, cy: float, transform: EditTransform) -> tuple[float, float] | None:
    xmin, xmax, ymin, ymax = transform.bounds
    if transform.scale <= 0:
        return None
    x = xmin + (cx - transform.offset_x) / transform.scale
    y = ymax - (cy - transform.offset_y) / transform.scale
    return x, y


def compute_roi_handle_positions(
    roi: Roi,
    transform: EditTransform,
    *,
    handle_radius: float = 6.0,
) -> list[dict[str, float | int | str]]:
    if transform.scale <= 0:
        return []
    theta = math.radians(roi.angle_deg)
    ux = np.array([math.cos(theta), math.sin(theta)])
    uy = np.array([-math.sin(theta), math.cos(theta)])
    half_w = 0.5 * roi.width
    half_h = 0.5 * roi.height
    width_vec = half_w * ux
    height_vec = half_h * uy
    rotate_offset_px = max(handle_radius * 3.0, 18.0)
    rotate_offset = rotate_offset_px / transform.scale
    rotate_vec = (half_h + rotate_offset) * uy
    handles = [
        ("width", 1, roi.cx + width_vec[0], roi.cy + width_vec[1]),
        ("width", -1, roi.cx - width_vec[0], roi.cy - width_vec[1]),
        ("height", 1, roi.cx + height_vec[0], roi.cy + height_vec[1]),
        ("height", -1, roi.cx - height_vec[0], roi.cy - height_vec[1]),
        ("rotate", 0, roi.cx + rotate_vec[0], roi.cy + rotate_vec[1]),
    ]
    out: list[dict[str, float | int | str]] = []
    for kind, sign, hx, hy in handles:
        pos = data_to_canvas(float(hx), float(hy), transform)
        if pos is None:
            continue
        out.append({"kind": kind, "sign": int(sign), "cx": pos[0], "cy": pos[1]})
    return out


def compute_roi_canvas_geometry(
    roi: Roi,
    transform: EditTransform,
    *,
    handle_radius: float = 6.0,
) -> dict[str, object] | None:
    corners = roi_corners(roi)
    canvas_corners: list[float] = []
    for x, y in corners:
        pt = data_to_canvas(float(x), float(y), transform)
        if pt is None:
            return None
        canvas_corners.extend([pt[0], pt[1]])

    theta = math.radians(roi.angle_deg)
    uy = np.array([-math.sin(theta), math.cos(theta)])
    half_h = 0.5 * roi.height
    height_vec = half_h * uy
    rotate_offset_px = max(handle_radius * 3.0, 18.0)
    rotate_offset = rotate_offset_px / max(transform.scale, 1e-12)
    rotate_vec = (half_h + rotate_offset) * uy

    bottom_start = data_to_canvas(float(corners[0, 0]), float(corners[0, 1]), transform)
    bottom_end = data_to_canvas(float(corners[1, 0]), float(corners[1, 1]), transform)
    top_center = np.array([roi.cx, roi.cy]) + height_vec
    rotate_pos = np.array([roi.cx + rotate_vec[0], roi.cy + rotate_vec[1]])
    top_center_canvas = data_to_canvas(float(top_center[0]), float(top_center[1]), transform)
    rotate_canvas = data_to_canvas(float(rotate_pos[0]), float(rotate_pos[1]), transform)

    return {
        "polygon": canvas_corners,
        "bottom_edge": (bottom_start, bottom_end),
        "rotate_line": (top_center_canvas, rotate_canvas),
        "handles": compute_roi_handle_positions(roi, transform, handle_radius=handle_radius),
    }


class EditCanvasManager:
    """編集キャンバスの描画と座標系を管理する。"""

    def __init__(self, gui):
        self.gui = gui

    def edit_canvas_size(self) -> tuple[int, int]:
        if self.gui.edit_canvas is None:
            return 1, 1
        width = max(int(self.gui.edit_canvas.winfo_width()), 1)
        height = max(int(self.gui.edit_canvas.winfo_height()), 1)
        return width, height

    def fit_bounds_to_canvas(
        self, bounds: tuple[float, float, float, float]
    ) -> tuple[float, float, float, float]:
        xmin, xmax, ymin, ymax = bounds
        width, height = self.edit_canvas_size()
        if width <= 0 or height <= 0:
            return bounds
        span_x = max(xmax - xmin, 1e-12)
        span_y = max(ymax - ymin, 1e-12)
        canvas_ratio = width / height
        bounds_ratio = span_x / span_y
        if abs(bounds_ratio - canvas_ratio) < 1e-6:
            return bounds
        if bounds_ratio > canvas_ratio:
            new_span_y = span_x / canvas_ratio
            pad = (new_span_y - span_y) * 0.5
            ymin -= pad
            ymax += pad
        else:
            new_span_x = span_y * canvas_ratio
            pad = (new_span_x - span_x) * 0.5
            xmin -= pad
            xmax += pad
        return xmin, xmax, ymin, ymax

    def edit_view_bounds_or_base(self) -> tuple[float, float, float, float]:
        if self.gui.state.edit.view_bounds is not None:
            return self.fit_bounds_to_canvas(self.gui.state.edit.view_bounds)
        if self.gui.state.edit.base_bounds is not None:
            return self.fit_bounds_to_canvas(self.gui.state.edit.base_bounds)
        if self.gui._data_source is not None:
            return self.fit_bounds_to_canvas(self.gui._data_source.domain_bounds)
        return self.fit_bounds_to_canvas((0.0, 1.0, 0.0, 1.0))

    def roi_edit_bounds(self) -> tuple[float, float, float, float]:
        if self.gui.state.edit.base_bounds is not None:
            return self.fit_bounds_to_canvas(self.gui.state.edit.base_bounds)
        if self.gui._data_source is not None:
            return self.fit_bounds_to_canvas(self.gui._data_source.domain_bounds)
        return self.fit_bounds_to_canvas((0.0, 1.0, 0.0, 1.0))

    def edit_transform(self) -> EditTransform:
        bounds = self.edit_view_bounds_or_base()
        return compute_edit_transform(bounds, self.edit_canvas_size())

    def edit_zoom_ratio(self) -> float:
        if self.gui.state.edit.base_bounds is None:
            return 1.0
        base = self.fit_bounds_to_canvas(self.gui.state.edit.base_bounds)
        view = self.edit_view_bounds_or_base()
        base_span = max(base[1] - base[0], 1e-12)
        view_span = max(view[1] - view[0], 1e-12)
        return base_span / view_span

    def data_to_canvas(self, x: float, y: float) -> tuple[float, float] | None:
        return data_to_canvas(x, y, self.edit_transform())

    def canvas_to_data(self, cx: float, cy: float) -> tuple[float, float] | None:
        return canvas_to_data(cx, cy, self.edit_transform())

    def update_canvas_rect(
        self,
        rect_id: int | None,
        bounds: tuple[float, float, float, float],
        *,
        outline: str,
        dash: tuple[int, int] | None = None,
    ) -> int | None:
        if self.gui.edit_canvas is None:
            return rect_id
        xmin, xmax, ymin, ymax = bounds
        p1 = self.data_to_canvas(xmin, ymax)
        p2 = self.data_to_canvas(xmax, ymin)
        if p1 is None or p2 is None:
            return rect_id
        if rect_id is None:
            rect_id = self.gui.edit_canvas.create_rectangle(
                p1[0],
                p1[1],
                p2[0],
                p2[1],
                outline=outline,
                dash=dash,
                width=1,
            )
        else:
            self.gui.edit_canvas.coords(rect_id, p1[0], p1[1], p2[0], p2[1])
            self.gui.edit_canvas.itemconfig(rect_id, outline=outline, dash=dash, width=1)
        return rect_id

    def update_canvas_text_with_bg(
        self,
        text_id: int | None,
        bg_id: int | None,
        text: str,
        *,
        x: float,
        y: float,
        anchor: str,
    ) -> tuple[int | None, int | None]:
        if self.gui.edit_canvas is None:
            return text_id, bg_id
        if text_id is None:
            text_id = self.gui.edit_canvas.create_text(
                x,
                y,
                anchor=anchor,
                text=text,
                fill="#333333",
                font=("TkDefaultFont", 9),
            )
        else:
            self.gui.edit_canvas.coords(text_id, x, y)
            self.gui.edit_canvas.itemconfig(
                text_id,
                text=text,
                anchor=anchor,
                fill="#333333",
                font=("TkDefaultFont", 9),
            )
        bbox = self.gui.edit_canvas.bbox(text_id)
        if bbox:
            pad = 3
            rect_coords = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
            if bg_id is None:
                bg_id = self.gui.edit_canvas.create_rectangle(
                    *rect_coords,
                    fill="#ffffff",
                    outline="#dddddd",
                    width=1,
                )
            else:
                self.gui.edit_canvas.coords(bg_id, *rect_coords)
                self.gui.edit_canvas.itemconfig(bg_id, fill="#ffffff", outline="#dddddd", width=1)
            self.gui.edit_canvas.tag_lower(bg_id, text_id)
        return text_id, bg_id

    def update_edit_bounds_overlay(self):
        if self.gui.edit_canvas is None or self.gui._data_source is None:
            return
        if self.gui._edit_domain_rect_id is not None:
            self.gui.edit_canvas.delete(self.gui._edit_domain_rect_id)
            self.gui._edit_domain_rect_id = None
        if self.gui._edit_pad_rect_id is not None:
            self.gui.edit_canvas.delete(self.gui._edit_pad_rect_id)
            self.gui._edit_pad_rect_id = None

    def update_edit_overlay_text(self):
        if self.gui.edit_canvas is None:
            return
        step = self.gui.state.edit.context.get("step")
        time_val = self.gui.state.edit.context.get("time")
        value_col = self.gui.state.edit.context.get("value")
        zoom = self.edit_zoom_ratio()

        lines = ["編集ビュー（全体表示）", "表示: 全体+余白"]
        if step is not None:
            if time_val is None:
                lines.append(f"step={step}  value={value_col}")
            else:
                lines.append(f"step={step}  t={time_val:g}  value={value_col}")
        lines.append("スケール: 全体min/max（1ステップ）")
        lines.append(f"ズーム: {zoom:.2f}x")
        text = "\n".join(lines)

        self.gui._edit_overlay_text_id, self.gui._edit_overlay_bg_id = self.update_canvas_text_with_bg(
            self.gui._edit_overlay_text_id,
            self.gui._edit_overlay_bg_id,
            text,
            x=8,
            y=6,
            anchor="nw",
        )

        guide = "ドラッグ: 移動\nハンドル: 拡縮 / 回転\nCtrl+ホイール: ズーム"
        _, height = self.edit_canvas_size()
        self.gui._edit_hint_text_id, self.gui._edit_hint_bg_id = self.update_canvas_text_with_bg(
            self.gui._edit_hint_text_id,
            self.gui._edit_hint_bg_id,
            guide,
            x=8,
            y=height - 6,
            anchor="sw",
        )

    def update_edit_overlay(self):
        if self.gui.edit_canvas is None:
            return
        self.update_edit_outline()
        self.update_edit_bounds_overlay()
        if self.gui._roi_patch is not None:
            if self.gui._edit_pad_rect_id is not None:
                self.gui.edit_canvas.tag_lower(self.gui._edit_pad_rect_id, self.gui._roi_patch)
            if self.gui._edit_domain_rect_id is not None:
                self.gui.edit_canvas.tag_lower(self.gui._edit_domain_rect_id, self.gui._roi_patch)
        self.update_edit_overlay_text()
        for item_id in (
            self.gui._edit_overlay_bg_id,
            self.gui._edit_overlay_text_id,
            self.gui._edit_hint_bg_id,
            self.gui._edit_hint_text_id,
        ):
            if item_id is not None:
                self.gui.edit_canvas.tag_raise(item_id)

    def compute_grid_outline(self, grid: RoiGrid) -> np.ndarray | None:
        try:
            x = np.asarray(grid.x, dtype=float)
            y = np.asarray(grid.y, dtype=float)
        except Exception:
            return None
        if x.size == 0 or y.size == 0:
            return None
        top = np.column_stack([x[0, :], y[0, :]])
        right = np.column_stack([x[1:, -1], y[1:, -1]])
        bottom = np.column_stack([x[-1, -2::-1], y[-1, -2::-1]])
        left = np.column_stack([x[-2:0:-1, 0], y[-2:0:-1, 0]])
        outline = np.vstack([top, right, bottom, left, top[:1]])
        return outline

    def update_edit_outline(self):
        if self.gui.edit_canvas is None:
            return
        outline = self.gui.state.edit.outline_points
        if outline is None or outline.size == 0:
            if self.gui._edit_outline_id is not None:
                self.gui.edit_canvas.delete(self.gui._edit_outline_id)
                self.gui._edit_outline_id = None
            return
        coords: list[float] = []
        for x, y in outline:
            pt = self.data_to_canvas(float(x), float(y))
            if pt is None:
                continue
            coords.extend([pt[0], pt[1]])
        if len(coords) < 4:
            return
        if self.gui._edit_outline_id is None:
            self.gui._edit_outline_id = self.gui.edit_canvas.create_line(
                *coords,
                fill="#666666",
                width=1,
                smooth=False,
            )
        else:
            self.gui.edit_canvas.coords(self.gui._edit_outline_id, *coords)
            self.gui.edit_canvas.itemconfig(self.gui._edit_outline_id, fill="#666666", width=1)

    def render_edit_background(self, frame, value_col, cmap, scale):
        width, height = self.edit_canvas_size()
        if width < 2 or height < 2:
            return

        grid = build_edit_grid(frame, value_col=value_col, max_points=40000)
        self.gui.state.edit.outline_points = self.compute_grid_outline(grid)

        vals = np.asarray(grid.v, dtype=float)
        if scale is None:
            finite = vals[np.isfinite(vals)]
            if finite.size:
                vmin, vmax = float(finite.min()), float(finite.max())
            else:
                vmin, vmax = 0.0, 1.0
        else:
            vmin, vmax = scale

        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        dpi = 100
        if self.gui._edit_fig is None:
            self.gui._edit_fig = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
            self.gui._edit_ax = self.gui._edit_fig.add_axes([0, 0, 1, 1])
            self.gui._edit_agg = FigureCanvasAgg(self.gui._edit_fig)
        else:
            self.gui._edit_fig.set_size_inches(width / dpi, height / dpi, forward=True)

        ax = self.gui._edit_ax
        ax.clear()
        ax.set_axis_off()
        ax.set_aspect("equal", adjustable="box")
        bounds = self.edit_view_bounds_or_base()
        ax.set_xlim(bounds[0], bounds[1])
        ax.set_ylim(bounds[2], bounds[3])
        ax.pcolormesh(
            grid.x,
            grid.y,
            vals,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            shading="gouraud",
        )

        assert self.gui._edit_agg is not None
        self.gui._edit_agg.draw()
        buf = io.BytesIO()
        self.gui._edit_agg.print_png(buf)
        png_data = base64.b64encode(buf.getvalue()).decode("ascii")
        self.gui._edit_image_tk = tk.PhotoImage(data=png_data)

        if self.gui._edit_image_id is None:
            self.gui._edit_image_id = self.gui.edit_canvas.create_image(0, 0, anchor="nw", image=self.gui._edit_image_tk)
        else:
            self.gui.edit_canvas.itemconfig(self.gui._edit_image_id, image=self.gui._edit_image_tk)
        self.gui.edit_canvas.tag_lower(self.gui._edit_image_id)
        self.update_edit_outline()

    def schedule_edit_background_render(self, immediate: bool = False):
        if self.gui.state.edit.render_context is None:
            return
        if self.gui.state.edit.render_job is not None:
            try:
                self.gui.after_cancel(self.gui.state.edit.render_job)
            except Exception:
                pass
        delay = 0 if immediate else 120
        self.gui.state.edit.render_job = self.gui.after(delay, self.render_edit_background_from_context)

    def render_edit_background_from_context(self):
        self.gui.state.edit.render_job = None
        context = self.gui.state.edit.render_context
        if context is None:
            return
        self.render_edit_background(
            context["frame"],
            context["value_col"],
            context["cmap"],
            context["scale"],
        )
        self.gui.state.edit.map_dirty = False

    def update_edit_roi_artists(self, roi: Roi):
        if self.gui.edit_canvas is None:
            return
        transform = self.edit_transform()
        geometry = compute_roi_canvas_geometry(roi, transform)
        if geometry is None:
            return

        canvas_corners = geometry["polygon"]
        bottom_start, bottom_end = geometry["bottom_edge"]
        top_center_canvas, rotate_canvas = geometry["rotate_line"]

        if self.gui._roi_patch is None:
            self.gui._roi_patch = self.gui.edit_canvas.create_polygon(
                canvas_corners,
                outline="#ffcc00",
                width=2,
                fill="",
                joinstyle=tk.ROUND,
            )
            self.gui._roi_bottom_edge = self.gui.edit_canvas.create_line(
                0,
                0,
                0,
                0,
                fill="#00bcd4",
                width=3,
            )
            self.gui._roi_rotate_line = self.gui.edit_canvas.create_line(
                0,
                0,
                0,
                0,
                fill="#00bcd4",
                width=1,
            )
            self.gui._roi_handles = []
            for _ in range(5):
                hid = self.gui.edit_canvas.create_oval(
                    0,
                    0,
                    0,
                    0,
                    fill="#ffcc00",
                    outline="#333333",
                    width=1,
                )
                self.gui._roi_handles.append({"id": hid, "kind": "width", "sign": 1, "cx": 0.0, "cy": 0.0})
        else:
            self.gui.edit_canvas.coords(self.gui._roi_patch, *canvas_corners)

        if self.gui._roi_bottom_edge is not None and bottom_start and bottom_end:
            self.gui.edit_canvas.coords(
                self.gui._roi_bottom_edge,
                bottom_start[0],
                bottom_start[1],
                bottom_end[0],
                bottom_end[1],
            )
        if self.gui._roi_rotate_line is not None and top_center_canvas and rotate_canvas:
            self.gui.edit_canvas.coords(
                self.gui._roi_rotate_line,
                top_center_canvas[0],
                top_center_canvas[1],
                rotate_canvas[0],
                rotate_canvas[1],
            )

        handles = geometry["handles"]
        handle_radius = 6.0
        for handle, info in zip(self.gui._roi_handles, handles):
            handle["kind"] = info["kind"]
            handle["sign"] = info["sign"]
            handle["cx"] = info["cx"]
            handle["cy"] = info["cy"]
            hid = handle["id"]
            self.gui.edit_canvas.coords(
                hid,
                info["cx"] - handle_radius,
                info["cy"] - handle_radius,
                info["cx"] + handle_radius,
                info["cy"] + handle_radius,
            )
            fill = "#00bcd4" if info["kind"] == "rotate" else "#ffcc00"
            self.gui.edit_canvas.itemconfig(hid, fill=fill)

        if self.gui._roi_patch is not None:
            self.gui.edit_canvas.tag_raise(self.gui._roi_patch)
        if self.gui._roi_bottom_edge is not None:
            self.gui.edit_canvas.tag_raise(self.gui._roi_bottom_edge)
        if self.gui._roi_rotate_line is not None:
            self.gui.edit_canvas.tag_raise(self.gui._roi_rotate_line)
        for handle in self.gui._roi_handles:
            self.gui.edit_canvas.tag_raise(handle["id"])

        self.update_edit_overlay()
