"""生成讲义全部电路图（例题/习题）与通用方法图。

布线原则：
  1. 严格正交或严格对称斜线，避免斜线交叉（交叉在原理图里等于误导）；
  2. 电桥采用"菱形"排布：源在左右两角，端口在上下两角；
  3. 标签用 figlib 的法线偏移 + 外侧对齐，避免压住符号。
运行：MPLCONFIGDIR=.mplcache PYTHONPATH=tools python -W ignore tools/make_circuits.py
"""
import matplotlib.pyplot as plt
from figlib import (canvas, out, txt, arrow, wire, term, res, src_v, src_i,
                    dep_v, dep_i, C_MAIN, C_HL, C_DEP, C_GREY, C_BOX, C_FILL,
                    C_EQ, FS)

V = r"\ \mathrm{V}"
A = r"\ \mathrm{A}"
O = r"\ \Omega"


def lab_r(name, val, unit=O):
    return "$%s=%s%s$" % (name, val, unit)


def dot(ax, p):
    ax.plot([p[0]], [p[1]], "o", ms=6.0, color=C_MAIN, zorder=6)


def port_vertical(ax, x, ytop, ybot, fs=14):
    """竖直端口：a 在上(+)、b 在下(−)。

    端口变量画在端钮右侧的空白区（+ / − / 箭头 / u），不再压到内部元件上。
    """
    txt(ax, x + 0.26, ytop + 0.26, "a", fs=fs, ha="left")
    txt(ax, x + 0.26, ybot - 0.26, "b", fs=fs, ha="left")
    xm = x + 0.95
    txt(ax, xm, ytop, "$+$", fs=15, color=C_HL)
    txt(ax, xm, ybot, "$-$", fs=15, color=C_HL)
    arrow(ax, (xm, ytop - 0.34), (xm, ybot + 0.34), color=C_HL, lw=1.5, ms=11)
    txt(ax, xm + 0.44, (ytop + ybot) / 2, "$u$", fs=16, color=C_HL)


def vmark(ax, x, ytop, ybot, label, color=C_DEP, fs=13, lx=-0.10):
    """竖直方向的电压参考标注：+ 在上、− 在下、中间带箭头，label 放左侧。"""
    txt(ax, x, ytop, "$+$", fs=fs, color=color)
    txt(ax, x, ybot, "$-$", fs=fs, color=color)
    arrow(ax, (x, ytop - 0.34), (x, ybot + 0.34), color=color, lw=1.4, ms=10)
    txt(ax, x - 0.50 + lx, (ytop + ybot) / 2, label, fs=fs, color=color)


# ================================================================= 例1
def ex1():
    fig, ax = canvas(8.4, 4.4, (-3.4, 8.2), (-1.0, 5.4))
    y1, y0 = 4.2, 0.0
    x1, x2, x3 = 0.0, 2.7, 5.2

    wire(ax, (x1, y1), (-1.5, y1))
    src_v(ax, (-1.5, y1), (-1.5, y0), lab_r("U_S", 12, V), side=-1, off=0.72)
    wire(ax, (-1.5, y0), (x1, y0))

    res(ax, (x1, y1), (x2, y1), lab_r("R_1", 2), off=0.46, side=1)
    res(ax, (x2, y1), (x2, y0), lab_r("R_2", 2), off=0.54, side=1)
    res(ax, (x2, y1), (x3, y1), lab_r("R_3", 2), off=0.46, side=1)
    res(ax, (x3, y1), (x3, y0), lab_r("R_4", 6), off=0.54, side=1)

    wire(ax, (x2, y0), (x1, y0))
    wire(ax, (x3, y0), (x2, y0))
    for p in [(x1, y1), (x1, y0), (x2, y1), (x2, y0), (x3, y1), (x3, y0)]:
        dot(ax, p)

    xa = 6.9
    wire(ax, (x3, y1), (xa, y1))
    wire(ax, (x3, y0), (xa, y0))
    port_vertical(ax, xa, y1, y0)
    out(fig, "fig06_ex1")


