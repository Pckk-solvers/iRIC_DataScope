import numpy as np
import h5py

def decode_int8_char_table(a: np.ndarray) -> list[str]:
    a = np.asarray(a)
    if a.dtype != np.int8 or a.ndim != 2:
        raise TypeError(f"unexpected: shape={a.shape}, dtype={a.dtype}")
    out = []
    for row in a:
        s = bytes(row.tolist()).decode("ascii", errors="ignore")
        out.append(s.replace("\x00", "").strip())
    return out

with h5py.File(r"output/Case1.cgn", "r") as f:
    node_path = "iRIC/iRICZone/ZoneIterativeData/FlowSolutionPointers"
    raw = f[node_path][" data"][()]
    names = decode_int8_char_table(raw)

    print("step count:", len(names))
    print("first 5:", names[:5])
    # 指してる先が存在するかチェック（最初の5個だけ）
    zone_path = "iRIC/iRICZone"
    for n in names[:5]:
        p = f"{zone_path}/{n}"
        print(p, "exists:", p in f)

with h5py.File(r"output/Case1.cgn", "r") as f:
    zone_path = "iRIC/iRICZone"
    sol = names[0]
    g = f[f"{zone_path}/{sol}"]
    print("FlowSolution keys sample:", list(g.keys())[:30])