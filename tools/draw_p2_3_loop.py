# -*- coding: utf-8 -*-
"""画「题图 2-3」用电源等效变换化简后的单回路等效电路。

化简链条（两处电源等效变换 + 三处合并）：

  ① 左侧：8V 串 R1=4Ω  →  2A 并 4Ω；再与 R2=4Ω 并联 → 2A 并 2Ω
             →  4V 串 2Ω（+ 朝节点 A）
  ② 右下：10V 串 R4=2Ω  →  5A 并 2Ω（电流由地流入 B）
  ③ 右侧：R5=2Ω 与 2A 理想电流源串联，该支路电流被钳定为 2A（B→地），
     电阻值不影响电流 → 该支路等效为 2A 电流源（B→地）
  ④ 节点 B：5A 入 − 2A 出 = 3A 入，与 2Ω 并联 → 6V 串 2Ω（+ 朝节点 B）
  ⑤ 全电路只剩一个回路：4V — 2Ω — A — 1Ω — B — 2Ω — 6V
     KVL：4 − 2I − 1I − 2I − 6 = 0  →  I = −0.4 A

用法： python tools\\draw_p2_3_loop.py
输出： out\\p2_3_等效回路.png / .svg
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DengXian"]
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out", "p2_3")

LW = 1.9
RS_L, RS_W = 0.92, 0.32
SRC_R = 0.40
DOT_R = 0.07
FS = 15
X0, XR = 0.0, 8.0        # 左竖线 / 右竖线
YT, YB = 4.0, 0.0        # 上轨 / 下轨
XA, XB = 3.0, 6.0        # 节点 A / B


def wire(ax, *pts, lw=LW):
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color="black", lw=lw,
            solid_capstyle="round", solid_joinstyle="round", zorder=2)


def res_h(ax, cx, cy, label, dy=0.44):
    ax.add_patch(Rectangle((cx - RS_L / 2, cy - RS_W / 2), RS_L, RS_W,
                           fill=False, ec="black", lw=LW, zorder=3))
    ax.text(cx, cy + dy, label, ha="center", va="bottom", fontsize=FS)


def src_v(ax, cx, cy, label, sub=None):
    ax.add_patch(Circle((cx, cy), SRC_R, fill=False, ec="black", lw=LW, zorder=3))
    s, mx = 0.115, cx - 0.30
    for is_plus, yy in ((True, cy + SRC_R + 0.24), (False, cy - SRC_R - 0.24)):
        ax.plot([mx - s, mx + s], [yy, yy], color="black", lw=LW, zorder=4)
        if is_plus:
            ax.plot([mx, mx], [yy - s, yy + s], color="black", lw=LW, zorder=4)
    ax.text(cx - 0.58, cy, label, ha="right", va="center", fontsize=FS)
    if sub:
        ax.text(cx, cy - SRC_R - 0.95, sub, ha="center", va="top",
                fontsize=FS - 4, color="#1a5fb4")


def dot(ax, x, y):
    ax.add_patch(Circle((x, y), DOT_R, fc="black", ec="black", zorder=5))


def dir_arrow(ax, x, y, toward_right=True):
    d = 1 if toward_right else -1
    ax.plot([x - 0.34 * d, x + 0.10 * d], [y, y], color="black", lw=1.5, zorder=6)
    ax.add_patch(Polygon([(x + 0.20 * d, y), (x - 0.02 * d, y + 0.135),
                          (x - 0.02 * d, y - 0.135)],
                         closed=True, fc="black", ec="black", lw=0.4, zorder=6))


def main():
    fig, ax = plt.subplots(figsize=(10.2, 5.6))

    # 上轨
    wire(ax, (X0, YT), (1.5 - RS_L / 2, YT))
    wire(ax, (1.5 + RS_L / 2, YT), (XA, YT))
    wire(ax, (XA, YT), (4.5 - RS_L / 2, YT))
    wire(ax, (4.5 + RS_L / 2, YT), (XB, YT))
    wire(ax, (XB, YT), (7.0 - RS_L / 2, YT))
    wire(ax, (7.0 + RS_L / 2, YT), (XR, YT))
    res_h(ax, 1.5, YT, r"$2\,\Omega$")
    res_h(ax, 4.5, YT, r"$1\,\Omega$")
    res_h(ax, 7.0, YT, r"$2\,\Omega$")

    # 左竖支路：4V
    wire(ax, (X0, YT), (X0, 2.0 + SRC_R))
    wire(ax, (X0, 2.0 - SRC_R), (X0, YB))
    src_v(ax, X0, 2.0, r"$4\,\mathrm{V}$", "（8 V 与 4Ω∥4Ω 等效）")

    # 右竖支路：6V
    wire(ax, (XR, YT), (XR, 2.0 + SRC_R))
    wire(ax, (XR, 2.0 - SRC_R), (XR, YB))
    src_v(ax, XR, 2.0, r"$6\,\mathrm{V}$", "（10 V 支路与 2A 支路合并）")

    # 下轨
    wire(ax, (X0, YB), (XR, YB))

    # 节点与参考方向
    dot(ax, XA, YT); dot(ax, XB, YT)
    ax.text(XA - 0.16, YT + 0.14, r"$A$", ha="right", va="bottom",
            fontsize=FS + 1, color="#1a5fb4")
    ax.text(XB + 0.16, YT + 0.14, r"$B$", ha="left", va="bottom",
            fontsize=FS + 1, color="#1a5fb4")
    ax.text(3.75, YT + 0.44, r"$I$", ha="center", va="bottom", fontsize=FS + 2)
    dir_arrow(ax, 4.05, YT)

    # 结论
    ax.text((X0 + XR) / 2, YB - 0.95,
            r"$KVL:\ 4-2I-1I-2I-6=0\ \Rightarrow\ I=-\dfrac{2}{5}\ \mathrm{A}=-0.4\ \mathrm{A}$"
            "\n实际由 B 流向 A（与图中箭头相反）",
            ha="center", va="top", fontsize=FS - 1, color="#c01c28", linespacing=1.7)

    ax.set_xlim(X0 - 2.4, XR + 2.4)
    ax.set_ylim(YB - 1.95, YT + 1.05)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout(pad=0.2)
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "svg"):
        p = os.path.join(OUT, f"p2_3_等效回路.{ext}")
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
        print("saved", p, os.path.getsize(p), "bytes")
    plt.close(fig)


if __name__ == "__main__":
    main()
