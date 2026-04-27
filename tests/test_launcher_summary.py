from __future__ import annotations

import zipfile

from iRIC_DataScope.app import summarize_input_path


def test_summarize_missing_input() -> None:
    summary = summarize_input_path(None)

    assert summary.label == "入力未選択"
    assert not summary.valid


def test_summarize_csv_directory(tmp_path) -> None:
    (tmp_path / "Result_0001.csv").write_text("x,y\n1,2\n", encoding="utf-8")

    summary = summarize_input_path(tmp_path)

    assert summary.label == "CSV フォルダ"
    assert summary.valid
    assert "Result_*.csv を検出" in summary.details


def test_summarize_project_directory(tmp_path) -> None:
    (tmp_path / "Case1.cgn").write_bytes(b"dummy")
    (tmp_path / "Solution1.cgn").write_bytes(b"dummy")
    (tmp_path / "Solution2.cgn").write_bytes(b"dummy")

    summary = summarize_input_path(tmp_path)

    assert summary.label == "プロジェクトフォルダ"
    assert summary.valid
    assert "Solution*.cgn: 2 件" in summary.details


def test_summarize_ipro_file(tmp_path) -> None:
    ipro_path = tmp_path / "case.ipro"
    with zipfile.ZipFile(ipro_path, "w") as zf:
        zf.writestr("case/Solution1.cgn", b"dummy")

    summary = summarize_input_path(ipro_path)

    assert summary.label == "iRIC プロジェクト"
    assert summary.valid
    assert "Solution*.cgn: 1 件" in summary.details


def test_summarize_project_xml_file(tmp_path) -> None:
    (tmp_path / "project.xml").write_text(
        (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<iRICProject separateResult="false">\n'
            '  <CgnsFileList current="CaseA">\n'
            '    <CgnsFileEntry filename="CaseA" />\n'
            "  </CgnsFileList>\n"
            "</iRICProject>\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "CaseA.cgn").write_bytes(b"dummy")

    summary = summarize_input_path(tmp_path / "project.xml")

    assert summary.label == "プロジェクトフォルダ"
    assert summary.valid
