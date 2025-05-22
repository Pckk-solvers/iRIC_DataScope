import os
import logging
import pandas as pd


# ロガー取得
logger = logging.getLogger(__name__)

def write_sheets(
    data: dict[tuple[int, int], pd.DataFrame],
    output_path: str
) -> None:
    """
    格子点ごとの時系列 DataFrame を Excel ファイルに出力する

    Args:
        data (dict[tuple[int,int], pd.DataFrame]): (I,J) をキーとした DataFrame の辞書
        output_path (str): 出力先 Excel ファイルのパス
    """
    # 出力ディレクトリ作成
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    logger.info(f"Excel ファイル出力開始: {output_path}")
    # XlsxWriter をエンジンに指定
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        for (i, j), df in data.items():
            sheet_name = f"(I,J)=({i},{j})"
            logger.debug(f"シート出力: {sheet_name} ({df.shape[0]} 行)")
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # カラム幅を自動調整
            workbook  = writer.book
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns):
                # データ長とヘッダ長の最大値 + 2 を幅に設定
                max_len = max(
                    df[col].astype(str).map(len).max(),
                    len(col)
                ) + 2
                worksheet.set_column(idx, idx, max_len)

    logger.info("Excel ファイル出力完了")
