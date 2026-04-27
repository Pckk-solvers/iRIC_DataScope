from __future__ import annotations

import pandas as pd

from iRIC_DataScope.section_analyze.models import SectionLine
from iRIC_DataScope.section_analyze.sampler import map_section_nodes


def test_map_section_nodes_dedupes_repeated_nearest_nodes() -> None:
    grid = pd.DataFrame(
        [
            {"I": 1, "J": 1, "X": 0.0, "Y": 0.0},
            {"I": 1, "J": 2, "X": 10.0, "Y": 0.0},
        ]
    )
    line = SectionLine(
        section_id="SEC001",
        section_name="SEC001",
        source_feature_id=1,
        order_no=1,
        points=((0.0, 0.0), (10.0, 0.0)),
    )

    nodes, interval = map_section_nodes(grid, [line], sample_interval=1.0)

    assert interval == 1.0
    assert [(node.i, node.j) for node in nodes] == [(1, 1), (1, 2)]
    assert nodes[0].nearest_dist == 0.0

