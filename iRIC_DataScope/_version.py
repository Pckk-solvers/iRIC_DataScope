# iRIC_DataScope/_version.py
"""
アプリバージョンの単一ソース。

解決の優先順:
  1. importlib.metadata（pip install -e / uv sync --dev でインストール済みの場合）
  2. pyproject.toml を直接読む（開発時、未インストールでも動く）
  3. _FALLBACK_VERSION（ビルド時に pyproject.toml のバージョンで書き換えられる）
"""
from __future__ import annotations

__all__ = ["__version__"]

# --- ビルド時にこの値が書き換えられる ---
_FALLBACK_VERSION = "dev"


def _resolve_version() -> str:
    # 1. インストール済みメタデータから取得
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version("iric-datascope")
        except PackageNotFoundError:
            pass
    except Exception:
        pass

    # 2. pyproject.toml から直接読む（開発時）
    try:
        import tomllib
        from pathlib import Path
        # _version.py → iRIC_DataScope/ → project root
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject.is_file():
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            ver = data.get("project", {}).get("version", "")
            if isinstance(ver, str) and ver.strip():
                return ver.strip()
    except Exception:
        pass

    # 3. フォールバック（ビルド済み EXE ではここに到達）
    return _FALLBACK_VERSION


__version__: str = _resolve_version()
