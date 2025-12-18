from __future__ import annotations

from pathlib import Path

from .cgns_reader import IricStepFrame


def format_iric_time(t) -> str:
    try:
        tf = float(t)
        if abs(tf - round(tf)) < 1e-12:
            return str(int(round(tf)))
        return f"{tf:g}"
    except Exception:
        return str(t)


def write_iric_result_csv(frame: IricStepFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as fp:
        fp.write(f"iRIC output t = {format_iric_time(frame.time)}\n")
        fp.write(f"{frame.imax},{frame.jmax}\n")
        frame.df.to_csv(fp, index=False)


def export_iric_result_csv(frames, out_dir: Path, filename_template: str = "Result_{step}.csv") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for frame in frames:
        out_path = out_dir / filename_template.format(step=frame.step)
        write_iric_result_csv(frame, out_path)

