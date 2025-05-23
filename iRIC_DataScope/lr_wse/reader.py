# iRIC_DataScope\lr_wse\reader.py
from pathlib import Path
import pandas as pd
from typing import Tuple, Optional

def extract_time(first_line: str) -> Optional[float]:
    """
    1行目の文字列から時刻（t）を抽出する。
    例: "iRIC output t = 0.0" → 0.0
    抽出できなければ None を返す。
    """
    if "iRIC output t =" in first_line:
        try:
            return float(first_line.split("=", 1)[1].strip())
        except ValueError:
            return None
    return None

def read_iric_csv(
    file_path: Path,
    skip_rows: int = 2,
    encoding: str = "utf-8"
) -> Tuple[Optional[float], pd.DataFrame]:
    """
    指定されたファイルを読み込み、
    1行目から時刻を extract_time で取得し、
    3行目以降を pandas.DataFrame として返す。

    Parameters
    ----------
    file_path : Path
        読み込む CSV ファイルのパス
    skip_rows : int
        pandas.read_csv に渡すスキップ行数（デフォルト 2）
    encoding : str
        ファイル読み込み時の文字エンコーディング

    Returns
    -------
    t_value : Optional[float]
        抽出した時刻（取得できなければ None）
    df : pd.DataFrame
        CSV のデータ部分（skiprows 行分スキップ後）
    """
    # 1行目を読み込んで時刻を抽出
    with file_path.open("r", encoding=encoding) as f:
        first = f.readline().strip()
    t_value = extract_time(first)

    # データ部分を DataFrame で読み込む
    df = pd.read_csv(file_path, skiprows=skip_rows, encoding=encoding)
    return t_value, df
