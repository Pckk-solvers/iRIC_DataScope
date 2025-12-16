from pathlib import Path
from zipfile import ZipFile
import tempfile


def extract_case_cgn(ipro: Path, out_dir: Path, case="Case1.cgn") -> Path:
    # CGNSだけ取り出す
    out_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(ipro) as z:
        target = next((n for n in z.namelist() if n.endswith("/"+case) or n.endswith("\\"+case) or Path(n).name == case), None)
        if not target:
            raise FileNotFoundError(f"{case} not found in {ipro}")
        out = out_dir / case
        with z.open(target) as src, open(out, "wb") as dst:
            dst.write(src.read())
    return out


def is_hdf5(path: Path) -> bool:
    # HDF5かどうかの判定
    with path.open("rb") as f:
        return f.read(8) == b"\x89HDF\r\n\x1a\n"


output = Path("output")
out = extract_case_cgn(Path("dev-1216-file.ipro"), output)
print("Case1:", out)
print(is_hdf5(out))
