from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator, MultipleLocator
import pandas as pd
from matplotlib.figure import Figure

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


def _tick_step(value_range: float) -> float:
    if value_range <= 0.0:
        return 1.0
    rough = value_range / 5.0
    power = math.floor(math.log10(rough))
    base = 10 ** power
    normalized = rough / base
    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return nice * base


def _y_axis_spec(values: pd.Series) -> tuple[float, float, float]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return (0.0, 1.0, 0.2)
    lower = float(numeric.min())
    upper = float(numeric.max())
    if math.isclose(lower, upper):
        step = _tick_step(max(abs(lower) * 0.1, 1.0))
        return (lower - step, lower + step, step)

    step = _tick_step(upper - lower)
    # 1目盛ぶん上下に余白を確保し、目盛で閉じる
    bottom = math.floor(lower / step) * step - step
    top = math.ceil(upper / step) * step + step
    if math.isclose(bottom, top):
        top = bottom + step * 2
    return (bottom, top, step)


def collect_graph_limits(
    timeseries: pd.DataFrame,
    *,
    x_tick_interval_hour: float | None = None,
) -> tuple[float, float]:
    time_sec = pd.to_numeric(timeseries.get("time", pd.Series(dtype=float)), errors="coerce").dropna()
    if time_sec.empty:
        return (0.0, 1.0)
    values = time_sec / 3600.0
    x_min = float(values.min())
    x_max = float(values.max())
    if math.isclose(x_min, x_max):
        step = x_tick_interval_hour if x_tick_interval_hour and x_tick_interval_hour > 0 else 1.0
        return (x_min - step, x_min)
    step = x_tick_interval_hour if x_tick_interval_hour and x_tick_interval_hour > 0 else _tick_step(x_max - x_min)
    # 開始側は1目盛ぶん余白、終了側は最終目盛で閉じる
    left = math.floor(x_min / step) * step - step
    right = math.ceil(x_max / step) * step
    if math.isclose(left, right):
        right = left + step
    return (left, right)


def _render_section_graph(
    path: Path,
    section_id: str,
    section_name: str,
    group: pd.DataFrame,
    *,
    x_limits: tuple[float, float],
    y_limits: tuple[float, float],
    y_tick_step: float,
    x_tick_interval_hour: float | None,
    title_template: str,
    graph_width_inch: float,
    graph_height_inch: float,
    graph_dpi: int,
) -> None:
    fig = build_section_figure(
        section_id=section_id,
        section_name=section_name,
        group=group,
        x_limits=x_limits,
        y_limits=y_limits,
        y_tick_step=y_tick_step,
        x_tick_interval_hour=x_tick_interval_hour,
        title_template=title_template,
        graph_width_inch=graph_width_inch,
        graph_height_inch=graph_height_inch,
        graph_dpi=graph_dpi,
    )
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def build_section_figure(
    *,
    section_id: str,
    section_name: str,
    group: pd.DataFrame,
    x_limits: tuple[float, float],
    y_limits: tuple[float, float],
    y_tick_step: float,
    x_tick_interval_hour: float | None,
    title_template: str,
    graph_width_inch: float,
    graph_height_inch: float,
    graph_dpi: int,
) -> Figure:
    frame = group.loc[:, ["time", "mean_wse"]].copy()
    frame["time"] = pd.to_numeric(frame["time"], errors="coerce")
    frame["time_hour"] = frame["time"] / 3600.0
    frame["mean_wse"] = pd.to_numeric(frame["mean_wse"], errors="coerce")
    frame = frame.dropna(subset=["time_hour"]).sort_values("time_hour")

    fig, ax = plt.subplots(figsize=(graph_width_inch, graph_height_inch), dpi=graph_dpi)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    safe_title_template = title_template or "{section_id} {section_name} / 平均水位時系列"
    try:
        title = safe_title_template.format(section_id=section_id, section_name=section_name).strip()
    except Exception:
        title = f"{section_id} {section_name} / 平均水位時系列".strip()
    ax.set_title(title, fontsize=12, color=TEXT_COLOR, pad=12)
    ax.set_xlabel("時間[h]", fontsize=11, color=TEXT_COLOR, labelpad=8)
    ax.set_ylabel("水位[T.P.m]", fontsize=11, color=TEXT_COLOR, labelpad=8)

    ax.grid(True, which="major", axis="both", linestyle="--", color="#9AA7B6", linewidth=0.8)
    ax.tick_params(axis="both", labelsize=9, colors=TEXT_COLOR)
    if x_tick_interval_hour and x_tick_interval_hour > 0:
        ax.xaxis.set_major_locator(MultipleLocator(base=x_tick_interval_hour))
    else:
        ax.xaxis.set_major_locator(MaxNLocator(nbins=7))
    if y_tick_step > 0:
        ax.yaxis.set_major_locator(MultipleLocator(base=y_tick_step))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value:g}"))

    for spine in ("top", "right", "left", "bottom"):
        ax.spines[spine].set_visible(True)
        ax.spines[spine].set_color("black")
        ax.spines[spine].set_linewidth(0.9)

    if not frame.empty and frame["mean_wse"].notna().any():
        valid = frame.dropna(subset=["mean_wse"])
        ax.plot(frame["time_hour"], frame["mean_wse"], color=LINE_COLOR, linewidth=1.8)
        peak = valid.sort_values(["mean_wse", "time_hour"], ascending=[False, True]).iloc[0]
        peak_time = float(peak["time_hour"])
        peak_value = float(peak["mean_wse"])
        peak_time_label = f"{peak_time:g}"
        ax.scatter([peak_time], [peak_value], s=36, color=LINE_COLOR, edgecolors="white", linewidths=0.8, zorder=3)
        ax.annotate(
            f"Max {peak_value:.2f} (t={peak_time_label}h)",
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
    return fig


def write_section_graphs(
    output_dir: Path,
    timeseries: pd.DataFrame,
    *,
    overwrite: bool,
    shared_y_scale: bool = False,
    x_tick_interval_hour: float | None = None,
    title_template: str = "{section_id} {section_name} / 平均水位時系列",
    graph_width_inch: float = 12.0,
    graph_height_inch: float = 4.8,
    graph_dpi: int = 180,
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

    x_limits = collect_graph_limits(timeseries, x_tick_interval_hour=x_tick_interval_hour)
    shared_y_spec: tuple[float, float, float] | None = None
    if shared_y_scale:
        shared_y_spec = _y_axis_spec(timeseries.get("mean_wse", pd.Series(dtype=float)))
    output_files: list[Path] = []
    for section_id, group in timeseries.groupby("section_id", sort=False):
        first = group.iloc[0]
        section_name = str(first.get("section_name", section_id))
        y_spec = shared_y_spec or _y_axis_spec(group.get("mean_wse", pd.Series(dtype=float)))
        y_limits = (y_spec[0], y_spec[1])
        path = graph_dir / f"{_safe_filename(section_id)}.png"
        _render_section_graph(
            path,
            str(section_id),
            section_name,
            group,
            x_limits=x_limits,
            y_limits=y_limits,
            y_tick_step=y_spec[2],
            x_tick_interval_hour=x_tick_interval_hour,
            title_template=title_template,
            graph_width_inch=graph_width_inch,
            graph_height_inch=graph_height_inch,
            graph_dpi=graph_dpi,
        )
        output_files.append(path)
    return tuple(output_files)
