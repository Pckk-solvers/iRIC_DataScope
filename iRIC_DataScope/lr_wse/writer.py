# iRIC_DataScope\lr_wse\writer.py

import pandas as pd
from pathlib import Path
from typing import Union, List, Optional
from openpyxl import load_workbook

def load_temp_csvs(
    temp_dir: Union[Path, str]
) -> List[pd.DataFrame]:
    temp_dir = Path(temp_dir)
    paths = sorted(temp_dir.glob("*.csv"), key=lambda p: p.name)
    merged = [p for p in paths if not p.name.startswith(("L_", "R_"))]
    if merged:
        paths = merged
    return [pd.read_csv(p, encoding="utf-8-sig") for p in paths]

def combine_to_excel(
    temp_dir: Union[Path, str],
    output_dir: Union[Path, str],
    excel_filename: str,
    missing_elev: Optional[Union[str, float]] = None,
    min_depth: Optional[float] = None,
) -> Path:
    """
    iRIC 左右岸最大水位整理ツール

    temp_dir 内の左右別 CSV を読み込み、
    各 KP ごとに左右岸の最大水位を同じ行にまとめて、
    KP の数値部分で昇順ソートした上で Summary シートに書き出します。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    excel_path = output_dir / excel_filename

    frames = load_temp_csvs(temp_dir)
    if frames:
        df = pd.concat(frames, ignore_index=True)

        # 左岸／右岸用に分割
        left  = df[[c for c in df.columns if c.startswith(("KP","t","L_"))]].copy()
        right = df[[c for c in df.columns if c.startswith(("KP","t","R_"))]].copy()

        # 各 KP で最大の行番号を取得
        left_idx  = left.groupby("KP")["L_watersurfaceelevation(m)"].idxmax().dropna().astype(int)
        right_idx = right.groupby("KP")["R_watersurfaceelevation(m)"].idxmax().dropna().astype(int)

        # 最大値行だけ取り出し
        left_max  = left.loc[left_idx].set_index("KP").rename(columns={"t": "L_t"})
        right_max = right.loc[right_idx].set_index("KP").rename(columns={"t": "R_t"})

        # KP をキーにマージ
        summary = left_max.join(right_max, how="outer").reset_index()

        # 列順を整理
        desired_cols = [
            "KP",
            "L_t", "L_I", "L_J", "L_X", "L_Y",
            "L_watersurfaceelevation(m)", "L_elevation(m)", "L_depth(m)",
            "R_t", "R_I", "R_J", "R_X", "R_Y",
            "R_watersurfaceelevation(m)", "R_elevation(m)", "R_depth(m)",
        ]
        cols = [c for c in desired_cols if c in summary.columns] + [
            c for c in summary.columns if c not in desired_cols
        ]
        summary = summary.loc[:, cols]

        # KP の数値部分でソート
        if pd.api.types.is_numeric_dtype(summary["KP"]):
            # KPが数値の場合はそのままソート
            summary.sort_values(by="KP", inplace=True)
        else:
            # KPが文字列の場合はkを取り除いてからソート
            summary["KP_numeric"] = summary["KP"].str.rstrip("kK").astype(float)
            summary.sort_values(by="KP_numeric", inplace=True)
            summary.drop(columns="KP_numeric", inplace=True)

        # 欠損値置換
        if missing_elev is not None:
            if isinstance(missing_elev, str) and missing_elev == "":
                summary = summary.fillna("")       # 空白セル
            else:
                summary = summary.fillna(missing_elev)

        # 最小水深一致時の無効化（左右岸別）
        if min_depth is not None:
            if "L_depth(m)" in df.columns:
                left_invalid = df[df["L_depth(m)"] <= min_depth]["KP"].dropna().unique()
                if "L_watersurfaceelevation(m)" in summary.columns:
                    col = "L_watersurfaceelevation(m)"
                    summary[col] = summary[col].astype("object")
                    summary.loc[summary["KP"].isin(left_invalid), col] = "取得不可"
                if "L_elevation(m)" in summary.columns:
                    col = "L_elevation(m)"
                    summary[col] = summary[col].astype("object")
                    summary.loc[summary["KP"].isin(left_invalid), col] = "取得不可"
            if "R_depth(m)" in df.columns:
                right_invalid = df[df["R_depth(m)"] <= min_depth]["KP"].dropna().unique()
                if "R_watersurfaceelevation(m)" in summary.columns:
                    col = "R_watersurfaceelevation(m)"
                    summary[col] = summary[col].astype("object")
                    summary.loc[summary["KP"].isin(right_invalid), col] = "取得不可"
                if "R_elevation(m)" in summary.columns:
                    col = "R_elevation(m)"
                    summary[col] = summary[col].astype("object")
                    summary.loc[summary["KP"].isin(right_invalid), col] = "取得不可"
    else:
        summary = pd.DataFrame()

    # Excel出力前にKP列に"k"を付加（元の形式に復元）
    if not summary.empty and 'KP' in summary.columns and pd.api.types.is_numeric_dtype(summary['KP']):
        summary['KP'] = summary['KP'].astype(str) + 'k'

    # Excel に書き出し
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)

    # 列幅自動調整
    wb = load_workbook(excel_path)
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = max((len(str(cell.value)) for cell in col if cell.value), default=0)
            sheet.column_dimensions[col[0].column_letter].width = max_len + 2
    wb.save(excel_path)

    return excel_path
