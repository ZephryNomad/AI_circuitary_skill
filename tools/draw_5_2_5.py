# -*- coding: utf-8 -*-
"""按教材原图样式重绘「题图 5.2.5」——分压式偏置共射放大电路。

原图细节（据题图三倍放大裁片逐项核对；裁片是本地一次性取证用，未纳入仓库）
    · V_CC 空心端子在上轨右端；上轨向左延伸到 R_b1 顶端上方
    · R_b1：上轨 → 基极节点，位号标在电阻体左侧
    · I₁：竖箭头画在 R_b1 右侧空白处，朝下，标签在箭头右边
    · 基极节点（实心点）：C_b1 从左侧引入，I_B 箭头向右指向基极
    · C_b1：两块竖板，**「+」在右板**（靠基极一侧）；v_i 空心端子在左
    · R_b2：基极节点 → 底轨，位号标在电阻体右侧
    · R_c：上轨 → 集电极，位号在左侧
    · 集电极节点（实心点）：向右经 C_b2（**「+」在左板**）到 v_o 空心端子
    · T：基极竖条 + 集电极斜线 + 发射极斜线（发射极带朝外实心箭头）
    · R_e：发射极 → 底轨，位号在右侧
    · 底轨：R_b2 底端 → R_e 底端，右端下方画接地符号

用法
    python tools/draw_5_2_5.py
输出
    out/p5_2_5/p5_2_5_题图.png / .svg      干净重绘（只有元件与参考方向）
    out/p5_2_5/p5_2_5_解答.png / .svg      同一张图 + 工作点与设计值
"""
from __future__ import annotations

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DengXian"]
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out", "p5_2_5")

# ---- 版面（数据单位）-------------------------------------------------------
YBOT, YTOP = 0.0, 6.0
X_B1 = 0.0           # R_b1 / R_b2 / 基极节点所在竖列
X_T = 4.6            # R_c / 集电极 / 发射极 / R_e 所在竖列
YB = 3.00            # 基极节点高度
YC = 4.10            # 集电极节点高度（C_b2 引出点）
Y_RC = 4.95          # R_c 电阻体中心
Y_RE = 0.95          # R_e 电阻体中心
Y_RB1 = 4.60         # R_b1 电阻体中心
Y_RB2 = 1.45         # R_b2 电阻体中心
X_VCC = 6.30         # V_CC 空心端子
X_VO = 8.55          # v_o 空心端子
X_VI = -3.20         # v_i 空心端子
X_CB2 = 6.65         # C_b2 中心
X_CB1 = -1.80        # C_b1 中心
X_BAR = X_T - 0.52   # 晶体管基极竖条

LW = 1.9
RS_L, RS_W = 1.00, 0.36      # 电阻体 长 / 宽
DOT_R = 0.075
TERM_R = 0.095
FS = 15
PLUS_S = 0.105               # 「+」符号半长


# ---- 图元 ------------------------------------------------------------------
def wire(ax, *pts, lw=LW):
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color="black", lw=lw,
            solid_capstyle="round", solid_joinstyle="round", zorder=2)


def res_v(ax, cx, cy, label, lab_dx=-0.55, lab_ha="right"):
    """竖直电阻：空心矩形 + 位号。"""
    ax.add_patch(Rectangle((cx - RS_W / 2, cy - RS_L / 2), RS_W, RS_L,
                           fill=False, ec="black", lw=LW, zorder=3))
    ax.text(cx + lab_dx, cy, label, ha=lab_ha, va="center", fontsize=FS,
            zorder=6)


def plus_sign(ax, x, y, s=PLUS_S):
    ax.plot([x - s, x + s], [y, y], color="black", lw=LW - 0.2, zorder=6)
    ax.plot([x, x], [y - s, y + s], color="black", lw=LW - 0.2, zorder=6)


def cap_h(ax, cx, cy, label, plus_side="right", gap=0.36, plate=0.44):
    """水平电容：两块竖直平板。plus_side 指定「+」标在哪一侧板旁。"""
    g = gap / 2
    for xx in (cx - g, cx + g):
        ax.plot([xx, xx], [cy - plate / 2, cy + plate / 2], color="black",
                lw=LW, zorder=3)
    ax.text(cx, cy + plate / 2 + 0.14, label, ha="center", va="bottom",
            fontsize=FS, zorder=6)
    if plus_side == "right":
        plus_sign(ax, cx + g + 0.26, cy + 0.20)
    elif plus_side == "left":
        plus_sign(ax, cx - g - 0.26, cy + 0.20)


