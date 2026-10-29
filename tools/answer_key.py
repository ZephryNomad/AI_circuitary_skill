"""answer_key.py —— 用讲义自己给出的答案校验网表转换，逐题对照

为什么关键
    前面两层（往返自检、ngspice）证明的是"我的网表与我的解析器/ngspice 一致"，
    但如果我把题目抄错了（比如把 R3=2Ω 写成 3Ω），三者依然会一致地错。
    唯一能证明"抄对了"的东西是**外部答案**。
    src/book.md 的习题答案区就是这样的外部答案：先写定答案，本脚本只做比对，
    不参与任何计算，答案字符串原样来自讲义，改题卡就会立刻失败。

用法
    python tools/answer_key.py            # 全部对照
    python tools/answer_key.py --verbose  # 附带每个中间量
"""
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import convert as CV
import netlist as NL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 答案全部逐字抄自 src/book.md 的「习题答案」区，独立于网表与求解器。
# 字段：(卡片文件, 标题, 端口, u_oc, i_sc, R_eq, R_L, i_L, u_L, P_L, P_max)
KEY = [
    ("hw1.card", "习题1 三节梯形网络", ("4", "0"),
     "6", None, "3", "3", "1", "3", "3", "3"),
    ("hw2.card", "习题2 电桥（端口在中间节点）", ("2", "3"),
     "4", "1", "4", "4", "1/2", "2", "1", "1"),
    ("hw3.card", "习题3 含 VCVS", ("3", "0"),
     "8", "4", "2", "3", "8/5", "24/5", "192/25", "8"),
    ("hw4.card", "习题4 电流源激励", ("2", "0"),
     "3", "3/2", "2", "2", "3/4", "3/2", "9/8", "9/8"),
]


def F(s):
    return Fraction(s) if s is not None else None


def check_one(fname, title, port, *expect):
    path = os.path.join(ROOT, "netlists", fname)
    with open(path, encoding="utf-8") as f:
        card = NL.parse_card(f.read(), title_fallback=title)
    if card["port"] != port:
        return ["端口不符：卡里 %r，答案表 %r" % (card["port"], port)], None

    rl = F(expect[3])
    sol = CV.solve_card(card, rl=rl)
    th = sol["thevenin"]

    names = ["u_oc", "i_sc", "R_eq", "R_L", "i_L", "u_L", "P_L", "P_max"]
    got = [th.get("u_oc"), th.get("i_sc"), th.get("R_eq"), th.get("R_L"),
           th.get("i_L"), th.get("u_L"), th.get("P_L"), th.get("P_max")]

    diff = []
    for nm, exp_s, g in zip(names, expect, got):
        e = F(exp_s)
        if e is None:
            continue
        if g is None:
            diff.append("%s：答案 %s，但程序没算出这一项" % (nm, exp_s))
            continue
        if Fraction(g) != e:
            diff.append("%s：讲义答案 %s，程序 %s" % (nm, exp_s, g))
    return diff, dict(zip(names, got))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    verbose = "--verbose" in argv
    bad = 0
    for entry in KEY:
        fname, title, port = entry[0], entry[1], entry[2]
        expect = entry[3:]
        try:
            diff, got = check_one(fname, title, port, *expect)
        except NL.CardError as e:
            print("[失败] %s：%s" % (fname, e))
            bad += 1
            continue
        status = "通过" if not diff else "**不一致**"
        print("== %s ==  %s" % (title, status))
        if verbose and got:
            for k, v in got.items():
                if v is not None:
                    print("     %-5s = %s" % (k, v))
        if diff:
            bad += 1
            for d in diff:
                print("     [不一致] " + d)
    print("\n%d/%d 题与讲义答案完全一致" % (len(KEY) - bad, len(KEY)))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
