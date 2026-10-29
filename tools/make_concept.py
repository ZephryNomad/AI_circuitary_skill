"""概念图（第 2 版）：统一用 matplotlib 手绘，坐标完全可控。

布局原则：
  1. 元件标签一律放在元件"外侧且远离其他元素"的位置；
  2. 标题（栏目标题）与元件标签至少相隔 0.5 个单位；
  3. 电压源/电流源用圆圈 + 极内符号，导线在圆圈边缘断开。
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib import rcParams

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False
rcParams["mathtext.fontset"] = "cm"

C_MAIN = "#1f2933"
C_BOX = "#2f5d8a"
C_EQ = "#b45309"
C_HL = "#be123c"
C_FILL = "#eff6ff"


def canvas(w, h, xlim, ylim):
    fig, ax = plt.subplots(figsize=(w, h), dpi=260)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def arrow(ax, p1, p2, color=C_MAIN, lw=1.7, ms=12):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=ms,
                                 color=color, lw=lw, shrinkA=0, shrinkB=0))


def txt(ax, x, y, s, **kw):
    kw.setdefault("fontsize", 12)
    kw.setdefault("ha", "center")
    kw.setdefault("va", "center")
    ax.text(x, y, s, **kw)


def out(fig, name, pad=0.06):
    import os
    os.makedirs("figs", exist_ok=True)
    fig.savefig(f"figs/{name}.png", bbox_inches="tight", pad_inches=pad,
                facecolor="white")
    plt.close(fig)
    print("saved", f"figs/{name}.png")


def wire(ax, p1, p2, color=C_MAIN, lw=1.8):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, lw=lw,
            solid_capstyle="round", zorder=2)


def res_v(ax, x, ytop, ybot, label=None, lab_dx=0.62, h=0.90, w=0.34,
          color=C_EQ, fs=13):
    """竖放矩形电阻，标签默认放在右侧。"""
    yc = (ytop + ybot) / 2
    wire(ax, (x, ytop), (x, yc + h / 2))
    wire(ax, (x, yc - h / 2), (x, ybot))
    ax.add_patch(Rectangle((x - w / 2, yc - h / 2), w, h, facecolor="white",
                           edgecolor=color, lw=2.0, zorder=5))
    if label:
        txt(ax, x + lab_dx, yc, label, fontsize=fs, color=color, ha="left")
    return yc


def res_h(ax, xleft, xright, y, label=None, lab_dy=0.52, w=0.72, h=0.34,
          color=C_EQ, fs=13):
    """横放矩形电阻，标签默认放在上方。"""
    xc = (xleft + xright) / 2
    wire(ax, (xleft, y), (xc - w / 2, y))
    wire(ax, (xc + w / 2, y), (xright, y))
    ax.add_patch(Rectangle((xc - w / 2, y - h / 2), w, h, facecolor="white",
                           edgecolor=color, lw=2.0, zorder=5))
    if label:
        txt(ax, xc, y + lab_dy, label, fontsize=fs, color=color)
    return xc


def src_v(ax, x, ytop, ybot, label, lab_dx=0.78, r=0.42, color=C_EQ, fs=13):
    """竖放电压源（+ 上 - 下），标签默认右上。"""
    yc = (ytop + ybot) / 2
    wire(ax, (x, ytop), (x, yc + r))
    wire(ax, (x, yc - r), (x, ybot))
    ax.add_patch(plt.Circle((x, yc), r, facecolor="white", edgecolor=color,
                            lw=2.0, zorder=5))
    txt(ax, x, yc + 0.20, "$+$", fontsize=14, color=color)
    txt(ax, x, yc - 0.20, "$-$", fontsize=14, color=color)
    txt(ax, x + lab_dx, yc, label, fontsize=fs, color=color, ha="left")
    return yc


def src_i(ax, x, ytop, ybot, label, lab_dx=0.80, r=0.42, color=C_EQ, fs=13,
          up=True):
    """竖放电流源（箭头在圆内），标签默认右侧。"""
    yc = (ytop + ybot) / 2
    wire(ax, (x, ytop), (x, yc + r))
    wire(ax, (x, yc - r), (x, ybot))
    ax.add_patch(plt.Circle((x, yc), r, facecolor="white", edgecolor=color,
                            lw=2.0, zorder=5))
    if up:
        arrow(ax, (x, yc - 0.24), (x, yc + 0.22), color=color, lw=1.9, ms=13)
    else:
        arrow(ax, (x, yc + 0.24), (x, yc - 0.22), color=color, lw=1.9, ms=13)
    # zorder 提升箭头
    for p in ax.patches[-1:]:
        p.set_zorder(6)
    txt(ax, x + lab_dx, yc, label, fontsize=fs, color=color, ha="left")
    return yc


def term(ax, x, y, name=None, dx=0.22, dy=0.24, align="left", fs=13):
    """端钮圆点 + 名称。"""
    ax.plot([x], [y], "o", ms=6.8, color=C_MAIN, zorder=6)
    if name:
        ha = align
        txt(ax, x + dx, y + dy, name, fontsize=fs, ha=ha)


# ================================================================= 图1
def fig01():
    fig, ax = canvas(7.2, 3.5, (-0.3, 7.0), (-0.3, 3.4))
    ax.add_patch(Rectangle((0, 0.30), 2.9, 2.85, facecolor=C_FILL,
                           edgecolor=C_BOX, lw=2.0))
    txt(ax, 1.45, 2.48, "单口网络 $N$", fontsize=17, color=C_BOX)
    txt(ax, 1.45, 1.78, "线性电阻 + 独立源", fontsize=10.5, color=C_BOX)
    txt(ax, 1.45, 1.38, "+ 线性受控源", fontsize=10.5, color=C_BOX)
    txt(ax, 1.45, 0.72, "（内部结构未知也可以）", fontsize=9.5, color="#64748b")

    ya, yb = 2.62, 0.82
    wire(ax, (2.9, ya), (4.3, ya))
    wire(ax, (2.9, yb), (4.3, yb))
    term(ax, 4.3, ya, "a", dx=0.20, dy=0.28)
    term(ax, 4.3, yb, "b", dx=0.20, dy=-0.28)

    # 端口电压 u
    txt(ax, 5.90, ya, "$+$", fontsize=17, color=C_HL)
    txt(ax, 5.90, yb, "$-$", fontsize=17, color=C_HL)
    arrow(ax, (5.55, ya - 0.06), (5.55, yb + 0.06), color=C_HL, lw=1.5, ms=11)
    txt(ax, 6.30, (ya + yb) / 2, "$u$", fontsize=17, color=C_HL, ha="left")

    # 端口电流 i（由 a 流入网络，向左）
    arrow(ax, (4.22, ya + 0.40), (3.55, ya + 0.40), color=C_HL, lw=1.8, ms=13)
    txt(ax, 3.88, ya + 0.72, "$i$", fontsize=16, color=C_HL)

    txt(ax, 6.28, 3.05, "端口变量", fontsize=10.5, color=C_HL, ha="center")
    out(fig, "fig01_blackbox")


# ================================================================= 图2
def fig02():
    fig, ax = canvas(10.8, 3.5, (-0.4, 10.2), (-0.35, 3.4))
    # 左：原网络
    ax.add_patch(Rectangle((0, 0.30), 2.4, 2.85, facecolor=C_FILL,
                           edgecolor=C_BOX, lw=2.0))
    txt(ax, 1.2, 1.72, "$N$", fontsize=21, color=C_BOX)
    ya, yb = 2.62, 0.82
    wire(ax, (2.4, ya), (3.5, ya))
    wire(ax, (2.4, yb), (3.5, yb))
    term(ax, 3.5, ya, "a", dx=0.22, dy=0.26)
    term(ax, 3.5, yb, "b", dx=0.22, dy=-0.26)
    txt(ax, 1.2, -0.14, "原单口网络", fontsize=11, color=C_BOX)

    txt(ax, 4.35, 1.72, "$=$", fontsize=25)

    # 右：戴维宁等效
    x0 = 5.55
    x1 = x0 + 2.5            # 电阻右端
    xp = x1 + 1.15           # 端口位置
    res_h(ax, x0, x1, ya, "$R_{eq}$")
    src_v(ax, x0, ya, yb, "$u_{oc}$", lab_dx=0.76)
    wire(ax, (x1, ya), (xp, ya))
    wire(ax, (x0, yb), (xp, yb))
    term(ax, xp, ya, "a", dx=0.22, dy=0.26)
    term(ax, xp, yb, "b", dx=0.22, dy=-0.26)
    txt(ax, (x0 + xp) / 2, -0.14, "戴维宁等效电路", fontsize=11, color=C_EQ)
    out(fig, "fig02_thevenin_equiv")


# ================================================================= 图3
def fig03():
    fig, ax = canvas(9.6, 3.9, (-0.4, 9.2), (-0.5, 3.7))
    ya, yb = 2.55, 0.80

    def block(x0, kind, title):
        x1 = x0 + 2.3
        xp = x1 + 1.05
        res_h(ax, x0, x1, ya, "$R_{eq}$")
        if kind == "V":
            src_v(ax, x0, ya, yb, "$u_{oc}$", lab_dx=0.74)
        else:
            src_i(ax, x0, ya, yb, "$i_{sc}$", lab_dx=0.74, up=True)
        wire(ax, (x1, ya), (xp, ya))
        wire(ax, (x0, yb), (xp, yb))
        term(ax, xp, ya, "a", dx=0.22, dy=0.26)
        term(ax, xp, yb, "b", dx=0.22, dy=-0.26)
        txt(ax, (x0 + xp) / 2, 3.34, title, fontsize=12.5, color=C_EQ)

    block(0.0, "V", "戴维宁等效")
    txt(ax, 4.05, 1.68, "$\\Longleftrightarrow$", fontsize=22)
    block(4.60, "I", "诺顿等效")
    txt(ax, 4.05, 0.02, "$u_{oc}=i_{sc}\\,R_{eq}$", fontsize=13.5, color=C_EQ)
    out(fig, "fig03_norton")


# ================================================================= 图4
def fig04():
    import numpy as np
    fig, ax = plt.subplots(figsize=(6.6, 4.5), dpi=260)
    uoc, req = 6.0, 3.0
    i = np.linspace(0, uoc / req, 200)
    ax.plot(i, uoc - req * i, color=C_EQ, lw=2.6,
            label=r"外特性 $u=u_{oc}-R_{eq}i$")

    for rl, c, lb in [(2.0, "#0e7490", "$R_L=2\\,\\Omega$"),
                      (3.0, C_HL, "$R_L=3\\,\\Omega$（匹配）"),
                      (6.0, "#4d7c0f", "$R_L=6\\,\\Omega$")]:
        ii = np.linspace(0, uoc / rl, 60)
        ax.plot(ii, rl * ii, ls="--", lw=1.5, color=c, label=lb + " 负载线")

    ax.plot([uoc / (2 * req)], [uoc / 2], "o", ms=10, color=C_HL, zorder=6)
    bx = dict(fc="white", ec="none", alpha=0.88, pad=1.6)
    ax.annotate("最大功率点\n$R_L=R_{eq}$", xy=(uoc / (2 * req), uoc / 2),
                xytext=(2.30, 1.35), fontsize=10.5, color=C_HL,
                ha="left", va="bottom", bbox=bx, zorder=7,
                arrowprops=dict(arrowstyle="->", color=C_HL, lw=1.3))

    # u 轴截距 (i=0, u=u_oc) → 开路电压；i 轴截距 (i=i_sc, u=0) → 短路电流
    ax.plot([0], [uoc], "o", ms=7.5, color=C_BOX, zorder=6)
    ax.annotate("$u_{oc}$  开路电压", xy=(0, uoc), xytext=(1.20, 6.62),
                fontsize=10.5, color=C_BOX, ha="left", va="center", zorder=7,
                arrowprops=dict(arrowstyle="->", color=C_BOX, lw=1.3,
                                shrinkA=5, shrinkB=5))
    ax.plot([uoc / req], [0], "o", ms=7.5, color=C_BOX, zorder=6)
    ax.annotate("短路电流 $i_{sc}$", xy=(uoc / req + 0.05, 0.05),
                xytext=(2.42, 0.72), fontsize=10.5, color=C_BOX,
                ha="left", va="center", zorder=7,
                arrowprops=dict(arrowstyle="->", color=C_BOX, lw=1.3,
                                shrinkA=5, shrinkB=4))

    ax.set_xlabel("端口电流 $i$ / A", fontsize=11.5)
    ax.set_ylabel("端口电压 $u$ / V", fontsize=11.5)
    ax.set_title("线性单口网络的外特性是一条直线", fontsize=12.5)
    ax.set_xlim(-0.35, 4.55)
    ax.set_ylim(-0.45, 6.95)
    ax.grid(alpha=0.25, ls=":")
    ax.axhline(0, color="k", lw=0.9)
    ax.axvline(0, color="k", lw=0.9)
    ax.legend(fontsize=8.6, loc="upper right", framealpha=0.96,
              borderpad=0.5, labelspacing=0.35)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out(fig, "fig04_curve", pad=0.05)


if __name__ == "__main__":
    fig01()
    fig02()
    fig03()
    fig04()
