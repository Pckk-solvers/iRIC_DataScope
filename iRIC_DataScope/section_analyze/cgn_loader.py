from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from iRIC_DataScope.common.iric_data_source import DataSource
from iRIC_DataScope.section_analyze.models import DEPTH_COLUMN, WSE_COLUMN


VALUE_COLUMNS = [WSE_COLUMN, DEPTH_COLUMN]


class SectionDataSource:
    def __init__(self, input_path: Path):
        self._data_source = DataSource.from_input(input_path, grid_location="node")

    @property
    def steps(self) -> list[int]:
        return list(self._data_source.steps or [])

    @property
    def step_count(self) -> int:
        return int(self._data_source.step_count)

    def close(self) -> None:
        self._data_source.close()

    def load_grid_nodes(self) -> pd.DataFrame:
        first_step = self.steps[0] if self.steps else 1
        frame = self._data_source.get_frame_with_columns(step=first_step, value_cols=[])
        return frame.df.loc[:, ["I", "J", "X", "Y"]].copy()

    def iter_result_frames(self, *, limit_steps: int | None = None) -> Iterable:
        count = 0
        for frame in self._data_source.iter_frames_with_columns(value_cols=VALUE_COLUMNS):
            yield frame
            count += 1
            if limit_steps is not None and count >= limit_steps:
                break

