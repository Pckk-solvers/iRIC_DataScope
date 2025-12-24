"""プレビュー用フレームの簡易キャッシュ。"""

from __future__ import annotations

from typing import Any


class PreviewFrameCache:
    """Cache for preview frames keyed by (step, value_col)."""

    def __init__(self):
        self._cache: dict[tuple[int, str], Any] = {}

    def clear(self) -> None:
        self._cache.clear()

    def get_or_fetch(self, *, data_source, step: int, value_col: str):
        key = (int(step), str(value_col))
        if key in self._cache:
            return self._cache[key]
        # 未キャッシュの場合は DataSource から取得して保持する。
        frame = data_source.get_frame(step=step, value_col=value_col)
        self._cache[key] = frame
        return frame

    def __len__(self) -> int:
        return len(self._cache)