# ================================================================= 例2
def ex2():
    fig, ax = canvas(7.8, 4.4, (-3.0, 7.6), (-1.0, 5.4))
    y1, y0 = 4.0, 0.0
    xi, x1, x2 = 0.0, 2.4, 4.9

    src_i(ax, (xi, y0), (xi, y1), lab_r("I_S", 2, A), side=-1, off=0.72,
          to_p2=True)
    wire(ax, (xi, y1), (x1, y1))
    res(ax, (x1, y1), (x1, y0), lab_r("R_1", 3), off=0.54, side=1)
    res(ax, (x1, y1), (x2, y1), lab_r("R_2", 3), off=0.46, side=1)
    res(ax, (x2, y1), (x2, y0), lab_r("R_3", 12), off=0.56, side=1)

    wire(ax, (xi, y0), (x1, y0))
    wire(ax, (x1, y0), (x2, y0))
    for p in [(xi, y1), (xi, y0), (x1, y1), (x1, y0), (x2, y1), (x2, y0)]:
        dot(ax, p)

    xp = 6.5
    wire(ax, (x2, y1), (xp, y1))
    wire(ax, (x2, y0), (xp, y0))
    port_vertical(ax, xp, y1, y0)
    out(fig, "fig07_ex2")


# =========================================================== 例3 / 习题2
def bridge(name, r, us=12):
    """不平衡电桥。

    节点：1=左角(源+) 0=右角 2=上角(a) 3=下角(b)。
    源与回线全部绕到菱形外侧（左 -1.6、下 -1.7、右 6.8），
    四条臂的标签沿外法线外移，互不遮挡。
    """
    fig, ax = canvas(9.4, 6.6, (-4.2, 9.0), (-2.6, 7.2))
    nl, nr = (0.0, 2.8), (5.6, 2.8)
    nt, nb = (2.8, 5.5), (2.8, 0.1)
    xl, xr, ybus = -1.6, 6.8, -1.7

    # 源回路：左竖线下到底，底横线右行，右竖线上到右角
    wire(ax, nl, (xl, nl[1]))
    src_v(ax, (xl, nl[1]), (xl, ybus), lab_r("U_S", us, V), side=-1, off=0.76)
    wire(ax, (xl, ybus), (xr, ybus))
    wire(ax, (xr, ybus), (xr, nr[1]))
    wire(ax, (xr, nr[1]), nr)

    # 四条臂
    res(ax, nl, nt)
    res(ax, nt, nr)
    res(ax, nl, nb)
    res(ax, nb, nr)

    # 标签：沿外法线（左上、右上、左下、右下）
    for (pa, pb, rname, val, dx, dy, ha) in [
            (nl, nt, "R_1", r[0], -0.66, 0.62, "right"),
            (nt, nr, "R_2", r[1], 0.66, 0.62, "left"),
            (nl, nb, "R_3", r[2], -0.72, -0.50, "right"),
            (nb, nr, "R_4", r[3], 0.72, -0.50, "left")]:
        mx = (pa[0] + pb[0]) / 2 + dx
        my = (pa[1] + pb[1]) / 2 + dy
        txt(ax, mx, my, lab_r(rname, val), fs=FS, color=C_EQ, ha=ha)

    for p in [nl, nr, nt, nb]:
        dot(ax, p)

    # 端口（上 a+，下 b−），标注放在菱形中部的右侧空白
    xm = nt[0] + 0.75
    txt(ax, nt[0] + 0.26, nt[1] + 0.26, "a", fs=14, ha="left")
    txt(ax, nb[0] + 0.26, nb[1] - 0.30, "b", fs=14, ha="left")
    txt(ax, xm, nt[1] - 0.30, "$+$", fs=15, color=C_HL)
    txt(ax, xm, nb[1] + 0.30, "$-$", fs=15, color=C_HL)
    arrow(ax, (xm, nt[1] - 0.68), (xm, nb[1] + 0.68), color=C_HL, lw=1.5,
          ms=11)
    txt(ax, xm + 0.42, (nt[1] + nb[1]) / 2, "$u$", fs=16, color=C_HL)
    out(fig, name)


