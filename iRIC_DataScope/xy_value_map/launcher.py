from __future__ import annotations

import tkinter as tk
from pathlib import Path

from .gui import XYValueMapGUI


def launch_from_launcher(
    master: tk.Misc,
    *,
    input_path: Path,
    output_dir: Path,
) -> XYValueMapGUI:
    return XYValueMapGUI(master, input_path=input_path, output_dir=output_dir)
