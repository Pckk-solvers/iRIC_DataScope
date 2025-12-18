from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class ConversionOptions:
    """
    CGNS / IPRO から iRIC 互換 CSV を生成する際のオプション

    location_preference:
      - "auto"   : Vertex を優先し、無ければ CellCenter を使う
      - "vertex" : Vertex を優先（無ければ CellCenter にフォールバック）
      - "cell"   : CellCenter を優先（無ければ Vertex にフォールバック）
    include_flow_solution:
      - True の場合、FlowSolution 系のスカラーを出力（形状が座標と一致するもののみ）
      - False の場合、座標のみを出力
    """

    case_name: str = "Case1.cgn"
    zone_path: str = "iRIC/iRICZone"
    vars_keep: list[str] | None = None
    step_from: int = 1
    step_to: int | None = None
    step_skip: int = 1
    fortran_order: bool = True
    location_preference: Literal["auto", "vertex", "cell"] = "auto"
    include_flow_solution: bool = True


def resolve_case_cgn(input_path: Path, case_name: str):
    """
    入力（.cgn / .ipro / dir）から CGNS を解決する contextmanager を返す。
    """
    from .cgns_reader import resolve_case_cgn as _resolve

    return _resolve(input_path, case_name)


def export_iric_like_csv(
    cgn_path: Path,
    out_dir: Path,
    *,
    zone_path: str = "iRIC/iRICZone",
    vars_keep: list[str] | None = None,
    step_from: int = 1,
    step_to: int | None = None,
    step_skip: int = 1,
    fortran_order: bool = True,
    location_preference: Literal["auto", "vertex", "cell"] = "auto",
    include_flow_solution: bool = True,
) -> None:
    """
    CGNS を読み込み iRIC 互換の Result_*.csv を out_dir に出力する。
    """
    from .cgns_reader import iter_iric_step_frames
    from .iric_csv_writer import export_iric_result_csv

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = iter_iric_step_frames(
        cgn_path,
        zone_path=zone_path,
        vars_keep=vars_keep,
        step_from=step_from,
        step_to=step_to,
        step_skip=step_skip,
        fortran_order=fortran_order,
        location_preference=location_preference,
        include_flow_solution=include_flow_solution,
    )
    export_iric_result_csv(frames, out_dir)


def convert_iric_project(
    input_path: Path,
    output_dir: Path,
    *,
    options: ConversionOptions | None = None,
) -> Path:
    """
    .ipro / .cgn / フォルダを受け取り、Result_*.csv を output_dir に生成する。
    戻り値は output_dir。
    """
    from .cgns_reader import resolve_case_cgn as _resolve

    opts = options or ConversionOptions()
    input_path = input_path.expanduser()
    output_dir = output_dir.expanduser()

    logger.info("Start CGNS→CSV: input=%s output=%s", input_path, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with _resolve(input_path, opts.case_name) as cgn:
        export_iric_like_csv(
            cgn_path=cgn,
            out_dir=output_dir,
            zone_path=opts.zone_path,
            vars_keep=opts.vars_keep,
            step_from=opts.step_from,
            step_to=opts.step_to,
            step_skip=opts.step_skip,
            fortran_order=opts.fortran_order,
            location_preference=opts.location_preference,
            include_flow_solution=opts.include_flow_solution,
        )

    logger.info("Done CGNS→CSV: %s", output_dir)
    return output_dir

