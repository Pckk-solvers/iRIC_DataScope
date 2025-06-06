# iRIC_DataScope\cross_section\excel_utils.py

from pathlib import Path
from typing import Dict
import pandas as pd
import numpy as np
import math
import xlsxwriter

from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
import math

def write_profile_charts(
    grouped_data: Dict[float, Dict[float, pd.DataFrame]],
    output_path: Path,
    show_legend: bool,
    show_title: bool,
    show_grid: bool,
    yticks_count: int,
    yticks_integer: bool,
    yaxis_mode: str,                              # "individual" | "global" | "representative" | "manual"
    yaxis_manual: Optional[Tuple[float, float]] = None,
    show_wse: bool = True, 
    x_scale: float = 1.0,
    y_scale: float = 1.0,
    sheet_prefix: str = ""
) -> Path:
    """
    各 Profile_ID・各時刻をシートに書き出し、
    yaxis_mode による範囲統一オプションを反映した上で
    折れ線グラフを挿入する。
    """
    # ■■ 全体スキャン (global / representative モード用) ■■
    if yaxis_mode == "global":
        all_vals = []
        for tdict in grouped_data.values():
            for df in tdict.values():
                all_vals.extend(df["Elevation"].tolist())
                all_vals.extend(df["WaterSurface"].tolist())
        global_min = min(all_vals)
        global_max = max(all_vals)

    elif yaxis_mode == "representative":
        ranges = []
        for tdict in grouped_data.values():
            for df in tdict.values():
                lo, hi = df["Elevation"].min(), df["Elevation"].max()
                ranges.append(hi - lo)
        rep_range = sorted(ranges)[len(ranges) // 2]

    # ■■ ExcelWriter の起動 ■■
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        workbook = writer.book

        for pid, time_dict in grouped_data.items():
            sheet_name = f"{sheet_prefix}{int(pid)}"

            # --- データ書き出し ---
            first_t, first_df = next(iter(time_dict.items()))
            first_df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]

            row_offset = len(first_df) + 2
            for t, df in list(time_dict.items())[1:]:
                df.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    startrow=row_offset,
                    startcol=0,
                    index=False,
                    header=False
                )
                row_offset += len(df) + 1

            # --- Y軸範囲の決定 ---
            if yaxis_mode == "manual" and yaxis_manual is not None:
                # GUI から受け取った値をそのまま使う
                y_min, y_max = yaxis_manual

            elif yaxis_mode == "global":
                y_min, y_max = global_min, global_max

            elif yaxis_mode == "representative":
                sheet_mins = [df["Elevation"].min() for df in time_dict.values()]
                y_min = min(sheet_mins)
                y_max = y_min + rep_range

            else:  # individual
                y_vals = []
                for df in time_dict.values():
                    y_vals.extend(df["Elevation"].tolist())
                    y_vals.extend(df["WaterSurface"].tolist())
                y_min, y_max = min(y_vals), max(y_vals)

            # --- 目盛計算 & マージン ---
            span      = y_max - y_min
            intervals = max(1, yticks_count - 1)

            if yticks_integer:
                step = max(1, math.ceil(span / intervals))
            else:
                step = span / intervals

            y_max_snapped = y_min + step * intervals
            margin        = span * 0.05
            y_min_plot    = max(y_min - margin, 0)
            y_max_plot    = y_max_snapped + margin

            # --- チャート作成 ---
            chart = workbook.add_chart({'type': 'scatter', 'subtype': 'straight'})
            n_rows = len(first_df)
            cols   = list(first_df.columns)
            idx_dist = cols.index("Cumulative_Distance")
            idx_elev = cols.index("Elevation")
            idx_wse  = cols.index("WaterSurface")

            # カラーパレット（Excel 既定）
            palette = [
                '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
            ]
            for i, (t, df) in enumerate(time_dict.items()):
                start_row = 1 + i * (n_rows + 1)
                end_row   = start_row + len(df) - 1
                color = palette[i % len(palette)]

                # Elevation（実線）
                chart.add_series({
                    'name':       f"t={t}",
                    'categories': [sheet_name, start_row, idx_dist, end_row, idx_dist],
                    'values':     [sheet_name, start_row, idx_elev,  end_row, idx_elev],
                    'line':       {'color': color, 'width': 1},
                })

                # WaterSurface（破線）※show_wse=True のときのみ
                if show_wse:
                    chart.add_series({
                        'name':       f"t={t} WSE",
                        'categories': [sheet_name, start_row, idx_dist, end_row, idx_dist],
                        'values':     [sheet_name, start_row, idx_wse,   end_row, idx_wse],
                        'line':       {'color': color, 'dash_type': 'dash'},
                    })

            # --- 軸設定・凡例・タイトル・サイズ ---
            chart.set_x_axis({
                'name':            'Distance',
                'major_gridlines': {'visible': show_grid},
            })
            chart.set_y_axis({
                'name':            'Elevation',
                'major_gridlines': {'visible': show_grid},
                'min':             y_min_plot,
                'max':             y_max_plot,
                'major_unit':      step,
                'major_tick_mark': 'outside',
                'num_format':      '0' if yticks_integer else '0.00',
            })
            if show_legend:
                chart.set_legend({'position': 'bottom'})
            else:
                chart.set_legend({'none': True})
            if show_title:
                chart.set_title({'name': f"I = {int(pid)}"})
            else:
                chart.set_title({'none': True})  # タイトルを明示的に非表示に
            chart.set_size({
                'width':  int(480 * x_scale),
                'height': int(320 * y_scale),
            })

            ws.insert_chart('H2', chart, {'x_scale':1, 'y_scale':1})

    return output_path

