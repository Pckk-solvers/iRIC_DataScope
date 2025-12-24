"""非同期処理（globalスケール計算）をまとめる。"""

from __future__ import annotations

import threading
from typing import Callable

from .processor import compute_global_value_range_rotated


class GlobalScaleWorker:
    """Background computation for global scale with token-based invalidation."""

    def __init__(self, scheduler: Callable[[Callable[[], None]], object]):
        self.token = 0
        self.vmin: float | None = None
        self.vmax: float | None = None
        self.running = False
        self._schedule = scheduler

    def invalidate(self) -> None:
        # 条件変更に備えてトークンを進め、既存結果を破棄する。
        self.token += 1
        self.vmin = None
        self.vmax = None

    def get_scale(self) -> tuple[float, float] | None:
        if self.vmin is None or self.vmax is None:
            return None
        return self.vmin, self.vmax

    def ensure_async(
        self,
        *,
        data_source,
        value_col: str,
        roi,
        dx: float,
        dy: float,
        status_text: str,
        on_status: Callable[[str], None],
        on_empty: Callable[[], None],
        on_error: Callable[[Exception], None],
        on_done: Callable[[float, float], None],
        on_token_mismatch: Callable[[], None],
    ) -> None:
        if data_source is None:
            return
        if self.running:
            return
        if self.vmin is not None and self.vmax is not None:
            return

        self.running = True
        self.token += 1
        token = self.token
        on_status(status_text)

        def worker():
            try:
                vmin, vmax = compute_global_value_range_rotated(
                    data_source,
                    value_col=value_col,
                    roi=roi,
                    dx=dx,
                    dy=dy,
                )
            except ValueError:
                # ROI内に値が無いケースは例外扱いのため空として通知する。
                def finish_empty():
                    token_matches = token == self.token
                    self.running = False
                    if not token_matches:
                        on_token_mismatch()
                        return
                    on_empty()

                self._schedule(finish_empty)
                return
            except Exception as err:
                # 予期しない例外はGUI側で通知する。
                def finish_error(err=err):
                    token_matches = token == self.token
                    self.running = False
                    if not token_matches:
                        on_token_mismatch()
                        return
                    on_error(err)

                self._schedule(finish_error)
                return

            def finish_done():
                token_matches = token == self.token
                self.running = False
                if token_matches:
                    self.vmin = vmin
                    self.vmax = vmax
                    on_done(vmin, vmax)
                # 条件変更済みでも最新描画は必要なので再描画を依頼する。
                on_token_mismatch()

            self._schedule(finish_done)

        threading.Thread(target=worker, daemon=True).start()
