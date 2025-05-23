# iRIC_DataScope\cross_section\plot_core.py

from pathlib import Path
from typing import Optional, List
from .data_loader import load_profile_data
from .excel_utils import write_profile_charts

def run_plot_profile(
    input_dir: Path,
    output_dir: Path,
    mode: str = "single",
    selected_file: Optional[Path] = None,
    include_ids: Optional[List[float]] = None,
    show_legend: bool = True,
    show_title: bool = True,
    show_grid: bool = True,
    yticks_count: int = 5,
    yticks_integer: bool = False,
    yaxis_mode: str = "individual",
    yaxis_manual: tuple[float, float] | None = None,  # ← 追加
    show_wse: bool = True,                        
    x_scale: float = 1.0,
    y_scale: float = 1.0,
    excel_filename: str = "profile_charts.xlsx",
    sheet_prefix: str = "Profile_"
) -> Path:
    """
    データ読み込みから Excel 出力まで一貫して実行。
    """
    # 1) データ読み込み
    grouped = load_profile_data(
        input_dir=input_dir,
        mode=mode,
        selected_file=selected_file,
        include_ids=include_ids
    )

    # 2) 出力先準備
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / excel_filename

    # 3) Excel & グラフ作成
    write_profile_charts(
        grouped_data=grouped,
        output_path=out_path,
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
        sheet_prefix=sheet_prefix
    )

    return out_path
