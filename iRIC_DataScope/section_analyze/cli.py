from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iRIC_DataScope.section_analyze.models import SectionAnalyzeOptions
from iRIC_DataScope.section_analyze.processor import run_section_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="側線SHPに沿ってiRIC計算結果を断面集計します。")
    parser.add_argument("--input", "-i", required=True, type=Path, help="CGNS / .ipro / プロジェクトフォルダ")
    parser.add_argument("--sections", "-s", required=True, type=Path, help="側線SHP")
    parser.add_argument("--output", "-o", required=True, type=Path, help="出力フォルダ")
    parser.add_argument("--depth-threshold", type=float, default=0.01, help="有効点判定に使う水深下限")
    parser.add_argument("--sample-interval", type=float, default=None, help="側線サンプリング間隔")
    parser.add_argument("--section-id-field", default=None, help="断面ID属性フィールド")
    parser.add_argument("--section-name-field", default=None, help="断面名属性フィールド")
    parser.add_argument("--overwrite", action="store_true", help="既存CSVを上書き")
    parser.add_argument("--dry-run", action="store_true", help="CSVを出力せず概要だけ確認")
    parser.add_argument("--limit-steps", type=int, default=None, help="先頭Nステップだけ処理")
    parser.add_argument(
        "--column-names",
        choices=["standard", "river"],
        default="standard",
        help="CSV列名。standard=内部向け英語名, river=河川業務向け日本語名",
    )
    return parser


def _print_result(result) -> None:
    print(f"Input: {result.input_path}")
    print(f"Sections: {result.section_shp_path}")
    print(f"Sections loaded: {result.section_count}")
    print(f"Sample interval: {result.sample_interval}")
    print(f"Mapped nodes: {result.mapped_node_count}")
    print(f"Steps: {result.step_count}")
    if result.dry_run:
        print("Dry run: no files written")
        return
    print("Wrote:")
    for path in result.output_files:
        print(f"  {path}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = int(exc.code) if isinstance(exc.code, int) else 1
        return 0 if code == 0 else 1

    options = SectionAnalyzeOptions(
        depth_threshold=args.depth_threshold,
        sample_interval=args.sample_interval,
        section_id_field=args.section_id_field,
        section_name_field=args.section_name_field,
        overwrite=args.overwrite,
        limit_steps=args.limit_steps,
        dry_run=args.dry_run,
        column_names=args.column_names,
    )
    try:
        result = run_section_analysis(
            input_path=args.input,
            section_shp_path=args.sections,
            output_dir=args.output,
            options=options,
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 2
    _print_result(result)
    return 0
