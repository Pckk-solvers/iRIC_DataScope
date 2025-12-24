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


def build_colormap(min_color: str, max_color: str, *, mode: str = "rgb"):
    from matplotlib import colormaps
    from matplotlib.colors import LinearSegmentedColormap, to_rgb

    mode_key = (mode or "rgb").strip().lower()
    if mode_key == "jet":
        cmap = colormaps.get_cmap("jet")
    elif mode_key == "hsv":
        try:
            import colorsys

            r1, g1, b1 = to_rgb(min_color)
            r2, g2, b2 = to_rgb(max_color)
            h1, s1, v1 = colorsys.rgb_to_hsv(r1, g1, b1)
            h2, s2, v2 = colorsys.rgb_to_hsv(r2, g2, b2)
            dh = h2 - h1
            if dh > 0.5:
                dh -= 1.0
            elif dh < -0.5:
                dh += 1.0
            steps = 256
            colors = []
            for i in range(steps):
                t = i / (steps - 1)
                h = (h1 + dh * t) % 1.0
                s = s1 + (s2 - s1) * t
                v = v1 + (v2 - v1) * t
                colors.append(colorsys.hsv_to_rgb(h, s, v))
            cmap = LinearSegmentedColormap.from_list("xy_value_map_hsv", colors)
        except Exception:
            cmap = LinearSegmentedColormap.from_list("xy_value_map", [min_color, max_color])
    else:
        cmap = LinearSegmentedColormap.from_list("xy_value_map", [min_color, max_color])

    try:
        cmap.set_bad(color=(0, 0, 0, 0))
    except Exception:
        pass
    return cmap
