from __future__ import annotations

from pathlib import Path
import tkinter as tk

from iRIC_DataScope.section_analyze.gui import SectionAnalyzeGUI


def launch_from_launcher(master: tk.Misc, *, input_path: Path, output_dir: Path):
    return SectionAnalyzeGUI(master, input_path=input_path, output_dir=output_dir)

