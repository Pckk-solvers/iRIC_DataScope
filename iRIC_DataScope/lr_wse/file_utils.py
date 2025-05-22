from pathlib import Path
import re
from typing import List


def list_iric_csvs(input_dir: Path) -> List[Path]:
    """
    指定ディレクトリ以下を再帰的に探索し、"Result_*.csv" という名前のCSVファイルをすべて取得して
    数値部分をキーにソートしたリストを返します。

    Parameters
    ----------
    input_dir : Path
        iRIC出力CSVが格納されたルートフォルダ

    Returns
    -------
    List[Path]
        "Result_*.csv" ファイルへの Path オブジェクトのリスト
    """
    # recursive glob for Result_*.csv
    csv_paths = list(input_dir.rglob("Result_*.csv"))

    def extract_index(p: Path) -> int:
        # ファイル名の数字部分を抽出して整数に変換
        m = re.search(r"Result_(\d+)\.csv$", p.name)
        return int(m.group(1)) if m else float('inf')

    csv_paths.sort(key=extract_index)
    return csv_paths
