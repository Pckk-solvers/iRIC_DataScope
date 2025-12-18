import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable


def load_bed_elevation(path: str) -> dict[str, np.ndarray]:
    """Load the tab separated bed elevation data and return columns."""
    data = np.genfromtxt(path, names=True)
    return {name: data[name] for name in data.dtype.names}


def plot_cases(data: dict[str, np.ndarray], output_path: str | None = None) -> None:
    """Plot Case0, Case1, and their difference as plan-view scatter maps with minimal empty space vertically."""
    x = data["X"]
    y = data["Y"]
    case0 = data["Case0"]
    case1 = data["Case1"]
    diff = case1 - case0

    # 各グラフの縦方向を引き伸ばす: share X/Y範囲の最小矩形のみをプロット、大きな余白ができないよう調整
    x_margin = (x.max() - x.min()) * 0.05
    y_margin = (y.max() - y.min()) * 0.05
    xlim = (x.min() - x_margin, x.max() + x_margin)
    ylim = (y.min() - y_margin, y.max() + y_margin)

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(10, 8),  # 少し縦長に調整
        constrained_layout=True
    )
    specs = [
        ("Case0", case0, "viridis", None),
        ("Case1", case1, "viridis", None),
        ("Case1 - Case0", diff, "RdBu_r", (-0.2, 0.2)),
    ]

    for ax, (title, values, cmap, clim) in zip(np.atleast_1d(axes), specs):
        sc = ax.scatter(x, y, c=values, cmap=cmap, s=15, edgecolor="none")
        if clim is not None:
            sc.set_clim(*clim)
        ax.set_title(title)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.set_aspect("auto")
        # -- カラーバーを軸内に重ねて小さく表示 --
        # inset_axesを使ってカラーバーをプロット領域内に重ねる
        from mpl_toolkits.axes_grid1.inset_locator import inset_axes
        # 横幅を「ax」の50%程度、縦幅は2.5%、位置は下部中央寄り
        cax = inset_axes(ax, width="50%", height="2.5%", 
                         loc='upper left',
                         bbox_to_anchor=(0.75, -0.1, 0.4, 1),
                         bbox_transform=ax.transAxes,
                         borderpad=0)
        cbar = fig.colorbar(sc, cax=cax, orientation="horizontal")
        cbar.set_label(title, labelpad=6, fontsize=10, loc='right')

    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
    else:
        plt.show()


if __name__ == "__main__":
    dataset = load_bed_elevation("result_bedelevation.txt")
    plot_cases(dataset, output_path="diff_case1-case0_plan.png")
