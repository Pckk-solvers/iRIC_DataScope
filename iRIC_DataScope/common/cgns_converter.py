from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Literal, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from iRIC_DataScope.common.cgns_reader import IricStepFrame


@dataclass
class ConversionOptions:
    """
    プロジェクトフォルダ / IPRO から iRIC 互換 CSV を生成する際のオプション

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
    入力（.ipro / dir）から CGNS を解決する contextmanager を返す。
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


def _iter_cgns_series_frames(
    cgn_paths: list[Path],
    steps: list[int],
    *,
    zone_path: str,
    vars_keep: list[str] | None,
    fortran_order: bool,
    location_preference: Literal["auto", "vertex", "cell"],
    include_flow_solution: bool,
) -> Generator["IricStepFrame", None, None]:
    from .cgns_reader import IricStepFrame, iter_iric_step_frames

    for idx, cgn_path in enumerate(cgn_paths):
        step = steps[idx]
        gen = iter_iric_step_frames(
            cgn_path,
            zone_path=zone_path,
            vars_keep=vars_keep,
            step_from=1,
            step_to=1,
            step_skip=1,
            fortran_order=fortran_order,
            location_preference=location_preference,
            include_flow_solution=include_flow_solution,
        )
        try:
            frame = next(gen)
        except StopIteration:
            continue
        yield IricStepFrame(
            step=step,
            time=frame.time,
            imax=frame.imax,
            jmax=frame.jmax,
            location=frame.location,
            df=frame.df,
        )


def convert_iric_project(
    input_path: Path,
    output_dir: Path,
    *,
    options: ConversionOptions | None = None,
) -> Path:
    """
    プロジェクトフォルダ / .ipro を受け取り、Result_*.csv を output_dir に生成する。
    戻り値は output_dir。
    """
    from .cgns_reader import resolve_case_cgn as _resolve
    from .iric_csv_writer import export_iric_result_csv
    from .iric_project import (
        discover_project_cgns,
        list_solution_cgns_in_ipro,
        parse_solution_step,
    )

    opts = options or ConversionOptions()
    input_path = input_path.expanduser()
    output_dir = output_dir.expanduser()

    logger.info("Start Project→CSV: input=%s output=%s", input_path, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_path.is_dir():
        info = discover_project_cgns(input_path, case_name=opts.case_name)
        if info.kind == "series":
            steps = []
            for idx, p in enumerate(info.paths, start=1):
                n = parse_solution_step(p.name)
                steps.append(n if n is not None else idx)
            frames = _iter_cgns_series_frames(
                info.paths,
                steps,
                zone_path=opts.zone_path,
                vars_keep=opts.vars_keep,
                fortran_order=opts.fortran_order,
                location_preference=opts.location_preference,
                include_flow_solution=opts.include_flow_solution,
            )
            export_iric_result_csv(frames, output_dir)
        else:
            export_iric_like_csv(
                cgn_path=info.paths[0],
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
    elif input_path.suffix.lower() == ".ipro":
        sol_names = list_solution_cgns_in_ipro(input_path)
        if sol_names:
            with tempfile.TemporaryDirectory(prefix="ipro_solution_") as td:
                td_path = Path(td)
                cgn_paths: list[Path] = []
                steps: list[int] = []
                with zipfile.ZipFile(input_path, "r") as z:
                    for idx, name in enumerate(sol_names, start=1):
                        out = td_path / Path(name).name
                        with z.open(name) as src, out.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                        cgn_paths.append(out)
                        n = parse_solution_step(Path(name).name)
                        steps.append(n if n is not None else idx)
                frames = _iter_cgns_series_frames(
                    cgn_paths,
                    steps,
                    zone_path=opts.zone_path,
                    vars_keep=opts.vars_keep,
                    fortran_order=opts.fortran_order,
                    location_preference=opts.location_preference,
                    include_flow_solution=opts.include_flow_solution,
                )
                export_iric_result_csv(frames, output_dir)
        else:
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
    elif input_path.suffix.lower() == ".cgn":
        raise ValueError("CGNS 単体の入力はサポートしていません。プロジェクトフォルダを指定してください。")
    else:
        raise ValueError(f"未対応の入力です: {input_path}")

    logger.info("Done Project→CSV: %s", output_dir)
    return output_dir
