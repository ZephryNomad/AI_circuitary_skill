"""convert.py —— 电路题目卡转网表 + 用精确 MNA 复算 + 往返一致性自检

用法
    python tools/convert.py netlists/例1.card          # 单张：打印网表与解答
    python tools/convert.py netlists --all             # 全目录批量
    python tools/convert.py netlists --all --outdir out/netlists
    python tools/convert.py netlists --all --json out/netlists/汇总.json

三层职责分得很清
    netlist.py   纯文本层：题目卡 <-> SPICE 网表，双向可逆，不做任何数值计算
    mna.py       纯求解层：sympy 精确 MNA，除源法/外加电源法取戴维宁参数
    本文件       串联层：读卡 -> 出网表 -> 网表再解析 -> 求解 -> 比对三者

自检（--selftest）会同时查两件事，任何一件不通过就返回非零退出码：
    A. 往返一致：card -> spice -> parse_spice 后的元件序列必须与原卡逐字段相等；
    B. 求解一致：解析回来的网表算出的 u_oc / i_sc / R_eq 必须与原卡算出的完全相等。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mna
from netlist import (CardError, netlist_table, nodes_of, parse_card,
                     parse_spice, to_mna, to_spice)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _sym(fr):
    """Fraction -> sympy 精确有理数（mna.py 要求 sympy 能直接吃）。"""
    from sympy import Rational
    return Rational(fr.numerator, fr.denominator)


def _to_sym_mna(elements):
    """to_mna 的 sympy 版本：把每个 Fraction 换成 Rational，保证全程无浮点。"""
    out = []
    for e in to_mna(elements):
        kind = e[0]
        if kind in ("R", "I"):
            out.append((kind, e[1], e[2], _sym(e[3])))
        elif kind == "V":
            out.append((kind, e[1], e[2], _sym(e[3]), e[4]))
        elif kind == "VCVS":
            out.append((kind, e[1], e[2], e[3], e[4], _sym(e[5]), e[6]))
        elif kind == "VCCS":
            out.append((kind, e[1], e[2], e[3], e[4], _sym(e[5])))
        elif kind == "CCVS":
            out.append((kind, e[1], e[2], e[3], _sym(e[4]), e[5]))
        elif kind == "CCCS":
            out.append((kind, e[1], e[2], e[3], _sym(e[4])))
        else:
            raise CardError("未知元件类型 %r" % kind)
    return out


# ------------------------------------------------------------------ 求解
def _i_branch(e, V, I):
    """按元件自身定义求「由 n1 经元件流向 n2」的电流。

    整个模块只承认这一套符号约定，报告里的正负号才有一致含义：
      R            欧姆定律 (V(n1)-V(n2))/R
      V/E/H        取 MNA 的源支路电流，I>0 即由 n1 经源流向 n2
      I            等于源值（I 元组的定义就是 n1 经源流向 n2）
      G            g*(V(c1)-V(c2))
      F            k*I(控制电压源)
    """
    k = e["kind"]
    if k == "R":
        return (V[e["n1"]] - V[e["n2"]]) / _sym(e["value"])
    if k in ("V", "E", "H"):
        return I[e["name"]]
    if k == "I":
        return _sym(e["value"])
    if k == "G":
        return _sym(e["value"]) * (V[e["c1"]] - V[e["c2"]])
    if k == "F":
        return _sym(e["value"]) * I[e["ctrl"]]
    raise CardError("未知元件类型 %r" % k)


def branches(card, sol):
    """列出每个元件的支路电流（n1 -> n2 为正）。"""
    out = []
    for e in card["elements"]:
        out.append({"name": e["name"], "kind": e["kind"], "n1": e["n1"],
                    "n2": e["n2"], "orig": e.get("_orig"),
                    "i": _i_branch(e, sol["V"], sol["I"])})
    return out


def power_balance(card, sol):
    """逐元件算吸收功率 p = u*i（u=V(n1)-V(n2)，i 由 n1 流向 n2），并求总和。

    这是基尔霍夫定律之外的一条独立约束（特勒根定理）：无源网络里全部元件
    吸收功率的代数和必须严格为 0，因为精确有理数运算下不该有舍入残差。
    它专门用来证伪一类"数值自洽但物理可疑"的解——比如某几个支路电流全为 0，
    到底是元件真的没电流，还是节点方程写错了导致虚假的零。若功率不平，
    说明网表与电路不是同一个东西。
    """
    rows = []
    total = 0
    for e in card["elements"]:
        i = _i_branch(e, sol["V"], sol["I"])
        u = sol["V"][e["n1"]] - sol["V"][e["n2"]]
        p = u * i
        total += p
        rows.append({"name": e["name"], "kind": e["kind"], "n1": e["n1"],
                     "n2": e["n2"], "orig": e.get("_orig"),
                     "u": u, "i": i, "p": p})
    return rows, total


def solve_card(card, rl=None):
    """对一张题目卡做直流分析，返回 dict（节点电压、源电流、支路电流、戴维宁参数）。

    节点电压一律以电路自身的地（节点 0）为参考显示；
    卡里有 '端口' 时，u_oc / i_sc / R_eq 由 mna.thevenin 以端口 b 为参考独立算出。
    两者参考点可能不同，所以报告里必须写明，否则会把某个节点电压读成
    0 以外的数而困惑。没有端口时只做直流分析（求支路电流、节点电压）。
    """
    from netlist import KIND_CN  # noqa: F401  （报告里按中文名展示元件类型）
    net = _to_sym_mna(card["elements"])
    present = nodes_of(card["elements"])
    if not present:
        raise CardError("题目卡里没有任何元件")
    port = card["port"]
    if port:
        a, b = port
        for nd in (a, b):
            if nd not in present:
                raise CardError("端口节点 %r 没有接到任何元件上" % nd)
        ref = "0" if "0" in present else b
    else:
        ref = "0" if "0" in present else present[0]
    try:
        V, I = mna.solve(net, ground=ref)
    except Exception as e:
        raise CardError("节点法矩阵不可解（%s）：常见原因是存在只由电压源构成的回路，"
                        "或某节点悬空" % type(e).__name__)
    th = None
    if port:
        try:
            th = mna.thevenin(net, a, b,
                              rl=(_sym(rl) if rl is not None else None))
        except Exception as e:
            raise CardError("求戴维宁参数时矩阵不可解（%s）：多半是端口 a-b 之间正好跨着"
                            "一个理想电压源，短路后变成两个电压源并联；换个端口或加串联电阻"
                            % type(e).__name__)
    sol = {"V": V, "I": I, "thevenin": th, "ref": ref}
    sol["branches"] = branches(card, sol)
    sol["asks"] = resolve_asks(card, sol)
    sol["power"], sol["p_total"] = power_balance(card, sol)
    return sol


# --------------------------------------------------------- 求什么就回答什么
ASK_V_RE = None


def _lookup(card, name):
    for e in card["elements"]:
        if e["name"] == name or e.get("_orig") == name:
            return e
    return None


def resolve_asks(card, sol):
    """把卡里 '求: xxx' 的每一项解析成 (标签, 值, 单位)。

    支持的写法：
        R3          元件 R3 由 n1 流向 n2 的电流
        I(R3)       同上
        V(3)        节点 3 相对参考点的电压
        V(2,3)      V(2)-V(3)
    """
    import re as _re
    out = []
    for raw in card["meta"].get("asks", []):
        tok = raw.strip()
        m = _re.match(r"^[VUv]\(\s*([^,)\s]+)\s*(?:,\s*([^,)\s]+)\s*)?\)$", tok)
        if m:
            n1, n2 = m.group(1), (m.group(2) or sol["ref"])
            for nd in (n1, n2):
                if nd not in sol["V"]:
                    raise CardError("求: %s —— 节点 %r 不存在" % (tok, nd))
            if n2 == sol["ref"]:
                label = "V(%s)" % n1
            else:
                label = "V(%s)-V(%s)" % (n1, n2)
            out.append((label, sol["V"][n1] - sol["V"][n2], "V"))
            continue
        m = _re.match(r"^[Ii]\(\s*(.+?)\s*\)$", tok)
        nm = m.group(1) if m else tok
        e = _lookup(card, nm)
        if e is None:
            raise CardError("求: %s —— 找不到名为 %r 的元件" % (tok, nm))
        i = _i_branch(e, sol["V"], sol["I"])
        out.append(("I(%s) 由 %s 流向 %s" % (e["name"], e["n1"], e["n2"]),
                    i, "A"))
    return out


# ------------------------------------------------------------- 往返自检
def _norm(e):
    """把元件 dict 归一化成可比较的元组（只留语义字段）。"""
    k = e["kind"]
    if k in ("R", "V", "I"):
        return (k, e["name"], e["n1"], e["n2"], e["value"])
    if k in ("E", "G"):
        return (k, e["name"], e["n1"], e["n2"], e["c1"], e["c2"], e["value"])
    return (k, e["name"], e["n1"], e["n2"], e["ctrl"], e["value"])


def roundtrip(card):
    """返回 (spice_text, parsed_card, 差异列表)。差异为空即往返一致。"""
    txt = to_spice(card)
    back = parse_spice(txt)
    lhs = [_norm(e) for e in card["elements"]]
    rhs = [_norm(e) for e in back["elements"]]
    diff = []
    if len(lhs) != len(rhs):
        diff.append("元件个数不同：原卡 %d，网表解析回 %d" % (len(lhs), len(rhs)))
    for i, (x, y) in enumerate(zip(lhs, rhs)):
        if x != y:
            diff.append("第 %d 个元件不同：原卡 %r，网表解析回 %r" % (i + 1, x, y))
    return txt, back, diff


def solve_consistency(card, rl=None):
    """原卡求解 vs 网表再解析后求解，逐项比较。返回 (原解, 回读解, 差异)。

    两条独立通道必须给出同一组数：
      通道1  题目卡 -> to_mna -> MNA
      通道2  题目卡 -> to_spice 文本 -> parse_spice -> to_mna -> MNA
    有端口时比戴维宁三参数，无端口时比全部支路电流；两者都比全部节点电压。
    """
    s1 = solve_card(card, rl)
    _, back, _ = roundtrip(card)
    back["port"] = card["port"]
    s2 = solve_card(back, rl)
    diff = []
    for nd in sorted(s1["V"]):
        if nd not in s2["V"]:
            diff.append("节点 %s 只在原卡中出现" % nd)
        elif s1["V"][nd] != s2["V"][nd]:
            diff.append("V(%s)：原卡 %s，网表 %s" % (nd, s1["V"][nd], s2["V"][nd]))
    if s1["thevenin"] is not None:
        for key in ("u_oc", "i_sc", "R_eq"):
            if s1["thevenin"][key] != s2["thevenin"][key]:
                diff.append("%s：原卡 %s，网表 %s"
                            % (key, s1["thevenin"][key], s2["thevenin"][key]))
    for b1, b2 in zip(s1["branches"], s2["branches"]):
        if b1["i"] != b2["i"]:
            diff.append("I(%s)：原卡 %s，网表 %s" % (b1["name"], b1["i"], b2["i"]))
    # 功率平衡是独立于节点方程的物理约束，两条通道都必须严格为 0
    for tag, s in (("原卡", s1), ("网表", s2)):
        if s["p_total"] != 0:
            diff.append("功率不平衡（%s）：全部元件吸收功率之和 = %s，应为 0"
                        % (tag, s["p_total"]))
    return s1, s2, diff


# ------------------------------------------------------------------ 输出
def report(card, path, rl=None):
    """生成一份人读报告（markdown 文本）。"""
    txt, back, rdiff = roundtrip(card)
    sol = solve_card(card, rl)
    L = []
    L.append("## %s" % card["title"])
    if card["meta"].get("note"):
        L.append("")
        L.append("> %s" % card["meta"]["note"])
    L.append("")
    L.append("源文件：`%s`" % path)
    L.append("")
    L.append("### 一、元件清单与网表对照")
    L.append("")
    L.append("| 元件 | 类型 | 电路描述 | SPICE 语句 |")
    L.append("|---|---|---|---|")
    for name, kind_cn, desc, spice in netlist_table(card):
        L.append("| `%s` | %s | %s | `%s` |" % (name, kind_cn, desc, spice))
    L.append("")
    L.append("### 二、生成的 SPICE 网表")
    L.append("")
    L.append("```spice")
    L.append(txt.rstrip())
    L.append("```")
    L.append("")
    L.append("### 三、独立复算（精确有理数解，非浮点）")
    L.append("")
    if sol["asks"]:
        L.append("**题目所求：**")
        L.append("")
        L.append("| 待求量 | 结果 |")
        L.append("|---|---|")
        for label, val, unit in sol["asks"]:
            L.append("| %s | **%s %s** |" % (label, val, unit))
        L.append("")
    L.append("节点电压以电路自身参考点 %s 为 0："
             % sol["ref"])
    L.append("")
    L.append("| 量 | 值 |")
    L.append("|---|---|")
    for nd in sorted(sol["V"], key=lambda x: (x != "0", x)):
        L.append("| 节点电压 V(%s) | %s V |" % (nd, sol["V"][nd]))
    L.append("")
    L.append("各支路电流（正方向 n1 → n2，即从元件第一端经元件流向第二端）：")
    L.append("")
    L.append("| 元件 | 类型 | 支路 | 电流 |")
    L.append("|---|---|---|---|")
    for b in sol["branches"]:
        nm = b["name"] if not b["orig"] else "%s（原写 %s）" % (b["name"], b["orig"])
        L.append("| `%s` | %s | %s → %s | %s A |"
                 % (nm, b["kind"], b["n1"], b["n2"], b["i"]))
    L.append("")
    L.append("功率平衡校核（每行 p = u·i，u=V(n1)-V(n2)，i 由 n1 流向 n2；"
             "吸收为正式）：")
    L.append("")
    L.append("| 元件 | 支路 | u | i | p = u·i |")
    L.append("|---|---|---|---|---|")
    for r in sol["power"]:
        nm = r["name"] if not r["orig"] else "%s（原写 %s）" % (r["name"], r["orig"])
        L.append("| `%s` | %s → %s | %s V | %s A | %s W |"
                 % (nm, r["n1"], r["n2"], r["u"], r["i"], r["p"]))
    L.append("| **合计** |  |  |  | **%s W** |" % sol["p_total"])
    L.append("")
    th = sol["thevenin"]
    if th is not None:
        L.append("戴维宁等效（端口 a-b）：")
        L.append("")
        L.append("| 量 | 值 |")
        L.append("|---|---|")
        L.append("| 开路电压 u_oc | %s V |" % th["u_oc"])
        L.append("| 短路电流 i_sc | %s A |" % th["i_sc"])
        L.append("| 等效电阻 R_eq | %s Ω |" % th["R_eq"])
        if "u_oc/i_sc" in th:
            ok = "一致" if th["u_oc/i_sc"] == th["R_eq"] else "不一致"
            L.append("| 校验 u_oc/i_sc | %s Ω（与 R_eq %s） |"
                     % (th["u_oc/i_sc"], ok))
        if "R_L" in th:
            L.append("| 接 R_L=%s Ω 时 u_L | %s V |" % (th["R_L"], th["u_L"]))
            L.append("| 接 R_L=%s Ω 时 i_L | %s A |" % (th["R_L"], th["i_L"]))
            L.append("| 接 R_L=%s Ω 时 P_L | %s W |" % (th["R_L"], th["P_L"]))
            L.append("| 最大功率 P_max | %s W（在 R_L=R_eq=%s Ω 时取得） |"
                     % (th["P_max"], th["R_eq"]))
        L.append("")
    L.append("### 四、自检")
    L.append("")
    L.append("- 往返一致：%s" % ("通过" if not rdiff else "**失败** " + "；".join(rdiff)))
    L.append("- 功率平衡：%s（全部元件吸收功率之和 = %s W）"
             % ("通过" if sol["p_total"] == 0 else "**失败**", sol["p_total"]))
    L.append("")
    return "\n".join(L), rdiff


# ------------------------------------------------------------------ CLI
def load_cards(dirpath):
    out = []
    for fn in sorted(os.listdir(dirpath)):
        if fn.lower().endswith((".card", ".dsl", ".net")):
            p = os.path.join(dirpath, fn)
            with open(p, encoding="utf-8") as f:
                txt = f.read()
            out.append((p, parse_card(txt, title_fallback=os.path.splitext(fn)[0])))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="电路题目卡 -> SPICE 网表 + 精确复算")
    ap.add_argument("target", help="单个 .card 文件，或含多张卡的目录")
    ap.add_argument("--all", action="store_true", help="target 是目录时批量处理")
    ap.add_argument("--outdir", default=None, help="报告与网表输出目录")
    ap.add_argument("--rl", default=None, help="负载电阻（可选）")
    ap.add_argument("--json", default=None, help="把全部结果汇总成 JSON")
    ap.add_argument("--selftest", action="store_true", help="跑往返+求解双自检")
    args = ap.parse_args(argv)

    from fractions import Fraction
    rl = Fraction(args.rl) if args.rl else None

    if args.all or os.path.isdir(args.target):
        cards = load_cards(args.target)
    else:
        with open(args.target, encoding="utf-8") as f:
            txt = f.read()
        cards = [(args.target,
                  parse_card(txt, title_fallback=os.path.splitext(
                      os.path.basename(args.target))[0]))]
    if not cards:
        print("没有找到任何题目卡（.card/.dsl/.net）", file=sys.stderr)
        return 2

    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)

    fails = []
    bundle = []
    for path, card in cards:
        try:
            text, rdiff = report(card, path, rl)
        except CardError as e:
            print("[跳过] %s：%s" % (path, e), file=sys.stderr)
            fails.append((path, str(e)))
            continue
        if args.outdir:
            stem = os.path.splitext(os.path.basename(path))[0]
            # newline="\n" 是必须的：否则 Windows 上会把 \n 翻成 \r\n，
            # 同一份产物在 Linux 与 Windows 上生成出不同字节，diff 一片红。
            with open(os.path.join(args.outdir, stem + ".md"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(text)
            with open(os.path.join(args.outdir, stem + ".cir"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(to_spice(card))
        else:
            print(text)
        if rdiff:
            fails.append((path, "往返不一致"))

        if args.selftest:
            s1, s2, sdiff = solve_consistency(card, rl)
            if sdiff:
                fails.append((path, "求解不一致：" + "；".join(sdiff)))
            th1 = s1["thevenin"] or {}
            bundle.append({
                "file": os.path.basename(path),
                "title": card["title"],
                "port": list(card["port"]) if card["port"] else None,
                "elements": len(card["elements"]),
                "asks": [{"label": lb, "value": str(v), "unit": u}
                         for lb, v, u in s1["asks"]],
                "branches": [{"name": b["name"], "kind": b["kind"],
                              "n1": b["n1"], "n2": b["n2"],
                              "i": str(b["i"])} for b in s1["branches"]],
                "V": {k: str(v) for k, v in s1["V"].items()},
                "u_oc": str(th1.get("u_oc", "")),
                "i_sc": str(th1.get("i_sc", "")),
                "R_eq": str(th1.get("R_eq", "")),
                "roundtrip": "ok" if not rdiff else "fail",
                "solve": "ok" if not sdiff else "fail",
            })

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("已写出 %s（%d 条）" % (args.json, len(bundle)))

    if fails:
        print("\n自检未通过 %d 项：" % len(fails), file=sys.stderr)
        for p, why in fails:
            print("  - %s：%s" % (p, why), file=sys.stderr)
        return 1
    if args.selftest:
        print("\n自检全部通过：%d 张卡，往返一致 + 求解一致" % len(cards))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
