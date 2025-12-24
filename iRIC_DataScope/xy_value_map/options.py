from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .style import (
    DEFAULT_CBAR_LABEL_FONT_SIZE,
    DEFAULT_TICK_FONT_SIZE,
    DEFAULT_TITLE_FONT_SIZE,
)


@dataclass
class OutputOptions:
    show_title: bool = True
    title_text: str = ""
    show_ticks: bool = True
    show_frame: bool = True
    show_cbar: bool = True
    cbar_label: str = ""
    pad_inches: float = 0.02
    title_font_size: float | None = DEFAULT_TITLE_FONT_SIZE
    tick_font_size: float | None = DEFAULT_TICK_FONT_SIZE
    cbar_label_font_size: float | None = DEFAULT_CBAR_LABEL_FONT_SIZE
    figsize: Tuple[float, float] = (6.0, 4.0)
    colormap_mode: str = "rgb"
    output_scale: float = 1.0

    def to_kwargs(self) -> dict[str, object]:
        return {
            "show_title": self.show_title,
            "title_text": self.title_text,
            "show_ticks": self.show_ticks,
            "show_frame": self.show_frame,
            "show_cbar": self.show_cbar,
            "cbar_label": self.cbar_label,
            "pad_inches": self.pad_inches,
            "title_font_size": self.title_font_size,
            "tick_font_size": self.tick_font_size,
            "cbar_label_font_size": self.cbar_label_font_size,
            "figsize": tuple(self.figsize),
            "colormap_mode": self.colormap_mode,
            "output_scale": self.output_scale,
        }
