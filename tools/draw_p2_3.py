# -*- coding: utf-8 -*-
"""按教材原图样式重绘「题图 2-3」电路，并输出带解答标注的版本。

几何坐标直接取自原扫描图的像素测量（见 _q/ 下的放大图与暗像素统计），
换算比例：x_px 136→0, 608→12；y_px 618→0, 316→6。

用法：
    python tools\\draw_p2_3.py
输出：
    out\\p2_3_题图.png / .svg         原图样式的干净重绘
    out\\p2_3_解答.png / .svg         同一张图 + 节点电压与结果标注
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle

# 中文注释需要 CJK 字体；公式（$...$）仍走 mathtext。
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DengXian"]
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out", "p2_3")

# ---- 版面（数据单位）------------------------------------------------------
YBOT, YTOP = 0.0, 6.0          # 下轨 / 上轨
X0, XA, XB, X2 = 0.0, 4.0, 8.0, 12.0
LW = 1.9                       # 导线线宽
RS_L, RS_W = 0.92, 0.34        # 电阻箱 长/宽
SRC_R = 0.42                   # 电源圆半径
DOT_R = 0.075                  # 结点实心圆
FS = 15                        # 标注字号


# ---- 基本图元 -------------------------------------------------------------
def wire(ax, *pts, lw=LW):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color="black", lw=lw, solid_capstyle="round",
            solid_joinstyle="round", zorder=2)


def res_h(ax, cx, cy, label, lab_dy=0.52):
    """水平电阻（空心矩形），接线从左右两端引出由调用者画。"""
    ax.add_patch(Rectangle((cx - RS_L / 2, cy - RS_W / 2), RS_L, RS_W,
                           fill=False, ec="black", lw=LW, zorder=3))
    ax.text(cx, cy + lab_dy, label, ha="center", va="bottom", fontsize=FS)


def res_v(ax, cx, cy, label, lab_dx=-0.62, lab_ha="right"):
    ax.add_patch(Rectangle((cx - RS_W / 2, cy - RS_L / 2), RS_W, RS_L,
                           fill=False, ec="black", lw=LW, zorder=3))
    ax.text(cx + lab_dx, cy, label, ha=lab_ha, va="center", fontsize=FS)


def src_v(ax, cx, cy, plus_up=True):
    """竖直放置的独立电压源：圆 + 上下两个极性符号。

    极性符号画在导线**左侧偏置**处（不压在导线上），否则横杠压在竖导线上会
    在视觉上与「+」混淆。
    """
    ax.add_patch(Circle((cx, cy), SRC_R, fill=False, ec="black", lw=LW, zorder=3))
    s = 0.115
    mx = cx - 0.30                      # 极性符号的水平偏置
    for is_plus, yy in ((plus_up, cy + SRC_R + 0.24), (not plus_up, cy - SRC_R - 0.24)):
        ax.plot([mx - s, mx + s], [yy, yy], color="black", lw=LW, zorder=4)
        if is_plus:
            ax.plot([mx, mx], [yy - s, yy + s], color="black", lw=LW, zorder=4)


def isrc_v(ax, cx, cy, label, arrow_down=True):
    """竖直放置的独立电流源：圆内一条水平直径 + 引线上的实心三角箭头。"""
    ax.add_patch(Circle((cx, cy), SRC_R, fill=False, ec="black", lw=LW, zorder=3))
    ax.plot([cx - SRC_R, cx + SRC_R], [cy, cy], color="black", lw=LW, zorder=3)
    # 箭头画在圆下方的引线上，表示该支路电流方向（与教学图一致）
    y_at = cy - SRC_R - 0.50
    h, w = 0.28, 0.10
    if arrow_down:
        tri = [(cx - w, y_at + h), (cx + w, y_at + h), (cx, y_at)]
    else:
        tri = [(cx - w, y_at), (cx + w, y_at), (cx, y_at + h)]
    ax.add_patch(Polygon(tri, closed=True, fc="black", ec="black", lw=0.5, zorder=5))
    ax.text(cx - 0.58, cy - 0.24, label, ha="right", va="center", fontsize=FS)


def dot(ax, x, y):
    ax.add_patch(Circle((x, y), DOT_R, fc="black", ec="black", zorder=5))


def dir_arrow(ax, x, y, dx=0.55):
    """导线上的电流参考方向小箭头（水平向右）。"""
    h = dx / 2
    ax.add_patch(Polygon([(x - 0.32, y), (x - 0.32 - 0.26 * (1 if dx > 0 else -1), y + 0.13),
                          (x - 0.32 - 0.26 * (1 if dx > 0 else -1), y - 0.13)],
                         closed=True, fc="black", ec="black", lw=0.4, zorder=6))
    ax.plot([x - 0.58, x + 0.06], [y, y], color="black", lw=1.3, zorder=6)


# ---- 主体 -----------------------------------------------------------------
def draw_base(ax):
    """画电路本体（所有元件 + 导线 + 结点）。"""
    XR1, XR3, XR5 = 1.7, 6.0, 10.0        # 三个水平电阻的中心

    # 上轨：从左到右被三个水平电阻截断
    wire(ax, (X0, YTOP), (XR1 - RS_L / 2, YTOP))
    wire(ax, (XR1 + RS_L / 2, YTOP), (XA, YTOP))
    wire(ax, (XA, YTOP), (XR3 - RS_L / 2, YTOP))
    wire(ax, (XR3 + RS_L / 2, YTOP), (XB, YTOP))
    wire(ax, (XB, YTOP), (XR5 - RS_L / 2, YTOP))
    wire(ax, (XR5 + RS_L / 2, YTOP), (X2, YTOP))

    res_h(ax, XR1, YTOP, r"$4\,\Omega$")
    res_h(ax, XR3, YTOP, r"$1\,\Omega$")
    res_h(ax, XR5, YTOP, r"$2\,\Omega$")

    # 左支路：8V 源
    wire(ax, (X0, YTOP), (X0, 3.0 + SRC_R))
    wire(ax, (X0, 3.0 - SRC_R), (X0, YBOT))
    src_v(ax, X0, 3.0, plus_up=True)
    ax.text(X0 - 0.60, 3.0, r"$8\,\mathrm{V}$", ha="right", va="center", fontsize=FS)

    # A 点竖支路：4Ω 到地
    wire(ax, (XA, YTOP), (XA, 4.1 + RS_L / 2))
    wire(ax, (XA, 4.1 - RS_L / 2), (XA, YBOT))
    res_v(ax, XA, 4.1, r"$4\,\Omega$")

    # 1Ω（A—B）上的电流参考方向 I
    ax.text(4.65, YTOP + 0.44, r"$I$", ha="center", va="bottom", fontsize=FS + 2)
    dir_arrow(ax, 5.35, YTOP)

    # B 点竖支路：2Ω + 10V 源到地
    wire(ax, (XB, YTOP), (XB, 4.1 + RS_L / 2))
    wire(ax, (XB, 4.1 - RS_L / 2), (XB, 1.95 + SRC_R))
    wire(ax, (XB, 1.95 - SRC_R), (XB, YBOT))
    res_v(ax, XB, 4.1, r"$2\,\Omega$")
    src_v(ax, XB, 1.95, plus_up=True)
    ax.text(XB - 0.60, 1.95, r"$10\,\mathrm{V}$", ha="right", va="center", fontsize=FS)

    # 右侧竖支路：2A 电流源到地
    wire(ax, (X2, YTOP), (X2, 3.2 + SRC_R))
    wire(ax, (X2, 3.2 - SRC_R - 0.50), (X2, YBOT))
    isrc_v(ax, X2, 3.2, r"$2\,\mathrm{A}$", arrow_down=True)

    # 下轨
    wire(ax, (X0, YBOT), (X2, YBOT))

    # 结点
    dot(ax, XA, YTOP); dot(ax, XB, YTOP)
    dot(ax, XA, YBOT); dot(ax, XB, YBOT)


def make(annotate: bool, path_stem: str):
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    draw_base(ax)
    if annotate:
        # 节点名贴在结点左侧，避开 1Ω 上方的 I 标注
        ax.text(XA - 0.18, YTOP + 0.16, r"$A$", ha="right", va="bottom",
                fontsize=FS + 1, color="#1a5fb4")
        ax.text(XB + 0.18, YTOP + 0.16, r"$B$", ha="left", va="bottom",
                fontsize=FS + 1, color="#1a5fb4")
        # 节点电压贴在各自竖支路底部附近
        ax.text(XA + 0.22, YBOT + 0.30, r"$4.8\ \mathrm{V}$", ha="left", va="bottom",
                fontsize=FS - 2, color="#1a5fb4")
        ax.text(XB + 0.22, YBOT + 0.30, r"$5.2\ \mathrm{V}$", ha="left", va="bottom",
                fontsize=FS - 2, color="#1a5fb4")
        # 答案放在图下方空白处（不画引线，避免与地线混淆）
        ax.text(6.0, YBOT - 0.72,
                r"$I=-\dfrac{2}{5}\ \mathrm{A}=-0.4\ \mathrm{A}$" "\n"
                "实际由 B 流向 A（与图中箭头相反）",
                ha="center", va="top", fontsize=FS - 1, color="#c01c28",
                linespacing=1.7)

    ax.set_xlim(X0 - 1.9, X2 + 1.2)
    ax.set_ylim(YBOT - (1.75 if annotate else 0.55), YTOP + 1.05)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout(pad=0.2)
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "svg"):
        p = os.path.join(OUT, f"{path_stem}.{ext}")
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
        print("saved", p, os.path.getsize(p), "bytes")
    plt.close(fig)


if __name__ == "__main__":
    make(False, "p2_3_题图")
    make(True, "p2_3_解答")
