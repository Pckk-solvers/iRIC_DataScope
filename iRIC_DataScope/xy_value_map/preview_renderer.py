"""プレビュー描画の処理をまとめ、GUIから分離する。"""

from __future__ import annotations

from .options import OutputOptions
from .plot import render_xy_value_map
from .processor import Roi


class PreviewRenderer:
    """プレビュー描画の責務をまとめたヘルパー。"""

    def __init__(self, fig, ax, canvas):
        self.fig = fig
        self.ax = ax
        self.canvas = canvas
        self.mesh = None
        self.cbar = None
        self.tight_rect = None

    def reset_axes(self):
        """既存のAxesやカラーバーを破棄して初期化する。"""
        try:
            face = self.fig.get_facecolor()
        except Exception:
            face = None
        try:
            self.fig.clf()
        except Exception:
            pass
        try:
            self.ax = self.fig.add_subplot(111)
        except Exception:
            pass
        if face is not None:
            try:
                self.fig.patch.set_facecolor(face)
            except Exception:
                pass
        self.cbar = None
        self.mesh = None
        self.tight_rect = None

    def build_plot_title(self, *, step: int, t: float, value_col: str, output_opts: OutputOptions) -> str:
        if not output_opts.show_title:
            return ""
        if output_opts.title_text:
            return output_opts.title_text
        return ""

    def apply_plot_options(self, *, mesh, output_opts: OutputOptions):
        """目盛り/枠線/カラーバーの表示を調整する。"""
        show_ticks = bool(output_opts.show_ticks)
        show_frame = bool(output_opts.show_frame)
        show_cbar = bool(output_opts.show_cbar)

        self.ax.tick_params(
            bottom=show_ticks,
            left=show_ticks,
            labelbottom=show_ticks,
            labelleft=show_ticks,
        )

        for spine in self.ax.spines.values():
            spine.set_visible(show_frame)

        if show_cbar:
            if self.cbar is not None:
                try:
                    self.cbar.remove()
                except Exception:
                    pass
                self.cbar = None
            if mesh is None:
                return
            try:
                bbox = self.ax.get_position()
                cb_width = 0.03
                cb_pad = 0.005
                cax = self.fig.add_axes(
                    [
                        bbox.x1 + cb_pad,
                        bbox.y0,
                        cb_width,
                        bbox.height,
                    ]
                )
                self.cbar = self.fig.colorbar(mesh, cax=cax)
                cbar_label = output_opts.cbar_label
                if cbar_label:
                    try:
                        self.cbar.ax.set_ylabel(
                            cbar_label,
                            fontsize=output_opts.cbar_label_font_size,
                            rotation=270,
                            labelpad=10,
                        )
                    except Exception:
                        pass
                tick_fs = output_opts.tick_font_size
                if tick_fs is not None:
                    try:
                        self.cbar.ax.tick_params(labelsize=tick_fs)
                    except Exception:
                        pass
            except Exception:
                self.cbar = None
        else:
            if self.cbar is not None:
                try:
                    self.cbar.remove()
                except Exception:
                    pass
                self.cbar = None

    def draw_empty_preview(
        self,
        roi: Roi,
        *,
        output_opts: OutputOptions,
        title: str = "No points in ROI",
    ):
        """ROI内に点がない場合のダミー描画。"""
        self.reset_axes()
        self.apply_plot_options(mesh=None, output_opts=output_opts)
        title = title if output_opts.show_title else ""
        self.ax.set_title(title)
        width = max(float(roi.width), 1e-12)
        height = max(float(roi.height), 1e-12)
        self.ax.set_xlim(0.0, width)
        self.ax.set_ylim(0.0, height)
        self.ax.set_aspect("equal", adjustable="box")
        self._draw_and_overlay(pad_inches=output_opts.pad_inches)

    def draw_preview(
        self,
        *,
        x,
        y,
        vals,
        roi: Roi,
        value_col: str,
        step: int,
        t: float,
        cmap,
        vmin: float,
        vmax: float,
        output_opts: OutputOptions,
    ):
        """通常のプレビュー描画。"""
        self.reset_axes()
        title = self.build_plot_title(step=step, t=t, value_col=value_col, output_opts=output_opts)
        self.mesh = render_xy_value_map(
            fig=self.fig,
            ax=self.ax,
            x=x,
            y=y,
            vals=vals,
            roi=roi,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            title=title,
            show_ticks=output_opts.show_ticks,
            show_frame=output_opts.show_frame,
            show_cbar=output_opts.show_cbar,
            cbar_label=output_opts.cbar_label,
            title_font_size=output_opts.title_font_size,
            tick_font_size=output_opts.tick_font_size,
            cbar_label_font_size=output_opts.cbar_label_font_size,
        )
        self._draw_and_overlay(pad_inches=output_opts.pad_inches)

    def update_tight_bbox_overlay(self, pad_inches: float = 0.02):
        """Preview 用: bbox_inches='tight' 相当の領域を破線で可視化する。"""
        try:
            if self.fig is None or self.canvas is None:
                return
            if self.tight_rect is not None:
                try:
                    self.tight_rect.remove()
                except Exception:
                    pass
                self.tight_rect = None

            self.canvas.draw()
            renderer = self.canvas.get_renderer()
            if renderer is None:
                return

            from matplotlib.transforms import Bbox

            tight = self.fig.get_tightbbox(renderer)
            fig_box = self.fig.get_window_extent(renderer)
            if tight is None or fig_box is None:
                return
            dpi = self.fig.get_dpi()
            pad_px = max(pad_inches, 0.0) * dpi
            tight_px = tight.transformed(self.fig.dpi_scale_trans)
            bbox = Bbox.from_extents(
                tight_px.x0 - pad_px, tight_px.y0 - pad_px, tight_px.x1 + pad_px, tight_px.y1 + pad_px
            )

            w_fig = fig_box.width
            h_fig = fig_box.height
            if w_fig <= 0 or h_fig <= 0:
                return
            x0 = (bbox.x0 - fig_box.x0) / w_fig
            y0 = (bbox.y0 - fig_box.y0) / h_fig
            width = bbox.width / w_fig
            height = bbox.height / h_fig
            if width <= 0 or height <= 0:
                return

            from matplotlib.patches import Rectangle

            rect = Rectangle(
                (x0, y0),
                width,
                height,
                transform=self.fig.transFigure,
                fill=False,
                edgecolor="#808080",
                linestyle="--",
                linewidth=1.0,
                zorder=20,
            )
            rect.set_clip_on(False)
            self.fig.add_artist(rect)
            self.tight_rect = rect
            self.canvas.draw_idle()
        except Exception:
            pass

    def _draw_and_overlay(self, *, pad_inches: float):
        if self.canvas is None:
            return
        self.canvas.draw_idle()
        self.update_tight_bbox_overlay(pad_inches=pad_inches)
