"""GUIテスト向けにTkのルートを用意するfixtureを提供する。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

try:
    import tkinter as tk
except Exception:  # pragma: no cover - optional GUI dependency
    tk = None

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(scope="session")
def tk_root():
    if tk is None:
        pytest.skip("tkinter not available")
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass
