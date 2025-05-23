#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# iRIC_DataScope\lr_wse\main.py
"""
P_5: iRIC 左右岸最大水位整理ツール

このモジュールは CLI および GUI から利用できるエントリポイントを統一化し、
`run_p5` 関数を内部定義しています。
"""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Optional, Union

from .config import load_setting
from .extractor import extract_all
from .writer import combine_to_excel


def run_p5(
    input_dir: Path,
    config_file: Path,
    output_dir: Path,
    excel_filename: str = "summary.xlsx",
    missing_elev: Optional[Union[str, float]] = None,
    temp_dir: Optional[Path] = None
) -> Path:
    """
    iRIC 左右岸最大水位整理の共通処理。
    - input_dir: iRIC出力CSVがあるフォルダ
    - config_file: 設定CSVファイルのパス
    - output_dir: Excel出力先フォルダ
    - excel_filename: 出力ファイル名
    - missing_elev: 欠損標高置換値
    - temp_dir: 中間CSVの出力先（省略時は一時ディレクトリを使用）

    Returns:
        Path: 出力したExcelファイルのパス
    """
    # 設定読み込み
    setting_df = load_setting(config_file)

    # 中間CSV処理
    if temp_dir:
        temp_dir.mkdir(parents=True, exist_ok=True)
        td = temp_dir
        extract_all(input_dir=input_dir, setting_df=setting_df, temp_dir=td)
    else:
        with TemporaryDirectory() as td_path:
            td = Path(td_path)
            extract_all(input_dir=input_dir, setting_df=setting_df, temp_dir=td)
            return combine_to_excel(
                temp_dir=td,
                output_dir=output_dir,
                excel_filename=excel_filename,
                missing_elev=missing_elev
            )
    return combine_to_excel(
        temp_dir=td,
        output_dir=output_dir,
        excel_filename=excel_filename,
        missing_elev=missing_elev
    )


def main():
    parser = argparse.ArgumentParser(
        description="左右岸水位抽出: 設定に基づき左右岸データを抽出し、中間CSVを生成、最終Excelを出力"
    )
    parser.add_argument(
        "-i", "--input-dir",
        type=Path,
        required=True,
        help="iRIC出力CSV(Result_*.csv)が格納されたフォルダ"
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

    # 存在チェック
    if not args.input_dir.is_dir():
        print(f"エラー: 入力フォルダが存在しないかディレクトリではありません: {args.input_dir}")
        sys.exit(1)
    if not args.config_file.is_file():
        print(f"エラー: 設定ファイルが存在しないかファイルではありません: {args.config_file}")
        sys.exit(1)
    if not args.output_dir.is_dir():
        print(f"エラー: 出力フォルダが存在しないかディレクトリではありません: {args.output_dir}")
        sys.exit(1)

    try:
        out_path = run_p5(
            input_dir=args.input_dir,
            config_file=args.config_file,
            output_dir=args.output_dir,
            excel_filename=args.excel_name,
            missing_elev=args.missing_elev
        )
        print(f"処理が完了しました。Excelを出力しました: {out_path}")
    except Exception as e:
        print(f"実行中にエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
