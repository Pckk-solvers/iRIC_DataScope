# iRIC_DataScope\time_series\processor.py

import logging
from typing import List, Tuple, Dict
import pandas as pd
from iRIC_DataScope.common.csv_reader import list_csv_files, read_iric_csv

# ロガー取得
logger = logging.getLogger(__name__)


def extract_records(
    csv_path: str,
    grid_points: List[Tuple[int, int]],
    variables: List[str]
) -> List[Dict]:
    """
    単一の CSV ファイルから、指定した格子点と変数の時刻データを抽出する

    Args:
        csv_path (str): 読み込む CSV ファイルのパス
        grid_points (List[Tuple[int,int]]): 抽出対象の格子点 (i, j) のリスト
        variables (List[str]): 抽出対象の変数名リスト

    Returns:
        List[Dict]: 各格子点の時間・I・J・各変数をキーとする辞書のリスト
    """
    # CSV 読み込みと時刻抽出
    time_val, df = read_iric_csv(csv_path)
    logger.debug(f"読み込んだ CSV: {csv_path} (time={time_val})")

    # 必須カラム確認
    required_cols = {'I', 'J'}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        logger.error(f"必須カラムが不足しています: {missing}")
        raise KeyError(f"必須カラムが不足: {missing}")

    records: List[Dict] = []
    for i_val, j_val in grid_points:
        sub = df[(df['I'] == i_val) & (df['J'] == j_val)]
        if sub.empty:
            logger.warning(f"データなし: 格子点 ({i_val},{j_val}) in {csv_path}")
            continue
        row = sub.iloc[0]
        rec = {'time': time_val, 'I': i_val, 'J': j_val}
        for var in variables:
            rec[var] = row.get(var)
        records.append(rec)
    logger.info(f"{csv_path} から {len(records)} レコードを抽出しました")
    return records


def aggregate_all(
    input_dir: str,
    grid_points: List[Tuple[int, int]],
    variables: List[str]
) -> Dict[Tuple[int, int], pd.DataFrame]:
    """
    指定ディレクトリ内の全 CSV を処理し、格子点ごとの時系列 DataFrame をまとめて返す

    Args:
        input_dir (str): CSV ファイルが置かれたディレクトリパス
        grid_points (List[Tuple[int,int]]): 抽出対象の格子点リスト
        variables (List[str]): 抽出対象の変数名リスト

    Returns:
        Dict[Tuple[int,int], pd.DataFrame]: 格子点 (i,j) をキーとした時系列 DataFrame の辞書
    """
    logger.info(f"CSV 集計開始: {input_dir}")
    csv_files = list_csv_files(input_dir)
    logger.info(f"処理対象 CSV ファイル数: {len(csv_files)}")

    all_data: Dict[Tuple[int, int], List[Dict]] = {pt: [] for pt in grid_points}
    for path in csv_files:
        try:
            recs = extract_records(path, grid_points, variables)
            for rec in recs:
                key = (rec['I'], rec['J'])
                all_data[key].append(rec)
        except Exception:
            logger.error(f"CSV 処理失敗: {path}", exc_info=True)

    # DataFrame 化
    result: Dict[Tuple[int, int], pd.DataFrame] = {}
    for key, rec_list in all_data.items():
        if rec_list:
            df_ts = pd.DataFrame(rec_list).sort_values('time').reset_index(drop=True)
            logger.debug(f"格子点 {key}: {df_ts.shape[0]} レコード")
        else:
            df_ts = pd.DataFrame(columns=['time', 'I', 'J'] + variables)
            logger.warning(f"格子点 {key} にデータがありませんでした")
        result[key] = df_ts
    logger.info("CSV 集計完了")
    return result


if __name__ == "__main__":
    # テスト用サンプル -- 必要に応じてパスやパラメータを変更してください
    sample_dir = "sample_data"
    grid_points = [(10, 5), (20, 15)]
    variables = ["watersurfaceelevation(m)", "vorticity(s-1)"]

    print("--- list_csv_files テスト ---")
    try:
        files = list_csv_files(sample_dir)
        print(f"見つかったファイル数: {len(files)}")
    except Exception as e:
        print(f"list_csv_files エラー: {e}")

    print("\n--- aggregate_all テスト ---")
    try:
        data = aggregate_all(sample_dir, grid_points, variables)
        for key, df_ts in data.items():
            print(f"\n格子点 {key} の先頭データ:")
            print(df_ts.head())
    except Exception as e:
        print(f"aggregate_all エラー: {e}")
