from __future__ import annotations

import tkinter as tk
from pathlib import Path

from .gui_components import TimeSeriesGUI


def launch_from_launcher(
    master: tk.Misc,
    *,
    input_path: Path,
    output_dir: Path,
) -> TimeSeriesGUI:
    return TimeSeriesGUI(
        master=master,
        initial_input_dir=input_path,
        initial_output_dir=output_dir,
    )
