# iRIC_DataScope\time_series\processor.py

import logging
from pathlib import Path
from typing import List, Tuple, Dict
import pandas as pd
from iRIC_DataScope.common.csv_reader import list_csv_files, read_iric_csv
from iRIC_DataScope.common.iric_data_source import DataSource
from iRIC_DataScope.common.iric_project import classify_input_dir

# ロガー取得
logger = logging.getLogger(__name__)


def extract_records_from_df(
    df: pd.DataFrame,
    time_val: float,
    grid_points: List[Tuple[int, int]],
    variables: List[str],
    source_label: str = ""
) -> List[Dict]:
    """
    DataFrame から、指定した格子点と変数の時刻データを抽出する。
    """
    if source_label:
        logger.debug(f"読み込んだデータ: {source_label} (time={time_val})")

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
            logger.warning(f"データなし: 格子点 ({i_val},{j_val}) in {source_label}")
            continue
        row = sub.iloc[0]
        rec = {'time': time_val, 'I': i_val, 'J': j_val}
        for var in variables:
            rec[var] = row.get(var)
        records.append(rec)
    logger.info(f"{source_label} から {len(records)} レコードを抽出しました")
    return records


def extract_records(
    csv_path: str,
    grid_points: List[Tuple[int, int]],
    variables: List[str]
) -> List[Dict]:
    """
    単一の CSV ファイルから、指定した格子点と変数の時刻データを抽出する
    """
    time_val, df = read_iric_csv(csv_path)
    return extract_records_from_df(
        df=df,
        time_val=time_val,
        grid_points=grid_points,
        variables=variables,
        source_label=csv_path,
    )


def aggregate_all(
    input_path: Path | str,
    grid_points: List[Tuple[int, int]],
    variables: List[str],
    *,
    grid_location: str = "node",
) -> Dict[Tuple[int, int], pd.DataFrame]:
    """
    入力パスの全ステップを処理し、格子点ごとの時系列 DataFrame をまとめて返す

    Args:
        input_path (Path | str): プロジェクトフォルダ / CSVフォルダ / .ipro
        grid_points (List[Tuple[int,int]]): 抽出対象の格子点リスト
        variables (List[str]): 抽出対象の変数名リスト

    Returns:
        Dict[Tuple[int,int], pd.DataFrame]: 格子点 (i,j) をキーとした時系列 DataFrame の辞書
    """
    input_path = Path(input_path)
    logger.info(f"時系列集計開始: {input_path}")

    csv_files: list[str] = []
    if input_path.is_dir():
        kind = classify_input_dir(input_path)
        if kind == "csv_dir":
            csv_files = list_csv_files(str(input_path))
            logger.info(f"処理対象 CSV ファイル数: {len(csv_files)}")

    all_data: Dict[Tuple[int, int], List[Dict]] = {pt: [] for pt in grid_points}
    if csv_files:
        for path in csv_files:
            try:
                recs = extract_records(path, grid_points, variables)
                for rec in recs:
                    key = (rec['I'], rec['J'])
                    all_data[key].append(rec)
            except Exception:
                logger.error(f"CSV 処理失敗: {path}", exc_info=True)
    else:
        data_source = DataSource.from_input(input_path, grid_location=grid_location)
        try:
            frames = data_source.iter_frames_with_columns(value_cols=variables)
            for frame in frames:
                try:
                    recs = extract_records_from_df(
                        df=frame.df,
                        time_val=frame.time,
                        grid_points=grid_points,
                        variables=variables,
                        source_label=f"step={frame.step}",
                    )
                except Exception:
                    logger.error(f"データ処理失敗: step={frame.step}", exc_info=True)
                    continue
                for rec in recs:
                    key = (rec['I'], rec['J'])
                    all_data[key].append(rec)
        finally:
            data_source.close()

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

    logger.info("--- list_csv_files テスト ---")
    try:
        files = list_csv_files(sample_dir)
        logger.info(f"見つかったファイル数: {len(files)}")
    except Exception as e:
        logger.error(f"list_csv_files エラー: {e}", exc_info=True)

    logger.info("\n--- aggregate_all テスト ---")
    try:
        data = aggregate_all(sample_dir, grid_points, variables)
        for key, df_ts in data.items():
            logger.info(f"\n格子点 {key} の先頭データ:")
            logger.debug(df_ts.head().to_string())
    except Exception as e:
        logger.error(f"aggregate_all エラー: {e}", exc_info=True)
