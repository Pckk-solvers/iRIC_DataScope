from __future__ import annotations

import tkinter as tk
from pathlib import Path

from .gui import LrWseGUI


def launch_from_launcher(
    master: tk.Misc,
    *,
    input_path: Path,
    output_dir: Path,
) -> LrWseGUI:
    return LrWseGUI(master, input_dir=input_path, output_dir=output_dir)
