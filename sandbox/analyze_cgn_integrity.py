#!/usr/bin/env python3
"""
Quick integrity probe for iRIC/CGNS(HDF5) files.

Usage:
  uv run python sandbox/analyze_cgn_integrity.py "C:\\path\\to\\Case1.cgn"
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import h5py
import numpy as np


def parse_superblock_v0(header: bytes) -> dict[str, int]:
    # HDF5 v0 superblock: base/free/eof/driver addresses begin at offset 24
    # when offset-size is 8 bytes (common on modern files).
    offset_size = header[13]
    if offset_size not in (4, 8):
        raise ValueError(f"unexpected offset size: {offset_size}")
    start = 24
    fmt = "<I" if offset_size == 4 else "<Q"
    step = offset_size
    base_addr = struct.unpack(fmt, header[start : start + step])[0]
    free_addr = struct.unpack(fmt, header[start + step : start + 2 * step])[0]
    eof_addr = struct.unpack(fmt, header[start + 2 * step : start + 3 * step])[0]
    driver_addr = struct.unpack(fmt, header[start + 3 * step : start + 4 * step])[0]
    return {
        "offset_size": offset_size,
        "base_addr": base_addr,
        "free_addr": free_addr,
        "eof_addr": eof_addr,
        "driver_addr": driver_addr,
    }


def contains_ascii_token(path: Path, token: bytes, chunk_size: int = 8 * 1024 * 1024) -> bool:
    with path.open("rb") as f:
        overlap = b""
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                return False
            data = overlap + chunk
            if token in data:
                return True
            overlap = data[-len(token) + 1 :] if len(token) > 1 else b""


def probe_hdf5(path: Path) -> dict[str, object]:
    report: dict[str, object] = {
        "file": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
    }
    if not path.exists():
        return report

    with path.open("rb") as f:
        header = f.read(128)
    report["signature_ok"] = header[:8] == b"\x89HDF\r\n\x1a\n"
    report["superblock_version"] = header[8]

    if report["signature_ok"] and report["superblock_version"] == 0:
        sb = parse_superblock_v0(header)
        report["superblock"] = sb
        report["eof_matches_filesize"] = sb["eof_addr"] == report["size_bytes"]

    tokens = [
        b"iRIC",
        b"GridCoordinates",
        b"CoordinateX",
        b"FlowSolutionPointers",
        b"FlowSolution1",
    ]
    token_hits: dict[str, bool] = {}
    for t in tokens:
        token_hits[t.decode("ascii")] = contains_ascii_token(path, t)
    report["raw_token_hits"] = token_hits

    h5: dict[str, object] = {}
    report["h5py_probe"] = h5
    try:
        with h5py.File(path, "r") as f:
            h5["open_ok"] = True
            h5["root_keys"] = list(f.keys())

            path_checks: dict[str, dict[str, object]] = {}
            for p in [
                "iRIC",
                "iRIC/iRICZone",
                "iRIC/iRICZone/GridCoordinates",
                "iRIC/iRICZone/GridCoordinates/CoordinateX",
                "iRIC/iRICZone/ZoneIterativeData/FlowSolutionPointers",
            ]:
                try:
                    obj = f[p]
                    path_checks[p] = {"ok": True, "type": type(obj).__name__}
                except Exception as exc:  # pragma: no cover - diagnostic path
                    path_checks[p] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            h5["path_checks"] = path_checks

            visited: list[str] = []
            f.visit(lambda name: visited.append(name))
            h5["reachable_count"] = len(visited)
            h5["reachable_head"] = visited[:120]
    except Exception as exc:  # pragma: no cover - diagnostic path
        h5["open_ok"] = False
        h5["error"] = f"{type(exc).__name__}: {exc}"

    return report


def _dataset_sample(ds: h5py.Dataset, max_items: int = 12) -> list[float] | list[int] | list[str]:
    if ds.shape == ():
        try:
            v = ds[()]
            if isinstance(v, bytes):
                return [v.decode("utf-8", errors="replace")]
            if np.isscalar(v):
                return [v.item() if hasattr(v, "item") else v]
            return [str(v)]
        except Exception:
            return []
    try:
        n = int(np.prod(ds.shape))
        if n <= 0:
            return []
        if len(ds.shape) == 1:
            arr = ds[: min(max_items, ds.shape[0])]
        else:
            idx = tuple(slice(0, 1) for _ in ds.shape[:-1]) + (slice(0, min(max_items, ds.shape[-1])),)
            arr = ds[idx]
        flat = np.asarray(arr).reshape(-1)
        out: list[float] | list[int] | list[str] = []
        for v in flat[:max_items]:
            if isinstance(v, (bytes, bytearray)):
                out.append(bytes(v).decode("utf-8", errors="replace"))
            elif np.isscalar(v):
                out.append(v.item() if hasattr(v, "item") else v)
            else:
                out.append(str(v))
        return out
    except Exception:
        return []


def extract_zone_dataset_info(path: Path) -> dict[str, object]:
    info: dict[str, object] = {"file": str(path), "zone_datasets": []}
    if not path.exists():
        info["error"] = "file_not_found"
        return info
    try:
        with h5py.File(path, "r") as f:
            rows: list[dict[str, object]] = []

            def cb(name: str, obj: object) -> None:
                if not isinstance(obj, h5py.Dataset):
                    return
                if not name.startswith("iRIC/iRICZone/"):
                    return
                if not name.endswith("/ data"):
                    return
                parent = name.rsplit("/", 1)[0]
                rows.append(
                    {
                        "path": name,
                        "variable": parent.split("/")[-1],
                        "shape": list(obj.shape),
                        "dtype": str(obj.dtype),
                        "sample": _dataset_sample(obj),
                    }
                )

            f.visititems(cb)
            info["zone_datasets"] = sorted(rows, key=lambda r: str(r["path"]))
            info["count"] = len(rows)
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze CGNS/HDF5 integrity quickly.")
    parser.add_argument("cgn_file", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--extract-zone",
        action="store_true",
        help="Also extract reachable iRIC/iRICZone/*/ data dataset summaries.",
    )
    args = parser.parse_args()

    report = probe_hdf5(args.cgn_file)
    if args.extract_zone:
        report["zone_extract"] = extract_zone_dataset_info(args.cgn_file)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
