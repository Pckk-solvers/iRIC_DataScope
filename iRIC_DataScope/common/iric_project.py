from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class ProjectCgns:
    kind: Literal["single", "series"]
    paths: list[Path]


PROJECT_XML_NAME = "project.xml"


@dataclass(frozen=True)
class ProjectXmlMeta:
    case_entries: list[str]
    current_case: str | None
    separate_result: bool


def parse_solution_step(name: str) -> int | None:
    m = re.search(r"Solution(\d+)\.cgn$", name, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _normalize_case_entry(value: str) -> str:
    p = Path(value.strip())
    if not p.suffix:
        p = p.with_suffix(".cgn")
    return p.as_posix()


def _to_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_project_xml_meta(xml_text: str) -> ProjectXmlMeta | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    separate_result = _to_bool(root.attrib.get("separateResult"))
    current_case = None
    case_entries: list[str] = []

    for cgns_list in root.findall(".//CgnsFileList"):
        current = cgns_list.attrib.get("current")
        if current:
            current_case = _normalize_case_entry(current)
        for entry in cgns_list.findall(".//CgnsFileEntry"):
            filename = entry.attrib.get("filename")
            if filename:
                case_entries.append(_normalize_case_entry(filename))

    deduped: list[str] = []
    seen: set[str] = set()
    for name in case_entries:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(name)
    return ProjectXmlMeta(
        case_entries=deduped,
        current_case=current_case,
        separate_result=separate_result,
    )


def _find_project_xml_in_dir(project_dir: Path) -> Path | None:
    direct = project_dir / PROJECT_XML_NAME
    if direct.exists():
        return direct
    hits = sorted(project_dir.rglob(PROJECT_XML_NAME), key=lambda p: str(p).lower())
    return hits[0] if hits else None


def _load_project_xml_meta_from_dir(project_dir: Path) -> tuple[Path, ProjectXmlMeta] | None:
    xml_path = _find_project_xml_in_dir(project_dir)
    if not xml_path:
        return None
    try:
        text = xml_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = xml_path.read_text(encoding="utf-8-sig")
    except Exception:
        return None
    meta = _read_project_xml_meta(text)
    if meta is None:
        return None
    return xml_path, meta


def _find_project_xml_in_ipro(ipro_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(ipro_path, "r") as z:
            names = [name for name in z.namelist() if Path(name).name.lower() == PROJECT_XML_NAME]
    except Exception:
        return None
    if not names:
        return None
    names.sort(key=lambda s: (s.count("/"), s.lower()))
    return names[0]


def _load_project_xml_meta_from_ipro(ipro_path: Path) -> tuple[str, ProjectXmlMeta] | None:
    xml_name = _find_project_xml_in_ipro(ipro_path)
    if not xml_name:
        return None
    try:
        with zipfile.ZipFile(ipro_path, "r") as z:
            raw = z.read(xml_name)
    except Exception:
        return None
    text = raw.decode("utf-8", errors="ignore")
    meta = _read_project_xml_meta(text)
    if meta is None:
        return None
    return xml_name, meta


def _sort_solution_paths(candidates: list[Path]) -> list[Path]:
    def sort_key(p: Path) -> tuple[int, str]:
        n = parse_solution_step(p.name)
        if n is None:
            n = 10**9
        return (n, p.name.lower())

    return sorted(candidates, key=sort_key)


def _sort_solution_zip_names(candidates: list[str]) -> list[str]:
    def sort_key(name: str) -> tuple[int, str]:
        n = parse_solution_step(Path(name).name)
        if n is None:
            n = 10**9
        return (n, name.lower())

    return sorted(candidates, key=sort_key)


def _resolve_case_path_from_dir(project_dir: Path, case_ref: str) -> Path | None:
    case_path = Path(case_ref)
    direct = project_dir / case_path
    if direct.exists():
        return direct
    if case_path.suffix.lower() == ".cgn":
        hits = sorted(project_dir.rglob(case_path.name), key=lambda p: str(p).lower())
        if hits:
            return hits[0]
    return None


def _resolve_case_name_candidates(case_name: str, meta: ProjectXmlMeta | None) -> list[str]:
    candidates: list[str] = []

    def add(name: str | None) -> None:
        if not name:
            return
        normalized = _normalize_case_entry(name)
        if normalized.lower() not in {n.lower() for n in candidates}:
            candidates.append(normalized)

    if meta is not None:
        add(meta.current_case)
        for entry in meta.case_entries:
            add(entry)
    add(case_name)
    return candidates


def list_solution_cgns_in_ipro(ipro_path: Path) -> list[str]:
    meta_info = _load_project_xml_meta_from_ipro(ipro_path)
    if meta_info is not None:
        xml_name, meta = meta_info
        xml_dir = Path(xml_name).parent
        result_prefix = (xml_dir / "result").as_posix().strip("./")
        try:
            with zipfile.ZipFile(ipro_path, "r") as z:
                names = z.namelist()
        except Exception:
            return []
        if meta.separate_result:
            in_result = []
            for name in names:
                norm = name.replace("\\", "/")
                if not re.search(r"(?:^|/)Solution\d+\.cgn$", norm, flags=re.IGNORECASE):
                    continue
                if result_prefix:
                    if norm.lower().startswith(result_prefix.lower() + "/"):
                        in_result.append(norm)
                elif "/result/" in norm.lower() or norm.lower().startswith("result/"):
                    in_result.append(norm)
            if in_result:
                return _sort_solution_zip_names(in_result)

    try:
        with zipfile.ZipFile(ipro_path, "r") as z:
            names = z.namelist()
    except Exception:
        return []

    hits: list[str] = []
    for name in names:
        if re.search(r"(?:^|/)Solution\d+\.cgn$", name.replace("\\", "/"), flags=re.IGNORECASE):
            hits.append(name.replace("\\", "/"))
    if not hits:
        return []
    return _sort_solution_zip_names(hits)


def list_solution_cgns_in_dir(project_dir: Path) -> list[Path]:
    meta_info = _load_project_xml_meta_from_dir(project_dir)
    if meta_info is not None:
        xml_path, meta = meta_info
        if meta.separate_result:
            result_dir = xml_path.parent / "result"
            candidates = list(result_dir.rglob("Solution*.cgn")) if result_dir.exists() else []
            if candidates:
                return _sort_solution_paths(candidates)

    candidates = list(project_dir.rglob("Solution*.cgn"))
    if not candidates:
        return []
    return _sort_solution_paths(candidates)


def has_result_csv(input_dir: Path) -> bool:
    for _ in input_dir.rglob("Result_*.csv"):
        return True
    return False


def find_case_cgn(project_dir: Path, case_name: str) -> Path | None:
    meta_info = _load_project_xml_meta_from_dir(project_dir)
    meta = meta_info[1] if meta_info is not None else None
    for case_ref in _resolve_case_name_candidates(case_name, meta):
        hit = _resolve_case_path_from_dir(project_dir, case_ref)
        if hit:
            return hit

    hits = sorted(project_dir.rglob(case_name), key=lambda p: str(p).lower())
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


def is_valid_input_path(input_path: Path | None, case_name: str = "Case1.cgn") -> bool:
    if not input_path:
        return False
    if input_path.is_dir():
        try:
            classify_input_dir(input_path, case_name=case_name)
            return True
        except Exception:
            return False
    if not input_path.is_file():
        return False
    suffix = input_path.suffix.lower()
    if suffix in {".ipro", ".cgn"}:
        return True
    if suffix == ".xml" and input_path.name.lower() == PROJECT_XML_NAME:
        try:
            classify_input_dir(input_path.parent, case_name=case_name)
            return True
        except Exception:
            return False
    return False


def normalize_project_input_path(input_path: Path) -> Path:
    p = Path(input_path)
    if p.is_file() and p.suffix.lower() == ".xml" and p.name.lower() == PROJECT_XML_NAME:
        return p.parent
    return p
