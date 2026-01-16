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
    df = pd.read_csv(config_file, encoding="utf-8")
    
    # KP列をfloatで読み込めるか試し、失敗したら文字列としてkを取り除く
    if 'KP' in df.columns:
        try:
            df['KP'] = pd.to_numeric(df['KP'], errors='raise')
        except (ValueError, TypeError):
            # float変換に失敗した場合、文字列としてkを取り除いてからfloatに変換
            df['KP'] = df['KP'].astype(str).str.rstrip("kK")
            df['KP'] = pd.to_numeric(df['KP'], errors='coerce')
    
    return df
