from __future__ import annotations

from pathlib import Path

from iRIC_DataScope.section_analyze.models import SectionAnalyzeOptions
from iRIC_DataScope.section_analyze.shp_reader import read_section_lines


FIXTURE = Path("tests/fixtures/section_analyze/section_lines_sample.shp")


def test_read_section_lines_fixture() -> None:
    lines = read_section_lines(FIXTURE, SectionAnalyzeOptions())

    assert len(lines) == 5
    assert lines[0].section_id == "SEC001"
    assert lines[0].section_name == "J101 sample"
    assert len(lines[0].points) == 73


def test_read_section_lines_with_explicit_truncated_name_field() -> None:
    lines = read_section_lines(FIXTURE, SectionAnalyzeOptions(section_name_field="section_na"))

    assert lines[1].section_name == "J251 sample"

