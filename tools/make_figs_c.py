"""补图：fig16 最大功率曲线、fig17 习题4 电路、fig18 四步流程图。
运行：MPLCONFIGDIR=.mplcache PYTHONPATH=tools python -W ignore tools/make_figs_c.py
"""
import numpy as np
import matplotlib.pyplot as plt
from figlib import (canvas, out, txt, arrow, wire, term, res, src_v, src_i,
                    dep_v, dep_i, C_MAIN, C_HL, C_DEP, C_GREY, C_BOX, C_FILL,
                    C_EQ, FS)

V = r"\ \mathrm{V}"
A = r"\ \mathrm{A}"
O = r"\ \Omega"


# ------------------------------------------------- 图 16 最大功率曲线
def fig16(uoc=4, req=2):
    fig, ax = plt.subplots(figsize=(6.6, 4.1), dpi=260)
    rl = np.linspace(0.05, 12, 600)
    p = uoc ** 2 * rl / (req + rl) ** 2
    pmax = uoc ** 2 / (4 * req)

    ax.plot(rl, p, color=C_BOX, lw=2.4)
    ax.axhline(pmax / 2, color=C_GREY, lw=1.0, ls=(0, (5, 4)))
    ax.axvline(req, color=C_HL, lw=1.4, ls=(0, (5, 4)))
    ax.plot([req], [pmax], "o", ms=8, color=C_HL, zorder=6)

    txt(ax, req + 0.32, pmax * 1.03,
        "$P_{\\max}=\\dfrac{u_{oc}^2}{4R_{eq}}=%.3g\\ \\mathrm{W}$" % pmax,
        fs=12, color=C_HL, ha="left", va="bottom")
    txt(ax, req + 0.30, pmax * 0.30, "$R_L=R_{eq}=%g\\ \\Omega$" % req, fs=11.5,
        color=C_HL, ha="left")
    txt(ax, 7.6, pmax / 2 + 0.09, "$P_{\\max}/2$", fs=10.5, color=C_GREY,
        ha="center", va="bottom")

    ax.set_xlabel("负载电阻 $R_L$ / $\\Omega$", fontsize=11.5, color=C_MAIN)
    ax.set_ylabel("负载功率 $P_L$ / $\\mathrm{W}$", fontsize=11.5, color=C_MAIN)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, pmax * 1.28)
    ax.tick_params(colors=C_GREY, labelsize=9.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#9AA5B1")
    ax.grid(alpha=0.18, lw=0.7)
    out(fig, "fig16_power_curve")


# ------------------------------------------------- 图 17 习题4 电路
def fig17(is_val=3, r1=2, r2=2, r3=4):
    fig, ax = canvas(7.8, 4.4, (-3.0, 7.6), (-1.0, 5.4))
    y1, y0 = 4.0, 0.0
    xi, x1, x2 = 0.0, 2.4, 4.9

    src_i(ax, (xi, y0), (xi, y1), "$I_S=%s%s$" % (is_val, A), side=-1,
          off=0.78, to_p2=True)
    wire(ax, (xi, y1), (x1, y1))
    res(ax, (x1, y1), (x1, y0), "$R_1=%s%s$" % (r1, O), off=0.54, side=1)
    res(ax, (x1, y1), (x2, y1), "$R_2=%s%s$" % (r2, O), off=0.46, side=1)
    res(ax, (x2, y1), (x2, y0), "$R_3=%s%s$" % (r3, O), off=0.56, side=1)

    wire(ax, (xi, y0), (x1, y0))
    wire(ax, (x1, y0), (x2, y0))
    for p in [(xi, y1), (xi, y0), (x1, y1), (x1, y0), (x2, y1), (x2, y0)]:
        ax.plot([p[0]], [p[1]], "o", ms=5.5, color=C_MAIN, zorder=6)

    xp = 6.5
    wire(ax, (x2, y1), (xp, y1))
    wire(ax, (x2, y0), (xp, y0))
    txt(ax, xp + 0.26, y1 + 0.26, "a", fs=14, ha="left")
    txt(ax, xp + 0.26, y0 - 0.26, "b", fs=14, ha="left")
    xm = xp + 0.95
    txt(ax, xm, y1, "$+$", fs=15, color=C_HL)
    txt(ax, xm, y0, "$-$", fs=15, color=C_HL)
    arrow(ax, (xm, y1 - 0.34), (xm, y0 + 0.34), color=C_HL, lw=1.5, ms=11)
    txt(ax, xm + 0.44, (y1 + y0) / 2, "$u$", fs=16, color=C_HL)
    out(fig, "fig17_hw4")


if __name__ == "__main__":
    fig16()
    fig17()
