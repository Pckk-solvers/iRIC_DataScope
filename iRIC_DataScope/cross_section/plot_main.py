# iric_tools/plot_profile/plot_main.py

from pathlib import Path
from typing import Optional, List
from .plot_core import run_plot_profile

def plot_main(
    input_dir: str,
    output_dir: str,
    mode: str = "single",
    selected_file: Optional[str] = None,
    include_ids: Optional[List[float]] = None,
    show_legend: bool = True,
    show_title: bool = True,
    show_grid: bool = True,
    yticks_count: int = 5,
    yticks_integer: bool = False,
    yaxis_mode: str = "individual",
    yaxis_manual: tuple[float, float] | None = None,   # ← 追加
    show_wse: bool = True,                       
    x_scale: float = 1.0,
    y_scale: float = 1.0,
    excel_filename: str = "profile_charts.xlsx",
    sheet_prefix: str = "Profile_"
) -> Path:
    """
    GUI から呼び出されるエントリポイント。
    """
    in_dir  = Path(input_dir)
    out_dir = Path(output_dir)
    sel     = Path(selected_file) if selected_file else None

    return run_plot_profile(
        input_dir=in_dir,
        output_dir=out_dir,
        mode=mode,
        selected_file=sel,
        include_ids=include_ids,
        show_legend=show_legend,
        show_title=show_title,
        show_grid=show_grid,
        yticks_count=yticks_count,
        yticks_integer=yticks_integer,
        yaxis_mode=yaxis_mode,
        yaxis_manual=yaxis_manual,  # ← 追加
        show_wse=show_wse,                        
        x_scale=x_scale,
        y_scale=y_scale,
        excel_filename=excel_filename,
        sheet_prefix=sheet_prefix
    )
