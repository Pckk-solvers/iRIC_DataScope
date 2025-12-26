from __future__ import annotations

import tkinter as tk
from pathlib import Path

from .gui import ProfilePlotGUI


def launch_from_launcher(
    master: tk.Misc,
    *,
    input_path: Path,
    output_dir: Path,
) -> ProfilePlotGUI:
    return ProfilePlotGUI(master, input_dir=input_path, output_dir=output_dir)