# =========================================================== 例4 / 习题3
def vcvs(name, mu, r, us=12):
    """含电压控制电压源（VCVS）：电阻全部正交摆放，无斜线交叉。"""
    fig, ax = canvas(9.6, 5.2, (-2.4, 10.4), (-1.2, 6.2))
    yt, ym, y0 = 5.0, 2.9, 0.0
    x1, x2, x3 = 0.0, 3.4, 6.2

    src_v(ax, (x1, yt), (x1, y0), lab_r("U_S", us, V), side=-1, off=0.74)
    res(ax, (x1, yt), (x2, yt), lab_r("R_1", r[0]), off=0.46, side=1)
    res(ax, (x2, yt), (x2, y0), lab_r("R_2", r[1]), off=0.56, side=1)
    res(ax, (x2, yt), (x3, yt), lab_r("R_3", r[2]), off=0.46, side=1)
    res(ax, (x3, yt), (x3, ym), lab_r("R_4", r[3]), off=0.56, side=1)
    dep_v(ax, (x3, ym), (x3, y0), "$%s u_2$" % mu, off=0.86, side=1)

    wire(ax, (x1, y0), (x2, y0))
    wire(ax, (x2, y0), (x3, y0))
    for p in [(x1, yt), (x1, y0), (x2, yt), (x2, y0), (x3, yt), (x3, ym),
              (x3, y0)]:
        dot(ax, p)

    # 控制量 u2 的参考方向（画在 R2 左侧）
    vmark(ax, x2 - 0.66, 4.62, 0.42, "$u_2$")

    xp = 8.1
    wire(ax, (x3, yt), (xp, yt))
    wire(ax, (x3, y0), (xp, y0))
    port_vertical(ax, xp, yt, y0)
    out(fig, name)


# ================================================================ 例5
def vccs(name, g, r, us=12):
    """含电压控制电流源（VCCS）。"""
    fig, ax = canvas(9.8, 5.4, (-2.4, 10.6), (-1.2, 6.2))
    yt, y0 = 5.0, 0.0
    x1, x2, x3 = 0.0, 3.4, 6.4

    src_v(ax, (x1, yt), (x1, y0), lab_r("U_S", us, V), side=-1, off=0.74)
    res(ax, (x1, yt), (x2, yt), lab_r("R_1", r[0]), off=0.46, side=1)
    res(ax, (x2, yt), (x2, y0), lab_r("R_2", r[1]), off=0.56, side=1)
    res(ax, (x2, yt), (x3, yt), lab_r("R_3", r[2]), off=0.46, side=1)
    dep_i(ax, (x3, yt), (x3, y0), "$%s u_2$" % g, off=0.90, side=1, to_p2=True)

    wire(ax, (x1, y0), (x2, y0))
    wire(ax, (x2, y0), (x3, y0))
    for p in [(x1, yt), (x1, y0), (x2, yt), (x2, y0), (x3, yt), (x3, y0)]:
        dot(ax, p)

    # 控制量 u2 的参考方向（画在 R2 左侧）
    vmark(ax, x2 - 0.66, 4.62, 0.42, "$u_2$")

    xp = 8.3
    wire(ax, (x3, yt), (xp, yt))
    wire(ax, (x3, y0), (xp, y0))
    port_vertical(ax, xp, yt, y0)
    out(fig, name)


# ============================================================== 习题1 梯形
def hw1():
    """三节梯形网络（series R1,R3,R5；shunt R2,R4,R6），端口在节点 4。"""
    fig, ax = canvas(10.4, 4.4, (-3.4, 11.0), (-1.2, 5.4))
    yt, y0 = 4.4, 0.0
    x1, x2, x3, x4 = 0.0, 2.6, 5.2, 7.6

    # 源：节点 1 -> 地
    src_v(ax, (x1, yt), (x1, y0), lab_r("U_S", 24, V), side=-1, off=0.74)
    # 顶栏三个串联电阻
    res(ax, (x1, yt), (x2, yt), lab_r("R_1", 3), off=0.46, side=1)
    res(ax, (x2, yt), (x3, yt), lab_r("R_3", 2), off=0.46, side=1)
    res(ax, (x3, yt), (x4, yt), lab_r("R_5", 3), off=0.46, side=1)
    # 三个对地分流电阻
    res(ax, (x2, yt), (x2, y0), lab_r("R_2", 6), off=0.54, side=-1)
    res(ax, (x3, yt), (x3, y0), lab_r("R_4", 12), off=0.60, side=-1)
    res(ax, (x4, yt), (x4, y0), lab_r("R_6", 6), off=0.56, side=1)

    wire(ax, (x1, y0), (x4, y0))
    for p in [(x1, yt), (x1, y0), (x2, yt), (x2, y0), (x3, yt), (x3, y0),
              (x4, yt), (x4, y0)]:
        dot(ax, p)

    xp = x4 + 1.5
    wire(ax, (x4, yt), (xp, yt))
    wire(ax, (x4, y0), (xp, y0))
    port_vertical(ax, xp, yt, y0)
    out(fig, "fig11_hw1")


