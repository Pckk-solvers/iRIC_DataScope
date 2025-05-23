# iRIC_DataScope\lr_wse\file_utils.py
from pathlib import Path
from typing import List
from iRIC_DataScope.common.csv_reader import list_csv_files

def list_iric_csvs(input_dir: Path) -> List[Path]:
    """
    指定ディレクトリ以下を再帰的に探索し、
    すべての *.csv ファイルを取得して、
    パスをソート済みの Path リストで返します。
    """
    # list_csv_files は文字列のパスリストを返すので Path に変換
    csv_paths = [Path(p) for p in list_csv_files(str(input_dir))]
    return csv_paths

