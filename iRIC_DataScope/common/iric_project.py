from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ProjectCgns:
    kind: Literal["single", "series"]
    paths: list[Path]


def parse_solution_step(name: str) -> int | None:
    m = re.search(r"Solution(\d+)\.cgn$", name, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def list_solution_cgns_in_ipro(ipro_path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(ipro_path, "r") as z:
            names = z.namelist()
    except Exception:
        return []

    hits: list[tuple[int, str]] = []
    for name in names:
        if re.search(r"(?:^|/)Solution\d+\.cgn$", name, flags=re.IGNORECASE):
            n = parse_solution_step(Path(name).name)
            if n is None:
                n = 10**9
            hits.append((n, name))
    if not hits:
        return []
    hits.sort(key=lambda x: x[0])
    return [name for _, name in hits]


def list_solution_cgns_in_dir(project_dir: Path) -> list[Path]:
    candidates = list(project_dir.rglob("Solution*.cgn"))
    if not candidates:
        return []

    def sort_key(p: Path) -> tuple[int, str]:
        n = parse_solution_step(p.name)
        if n is None:
            n = 10**9
        return (n, p.name.lower())

    return sorted(candidates, key=sort_key)


def has_result_csv(input_dir: Path) -> bool:
    for _ in input_dir.rglob("Result_*.csv"):
        return True
    return False


def find_case_cgn(project_dir: Path, case_name: str) -> Path | None:
    hits = sorted(project_dir.rglob(case_name))
    if hits:
        return hits[0]
    return None


def discover_project_cgns(project_dir: Path, case_name: str = "Case1.cgn") -> ProjectCgns:
    if not project_dir.is_dir():
        raise NotADirectoryError(f"プロジェクトフォルダではありません: {project_dir}")

    solution_paths = list_solution_cgns_in_dir(project_dir)
    if solution_paths:
        return ProjectCgns(kind="series", paths=solution_paths)

    case_path = find_case_cgn(project_dir, case_name)
    if case_path:
        return ProjectCgns(kind="single", paths=[case_path])

    cgns = sorted(project_dir.rglob("*.cgn"))
    if not cgns:
        raise FileNotFoundError(f"CGNS が見つかりません: {project_dir}")
    if len(cgns) == 1:
        return ProjectCgns(kind="single", paths=[cgns[0]])
    raise FileNotFoundError(
        f"複数の CGNS が見つかりました。{case_name} が必要です: {project_dir}"
    )


def classify_input_dir(input_dir: Path, case_name: str = "Case1.cgn") -> Literal["csv_dir", "project_dir"]:
    if not input_dir.is_dir():
        raise NotADirectoryError(f"フォルダではありません: {input_dir}")
    has_csv = has_result_csv(input_dir)
    has_project = True
    project_error: Exception | None = None
    try:
        discover_project_cgns(input_dir, case_name=case_name)
    except Exception as exc:
        has_project = False
        project_error = exc

    if has_project:
        return "project_dir"
    if has_csv:
        return "csv_dir"
    if project_error is not None:
        raise project_error
    raise FileNotFoundError(f"Result_*.csv または CGNS が見つかりません: {input_dir}")