# ================================================================ 方法图
def method():
    """三种测法并列图：每栏独立排版，栏宽 3.2，栏间留白 1.0。"""
    fig, ax = canvas(12.6, 4.0, (-0.8, 12.6), (-1.9, 4.4))
    yt, yb = 2.75, 1.15          # 端口上/下引线高度
    bh = 2.35                    # 方框高

    def box(x0):
        ax.add_patch(plt.Rectangle((x0, (yt + yb) / 2 - bh / 2), 1.55, bh,
                                   facecolor=C_FILL, edgecolor=C_BOX, lw=1.8,
                                   zorder=4))
        txt(ax, x0 + 0.775, (yt + yb) / 2, "$N$", fs=19, color=C_BOX)
        return x0 + 1.55

    def caption(xc, line1, line2):
        txt(ax, xc, -0.30, line1, fs=11.5, color=C_EQ)
        txt(ax, xc, -0.78, line2, fs=10.5, color=C_GREY)

    # ---------- (a) 开路 ----------
    x0 = 0.0
    xe = box(x0)
    xp = xe + 0.75
    wire(ax, (xe, yt), (xp, yt))
    wire(ax, (xe, yb), (xp, yb))
    term(ax, (xp, yt))
    term(ax, (xp, yb))
    txt(ax, xp + 0.24, yt + 0.04, "a", fs=13, ha="left")
    txt(ax, xp + 0.24, yb - 0.04, "b", fs=13, ha="left")
    txt(ax, xp - 0.26, yt + 0.02, "$+$", fs=14, color=C_HL)
    txt(ax, xp - 0.26, yb - 0.02, "$-$", fs=14, color=C_HL)
    arrow(ax, (xp, yt - 0.26), (xp, yb + 0.26), color=C_HL, lw=1.4, ms=10)
    txt(ax, xp + 0.16, (yt + yb) / 2, "$u_{oc}$", fs=13, color=C_HL, ha="left")
    caption(x0 + 1.55, "(a) 开路，求 $u_{oc}$", "端口电流为 0")

    # ---------- (b) 短路 ----------
    x1 = 4.05
    xe = box(x1)
    xq = xe + 0.55
    wire(ax, (xe, yt), (xq, yt))
    wire(ax, (xe, yb), (xq, yb))
    wire(ax, (xq, yb), (xq, yt))
    arrow(ax, (xq, yt - 0.16), (xq, (yt + yb) / 2), color=C_HL, lw=1.5, ms=11)
    txt(ax, xq + 0.24, (yt + yb) / 2 + 0.22, "$i_{sc}$", fs=13, color=C_HL,
        ha="left")
    caption(x1 + 1.55, "(b) 短路，求 $i_{sc}$", "端口电压为 0")

    # ---------- (c) 除源 + 外加 1 A ----------
    x2 = 8.10
    xe = box(x2)
    xr = xe + 1.55
    wire(ax, (xe, yt), (xr, yt))
    wire(ax, (xe, yb), (xr, yb))
    src_i(ax, (xr, yb), (xr, yt), to_p2=True)
    txt(ax, xr, yb - 0.58, "$1\\ \\mathrm{A}$", fs=12, color=C_EQ)
    txt(ax, xr + 0.34, yt - 0.02, "$+$", fs=14, color=C_HL)
    txt(ax, xr + 0.34, yb + 0.02, "$-$", fs=14, color=C_HL)
    txt(ax, xr + 0.96, (yt + yb) / 2, "$u$", fs=13, color=C_HL)
    caption(x2 + 1.55, "(c) 除源，求 $R_{eq}$", "外加 1 A，量端口电压")

    txt(ax, 5.0, 4.05,
        "戴维宁等效参数 $u_{oc}$、$R_{eq}$ 的三条独立求法",
        fs=13, color=C_MAIN)
    out(fig, "fig05_method")


if __name__ == "__main__":
    ex1()
    ex2()
    bridge("fig08_ex3", (1, 3, 9, 3))
    vcvs("fig09_ex4", 2, (2, 2, 1, 6))
    vccs("fig10_ex5", 1, (2, 2, 3))
    hw1()
    bridge("fig12_hw2", (2, 4, 8, 4))
    vcvs("fig13_hw3", "1.5", (2, 2, 2, 3))
    method()
