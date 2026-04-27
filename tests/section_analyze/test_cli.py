from __future__ import annotations

from pathlib import Path

from iRIC_DataScope.section_analyze.cli import main


FIXTURE = Path("tests/fixtures/section_analyze/section_lines_sample.shp")


def _write_result_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "time=0.0",
                "2,2",
                "I,J,X,Y,watersurfaceelevation(m),depth(m)",
                "1,1,0.0,0.0,10.0,1.0",
                "1,2,10.0,0.0,11.0,1.0",
                "2,1,0.0,10.0,12.0,1.0",
                "2,2,10.0,10.0,13.0,1.0",
            ]
        ),
        encoding="utf-8",
    )


def test_cli_missing_required_args_returns_one() -> None:
    assert main([]) == 1


def test_cli_dry_run_writes_no_csv(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_result_csv(input_dir / "Result_0001.csv")
    output_dir = tmp_path / "out"

    code = main(
        [
            "--input",
            str(input_dir),
            "--sections",
            str(FIXTURE),
            "--output",
            str(output_dir),
            "--dry-run",
        ]
    )

    assert code == 0
    assert not output_dir.exists()


def test_cli_river_column_names(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_result_csv(input_dir / "Result_0001.csv")
    output_dir = tmp_path / "out"

    code = main(
        [
            "--input",
            str(input_dir),
            "--sections",
            str(FIXTURE),
            "--output",
            str(output_dir),
            "--column-names",
            "river",
        ]
    )

    assert code == 0
    header = (output_dir / "section_timeseries.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    assert "断面ID" in header
    assert "平均水位" in header


def test_cli_writes_graph_png(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_result_csv(input_dir / "Result_0001.csv")
    output_dir = tmp_path / "out"

    code = main(
        [
            "--input",
            str(input_dir),
            "--sections",
            str(FIXTURE),
            "--output",
            str(output_dir),
            "--overwrite",
        ]
    )

    assert code == 0
    graph_dir = output_dir / "section_graphs"
    png_files = sorted(graph_dir.glob("*.png"))
    assert png_files
    assert png_files[0].stat().st_size > 0


def test_cli_shared_y_scale_option(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_result_csv(input_dir / "Result_0001.csv")
    output_dir = tmp_path / "out"

    code = main(
        [
            "--input",
            str(input_dir),
            "--sections",
            str(FIXTURE),
            "--output",
            str(output_dir),
            "--overwrite",
            "--shared-y-scale",
        ]
    )

    assert code == 0
    assert (output_dir / "section_graphs").exists()
