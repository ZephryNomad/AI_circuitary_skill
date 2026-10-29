"""图 18：求 R_eq 的方法选择流程图。
运行：MPLCONFIGDIR=.mplcache PYTHONPATH=tools python -W ignore tools/make_figs_d.py
"""
from matplotlib.patches import FancyBboxPatch, Polygon
from figlib import (canvas, out, txt, arrow, C_MAIN, C_BOX, C_EQ, C_FILL,
                    C_GREY, C_HL)


def box(ax, cx, cy, w, h, fc=C_FILL, ec=C_BOX, lw=1.8, zorder=3):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle="round,pad=0.06,rounding_size=0.16",
                                fc=fc, ec=ec, lw=lw, zorder=zorder))


def diamond(ax, cx, cy, hw, hh, fc="#fef6e4", ec=C_EQ, lw=1.8):
    ax.add_patch(Polygon([(cx - hw, cy), (cx, cy + hh), (cx + hw, cy),
                          (cx, cy - hh)], closed=True, fc=fc, ec=ec,
                         lw=lw, zorder=3))


def fig18():
    fig, ax = canvas(9.6, 5.4, (-0.6, 12.6), (0.2, 6.4))

    # 起点
    box(ax, 6.0, 5.75, 4.2, 0.80)
    txt(ax, 6.0, 5.75, "要求等效电阻 $R_{eq}$", fs=13.5, color=C_MAIN)
    arrow(ax, (6.0, 5.29), (6.0, 4.76), color=C_GREY, lw=1.5, ms=12)

    # 判据菱形
    diamond(ax, 6.0, 4.05, 2.60, 0.68)
    txt(ax, 6.0, 4.05, "内部含受控源？", fs=13, color=C_EQ)

    # 左：不含受控源
    arrow(ax, (3.40, 4.05), (2.82, 4.05), color=C_GREY, lw=1.5, ms=12)
    txt(ax, 3.11, 4.36, "不含", fs=11.5, color=C_GREY)
    box(ax, 1.18, 3.05, 3.22, 1.60, fc="#f4faf6", ec="#2E7D52")
    txt(ax, 1.18, 3.46, "① 除源后串并联化简", fs=11.8, color=C_MAIN)
    txt(ax, 1.18, 2.98, "② 或直接用外加电源法", fs=11.8, color=C_MAIN)
    txt(ax, 1.18, 2.55, "（两种都对，选省事的）", fs=10.2, color=C_GREY)

    # 右：含受控源
    arrow(ax, (8.60, 4.05), (9.18, 4.05), color=C_GREY, lw=1.5, ms=12)
    txt(ax, 8.89, 4.36, "含", fs=11.5, color=C_HL)
    box(ax, 10.82, 3.05, 3.22, 1.60, fc="#fdf3f3", ec=C_HL)
    txt(ax, 10.82, 3.46, "只能外加电源法", fs=11.8, color=C_MAIN)
    txt(ax, 10.82, 2.98, "受控源必须保留", fs=11.8, color=C_HL)
    txt(ax, 10.82, 2.55, "不能当短路或开路删掉", fs=10.2, color=C_GREY)

    # 汇合
    arrow(ax, (1.18, 2.22), (1.18, 1.74), color=C_GREY, lw=1.5, ms=12)
    arrow(ax, (10.82, 2.22), (10.82, 1.74), color=C_GREY, lw=1.5, ms=12)
    arrow(ax, (1.18, 1.74), (10.82, 1.74), color=C_GREY, lw=1.5, ms=1)
    arrow(ax, (6.0, 1.74), (6.0, 1.32), color=C_GREY, lw=1.5, ms=12)

    box(ax, 6.0, 0.84, 8.8, 0.86, fc="#eef2f7", ec="#475569")
    txt(ax, 6.0, 0.84,
        "最后都用 $R_{eq}=u_{oc}/i_{sc}$ 交叉校验（$i_{sc}\\neq 0$ 时）",
        fs=12.5, color=C_MAIN)

    out(fig, "fig18_flow")


if __name__ == "__main__":
    fig18()
