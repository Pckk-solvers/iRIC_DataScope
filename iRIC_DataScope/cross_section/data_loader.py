# iRIC_DataScope\cross_section\data_loader.py

from pathlib import Path
from typing import Optional, List, Dict, Tuple
import pandas as pd
import numpy as np
from iRIC_DataScope.common.csv_reader import list_csv_files, read_iric_csv

def _read_and_prepare(file_path: Path) -> Tuple[float, pd.DataFrame]:
    """
    ファイルから時刻 t を読み取り、必要な列のみ選択して返す。
    累積距離の計算は含まない。

    Returns:
      t: float
      df: DataFrame(columns=[
          "Time", "Profile_ID", "Sort_Key",
          "X_Coordinate", "Y_Coordinate",
          "Elevation", "WaterSurface"
      ])
    """
    # 1) 共通モジュールで時刻とヘッダー付きデータを取得
    t, df = read_iric_csv(str(file_path))

    # 2) 必要な列のみ抽出
    cols = ["I", "J", "X", "Y", "elevation(m)", "watersurfaceelevation(m)"]
    df = df.loc[:, cols].copy()

    # 3) 内部用にリネーム
    df.rename(columns={
        "I": "Profile_ID",
        "J": "Sort_Key",
        "X": "X_Coordinate",
        "Y": "Y_Coordinate",
        "elevation(m)": "Elevation",
        "watersurfaceelevation(m)": "WaterSurface"
    }, inplace=True)

    # 4) 時刻列を先頭に追加
    df.insert(0, "Time", t)

    return t, df


def load_profile_data(
    input_dir: Path,
    mode: str = "single",
    selected_file: Optional[Path] = None,
    include_ids: Optional[List[float]] = None
) -> Dict[float, Dict[float, pd.DataFrame]]:
    """
    複数ファイルの Profile_ID ごと、各ファイルの時刻 t ごとに
    DataFrame をまとめた二重辞書を返す。

    Returns:
      {
        Profile_ID1: { t1: df1, t2: df2, ... },
        Profile_ID2: { t1: df1, t2: df2, ... },
        ...
      }
    """
    # 対象ファイル一覧取得
    if mode == "single":
        if selected_file:
            files = [selected_file]
        else:
            files = list_csv_files(str(input_dir))[:1]
    else:
        files = list_csv_files(str(input_dir))

    result: Dict[float, Dict[float, pd.DataFrame]] = {}

    for fp in files:
        fp_path = Path(fp)
        try:
            t, df = _read_and_prepare(fp_path)
        except Exception as e:
            print(f"⚠ {fp_path.name} の読み込み失敗: {e}")
            continue

        # Profile_IDごとに累積距離を計算
        for pid, grp in df.groupby("Profile_ID", dropna=False):
            if include_ids and pid not in include_ids:
                continue

            # ソートして隣接点間距離を計算
            sub = grp.sort_values("Sort_Key").reset_index(drop=True)
            dx = sub["X_Coordinate"].diff().fillna(0)
            dy = sub["Y_Coordinate"].diff().fillna(0)

            # 累積距離を計算し、小数第2位までに丸め
            cum = np.sqrt(dx*dx + dy*dy).cumsum()
            sub["Cumulative_Distance"] = np.round(cum, 2)

            # 必要列を抽出
            mini = sub[["Time", "Cumulative_Distance", "Elevation", "WaterSurface"]].copy()
            result.setdefault(pid, {})[t] = mini

    return result
