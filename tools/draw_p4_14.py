# -*- coding: utf-8 -*-
"""按教材原图样式重绘「题图 4-14」电路，并输出带解答标注的版本。

几何坐标取自原扫描图的像素测量（`_q4/whole.png` 及暗像素统计）：
  竖向支路 x_px：133(6A) / 192(4Ω+16V) / 348(6Ω) / 465(R_L)
  横向         y_px：342(下轨) / 168(上轨)
换算比例约 33.9 px/单位，取 X0=0, X1=2.0, XCC=3.9, XB=6.35, XV6=7.9, XC=9.8；
YBOT=0, YTOP=6。

用法：
    python tools\\draw_p4_14.py
输出：
    out\\p4_14_题图.png / .svg          原图样式的干净重绘
    out\\p4_14_解答.png / .svg          同一张图 + 节点电压与结果标注
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle

# 中文标注需要 CJK 字体；公式（$...$）仍走 mathtext。
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DengXian"]
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out", "p4_14")

# ---- 版面（数据单位）------------------------------------------------------
YBOT, YTOP = 0.0, 6.0
X0, X1, XCC, XB, XV6, XC = 0.0, 2.0, 3.9, 6.35, 7.9, 9.8
LW = 1.9
RS_L, RS_W = 0.92, 0.34        # 电阻筒 长/宽
SRC_R = 0.42                   # 电源圆半径
DOT_R = 0.075                  # 结点实心点
FS = 15                        # 标注字号
Y_S = 3.10                     # 6A 电流源圆心高度
Y_16V = 2.31                   # 16V 电压源圆心高度
Y_R4 = 5.30                    # 4Ω 电阻体中心
Y_R6 = 3.34                    # 6Ω 电阻体中心
Y_RL = 3.34                    # R_L 电阻体中心


# ---- 基本图元 -------------------------------------------------------------
def wire(ax, *pts, lw=LW):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color="black", lw=lw, solid_capstyle="round",
            solid_joinstyle="round", zorder=2)


def res_v(ax, cx, cy, label, lab_dx=-0.62, lab_ha="right"):
    """竖直电阻（空心矩形）。"""
    ax.add_patch(Rectangle((cx - RS_W / 2, cy - RS_L / 2), RS_W, RS_L,
                           fill=False, ec="black", lw=LW, zorder=3))
    ax.text(cx + lab_dx, cy, label, ha=lab_ha, va="center", fontsize=FS)


def res_v_var(ax, cx, cy, label):
    """竖直可变电阻：矩形 + 斜穿箭头（滑动端）。"""
    ax.add_patch(Rectangle((cx - RS_W / 2, cy - RS_L / 2), RS_W, RS_L,
                           fill=False, ec="black", lw=LW, zorder=3))
    # 斜箭头：自左下指向右上，穿过矩形
    x1, y1 = cx - 0.72, cy - 0.62
    x2, y2 = cx + 0.46, cy + 0.66
    ax.plot([x1, x2], [y1, y2], color="black", lw=1.5, zorder=6)
    # 箭头头部
    ax.add_patch(Polygon([(x2 + 0.16, y2 + 0.05),
                          (x2 - 0.20, y2 + 0.10),
                          (x2 - 0.03, y2 - 0.24)],
                         closed=True, fc="black", ec="black", lw=0.4, zorder=7))
    ax.text(cx + 0.62, cy, label, ha="left", va="center", fontsize=FS)


def src_v(ax, cx, cy, plus_up=True, label=None, lab_dx=-0.60, lab_dy=0.0,
          lab_ha="right"):
    """竖直独立电压源：圆 + 圆内**竖直**直径（教材画法）+ 上下极性符号。

    极性符号画在导线**左侧偏置**处（不压在导线上），否则横杠压在竖导线上会
    在视觉上与「+」混淆。
    """
    ax.add_patch(Circle((cx, cy), SRC_R, fill=False, ec="black", lw=LW, zorder=3))
    # 沿支路方向的直径线（教材用「圆内一条线」区分电压源/电流源）
    ax.plot([cx, cx], [cy - SRC_R, cy + SRC_R], color="black", lw=LW, zorder=3)
    s = 0.115
    mx = cx - 0.30
    for is_plus, yy in ((plus_up, cy + SRC_R + 0.24), (not plus_up, cy - SRC_R - 0.24)):
        ax.plot([mx - s, mx + s], [yy, yy], color="black", lw=LW, zorder=4)
        if is_plus:
            ax.plot([mx, mx], [yy - s, yy + s], color="black", lw=LW, zorder=4)
    if label:
        ax.text(cx + lab_dx, cy + lab_dy, label, ha=lab_ha, va="center", fontsize=FS)


def isrc_v(ax, cx, cy, label, arrow_up=True):
    """竖直独立电流源：圆内一条水平直径 + 引线上的实心三角箭头。"""
    ax.add_patch(Circle((cx, cy), SRC_R, fill=False, ec="black", lw=LW, zorder=3))
    ax.plot([cx - SRC_R, cx + SRC_R], [cy, cy], color="black", lw=LW, zorder=3)
    h, w = 0.30, 0.105
    if arrow_up:
        y_base = cy + SRC_R + 0.22
        tri = [(cx - w, y_base), (cx + w, y_base), (cx, y_base + h)]
    else:
        y_base = cy - SRC_R - 0.22
        tri = [(cx - w, y_base), (cx + w, y_base), (cx, y_base - h)]
    ax.add_patch(Polygon(tri, closed=True, fc="black", ec="black", lw=0.5, zorder=5))
    ax.text(cx - 0.60, cy - 0.20, label, ha="right", va="center", fontsize=FS)


def src_h(ax, cx, cy, plus_right=True, label=None, lab_dy=0.62):
    """水平独立电压源：圆 + 圆内**水平**直径 + 左右极性符号（画在圆上方）。"""
    ax.add_patch(Circle((cx, cy), SRC_R, fill=False, ec="black", lw=LW, zorder=3))
    ax.plot([cx - SRC_R, cx + SRC_R], [cy, cy], color="black", lw=LW, zorder=3)
    s = 0.115
    my = cy + SRC_R + 0.26               # 极性符号的竖直偏置（画在圆上方）
    for is_plus, xx in ((plus_right, cx + SRC_R + 0.26), (not plus_right, cx - SRC_R - 0.26)):
        ax.plot([xx - s, xx + s], [my, my], color="black", lw=LW, zorder=4)
        if is_plus:
            ax.plot([xx, xx], [my - s, my + s], color="black", lw=LW, zorder=4)
    if label:
        ax.text(cx - 0.10, cy + lab_dy + 0.30, label, ha="center", va="bottom", fontsize=FS)


def ccvs_h(ax, cx, cy, label, minus_left=True):
    """水平受控电压源：菱形（四角在轴上，内含一条水平线）+ 左右极性符号。"""
    hw, hh = 0.62, 0.44
    tri = [(cx - hw, cy), (cx, cy + hh), (cx + hw, cy), (cx, cy - hh)]
    ax.add_patch(Polygon(tri, closed=True, fill=False, ec="black", lw=LW, zorder=3))
    # 菱形内的水平线（教材画法，与独立电压源的「圆内线」同源）
    ax.plot([cx - hw, cx + hw], [cy, cy], color="black", lw=LW, zorder=3)
    my = cy + hh + 0.20
    s = 0.115
    xm = cx - hw - 0.28
    xp = cx + hw + 0.28
    # 负号
    ax.plot([xm - s, xm + s], [my, my], color="black", lw=LW, zorder=4)
    # 正号
    ax.plot([xp - s, xp + s], [my, my], color="black", lw=LW, zorder=4)
    ax.plot([xp, xp], [my - s, my + s], color="black", lw=LW, zorder=4)
    ax.text(cx - 0.06, cy + hh + 0.52, label, ha="center", va="bottom", fontsize=FS)


def dot(ax, x, y):
    ax.add_patch(Circle((x, y), DOT_R, fc="black", ec="black", zorder=5))


def arrow_down_on_wire(ax, x, y_top, label, dx=-0.42):
    """导线上竖直向下的电流参考方向箭头（配 I₁）。"""
    h, w = 0.30, 0.10
    ax.add_patch(Polygon([(x - w, y_top), (x + w, y_top), (x, y_top - h)],
                         closed=True, fc="black", ec="black", lw=0.5, zorder=6))
    ax.text(x + dx, y_top - 0.06, label, ha="right", va="top", fontsize=FS)


# ---- 主体 -----------------------------------------------------------------
def draw_base(ax):
    """画电路本体（所有元件 + 导线 + 结点）。"""
    # 上轨：左端 → CCVS 左端；CCVS 右端 → 6V 左端；6V 右端 → 右上角
    wire(ax, (X0, YTOP), (XCC - 0.62, YTOP))
    wire(ax, (XCC + 0.62, YTOP), (XV6 - SRC_R, YTOP))
    wire(ax, (XV6 + SRC_R, YTOP), (XC, YTOP))

    # 左竖支路：6A 电流源（箭头向上）
    wire(ax, (X0, YTOP), (X0, Y_S + SRC_R + 0.52))
    wire(ax, (X0, Y_S - SRC_R), (X0, YBOT))
    isrc_v(ax, X0, Y_S, r"$6\,\mathrm{A}$", arrow_up=True)

    # 第二竖支路：4Ω + 16V（+ 在上）
    wire(ax, (X1, YTOP), (X1, Y_R4 + RS_L / 2))
    wire(ax, (X1, Y_R4 - RS_L / 2), (X1, Y_16V + SRC_R))
    wire(ax, (X1, Y_16V - SRC_R), (X1, YBOT))
    res_v(ax, X1, Y_R4, r"$4\,\Omega$", lab_dx=0.60, lab_ha="left")
    # 教材原图中「16V」标在圆的右侧
    src_v(ax, X1, Y_16V, plus_up=True, label=r"$16\,\mathrm{V}$",
          lab_dx=0.56, lab_dy=0.0, lab_ha="left")

    # 受控电压源 2I₁（− 左 + 右）
    ccvs_h(ax, XCC, YTOP, r"$2I_1$", minus_left=True)

    # 第三竖支路：6Ω（I₁ 向下）
    wire(ax, (XB, YTOP), (XB, Y_R6 + RS_L / 2))
    wire(ax, (XB, Y_R6 - RS_L / 2), (XB, YBOT))
    res_v(ax, XB, Y_R6, r"$6\,\Omega$", lab_dx=-0.62, lab_ha="right")
    arrow_down_on_wire(ax, XB, YTOP - 0.30, r"$I_1$")

    # 6V 电压源（水平，− 左 + 右）
    src_h(ax, XV6, YTOP, plus_right=True, label=r"$6\,\mathrm{V}$")

    # 右侧竖支路：可变 R_L
    wire(ax, (XC, YTOP), (XC, Y_RL + RS_L / 2))
    wire(ax, (XC, Y_RL - RS_L / 2), (XC, YBOT))
    res_v_var(ax, XC, Y_RL, r"$R_L$")

    # 下轨
    wire(ax, (X0, YBOT), (XC, YBOT))

    # 结点（原图上有实心点的三处）
    dot(ax, X1, YTOP); dot(ax, XB, YTOP); dot(ax, XC, YTOP)
    dot(ax, X1, YBOT); dot(ax, XB, YBOT); dot(ax, XC, YBOT)


def make(annotate: bool, path_stem: str):
    fig, ax = plt.subplots(figsize=(9.8, 5.2))
    draw_base(ax)
    if annotate:
        # 节点电压不画在图上：上轨已有「2I₁」「6 V」标注，任何插入位置都会压字。
        # 改为在图下方统一列出，并用 V₁/V₃/V₄ 与正文一一对应。
        ax.text((X0 + XC) / 2, YBOT - 0.70,
                r"$R_L$ 断开时：$V_1=20\ \mathrm{V},\ \ V_3=30\ \mathrm{V},\ \ V_4=36\ \mathrm{V}$",
                ha="center", va="top", fontsize=FS - 2, color="#1a5fb4")
        ax.text((X0 + XC) / 2, YBOT - 1.22,
                r"$U_{\mathrm{oc}}=V_4=36\ \mathrm{V},\qquad R_{\mathrm{eq}}=3\ \Omega$",
                ha="center", va="top", fontsize=FS - 1, color="#c01c28")
        ax.text((X0 + XC) / 2, YBOT - 1.80,
                r"$R_L=R_{\mathrm{eq}}=3\ \Omega\ \ \Rightarrow\ \ P_{\max}=\dfrac{U_{\mathrm{oc}}^{2}}{4R_{\mathrm{eq}}}=108\ \mathrm{W}$",
                ha="center", va="top", fontsize=FS - 1, color="#c01c28")

    ax.set_xlim(X0 - 1.85, XC + 1.55)
    ax.set_ylim(YBOT - (2.35 if annotate else 0.55), YTOP + 1.15)
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
    make(False, "p4_14_题图")
    make(True, "p4_14_解答")