def terminal(ax, x, y, label, ha="left", dx=0.30):
    """空心小圆端子 + 名字。"""
    ax.add_patch(Circle((x, y), TERM_R, fill=False, ec="black", lw=1.4,
                        zorder=4))
    ax.text(x + dx, y, label, ha=ha, va="center", fontsize=FS, zorder=6)


def dot(ax, x, y):
    ax.add_patch(Circle((x, y), DOT_R, fc="black", ec="black", zorder=5))


def gnd(ax, x, y_top, w=0.52, gap=0.13):
    """接地符号：三横线，长度递减。y_top 是接入点（导线末端）。"""
    wire(ax, (x, y_top), (x, y_top - 0.20))
    for i, ww in enumerate((w, w * 0.62, w * 0.28)):
        yy = y_top - 0.20 - i * gap
        ax.plot([x - ww / 2, x + ww / 2], [yy, yy], color="black", lw=LW,
                zorder=3)


def arrow_down(ax, x, y_top, label, lab_side="right", h=0.36):
    """竖向导线上朝下的电流参考箭头，标签默认在右侧。"""
    ax.add_patch(Polygon([(x - 0.115, y_top), (x + 0.115, y_top),
                          (x, y_top - h)], closed=True, fc="black",
                         ec="black", lw=0.5, zorder=6))
    if lab_side == "right":
        ax.text(x + 0.26, y_top - 0.06, label, ha="left", va="top",
                fontsize=FS, zorder=6)
    else:
        ax.text(x - 0.26, y_top - 0.06, label, ha="right", va="top",
                fontsize=FS, zorder=6)


def arrow_right(ax, x_tip, y, label, h=0.38):
    """水平导线上朝右的电流参考箭头，标签在箭头上方。"""
    ax.add_patch(Polygon([(x_tip, y), (x_tip - h, y + 0.115),
                          (x_tip - h, y - 0.115)], closed=True, fc="black",
                         ec="black", lw=0.5, zorder=6))
    ax.text(x_tip - h / 2, y + 0.24, label, ha="center", va="bottom",
            fontsize=FS, zorder=6)


def npn(ax, x_col, y_base, name="T"):
    """NPN 晶体管。返回 (集电极斜线终点 y, 发射极斜线终点 y)。"""
    yb = 0.38
    ax.plot([X_BAR, X_BAR], [y_base - yb, y_base + yb], color="black",
            lw=LW + 0.8, zorder=4)
    y_c_end = y_base + 0.78
    y_e_end = y_base - 0.78
    ax.plot([X_BAR, x_col], [y_base + 0.26, y_c_end], color="black", lw=LW,
            zorder=3)
    ax.plot([X_BAR, x_col], [y_base - 0.26, y_e_end], color="black", lw=LW,
            zorder=3)
    # 发射极箭头：沿斜线朝外（右下）
    p0 = np.array([X_BAR, y_base - 0.26])
    p1 = np.array([x_col, y_e_end])
    d = (p1 - p0) / np.linalg.norm(p1 - p0)
    n = np.array([-d[1], d[0]])
    tip = p0 + d * 0.44
    back = tip - d * 0.26
    ax.add_patch(Polygon([tip, back + n * 0.115, back - n * 0.115],
                         closed=True, fc="black", ec="black", lw=0.5, zorder=6))
    ax.text(x_col + 0.28, y_base, name, ha="left", va="center", fontsize=FS,
            zorder=6)
    return y_c_end, y_e_end


