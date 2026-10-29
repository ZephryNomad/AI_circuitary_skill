"""补两张图：fig14（戴维宁等效源接负载）、fig15（独立源置零 vs 受控源保留）。
运行：MPLCONFIGDIR=.mplcache PYTHONPATH=tools python -W ignore tools/make_figs_b.py
"""
from figlib import (canvas, out, txt, arrow, wire, term, res, src_v, src_i,
                    dep_v, dep_i, C_MAIN, C_HL, C_DEP, C_GREY, C_BOX, C_FILL,
                    C_EQ, FS)


# ------------------------------------------------- 图 14 等效源 + 负载
def fig14():
    fig, ax = canvas(9.0, 4.4, (-2.6, 9.6), (-1.2, 5.4))
    y1, y0 = 4.2, 0.0
    x1, x2, x3 = 0.0, 3.2, 5.9

    src_v(ax, (x1, y1), (x1, y0), "$u_{oc}$", side=-1, off=0.80)
    res(ax, (x1, y1), (x2, y1), "$R_{eq}$", off=0.46, side=1)
    wire(ax, (x2, y1), (x3, y1))
    res(ax, (x3, y1), (x3, y0), "$R_L$", off=0.48, side=1)
    wire(ax, (x1, y0), (x3, y0))
    for p in [(x1, y1), (x1, y0), (x2, y1), (x3, y1), (x3, y0)]:
        ax.plot([p[0]], [p[1]], "o", ms=5.5, color=C_MAIN, zorder=6)

    # i_L：沿 R_L 由上到下（顺时针回路电流）
    xi = x3 - 0.40
    arrow(ax, (xi, y1 - 0.55), (xi, y0 + 0.55), color=C_HL, lw=1.5, ms=11)
    txt(ax, xi - 0.30, (y1 + y0) / 2, "$i_L$", fs=15, color=C_HL)

    # u_L：R_L 右侧
    xu = x3 + 1.35
    txt(ax, xu, y1 - 0.16, "$+$", fs=15, color=C_HL)
    txt(ax, xu, y0 + 0.16, "$-$", fs=15, color=C_HL)
    arrow(ax, (xu, y1 - 0.52), (xu, y0 + 0.52), color=C_HL, lw=1.5, ms=11)
    txt(ax, xu + 0.42, (y1 + y0) / 2, "$u_L$", fs=15, color=C_HL)

    txt(ax, (x1 + x2) / 2, -0.62, "戴维宁等效电路", fs=12, color=C_EQ)
    txt(ax, x3, -0.62, "外接负载", fs=12, color=C_MAIN)
    out(fig, "fig14_thevenin_load")


# ------------------------------------------- 图 15 置零规则三栏
def fig15():
    fig, ax = canvas(11.4, 2.3, (-0.5, 11.9), (0.35, 4.2))
    yc = 1.95
    pitch = 3.85

    def panel(i, title):
        cx = 1.35 + pitch * i
        txt(ax, cx + 1.05, 3.55, title, fs=12.5, color=C_MAIN)
        return cx

    def rel(cx):
        arrow(ax, (cx - 0.22, yc), (cx + 0.62, yc), color=C_GREY, lw=1.4, ms=12)

    def note(cx, line1, color=C_HL):
        txt(ax, cx, yc + 0.72, line1, fs=12, color=color)

    # (a) 独立电压源 -> 短路
    cx = panel(0, "(a) 独立电压源")
    src_v(ax, (cx - 0.95, yc + 0.30), (cx - 0.95, yc - 0.30), None)
    txt(ax, cx - 0.95, yc - 0.98, "$u_S$", fs=14, color=C_EQ)
    rel(cx)
    wire(ax, (cx + 0.80, yc), (cx + 1.95, yc))
    note(cx + 1.38, "短路")
    txt(ax, cx + 1.38, yc - 0.98, "$u_S=0$", fs=12, color=C_GREY)

    # (b) 独立电流源 -> 开路
    cx = panel(1, "(b) 独立电流源")
    src_i(ax, (cx - 0.95, yc - 0.30), (cx - 0.95, yc + 0.30), None, to_p2=True)
    txt(ax, cx - 0.95, yc - 0.98, "$i_S$", fs=14, color=C_EQ)
    rel(cx)
    wire(ax, (cx + 0.80, yc), (cx + 1.20, yc))
    wire(ax, (cx + 1.60, yc), (cx + 2.00, yc))
    note(cx + 1.40, "断开")
    txt(ax, cx + 1.40, yc - 0.98, "$i_S=0$", fs=12, color=C_GREY)

    # (c) 受控源 -> 保留
    cx = panel(2, "(c) 受控源")
    dep_v(ax, (cx - 0.95, yc + 0.34), (cx - 0.95, yc - 0.34), None)
    txt(ax, cx - 0.95, yc - 0.98, "$\\mu u_1$", fs=14, color=C_DEP)
    rel(cx)
    dep_v(ax, (cx + 1.35, yc + 0.34), (cx + 1.35, yc - 0.34), None)
    note(cx + 1.35, "原样保留")
    txt(ax, cx + 1.35, yc - 0.98, "不能置零", fs=12, color=C_GREY)

    out(fig, "fig15_zero_rule")


if __name__ == "__main__":
    fig14()
    fig15()
