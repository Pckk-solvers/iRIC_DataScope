"""lr_wse の入力CSVパースを検証する。"""

from __future__ import annotations

from pathlib import Path

from iRIC_DataScope.lr_wse.reader import extract_time, read_iric_csv


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_extract_time_valid() -> None:
    assert extract_time("iRIC output t = 1.5") == 1.5


def test_extract_time_invalid_value() -> None:
    assert extract_time("iRIC output t = abc") is None


def test_extract_time_missing_pattern() -> None:
    assert extract_time("t = 1.5") is None


def test_read_iric_csv_parses_time_and_dataframe(tmp_path: Path) -> None:
    csv_path = tmp_path / "Result_001.csv"
    _write_csv(
        csv_path,
        "iRIC output t = 1.5\n"
        "comment line\n"
        "I,J,watersurfaceelevation(m),elevation(m)\n"
        "1,2,3.0,4.0\n",
    )
    t_value, df = read_iric_csv(csv_path)
    assert t_value == 1.5
    assert list(df.columns) == ["I", "J", "watersurfaceelevation(m)", "elevation(m)"]
    assert df.shape == (1, 4)
    assert df.loc[0, "I"] == 1
