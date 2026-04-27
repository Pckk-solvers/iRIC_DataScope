from __future__ import annotations

import zipfile
from pathlib import Path

from iRIC_DataScope.common.iric_project import (
    find_case_cgn,
    is_valid_input_path,
    list_solution_cgns_in_ipro,
)


def _write_project_xml(path: Path, *, current: str = "Case1", separate_result: bool = True) -> None:
    path.write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<iRICProject separateResult="{"true" if separate_result else "false"}">\n'
            f'  <CgnsFileList current="{current}">\n'
            f'    <CgnsFileEntry filename="{current}" />\n'
            "  </CgnsFileList>\n"
            "</iRICProject>\n"
        ),
        encoding="utf-8",
    )


def test_find_case_cgn_prefers_project_xml_entry(tmp_path: Path) -> None:
    _write_project_xml(tmp_path / "project.xml", current="CaseMain")
    (tmp_path / "CaseMain.cgn").write_bytes(b"dummy")
    (tmp_path / "Case1.cgn").write_bytes(b"dummy")

    case = find_case_cgn(tmp_path, "Case1.cgn")

    assert case is not None
    assert case.name == "CaseMain.cgn"


def test_list_solution_cgns_in_ipro_prefers_project_result_dir(tmp_path: Path) -> None:
    ipro = tmp_path / "sample.ipro"
    xml_text = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<iRICProject separateResult="true">\n'
        '  <CgnsFileList current="Case1">\n'
        '    <CgnsFileEntry filename="Case1" />\n'
        "  </CgnsFileList>\n"
        "</iRICProject>\n"
    )
    with zipfile.ZipFile(ipro, "w") as z:
        z.writestr("project.xml", xml_text)
        z.writestr("result/Solution2.cgn", b"dummy")
        z.writestr("result/Solution1.cgn", b"dummy")
        z.writestr("other/Solution9.cgn", b"dummy")

    names = list_solution_cgns_in_ipro(ipro)

    assert names == ["result/Solution1.cgn", "result/Solution2.cgn"]


def test_is_valid_input_path_accepts_project_xml(tmp_path: Path) -> None:
    _write_project_xml(tmp_path / "project.xml", current="Case1")
    (tmp_path / "Case1.cgn").write_bytes(b"dummy")

    assert is_valid_input_path(tmp_path / "project.xml")