# ---- 主体 ------------------------------------------------------------------
def draw_base(ax):
    # 上轨：R_b1 顶端上方 → V_CC 端子；R_c 顶端接轨处有节点
    wire(ax, (X_B1, YTOP), (X_VCC, YTOP))
    terminal(ax, X_VCC, YTOP, r"$V_{\mathrm{CC}}$")
    dot(ax, X_T, YTOP)

    # R_b1：上轨 → 基极节点
    wire(ax, (X_B1, YTOP), (X_B1, Y_RB1 + RS_L / 2))
    wire(ax, (X_B1, Y_RB1 - RS_L / 2), (X_B1, YB))
    res_v(ax, X_B1, Y_RB1, r"$R_{\mathrm{b1}}$")

    # R_b2：基极节点 → 底轨
    wire(ax, (X_B1, YB), (X_B1, Y_RB2 + RS_L / 2))
    wire(ax, (X_B1, Y_RB2 - RS_L / 2), (X_B1, YBOT))
    res_v(ax, X_B1, Y_RB2, r"$R_{\mathrm{b2}}$", lab_dx=0.55, lab_ha="left")

    # 基极节点 + C_b1（+ 在右侧）+ v_i
    dot(ax, X_B1, YB)
    wire(ax, (X_CB1 + 0.18, YB), (X_B1, YB), (X_BAR, YB))
    wire(ax, (X_VI, YB), (X_CB1 - 0.18, YB))
    cap_h(ax, X_CB1, YB, r"$C_{\mathrm{b1}}$", plus_side="right")
    terminal(ax, X_VI, YB, r"$v_{\mathrm{i}}$", ha="right", dx=-0.30)

    # 晶体管
    y_c_end, y_e_end = npn(ax, X_T, YB)

    # 集电极：斜线端点 → 集电极节点 → R_c → 上轨
    wire(ax, (X_T, y_c_end), (X_T, Y_RC - RS_L / 2))
    wire(ax, (X_T, Y_RC + RS_L / 2), (X_T, YTOP))
    res_v(ax, X_T, Y_RC, r"$R_{c}$")

    # 集电极节点 + C_b2（+ 在左侧）+ v_o
    dot(ax, X_T, YC)
    wire(ax, (X_T, YC), (X_CB2 - 0.18, YC))
    cap_h(ax, X_CB2, YC, r"$C_{\mathrm{b2}}$", plus_side="left")
    wire(ax, (X_CB2 + 0.18, YC), (X_VO, YC))
    terminal(ax, X_VO, YC, r"$v_{\mathrm{o}}$")

    # 发射极：斜线端点 → R_e → 底轨
    wire(ax, (X_T, y_e_end), (X_T, Y_RE + RS_L / 2))
    wire(ax, (X_T, Y_RE - RS_L / 2), (X_T, YBOT))
    res_v(ax, X_T, Y_RE, r"$R_{e}$", lab_dx=0.55, lab_ha="left")

    # 底轨 + 接地符号（右端下方）
    wire(ax, (X_B1, YBOT), (X_T, YBOT))
    dot(ax, X_T, YBOT)
    gnd(ax, X_T, YBOT)

    # 参考方向：I₁ 在 R_b1 右侧朝下；I_B 指向基极
    arrow_down(ax, X_B1 + 0.30, Y_RB1 - 0.62, r"$I_1$")
    arrow_right(ax, X_BAR - 0.08, YB + 0.62, r"$I_{\mathrm{B}}$")


def make(annotate: bool, stem: str):
    fig, ax = plt.subplots(figsize=(8.6, 6.0))
    draw_base(ax)
    if annotate:
        # 图内一律不写计算结果：图上任何空位都会与 I₁/I_B/位号相撞（4-14 那次的教训）。
        # 全部数值与设计式集中放在图下方，分三行，蓝字=工作点，红字=设计结果。
        blue, red = "#1a5fb4", "#c01c28"
        cx = (X_VI + X_VO) / 2
        ax.text(cx, YBOT - 0.72,
                r"$I_B=10\ \mu\mathrm{A},\ \ I_1=100\ \mu\mathrm{A},\ \ "
                r"I_{R_{b2}}=90\ \mu\mathrm{A},\ \ I_{CQ}=1\ \mathrm{mA},\ \ "
                r"V_E=2.7\ \mathrm{V},\ \ V_B=3.4\ \mathrm{V},\ \ "
                r"V_{CEQ}=5\ \mathrm{V}$",
                ha="center", va="top", fontsize=FS - 3, color=blue)
        ax.text(cx, YBOT - 1.24,
                r"$R_e=V_E/I_E=2.7/1.01\approx 2.67\ \mathrm{k}\Omega"
                r"\ \Rightarrow\ 2.7\ \mathrm{k}\Omega$",
                ha="center", va="top", fontsize=FS - 1, color=red)
        ax.text(cx, YBOT - 1.92,
                r"$R_{b1}=(V_{\mathrm{CC}}-V_B)/I_1=(12-3.4)/0.1"
                r"=86\ \mathrm{k}\Omega$",
                ha="center", va="top", fontsize=FS - 1, color=red)
        ax.text(cx, YBOT - 2.60,
                r"$R_{b2}=V_B/(I_1-I_B)=3.4/0.09"
                r"\approx 37.8\ \mathrm{k}\Omega$",
                ha="center", va="top", fontsize=FS - 1, color=red)

    ax.set_xlim(X_VI - 0.95, X_VO + 1.20)
    ax.set_ylim(YBOT - (3.35 if annotate else 0.85), YTOP + 0.80)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout(pad=0.2)
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "svg"):
        p = os.path.join(OUT, "%s.%s" % (stem, ext))
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white")
        print("saved", p, os.path.getsize(p), "bytes")
    plt.close(fig)


def y_of_emitter():
    """发射极斜线终点高度（与 npn() 内部一致）。"""
    return YB - 0.78


if __name__ == "__main__":
    make(False, "p5_2_5_题图")
    make(True, "p5_2_5_解答")
