from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
import pandas as pd

from iRIC_DataScope.section_analyze.writer import GRAPH_DIR_NAME


LINE_COLOR = "#2F6DB3"
GRID_COLOR = "#D9DDE3"
TEXT_COLOR = "#243447"
NOTE_COLOR = "#506070"

plt.switch_backend("Agg")
matplotlib.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Meiryo", "Yu Gothic", "MS Gothic", "DejaVu Sans"],
        "axes.unicode_minus": False,
    }
)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", str(value)).strip()
    return cleaned or "section"


def _numeric_bounds(values: pd.Series, *, fallback: tuple[float, float]) -> tuple[float, float]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return fallback
    lower = float(numeric.min())
    upper = float(numeric.max())
    if math.isclose(lower, upper):
        margin = max(abs(lower) * 0.05, 1.0)
    else:
        margin = max((upper - lower) * 0.08, 0.5)
    return lower - margin, upper + margin


def collect_graph_limits(timeseries: pd.DataFrame) -> tuple[float, float]:
    return _numeric_bounds(timeseries.get("time", pd.Series(dtype=float)), fallback=(0.0, 1.0))


def _render_section_graph(
    path: Path,
    section_id: str,
    section_name: str,
    group: pd.DataFrame,
    *,
    x_limits: tuple[float, float],
    y_limits: tuple[float, float],
) -> None:
    frame = group.loc[:, ["time", "mean_wse"]].copy()
    frame["time"] = pd.to_numeric(frame["time"], errors="coerce")
    frame["mean_wse"] = pd.to_numeric(frame["mean_wse"], errors="coerce")
    frame = frame.dropna(subset=["time"]).sort_values("time")

    fig, ax = plt.subplots(figsize=(12.0, 4.8), dpi=180)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    title = f"{section_id} {section_name} / 平均水位時系列".strip()
    ax.set_title(title, fontsize=12, color=TEXT_COLOR, pad=12)
    ax.set_xlabel("時刻", fontsize=11, color=TEXT_COLOR, labelpad=8)
    ax.set_ylabel("平均水位", fontsize=11, color=TEXT_COLOR, labelpad=8)

    ax.grid(True, which="major", axis="both", color=GRID_COLOR, linewidth=0.7)
    ax.tick_params(axis="both", labelsize=9, colors=TEXT_COLOR)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=7, integer=True))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{int(round(value))}"))

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#B0B8C2")
        ax.spines[spine].set_linewidth(0.8)

    if not frame.empty and frame["mean_wse"].notna().any():
        valid = frame.dropna(subset=["mean_wse"])
        ax.plot(frame["time"], frame["mean_wse"], color=LINE_COLOR, linewidth=1.8)
        peak = valid.sort_values(["mean_wse", "time"], ascending=[False, True]).iloc[0]
        peak_time = float(peak["time"])
        peak_value = float(peak["mean_wse"])
        peak_time_label = int(round(peak_time))
        ax.scatter([peak_time], [peak_value], s=36, color=LINE_COLOR, edgecolors="white", linewidths=0.8, zorder=3)
        ax.annotate(
            f"最大 {peak_value:.2f} (t={peak_time_label})",
            xy=(peak_time, peak_value),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=8.5,
            color=NOTE_COLOR,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#D0D5DC", "alpha": 0.95},
            arrowprops={"arrowstyle": "->", "color": NOTE_COLOR, "lw": 0.8},
        )
    else:
        ax.text(
            0.5,
            0.5,
            "有効データなし",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            color=NOTE_COLOR,
        )

    ax.set_xlim(*x_limits)
    ax.set_ylim(*y_limits)
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def write_section_graphs(
    output_dir: Path,
    timeseries: pd.DataFrame,
    *,
    overwrite: bool,
    shared_y_scale: bool = False,
) -> tuple[Path, ...]:
    graph_dir = Path(output_dir) / GRAPH_DIR_NAME
    graph_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for existing in graph_dir.glob("*.png"):
            if existing.is_file():
                existing.unlink()
    elif any(graph_dir.glob("*.png")):
        raise FileExistsError(f"出力PNGが既に存在します。上書きする場合は --overwrite を指定してください: {graph_dir}")

    if timeseries.empty:
        return ()

    x_limits = collect_graph_limits(timeseries)
    shared_y_limits: tuple[float, float] | None = None
    if shared_y_scale:
        shared_y_limits = _numeric_bounds(timeseries.get("mean_wse", pd.Series(dtype=float)), fallback=(0.0, 1.0))
    output_files: list[Path] = []
    for section_id, group in timeseries.groupby("section_id", sort=False):
        first = group.iloc[0]
        section_name = str(first.get("section_name", section_id))
        y_limits = shared_y_limits or _numeric_bounds(group.get("mean_wse", pd.Series(dtype=float)), fallback=(0.0, 1.0))
        path = graph_dir / f"{_safe_filename(section_id)}.png"
        _render_section_graph(path, str(section_id), section_name, group, x_limits=x_limits, y_limits=y_limits)
        output_files.append(path)
    return tuple(output_files)
