"""figlib —— 电路/概念图绘制基元（matplotlib 手绘，坐标完全可控）

设计要点
  1. 所有图元统一按 "两点之间画一个元件" 的接口：sym(ax, p1, p2, label=...)
     这样斜放元件（电桥对角线）也能自动旋转。
  2. zorder 分层：导线 2 < 元件白底 5 < 元件内符号 6 < 文字 8。
     （早期 bug：圆圈白底 zorder=5 把 zorder=3 的 +/- 文字盖住了）
  3. 标注默认沿法线方向偏移，side=+1/-1 可换边，避免压线。
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Polygon
from matplotlib.transforms import Affine2D
from matplotlib import rcParams

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False
rcParams["mathtext.fontset"] = "cm"

C_MAIN = "#1f2933"      # 导线 / 主线
C_BOX = "#2f5d8a"       # 黑箱
C_EQ = "#b45309"        # 等效元件、元件符号
C_HL = "#be123c"        # 强调（端口变量、答案）
C_DEP = "#6d28d9"       # 受控源
C_FILL = "#eff6ff"
C_GREY = "#64748b"

Z_WIRE, Z_SYM, Z_MARK, Z_TXT = 2, 5, 6, 8

LW_WIRE = 1.9
FS = 13


# ------------------------------------------------------------------ 画布
def canvas(w, h, xlim, ylim, dpi=260):
    fig, ax = plt.subplots(figsize=(w, h), dpi=dpi)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def out(fig, name, pad=0.08):
    os.makedirs("figs", exist_ok=True)
    path = f"figs/{name}.png"
    fig.savefig(path, bbox_inches="tight", pad_inches=pad, facecolor="white")
    plt.close(fig)
    print("saved", path, os.path.getsize(path), "bytes")


def txt(ax, x, y, s, fs=FS, color=C_MAIN, ha="center", va="center", rot=0,
        boxed=False, bold=False, zorder=Z_TXT):
    kw = dict(fontsize=fs, color=color, ha=ha, va=va, rotation=rot,
              zorder=zorder)
    if bold:
        kw["fontweight"] = "bold"
    if boxed:
        kw["bbox"] = dict(facecolor="white", edgecolor="none", pad=2.0,
                          alpha=0.95)
    ax.text(x, y, s, **kw)


def arrow(ax, p1, p2, color=C_MAIN, lw=1.7, ms=12, zorder=Z_MARK, style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=ms,
                                 color=color, lw=lw, shrinkA=0, shrinkB=0,
                                 zorder=zorder))


def wire(ax, p1, p2, color=C_MAIN, lw=LW_WIRE):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, lw=lw,
            solid_capstyle="round", zorder=Z_WIRE)


def wire_path(ax, pts, color=C_MAIN, lw=LW_WIRE):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round",
            solid_joinstyle="round", zorder=Z_WIRE)


def term(ax, p, name=None, dx=0.0, dy=0.0, fs=FS, ha="center", va="center"):
    """端钮圆点 + 名称。"""
    ax.plot([p[0]], [p[1]], "o", ms=6.8, color=C_MAIN, zorder=Z_MARK)
    if name:
        txt(ax, p[0] + dx, p[1] + dy, name, fs=fs, ha=ha, va=va)


# ------------------------------------------------------------- 几何小工具
def _geom(p1, p2):
    p1 = np.array(p1, float)
    p2 = np.array(p2, float)
    d = p2 - p1
    L = float(np.hypot(*d))
    if L == 0:
        raise ValueError("两端点重合")
    u = d / L
    n = np.array([-u[1], u[0]])       # 左法线
    return p1, p2, u, n, L


def _stub(ax, p1, p2, half, u, n=None, color=C_MAIN):
    """从 p1、p2 各画一段到元件边缘的引线。"""
    m = (p1 + p2) / 2
    wire(ax, p1, m - u * half, color=color)
    wire(ax, p2, m + u * half, color=color)


def _label(ax, m, n, side, off, label, fs, color, rot=0, ha=None,
           va="center", boxed=False):
    """标签沿法线外移 off；竖直元件的标签自动靠外侧对齐，避免压住符号。"""
    if label is None:
        return
    p = m + n * (side * off)
    if ha is None:
        if abs(n[0]) > 0.9:                    # 竖直元件 -> 左右放（斜线一律居中）
            ha = "left" if (side * n[0]) > 0 else "right"
        else:
            ha = "center"
    txt(ax, p[0], p[1], label, fs=fs, color=color, rot=rot, ha=ha, va=va,
        boxed=boxed)


# ------------------------------------------------------------------ 元件
def res(ax, p1, p2, label=None, fs=FS, off=0.46, side=1, w=0.34, l=0.88,
        color=C_EQ, rot_label=False):
    """矩形电阻（IEC 符号），沿 p1→p2 方向自动旋转。"""
    p1, p2, u, n, L = _geom(p1, p2)
    half = min(l, L * 0.5) / 2
    _stub(ax, p1, p2, half, u)
    m = (p1 + p2) / 2
    ang = np.degrees(np.arctan2(u[1], u[0]))
    rect = Rectangle((-l / 2, -w / 2), l, w, facecolor="white",
                     edgecolor=color, lw=2.0, zorder=Z_SYM)
    rect.set_transform(Affine2D().rotate_deg(ang).translate(m[0], m[1])
                       + ax.transData)
    ax.add_patch(rect)
    _label(ax, m, n, side, off, label, fs, color,
           rot=(ang if rot_label else 0))


def _circle(ax, m, r, color):
    ax.add_patch(plt.Circle((m[0], m[1]), r, facecolor="white",
                            edgecolor=color, lw=2.0, zorder=Z_SYM))


def src_v(ax, p1, p2, label=None, fs=FS, off=0.72, side=1, plus_at_p1=True,
          r=0.42, color=C_EQ):
    """圆形独立电压源，+ 极靠近 p1（plus_at_p1=True）。"""
    p1, p2, u, n, L = _geom(p1, p2)
    m = (p1 + p2) / 2
    _stub(ax, p1, p2, r, u)
    _circle(ax, m, r, color)
    s = 1 if plus_at_p1 else -1
    txt(ax, *(m - u * 0.19 * s), "$+$", fs=15, color=color)
    txt(ax, *(m + u * 0.19 * s), "$-$", fs=15, color=color)
    _label(ax, m, n, side, off, label, fs, color)


def src_i(ax, p1, p2, label=None, fs=FS, off=0.72, side=1, to_p2=True,
          r=0.42, color=C_EQ):
    """圆形独立电流源，箭头由 p1 指向 p2（to_p2=True）。"""
    p1, p2, u, n, L = _geom(p1, p2)
    m = (p1 + p2) / 2
    _stub(ax, p1, p2, r, u)
    _circle(ax, m, r, color)
    s = 1 if to_p2 else -1
    arrow(ax, m - u * 0.24 * s, m + u * 0.22 * s, color=color, lw=1.9, ms=13)
    _label(ax, m, n, side, off, label, fs, color)


def _diamond(ax, m, u, n, a=0.62, b=0.40, color=C_DEP):
    pts = [m + u * a, m + n * b, m - u * a, m - n * b]
    ax.add_patch(Polygon(pts, closed=True, facecolor="white",
                         edgecolor=color, lw=2.0, zorder=Z_SYM))


def dep_v(ax, p1, p2, label=None, fs=FS, off=0.78, side=1,
          plus_at_p1=True, color=C_DEP):
    """菱形受控电压源。"""
    p1, p2, u, n, L = _geom(p1, p2)
    m = (p1 + p2) / 2
    _stub(ax, p1, p2, 0.62, u)
    _diamond(ax, m, u, n, color=color)
    s = 1 if plus_at_p1 else -1
    txt(ax, *(m - u * 0.30 * s), "$+$", fs=14, color=color)
    txt(ax, *(m + u * 0.30 * s), "$-$", fs=14, color=color)
    _label(ax, m, n, side, off, label, fs, color)


def dep_i(ax, p1, p2, label=None, fs=FS, off=0.78, side=1, to_p2=True,
          color=C_DEP):
    """菱形受控电流源。"""
    p1, p2, u, n, L = _geom(p1, p2)
    m = (p1 + p2) / 2
    _stub(ax, p1, p2, 0.62, u)
    _diamond(ax, m, u, n, color=color)
    s = 1 if to_p2 else -1
    arrow(ax, m - u * 0.26 * s, m + u * 0.26 * s, color=color, lw=1.9, ms=13)
    _label(ax, m, n, side, off, label, fs, color)


# ------------------------------------------------------------ 例题电路绘制
def draw_net(ax, net, pos, labels=None, fs=FS, port=None, port_label=True,
             port_arrow=True):
    """按 pos（节点 -> 坐标）绘制一个网络。

    net 元素与 mna.py 同格式：
      ('R', n1, n2, val)
      ('V', n1, n2, val, name)      n1 为 + 极
      ('I', n1, n2, val)            电流由 n1 流向 n2（n1→外部注入 n2）
      ('VCVS', n1, n2, c1, c2, mu, name)
      ('VCCS', n1, n2, c1, c2, g)
    labels: {(元素序号): 或 (kind, n1, n2) -> 自定义标注}
    port: (a, b) 端口节点，自动画端钮与 u/i 参考方向
    """
    labels = labels or {}
    for k, e in enumerate(net):
        kind = e[0]
        n1, n2 = e[1], e[2]
        p1, p2 = pos[n1], pos[n2]
        lab = labels.get(k, labels.get((kind, n1, n2)))
        side = labels.get((k, "side"), 1)
        off = labels.get((k, "off"), 0.46 if kind == "R" else 0.74)
        if kind == "R":
            res(ax, p1, p2, lab, fs=fs, side=side, off=off)
        elif kind == "V":
            src_v(ax, p1, p2, lab, fs=fs, side=side, off=off, plus_at_p1=True)
        elif kind == "I":
            src_i(ax, p1, p2, lab, fs=fs, side=side, off=off, to_p2=True)
        elif kind == "VCVS":
            dep_v(ax, p1, p2, lab, fs=fs, side=side, off=off)
        elif kind == "VCCS":
            dep_i(ax, p1, p2, lab, fs=fs, side=side, off=off)
        else:
            raise ValueError(kind)

    if port:
        a, b = port
        pa, pb = np.array(pos[a], float), np.array(pos[b], float)
        term(ax, pa, "a", dx=0.0, dy=0.0)
        term(ax, pb, "b", dx=0.0, dy=0.0)


def port_marks(ax, pa, pb, u=True, i=True, color=C_HL, fs=15):
    """在端口两点之间画 u 的 +/－ 与箭头、i 的箭头。pa 为 a（+）。"""
    pa = np.array(pa, float)
    pb = np.array(pb, float)
    u = (pb - pa) / np.hypot(*(pb - pa))
    n = np.array([-u[1], u[0]])
    mid = (pa + pb) / 2
    if u:
        txt(ax, *(pa + n * 0.34), "$+$", fs=fs, color=color)
        txt(ax, *(pb + n * 0.34), "$-$", fs=fs, color=color)
        arrow(ax, mid - n * 0.10 + u * 0.05, mid + n * 0.10, color=color,
              lw=1.5, ms=11)
        txt(ax, *(mid + n * 0.52), "$u$", fs=fs + 1, color=color)
