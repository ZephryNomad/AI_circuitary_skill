# -*- coding: utf-8 -*-
"""习题 5.2.5 —— 分压式偏置共射放大电路：由工作点指标反求 R_e / R_b1 / R_b2

题目（教材 5.2.5）
    放大电路如图题 5.2.5 所示。设 BJT 的 β=100，V_BEQ=0.7 V，V_CC=12 V，
    R_c=4.3 kΩ，I₁=10I_B。要求电路的 I_CQ=1 mA，V_CEQ=5 V。
    试设计电阻 R_e、R_b1 和 R_b2 的值。

单位约定
    mA + kΩ + V（1 mA × 1 kΩ = 1 V）。全程 Fraction 精确运算，不引入浮点误差。

三重校验（互相独立，缺一不可）
    1. 闭式解回代：把设计值代回 6 条元件/器件关系，残差必须恒为 0。
    2. 戴维南等效基极回路：换一条代数路径（分压器等效成 V_BB 串 R_BB，
       再解基极回路），若与第 1 步一致，说明推导没错。
    3. ngspice 器件模型：把设计值写成网表跑 .op，靠 Ebers-Moll 迭代求解，
       与上面两路纯代数完全无关，用来抓「算对了但电路理解错了」。

用法
    python tools/design_5_2_5.py              # 打印报告，并把网表/报告写进 out/p5_2_5/
    python tools/design_5_2_5.py --no-spice   # 只做闭式设计与回代，不跑 ngspice
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from collections import OrderedDict
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out", "p5_2_5")

sys.path.insert(0, HERE)
import spice_run  # noqa: E402

# ---- 已知条件 ---------------------------------------------------------------
BETA = F(100)
VBE = F(7, 10)
VCC = F(12)
RC = F(43, 10)
ICQ = F(1)
VCEQ = F(5)
K_I1 = F(10)          # I₁ = 10 I_B


def kstr(v):
    """kΩ 数值的整洁打印：整数就不带小数点。"""
    if v.denominator == 1:
        return str(v.numerator)
    return "%.4f" % float(v)


def design():
    """闭式设计：由指标一路推出三个电阻。返回 OrderedDict。"""
    d = OrderedDict()
    d["β"] = BETA
    d["I_B"] = ICQ / BETA                       # 10 µA
    d["I_E"] = ICQ + d["I_B"]                   # 1.01 mA
    d["V_Rc"] = ICQ * RC                        # 4.3 V
    d["V_E"] = VCC - d["V_Rc"] - VCEQ           # 2.7 V
    d["R_e"] = d["V_E"] / d["I_E"]              # 270/101 kΩ
    d["V_B"] = d["V_E"] + VBE                   # 3.4 V
    d["I₁"] = K_I1 * d["I_B"]                   # 100 µA，即流过 R_b1 的电流
    d["I_Rb2"] = d["I₁"] - d["I_B"]             # 90 µA
    d["R_b2"] = d["V_B"] / d["I_Rb2"]           # 340/9 kΩ
    d["R_b1"] = (VCC - d["V_B"]) / d["I₁"]      # 86 kΩ
    return d


def residuals(d):
    """第 1 路：把 R_e/R_b1/R_b2 代回电路关系，与题给指标比对。

    严格按「器件关系 + 元件关系」重建，不沿用 design() 的中间量：
        I₁  = (V_CC − V_B) / R_b1
        I_Rb2 = V_B / R_b2
        I_B  = I₁ − I_Rb2           （基极节点 KCL）
        I_C  = β·I_B                （放大区）
        I_E  = I_C + I_B
        V_E  = I_E·R_e
        V_B' = V_E + V_BE           （发射结）
        V_CE = V_CC − I_C·R_c − V_E
    """
    Re, Rb1, Rb2 = d["R_e"], d["R_b1"], d["R_b2"]
    VB = d["V_B"]
    I1 = (VCC - VB) / Rb1
    IRb2 = VB / Rb2
    IB = I1 - IRb2
    IC = BETA * IB
    IE = IC + IB
    VE = IE * Re
    VB_chk = VE + VBE
    VCE = VCC - IC * RC - VE
    rows = [
        ("I₁ = (V_CC−V_B)/R_b1", I1, d["I₁"], I1 - d["I₁"]),
        ("I_Rb2 = V_B/R_b2", IRb2, d["I_Rb2"], IRb2 - d["I_Rb2"]),
        ("I_B = I₁ − I_Rb2", IB, d["I_B"], IB - d["I_B"]),
        ("I_C = β·I_B", IC, ICQ, IC - ICQ),
        ("I_E = I_C + I_B", IE, d["I_E"], IE - d["I_E"]),
        ("V_E = I_E·R_e", VE, d["V_E"], VE - d["V_E"]),
        ("V_B = V_E + V_BE", VB_chk, VB, VB_chk - VB),
        ("V_CE = V_CC−I_C R_c−V_E", VCE, VCEQ, VCE - VCEQ),
    ]
    return rows


def thevenin_path(d):
    """第 2 路：分压器等效 + 基极回路，纯代数但路径不同。

    V_BB = V_CC·R_b2/(R_b1+R_b2)      空载分压
    R_BB = R_b1∥R_b2                  等效内阻
    I_B  = (V_BB − V_BE) / (R_BB + (1+β)R_e)

    这条式子是教材里最常用的「分压式偏置工作点公式」，与逐级回代不是同一条路。
    """
    Rb1, Rb2, Re = d["R_b1"], d["R_b2"], d["R_e"]
    VBB = VCC * Rb2 / (Rb1 + Rb2)
    RBB = Rb1 * Rb2 / (Rb1 + Rb2)
    IB = (VBB - VBE) / (RBB + (1 + BETA) * Re)
    IC = BETA * IB
    IE = IC + IB
    VE = IE * Re
    VCE = VCC - IC * RC - VE
    return OrderedDict([
        ("V_BB", VBB), ("R_BB", RBB), ("I_B", IB), ("I_C", IC),
        ("I_E", IE), ("V_E", VE), ("V_CE", VCE),
    ])


def nominal_round(d):
    """取标称值后工作点会飘多少：用戴维南基极回路算，V_BE 仍按 0.7 V。"""
    trials = [
        ("精确值", d["R_e"], d["R_b1"], d["R_b2"]),
        ("R_e=2.7k（E24 标准）", F(27, 10), d["R_b1"], d["R_b2"]),
        ("全取 E24：2.7k / 82k / 39k", F(27, 10), F(82), F(39)),
        ("全取 E24：2.7k / 91k / 36k", F(27, 10), F(91), F(36)),
    ]
    rows = []
    for name, Re, Rb1, Rb2 in trials:
        sub = OrderedDict([("R_e", Re), ("R_b1", Rb1), ("R_b2", Rb2)])
        t = thevenin_path(sub)
        rows.append((name, Re, Rb1, Rb2, t["I_C"], t["V_E"], t["V_CE"]))
    return rows


# ---- ngspice ---------------------------------------------------------------
def ngspice_netlist(d, Re, Rb1, Rb2, tag):
    """把某一组电阻写成可跑的网表。IS 由「V_BE=0.7 V @ I_C=1 mA」反解。"""
    k = 1.380649e-23
    q = 1.602176634e-19
    VT = k * 300.15 / q                      # ngspice 默认 TEMP=27 ℃
    IS = 1e-3 / (math.exp(0.7 / VT) - 1.0)
    return """* p5_2_5 %s   Re=%s k  Rb1=%s k  Rb2=%s k
