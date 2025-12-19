# iRIC_DataScope\cross_section\data_loader.py

from pathlib import Path
from typing import Optional, List, Dict, Tuple
import pandas as pd
import numpy as np

from iRIC_DataScope.common.csv_reader import list_csv_files, read_iric_csv
from iRIC_DataScope.common.iric_data_source import DataSource
from iRIC_DataScope.common.iric_project import classify_input_dir


def _prepare_frame(time_val: float, df: pd.DataFrame) -> Tuple[float, pd.DataFrame]:
    """
    時刻 t と DataFrame から必要な列のみ選択して返す。
    累積距離の計算は含まない。

    Returns:
      t: float
      df: DataFrame(columns=[
          "Time", "Profile_ID", "Sort_Key",
          "X_Coordinate", "Y_Coordinate",
          "Elevation", "WaterSurface"
      ])
    """
    # 必要な列のみ抽出
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
    df.insert(0, "Time", time_val)

    return time_val, df


def _read_and_prepare(file_path: Path) -> Tuple[float, pd.DataFrame]:
    """
    ファイルから時刻 t を読み取り、必要な列のみ選択して返す。
    累積距離の計算は含まない。
    """
    t, df = read_iric_csv(str(file_path))
    return _prepare_frame(t, df)


def load_profile_data(
    input_path: Path,
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
    result: Dict[float, Dict[float, pd.DataFrame]] = {}

    if selected_file and selected_file.exists():
        files = [selected_file]
    elif input_path.is_dir() and classify_input_dir(input_path) == "csv_dir":
        if mode == "single":
            files = list_csv_files(str(input_path))[:1]
        else:
            files = list_csv_files(str(input_path))
    else:
        files = []

    if files:
        for fp in files:
            fp_path = Path(fp)
            try:
                t, df = _read_and_prepare(fp_path)
            except Exception as e:
                print(f"? {fp_path.name} の読み込み失敗: {e}")
                continue
            _group_profile(result, t, df, include_ids)
        return result

    data_source = DataSource.from_input(input_path)
    try:
        frames = data_source.iter_frames_with_columns(
            value_cols=["elevation(m)", "watersurfaceelevation(m)"]
        )
        if mode == "single":
            frames = list(frames)[:1]
        for frame in frames:
            try:
                t, df = _prepare_frame(frame.time, frame.df)
            except Exception as e:
                print(f"? step={frame.step} の読み込み失敗: {e}")
                continue
            _group_profile(result, t, df, include_ids)
    finally:
        data_source.close()

    return result


def _group_profile(
    result: Dict[float, Dict[float, pd.DataFrame]],
    t: float,
    df: pd.DataFrame,
    include_ids: Optional[List[float]],
) -> None:
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
