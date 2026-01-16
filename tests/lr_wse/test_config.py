"""lr_wse 設定CSVの読込挙動を検証する。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from iRIC_DataScope.lr_wse.config import load_setting


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_setting_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError):
        load_setting(missing)


def test_load_setting_numeric_kp(tmp_path: Path) -> None:
    csv_path = tmp_path / "setting.csv"
    _write_csv(
        csv_path,
        "KP,LI,LJ,RI,RJ\n"
        "0.0,1,2,3,4\n"
        "1.5,5,6,7,8\n",
    )
    df = load_setting(csv_path)
    assert pd.api.types.is_numeric_dtype(df["KP"])
    assert df["KP"].tolist() == [0.0, 1.5]


def test_load_setting_kp_suffix_k(tmp_path: Path) -> None:
    csv_path = tmp_path / "setting.csv"
    _write_csv(
        csv_path,
        "KP,LI,LJ,RI,RJ\n"
        "97.6k,1,2,3,4\n"
        "98K,5,6,7,8\n",
    )
    df = load_setting(csv_path)
    assert pd.api.types.is_numeric_dtype(df["KP"])
    assert df["KP"].tolist() == pytest.approx([97.6, 98.0])


def test_load_setting_kp_invalid_coerce(tmp_path: Path) -> None:
    csv_path = tmp_path / "setting.csv"
    _write_csv(
        csv_path,
        "KP,LI,LJ,RI,RJ\n"
        "abc,1,2,3,4\n"
        "1.0k,5,6,7,8\n",
    )
    df = load_setting(csv_path)
    assert pd.isna(df.loc[0, "KP"])
    assert df.loc[1, "KP"] == pytest.approx(1.0)