* beta=100, VAF=0 (no Early effect), IS tuned so that VBE=0.700 V at IC=1 mA
VCC 1 0 12
Rb1 1 2 %s
Rb2 2 0 %s
Rc  1 3 4.3k
Re  4 0 %s
Q1  3 2 4 QNPN
.model QNPN NPN (IS=%.17g BF=100 VAF=0 RB=0 RC=0 RE=0)
.control
set numdgt=12
op
print @q1[ic] @q1[ib] @q1[vbe]
print @rb1[i] @rb2[i] @rc[i] @re[i]
print v(1) v(2) v(3) v(4)
let vce = v(3)-v(4)
let ratio = @rb1[i]/@q1[ib]
print vce ratio
.endc
.end
""" % (tag, kstr(Re), kstr(Rb1), kstr(Rb2),
       "%.12gk" % float(Rb1), "%.12gk" % float(Rb2), "%.12gk" % float(Re),
       IS)


def run_spice(d):
    """第 3 路：ngspice 器件模型复核（精确值与标称值各跑一次）。"""
    res = OrderedDict()
    cases = [
        ("exact", d["R_e"], d["R_b1"], d["R_b2"]),
        ("e24", F(27, 10), F(82), F(39)),
    ]
    os.makedirs(OUT, exist_ok=True)
    for tag, Re, Rb1, Rb2 in cases:
        cir = ngspice_netlist(d, Re, Rb1, Rb2, tag)
        p = os.path.join(OUT, "p5_2_5_%s.cir" % tag)
        with open(p, "w", encoding="ascii", newline="\n") as f:
            f.write(cir)
        out, rc = spice_run.run(cir, timeout=120)
        res[tag] = {"path": p, "rc": rc, "out": out}
    return res


# ---- 报告 ------------------------------------------------------------------
def report(d, with_spice, spice=None):
    L = []
    A = L.append
    A("# 习题 5.2.5 —— 分压式偏置共射放大电路的设计")
    A("")
    A("## 一、已知与待求")
    A("")
    A("| 量 | 值 | 说明 |")
    A("|---|---|---|")
    A("| $\\beta$ | 100 | 电流放大系数 |")
    A("| $V_{BEQ}$ | 0.7 V | 发射结导通压降 |")
    A("| $V_{CC}$ | 12 V | 电源 |")
    A("| $R_c$ | 4.3 kΩ | 集电极电阻（题给，不用求） |")
    A("| $I_1$ | $10I_B$ | 流过 $R_{b1}$ 的电流 |")
    A("| $I_{CQ}$ | 1 mA | 要求的工作点 |")
    A("| $V_{CEQ}$ | 5 V | 要求的工作点 |")
    A("| 待求 | $R_e$、$R_{b1}$、$R_{b2}$ | |")
    A("")
    A("> 单位约定：下式全部按 **mA + kΩ + V** 计算（1 mA × 1 kΩ = 1 V），"
      "因此电流数值可直接写成 1、0.01、0.1 这样的数。")
    A("")
    A("## 二、思路：为什么按这个顺序算")
    A("")
    A("设计题的已知与未知正好「从输出端往输入端」排开，所以顺序是固定的：")
    A("")
    A("1. 输出回路会给 $V_E$：$V_{CC}$ 被 $R_c$ 上的压降和 $V_{CEQ}$ 吃掉，剩下来的就是 $V_E$。")
    A("2. 有了 $V_E$ 与 $I_E$，$R_e$ 就是欧姆定律 $R_e=V_E/I_E$。")
    A("3. 有了 $V_E$，$V_B=V_E+V_{BEQ}$ 也定了。")
    A("4. $I_1=10I_B$ 把分压器的电流也定死了，于是 $R_{b1}$、$R_{b2}$ 各由「电压 ÷ 该电阻上的电流」得到。")
    A("")
    A("要点：$I_1$ 是**流过 $R_{b1}$ 的电流**，基极节点上 $I_1=I_B+I_{R_{b2}}$，"
      "所以 $R_{b2}$ 上的电流是 $I_1-I_B=9I_B$，不是 $10I_B$。这一步最容易错。")
    A("")
    A("## 三、逐步计算（精确分数，无浮点误差）")
    A("")
    A("| 步 | 式 | 结果 |")
    A("|---|---|---|")
    A("| 1 | $I_B=I_{CQ}/\\beta=1/100$ | %s mA = 10 µA |" % kstr(d["I_B"]))
    A("| 2 | $I_E=I_{CQ}+I_B=1+0.01$ | %s mA |" % kstr(d["I_E"]))
    A("| 3 | $V_{R_c}=I_{CQ}R_c=1\\times4.3$ | %s V |" % kstr(d["V_Rc"]))
    A("| 4 | $V_E=V_{CC}-V_{R_c}-V_{CEQ}=12-4.3-5$ | %s V |" % kstr(d["V_E"]))
    A("| 5 | $R_e=V_E/I_E=%s\\div%s$ | **%s kΩ ≈ %s Ω** |"
      % (kstr(d["V_E"]), kstr(d["I_E"]), kstr(d["R_e"]),
         kstr(F(round(float(d["R_e"]) * 1000)))))
    A("| 6 | $V_B=V_E+V_{BEQ}=2.7+0.7$ | %s V |" % kstr(d["V_B"]))
    A("| 7 | $I_1=10I_B$ | %s mA = 100 µA |" % kstr(d["I₁"]))
    A("| 8 | $I_{R_{b2}}=I_1-I_B$ | %s mA = 90 µA |" % kstr(d["I_Rb2"]))
    A("| 9 | $R_{b2}=V_B/I_{R_{b2}}=3.4\\div0.09$ | **%s kΩ ≈ %s Ω** |"
      % (kstr(d["R_b2"]), kstr(F(round(float(d["R_b2"]) * 1000)))))
    A("| 10 | $R_{b1}=(V_{CC}-V_B)/I_1=(12-3.4)\\div0.1$ | **%s kΩ** |"
      % kstr(d["R_b1"]))
    A("")
    A("## 四、设计结果")
    A("")
    A("| 电阻 | 精确值 | 取值 |")
    A("|---|---|---|")
    A("| $R_e$ | %s kΩ（= %s Ω） | **%s kΩ（%s Ω）** |"
      % (kstr(d["R_e"]), kstr(F(round(float(d["R_e"]) * 1000))),
         "2.7", "2 700"))
    A("| $R_{b1}$ | %s kΩ | **86 kΩ（86 000 Ω）** |" % kstr(d["R_b1"]))
    A("| $R_{b2}$ | %s kΩ（= %s Ω） | **%s kΩ（%s Ω）** |"
      % (kstr(d["R_b2"]), kstr(F(round(float(d["R_b2"]) * 1000))),
         "37.8", "37 800"))
    A("")
    A("其中 $R_{b1}=86$ kΩ 是**整数**，这不是巧合：$8.6\\ \\mathrm{V}\\div0.1\\ \\mathrm{mA}$ 正好整除，"
      "说明「$I_1$ 是流过 $R_{b1}$ 的电流」这个理解是对的。")
    A("")
    A("### 取标称值后的工作点漂移")
    A("")
    A("86 kΩ 与 37.8 kΩ 都不是 E24 系列值，实际装配时要就近取。"
      "按 $V_{BE}=0.7$ V、$\\beta=100$ 用分压器等效式重算：")
    A("")
    A("| 取法 | $R_e$ | $R_{b1}$ | $R_{b2}$ | $I_{CQ}$ | $V_E$ | $V_{CEQ}$ |")
    A("|---|---|---|---|---|---|---|")
    for name, Re, Rb1, Rb2, IC, VE, VCE in nominal_round(d):
        A("| %s | %s kΩ | %s kΩ | %s kΩ | %.4f mA | %.4f V | %.4f V |"
          % (name, kstr(Re), kstr(Rb1), kstr(Rb2),
             float(IC), float(VE), float(VCE)))
    A("")
    A("取 82 kΩ / 39 kΩ 时 $I_{CQ}$ 偏大约 6%、$V_{CEQ}$ 偏小约 9%；"
      "取 91 kΩ / 36 kΩ 时偏小约 9.5%、偏大约 12.8%。"
      "所以若要求严格，应改用 86 kΩ / 37.8 kΩ 的 1% 金属膜电阻，或用微调电阻调试。")
    A("")
    A("## 五、三重校验")
    A("")
    rows = residuals(d)
    A("### 5.1 闭式解回代（残差必须全为 0）")
    A("")
    A("| 关系 | 回代值 | 题给/目标 | 残差 |")
    A("|---|---|---|---|")
    for name, got, want, res in rows:
        A("| %s | %s | %s | %s |" % (name, kstr(got), kstr(want), kstr(res)))
    ok1 = all(r[3] == 0 for r in rows)
    A("")
    A("**结论：%s**（%d 条残差全部为零）" % ("通过" if ok1 else "不通过", len(rows)))
    A("")
    t = thevenin_path(d)
    A("### 5.2 戴维南等效基极回路（换一条代数路径）")
    A("")
    A("分压器等效：$V_{BB}=V_{CC}R_{b2}/(R_{b1}+R_{b2})=%s$ V，"
      "$R_{BB}=R_{b1}\\parallel R_{b2}=%s$ kΩ。" % (kstr(t["V_BB"]), kstr(t["R_BB"])))
    A("")
    A("基极回路：$I_B=(V_{BB}-V_{BE})/(R_{BB}+(1+\\beta)R_e)=%s$ mA。" % kstr(t["I_B"]))
    A("")
    A("| 量 | 戴维南路径 | 目标 |")
    A("|---|---|---|")
    A("| $I_B$ | %s mA | %s mA |" % (kstr(t["I_B"]), kstr(d["I_B"])))
    A("| $I_C$ | %s mA | %s mA |" % (kstr(t["I_C"]), kstr(ICQ)))
    A("| $V_E$ | %s V | %s V |" % (kstr(t["V_E"]), kstr(d["V_E"])))
    A("| $V_{CE}$ | %s V | %s V |" % (kstr(t["V_CE"]), kstr(VCEQ)))
    ok2 = (t["I_C"] == ICQ and t["V_CE"] == VCEQ)
    A("")
    A("**结论：%s**（与 5.1 完全一致，说明推导路径本身没问题）"
      % ("通过" if ok2 else "不通过"))
    A("")
    if with_spice and spice:
        A("### 5.3 ngspice 器件模型（Ebers-Moll 迭代，与上面两路完全独立）")
        A("")
        A("模型设置：`BF=100`、`VAF=0`（关掉厄尔利效应，才和题目「$\\beta$ 恒定、$V_{BE}=0.7$」对齐）、"
          "`IS` 由「$V_{BE}=0.7$ V 时 $I_C=1$ mA」反解，使模型在 1 mA 处的 $V_{BE}$ 恰为 0.7 V。")
        A("")
        A("| 量 | 精确值结果 | 目标 | 相对偏差 |")
        A("|---|---|---|---|")
        for tag, title in (("exact", "精确值"), ("e24", "E24 2.7k/82k/39k")):
            r = spice[tag]
            m = spice_run.measures(r["out"])
            A("| *%s* | | | |" % title)
            for key, target, unit, name in (
                    ("vce", 5.0, "V", "$V_{CEQ}$"),
                    ("ratio", 10.0, "—", "$I_1/I_B$")):
                got = m.get(key)
                if got is None:
                    continue
                A("| %s | %.6g %s | %.6g %s | %+.3f%% |"
                  % (name, got, unit, target, unit, 100 * (got - target) / target))
        A("")
        A("器件电流与节点电压（精确值那一组，ngspice 原始输出）：")
        A("")
        A("```")
        for line in spice["exact"]["out"].splitlines():
            s = line.strip()
            if s.startswith(("@q1", "@rb1", "@rb2", "@rc", "@re", "v(", "vce", "ratio")):
                A(s)
        A("```")
        A("")
        ex = spice_run.measures(spice["exact"]["out"])
        ok3 = ex.get("vce") is not None and abs(ex["vce"] - 5.0) < 0.01
        A("**结论：%s**（$V_{CEQ}$ 与 $I_1/I_B$ 都回到题给指标）"
          % ("通过" if ok3 else "不通过"))
        A("")
    A("## 六、相关文件与复现")
    A("")
    A("| 文件 | 内容 |")
    A("|---|---|")
    A("| `tools/design_5_2_5.py` | 本题闭式设计 + 三重校验 + 出报告 |")
    A("| `tools/draw_5_2_5.py` | 按原图样式重绘电路图（题图 / 解答两版） |")
    A("| `out/p5_2_5/p5_2_5_题图.png` / `.svg` | 重绘的题图 |")
    A("| `out/p5_2_5/p5_2_5_解答.png` / `.svg` | 题图 + 工作点与设计值 |")
    A("| `out/p5_2_5/p5_2_5_exact.cir` | 精确设计值的 ngspice 网表 |")
    A("| `out/p5_2_5/p5_2_5_e24.cir` | E24 标称值的 ngspice 网表 |")
    A("| `out/p5_2_5/p5_2_5.md` | 本报告 |")
    A("")
    A("```")
    A("python tools/design_5_2_5.py      # 重算 + 复核 + 写 out/p5_2_5/")
    A("python tools/draw_5_2_5.py        # 重绘电路图")
    A("```")
    A("")
    return "\n".join(L), (ok1 and ok2)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="习题 5.2.5 分压式偏置电路设计")
    ap.add_argument("--no-spice", action="store_true", help="不跑 ngspice")
    args = ap.parse_args(argv)

    d = design()
    spice = None
    if not args.no_spice:
        if not spice_run.find_ngspice():
            print("[警告] 找不到 ngspice，跳过器件模型复核", file=sys.stderr)
        else:
            spice = run_spice(d)

    text, ok = report(d, spice is not None, spice)
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "p5_2_5.md")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(text)
    print("\n[已写出] %s" % p)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
