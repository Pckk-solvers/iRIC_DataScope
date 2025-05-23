# iRIC_DataScope\lr_wse\config.py

import pandas as pd
from pathlib import Path

def load_setting(config_file: Path) -> pd.DataFrame:
    """
    設定ファイルを直接読み込みます。

    Args:
        config_file (Path): setting.csv のパス
    Returns:
        pd.DataFrame: 設定データ
    """
    if not config_file.is_file():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_file}")
    return pd.read_csv(config_file, encoding="utf-8")
