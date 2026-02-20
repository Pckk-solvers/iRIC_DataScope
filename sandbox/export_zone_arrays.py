#!/usr/bin/env python3
"""
Export reachable datasets under `iRIC/iRICZone/*/ data` from CGNS(HDF5).

Usage:
  uv run python sandbox/export_zone_arrays.py "C:\\path\\Case1.cgn" --out-dir sandbox/zone_export
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import h5py
import numpy as np


def sanitize(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
    return s or "dataset"


def export_zone_arrays(cgn_path: Path, out_dir: Path, export_csv: bool, export_npy: bool) -> dict[str, object]:
    report: dict[str, object] = {
        "file": str(cgn_path),
        "out_dir": str(out_dir),
        "datasets": [],
    }
    if not cgn_path.exists():
        report["error"] = "input_file_not_found"
        return report

    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    try:
        with h5py.File(cgn_path, "r") as f:
            def cb(name: str, obj: object) -> None:
                if not isinstance(obj, h5py.Dataset):
                    return
                if not name.startswith("iRIC/iRICZone/"):
                    return
                if not name.endswith("/ data"):
                    return

                parent = name.rsplit("/", 1)[0]
                variable = parent.split("/")[-1]
                arr = np.asarray(obj[()])
                base = sanitize(variable)
                item: dict[str, object] = {
                    "path": name,
                    "variable": variable,
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                }

                if export_npy:
                    npy_path = out_dir / f"{base}.npy"
                    np.save(npy_path, arr)
                    item["npy"] = str(npy_path)

                if export_csv:
                    if arr.ndim == 1:
                        csv_data = arr.reshape(-1, 1)
                    elif arr.ndim == 2:
                        csv_data = arr
                    else:
                        csv_data = None
                    if csv_data is not None:
                        csv_path = out_dir / f"{base}.csv"
                        np.savetxt(csv_path, csv_data, delimiter=",")
                        item["csv"] = str(csv_path)
                    else:
                        item["csv"] = "skipped(ndim>2)"

                rows.append(item)

            f.visititems(cb)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report

    report["datasets"] = rows
    report["count"] = len(rows)
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["manifest"] = str(manifest)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Export iRIC/iRICZone datasets to CSV/NPY.")
    parser.add_argument("cgn_file", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--no-csv", action="store_true", help="Do not write CSV files.")
    parser.add_argument("--no-npy", action="store_true", help="Do not write NPY files.")
    args = parser.parse_args()

    export_csv = not args.no_csv
    export_npy = not args.no_npy
    if not export_csv and not export_npy:
        raise SystemExit("Both CSV and NPY exports are disabled.")

    result = export_zone_arrays(args.cgn_file, args.out_dir, export_csv=export_csv, export_npy=export_npy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "error" in result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
