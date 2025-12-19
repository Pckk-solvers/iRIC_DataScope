# iRIC_DataScope\lr_wse\extractor.py
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Literal

from .reader import read_iric_csv  # assume reader provides t and df


def _coerce_index_value(value) -> float | int | None:
    if pd.isna(value):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(num):
        return None
    if float(num).is_integer():
        return int(num)
    return num


def extract_bank_data(
    df: pd.DataFrame,
    setting_df: pd.DataFrame,
    bank: Literal['L', 'R'],
    t: float
) -> pd.DataFrame:
    """
    設定 DataFrame の各行について、指定された岸のデータを抽出し、
    ファイルごとの時刻 t を追加して返します。
    Returns DataFrame with columns:
      KP, t,
      {prefix}_I, {prefix}_J,
      {prefix}_watersurfaceelevation,
      {prefix}_elevation,
      {prefix}_X, {prefix}_Y
    """
    records = []
    i_series = pd.to_numeric(df["I"], errors="coerce")
    j_series = pd.to_numeric(df["J"], errors="coerce")
    for _, s in setting_df.iterrows():
        KP = s['KP']
        if bank == 'L':
            i_key, j_key, prefix = 'LI', 'LJ', 'L'
        else:
            i_key, j_key, prefix = 'RI', 'RJ', 'R'

        coord_i = s.get(i_key)
        coord_j = s.get(j_key)
        coord_i_val = _coerce_index_value(coord_i)
        coord_j_val = _coerce_index_value(coord_j)

        # 初期値は NaN
        wse = np.nan
        elev = np.nan
        X = np.nan
        Y = np.nan

        if coord_i_val is not None and coord_j_val is not None:
            match = df[(i_series == coord_i_val) & (j_series == coord_j_val)]
            if not match.empty:
                row = match.iloc[0]
                wse = row.get('watersurfaceelevation(m)', np.nan)
                elev = row.get('elevation(m)', np.nan)
                X = row.get('X', np.nan)
                Y = row.get('Y', np.nan)

        records.append({
            'KP': KP,
            't': t,
            f'{prefix}_I': coord_i_val if coord_i_val is not None else coord_i,
            f'{prefix}_J': coord_j_val if coord_j_val is not None else coord_j,
            f'{prefix}_watersurfaceelevation(m)': wse,
            f'{prefix}_elevation(m)': elev,
            f'{prefix}_X': X,
            f'{prefix}_Y': Y,
        })
    return pd.DataFrame(records)


def extract_all(
    input_dir: Path,
    setting_df: pd.DataFrame,
    temp_dir: Path
) -> None:
    """
    iRIC 出力フォルダを再帰的に探索し、各 CSV を読み込んで左右岸抽出を行い、
    1ステップ分を1ファイルとして temp_dir に書き出します。
    """
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # ファイル探索
    csv_paths = list(input_dir.rglob("*.csv"))
    for csv_path in csv_paths:
        t, df = read_iric_csv(csv_path)
        left_df = extract_bank_data(df, setting_df, 'L', t)
        right_df = extract_bank_data(df, setting_df, 'R', t)
        merged = pd.merge(left_df, right_df, on=["KP", "t"], how="outer")
        # ファイル名ベースで書き出し
        stem = csv_path.stem
        merged.to_csv(temp_dir / f"{stem}.csv", index=False, encoding="utf-8-sig")


def extract_all_from_frames(
    frames,
    setting_df: pd.DataFrame,
    temp_dir: Path
) -> None:
    """
    IricStepFrame の iterable から左右岸抽出を行い、1ステップ分を1ファイルとして書き出す。
    """
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    for frame in frames:
        t = getattr(frame, "time", 0.0) or 0.0
        df = frame.df
        left_df = extract_bank_data(df, setting_df, 'L', t)
        right_df = extract_bank_data(df, setting_df, 'R', t)
        merged = pd.merge(left_df, right_df, on=["KP", "t"], how="outer")
        stem = f"Result_{frame.step}"
        merged.to_csv(temp_dir / f"{stem}.csv", index=False, encoding="utf-8-sig")
