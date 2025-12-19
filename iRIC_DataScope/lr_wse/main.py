#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\lr_wse\main.py
"""
lr_wse: iRIC 左右岸最大水位整理ツール

このモジュールは CLI および GUI から利用できるエントリポイントを統一化し、
`run_lr_wse` 関数を内部定義しています。
"""
import argparse
import logging
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Optional, Union

import pandas as pd

from iRIC_DataScope.common.iric_data_source import DataSource
from iRIC_DataScope.common.iric_project import classify_input_dir
from .config import load_setting
from .extractor import extract_all, extract_all_from_frames
from .writer import combine_to_excel

# ロガー設定
logger = logging.getLogger(__name__)


def run_lr_wse(
    input_path: Path,
    config_file: Path,
    output_dir: Path,
    excel_filename: str = "summary.xlsx",
    missing_elev: Optional[Union[str, float]] = None,
    temp_dir: Optional[Path] = None
) -> Path:
    """
    iRIC 左右岸最大水位整理の共通処理。
    - input_path: プロジェクトフォルダ / CSVフォルダ / .ipro
    - config_file: 設定CSVファイルのパス
    - output_dir: Excel出力先フォルダ
    - excel_filename: 出力ファイル名
    - missing_elev: 欠損標高置換値
    - temp_dir: 中間CSVの出力先（省略時は一時ディレクトリを使用）

    Returns:
        Path: 出力したExcelファイルのパス
    """
    logger.info("処理開始")
    logger.debug(f"パラメータ: input_path={input_path}, config_file={config_file}, output_dir={output_dir}, "
                 f"excel_filename={excel_filename}, missing_elev={missing_elev}, temp_dir={temp_dir}")
    
    # 設定読み込み
    logger.info("設定ファイル読み込み開始")
    setting_df = load_setting(config_file)
    logger.info("設定ファイル読み込み完了")

    # 中間CSV処理
    if temp_dir:
        logger.info("中間CSV出力開始 (指定ディレクトリ)")
        temp_dir.mkdir(parents=True, exist_ok=True)
        td = temp_dir
        _extract_input_to_temp(input_path=input_path, setting_df=setting_df, temp_dir=td)
        logger.info("中間CSV出力完了")
    else:
        logger.info("中間CSV出力開始 (一時ディレクトリ)")
        with TemporaryDirectory() as td_path:
            td = Path(td_path)
            _extract_input_to_temp(input_path=input_path, setting_df=setting_df, temp_dir=td)
            logger.info("中間CSV出力完了")
            logger.info("Excel結合開始")
            result = combine_to_excel(
                temp_dir=td,
                output_dir=output_dir,
                excel_filename=excel_filename,
                missing_elev=missing_elev
            )
            logger.info("処理完了")
            return result
    logger.info("Excel結合開始")
    result = combine_to_excel(
        temp_dir=td,
        output_dir=output_dir,
        excel_filename=excel_filename,
        missing_elev=missing_elev
    )
    logger.info("処理完了")
    return result


def _extract_input_to_temp(
    *,
    input_path: Path,
    setting_df: pd.DataFrame,
    temp_dir: Path,
) -> None:
    if input_path.is_file():
        if input_path.suffix.lower() != ".ipro":
            raise ValueError("入力にはプロジェクトフォルダ、CSVフォルダ、または .ipro を指定してください。")
        data_source = DataSource.from_input(input_path)
        try:
            frames = data_source.iter_frames_with_columns(
                value_cols=["watersurfaceelevation(m)", "elevation(m)"]
            )
            extract_all_from_frames(frames, setting_df=setting_df, temp_dir=temp_dir)
        finally:
            data_source.close()
        return

    kind = classify_input_dir(input_path)
    if kind == "csv_dir":
        extract_all(input_dir=input_path, setting_df=setting_df, temp_dir=temp_dir)
        return

    data_source = DataSource.from_input(input_path)
    try:
        frames = data_source.iter_frames_with_columns(
            value_cols=["watersurfaceelevation(m)", "elevation(m)"]
        )
        extract_all_from_frames(frames, setting_df=setting_df, temp_dir=temp_dir)
    finally:
        data_source.close()


def main():
    logger.info("CLI実行開始")
    parser = argparse.ArgumentParser(
        description="左右岸水位抽出: 設定に基づき左右岸データを抽出し、中間CSVを生成、最終Excelを出力"
    )
    parser.add_argument(
        "-i", "--input-dir",
        type=Path,
        required=True,
        help="プロジェクトフォルダ / CSVフォルダ / .ipro"
    )
    parser.add_argument(
        "-f", "--config-file",
        type=Path,
        required=True,
        help="設定CSVファイルのパス"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        required=True,
        help="最終Excelを出力するフォルダ"
    )
    parser.add_argument(
        "-e", "--excel-name",
        type=str,
        default="summary.xlsx",
        help="出力するExcelファイル名(.xlsxを含む)"
    )
    parser.add_argument(
        "--missing-elev",
        type=float,
        default=None,
        help="欠損標高を置き換える値(省略可)"
    )
    args = parser.parse_args()
    logger.debug(f"CLI引数: {args}")

    # 存在チェック
    in_path = args.input_dir
    in_ok = in_path.is_dir() or (in_path.is_file() and in_path.suffix.lower() == ".ipro")
    if not in_ok:
        logger.error(f"入力パスが無効: {in_path}")
        print(f"エラー: 入力が無効です（プロジェクトフォルダ/CSVフォルダ/.ipro）: {in_path}")
        sys.exit(1)
    if not args.config_file.is_file():
        logger.error(f"設定ファイルが無効: {args.config_file}")
        print(f"エラー: 設定ファイルが存在しないかファイルではありません: {args.config_file}")
        sys.exit(1)
    if not args.output_dir.is_dir():
        logger.error(f"出力フォルダが無効: {args.output_dir}")
        print(f"エラー: 出力フォルダが存在しないかディレクトリではありません: {args.output_dir}")
        sys.exit(1)

    try:
        logger.info("処理開始")
        out_path = run_lr_wse(
            input_path=in_path,
            config_file=args.config_file,
            output_dir=args.output_dir,
            excel_filename=args.excel_name,
            missing_elev=args.missing_elev
        )
        logger.info(f"処理完了: {out_path}")
        print(f"処理が完了しました。Excelを出力しました: {out_path}")
    except Exception as e:
        logger.error(f"実行エラー: {e}", exc_info=True)
        print(f"実行中にエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
