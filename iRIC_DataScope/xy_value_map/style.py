"""描画スタイルやフォント設定を集約する。"""

from __future__ import annotations

DEFAULT_TITLE_FONT_SIZE = 12.0
DEFAULT_TICK_FONT_SIZE = 10.0
DEFAULT_CBAR_LABEL_FONT_SIZE = 10.0
EDIT_COLORMAP_NAME = "Greys"

_JP_FONT_SET = False


def ensure_japanese_font():
    """Try to set a font that can render Japanese to avoid glyph warnings."""
    global _JP_FONT_SET
    if _JP_FONT_SET:
        return
    from matplotlib import font_manager, rcParams

    candidates = ["Yu Gothic", "Yu Gothic UI", "Meiryo", "MS Gothic", "Noto Sans CJK JP"]
    for name in candidates:
        try:
            path = font_manager.findfont(name, fallback_to_default=False)
            if path:
                rcParams["font.family"] = name
                rcParams["axes.unicode_minus"] = False
                _JP_FONT_SET = True
                return
        except Exception:
            continue
    rcParams["axes.unicode_minus"] = False
    _JP_FONT_SET = True


def get_edit_colormap():
    from matplotlib import colormaps

    # 編集キャンバス用の単色寄りカラーマップ。
    return colormaps.get_cmap(EDIT_COLORMAP_NAME)
