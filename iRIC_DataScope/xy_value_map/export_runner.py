"""画像出力の実行とバリデーションをまとめる。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .options import OutputOptions


def _validate_value_col(value_col: str) -> None:
    if not value_col or not str(value_col).strip():
        raise ValueError("Value（変数）を選択してください。")


def _normalize_manual_scale(scale_mode: str, manual_scale: tuple[object, object] | None) -> tuple[float, float] | None:
    if scale_mode != "manual":
        return None
    if manual_scale is None:
        raise ValueError("manual の場合は vmin/vmax を数値で入力してください。")
    try:
        vmin = float(manual_scale[0])
        vmax = float(manual_scale[1])
    except Exception as e:
        raise ValueError("manual の場合は vmin/vmax を数値で入力してください。") from e
    if vmin >= vmax:
        raise ValueError("vmin は vmax より小さい必要があります。")
    return vmin, vmax


def run_export_all(
    *,
    data_source,
    value_col: str,
    roi,
    dx: float,
    dy: float,
    min_color: str,
    max_color: str,
    output_opts: OutputOptions,
    output_dir: Path,
    scale_mode: str,
    manual_scale: tuple[object, object] | None,
    step_start: int | None = None,
    step_end: int | None = None,
    step_skip: int = 0,
    progress_factory: Callable[[int, str], object],
    export_func,
) -> Path:
    _validate_value_col(value_col)
    normalized_scale = _normalize_manual_scale(scale_mode, manual_scale)
    step_count = max(1, int(getattr(data_source, "step_count", 1)))
    try:
        start = int(step_start or 1)
    except Exception:
        start = 1
    try:
        end = int(step_end or step_count)
    except Exception:
        end = step_count
    start = max(1, min(start, step_count))
    end = max(1, min(end, step_count))
    if end < start:
        end = start
    if step_skip < 0:
        step_skip = 0
    stride = int(step_skip) + 1
    total = len(range(start, end + 1, stride))
    progress = progress_factory(max(1, total), "出力中")
    try:
        export_func(
            data_source=data_source,
            output_dir=output_dir,
            value_col=value_col,
            roi=roi,
            min_color=min_color,
            max_color=max_color,
            scale_mode=scale_mode,
            manual_scale=normalized_scale,
            dx=dx,
            dy=dy,
            show_title=output_opts.show_title,
            title_text=output_opts.title_text,
            show_ticks=output_opts.show_ticks,
            show_frame=output_opts.show_frame,
            show_cbar=output_opts.show_cbar,
            cbar_label=output_opts.cbar_label,
            title_font_size=output_opts.title_font_size,
            tick_font_size=output_opts.tick_font_size,
            cbar_label_font_size=output_opts.cbar_label_font_size,
            pad_inches=output_opts.pad_inches,
            figsize=output_opts.figsize,
            step_start=start,
            step_end=end,
            step_skip=step_skip,
            progress=progress,
        )
    except Exception as e:
        raise RuntimeError(f"画像出力に失敗しました:\n{e}") from e
    finally:
        try:
            progress.close()
        except Exception:
            pass
    return output_dir


def run_export_single_step(
    *,
    data_source,
    value_col: str,
    step: int,
    roi,
    dx: float,
    dy: float,
    min_color: str,
    max_color: str,
    output_opts: OutputOptions,
    output_dir: Path,
    scale_mode: str,
    manual_scale: tuple[object, object] | None,
    global_scale: tuple[float, float] | None,
    confirm_global_fallback: Callable[[str], bool],
    get_preview_frame: Callable[[int, str], object],
    compute_roi_minmax_fn,
    progress_factory: Callable[[int, str], object],
    export_func,
) -> Path | None:
    _validate_value_col(value_col)
    normalized_scale = _normalize_manual_scale(scale_mode, manual_scale)

    if normalized_scale is not None:
        vmin, vmax = normalized_scale
    else:
        if global_scale is not None:
            vmin, vmax = global_scale
        else:
            msg = (
                "global スケールがまだ計算されていないため、\n"
                "このステップの min/max（プレビューと同じ暫定スケール）で出力します。\n"
                "よろしいですか？"
            )
            if not confirm_global_fallback(msg):
                return None
            try:
                frame = get_preview_frame(step, value_col)
                minmax = compute_roi_minmax_fn(
                    frame,
                    value_col=value_col,
                    roi=roi,
                    dx=dx,
                    dy=dy,
                )
            except Exception as e:
                raise ValueError(f"スケール計算に失敗しました:\n{e}") from e
            if minmax is None:
                raise ValueError("ROI 内の Value が全て NaN/Inf か点がありません。")
            vmin, vmax = minmax

    progress = progress_factory(1, "出力中")
    try:
        if hasattr(progress, "update"):
            progress.update(current=0, total=1, text=f"出力中: step={step}")
        out_path = export_func(
            data_source=data_source,
            output_dir=output_dir,
            step=step,
            value_col=value_col,
            roi=roi,
            min_color=min_color,
            max_color=max_color,
            vmin=vmin,
            vmax=vmax,
            dx=dx,
            dy=dy,
            show_title=output_opts.show_title,
            title_text=output_opts.title_text,
            show_ticks=output_opts.show_ticks,
            show_frame=output_opts.show_frame,
            show_cbar=output_opts.show_cbar,
            cbar_label=output_opts.cbar_label,
            title_font_size=output_opts.title_font_size,
            tick_font_size=output_opts.tick_font_size,
            cbar_label_font_size=output_opts.cbar_label_font_size,
            pad_inches=output_opts.pad_inches,
            figsize=output_opts.figsize,
        )
    except Exception as e:
        raise RuntimeError(f"画像出力に失敗しました:\n{e}") from e
    finally:
        try:
            progress.close()
        except Exception:
            pass
    return out_path
