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

    candidates = [
        "Yu Gothic UI",
        "Yu Gothic",
        "Meiryo",
        "MS UI Gothic",
        "MS Gothic",
        "Noto Sans CJK JP",
        "Noto Sans JP",
    ]
    for name in candidates:
        try:
            path = font_manager.findfont(name, fallback_to_default=False)
        except Exception:
            path = None
        if path:
            try:
                font_manager.fontManager.addfont(path)
            except Exception:
                pass
            try:
                font_name = font_manager.FontProperties(fname=path).get_name()
            except Exception:
                font_name = name
            rcParams["font.family"] = font_name
            rcParams["axes.unicode_minus"] = False
            _JP_FONT_SET = True
            return

    try:
        for path in font_manager.findSystemFonts(fontext="ttf"):
            lower = path.lower()
            if any(
                key in lower
                for key in (
                    "yugoth",
                    "meiryo",
                    "msgothic",
                    "ms gothic",
                    "msuigothic",
                    "noto sans cjk",
                    "notosanscjk",
                    "noto sans jp",
                    "notosansjp",
                    "ipaexg",
                    "ipag",
                )
            ):
                try:
                    font_manager.fontManager.addfont(path)
                except Exception:
                    pass
                try:
                    font_name = font_manager.FontProperties(fname=path).get_name()
                except Exception:
                    font_name = None
                if font_name:
                    rcParams["font.family"] = font_name
                    rcParams["axes.unicode_minus"] = False
                    _JP_FONT_SET = True
                    return
    except Exception:
        pass

    rcParams["axes.unicode_minus"] = False
    _JP_FONT_SET = True


def get_edit_colormap():
    from matplotlib import colormaps

    # 編集キャンバス用の単色寄りカラーマップ。
    return colormaps.get_cmap(EDIT_COLORMAP_NAME)
