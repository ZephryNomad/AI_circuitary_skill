"""logic.py —— 数字电路（组合逻辑 / 时序逻辑）精确求解 + 穷举自检

为什么要单独一个文件
    tools/mna.py 与 tools/netlist.py 覆盖的是"模拟电路 / 电路原理"：元件、节点、
    电压电流。数字电路的题目不是这个结构——它给的是真值表、最小项、激励方程、
    状态表。硬塞进网表会两头不讨好，所以按题目结构分开建模，
    但共用同一套纪律：**答案必须能被穷举验证，不能只靠符号化简"看起来对"**。

覆盖的题目类型
    组合逻辑：真值表生成、最小项/最大项 → SOP/POS 最简式、卡诺图、门数统计、
              两级与非/或非实现、逐点穷举校验（含无关项语义）
    时序逻辑：状态转移表 → 次态 / 自启动检查 / 状态序列
              触发器激励求解（D / JK / T / RS）→ 由目标 Q 序列反推输入

题目卡语法（.logic）
    题名: 例 4-3 用卡诺图化简
    类型: 组合
    变量: A B C D
    最小项: 0 1 2 5 8 9 10
    无关项: 3 11 14 15
    形式: SOP

    题名: 由表达式写真值表
    类型: 组合
    变量: A B C
    表达式: (A & B) | (~A & C)

    题名: 状态表分析
    类型: 时序
    状态转移: 0 1 / 1 2 / 2 0 / 3 1

    题名: JK 激励求解
    类型: 时序
    触发器: JK
    Q序列: 0 1 0 0 1 0 1
"""
import itertools
import os
import re
import sys

from sympy import sympify, symbols
from sympy.logic.boolalg import And, Not, Or, false, simplify_logic, to_cnf, to_dnf, true

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


class LogicError(Exception):
    pass


# ----------------------------------------------------------------- 解析题目卡
def _strip_bom(text):
    return text[1:] if text.startswith("\ufeff") else text


def _ints(s):
    out = []
    for tok in re.split(r"[\s,，;；]+", s.strip()):
        if not tok:
            continue
        try:
            out.append(int(tok))
        except ValueError:
            raise LogicError("最小项/无关项 应为整数，收到 %r" % tok)
    return out


def parse_card(text, title_fallback="未命名"):
    text = _strip_bom(text)
    meta, rows = {}, []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("#") or ln.startswith("//"):
            continue
        m = re.match(r"^(题名|类型|变量|最小项|最大项|无关项|形式|表达式|状态转移|触发器|Q序列|初态|备注)\s*[:：]\s*(.*)$", ln)
        if m:
            meta[m.group(1)] = m.group(2).strip()
            continue
        rows.append(ln)
    for r in rows:
        # 允许纯数据行直接跟在 "状态转移:" 后面（每行 "现态 次态"）
        meta.setdefault("状态转移", "")
        meta["状态转移"] = (meta["状态转移"] + " / " + r).strip(" /")
    kind = meta.get("类型", "组合")
    if kind not in ("组合", "时序"):
        raise LogicError("类型只能是「组合」或「时序」，收到 %r" % kind)
    meta["类型"] = kind
    vars_ = (meta.get("变量") or "").replace(",", " ").split()
    meta["变量表"] = vars_
    return {"meta": meta, "title": meta.get("题名", title_fallback),
            "kind": kind, "vars": vars_}


# ----------------------------------------------------------------- 表达式工具
def _sym(expr_text, vars_):
    """把题卡里的布尔表达式文本转成 sympy 表达式。

    为什么不用 sympify 直接算：
        sympy 里 `^` 是**幂运算**，`A ^ B` 会变成 A**B，代值时就炸。
        而数字电路题里 `^` 恰恰表示异或。所以改用 Python AST 自己遍历，
        把 & | ^ ~ 明确映射成 And / Or / Xor / Not。
    """
    import ast

    s = expr_text
    s = (s.replace("·", "&").replace("∧", "&").replace("⋅", "&")
          .replace("∨", "|").replace("＋", "+").replace("⊕", "^")
          .replace("'", "~").replace("’", "~").replace("¯", "~")
          .replace("！", "~").replace("﹁", "~"))
    s = re.sub(r"\bNOT\b", "~", s, flags=re.I)
    s = re.sub(r"\bAND\b", "&", s, flags=re.I)
    s = re.sub(r"\bOR\b", "|", s, flags=re.I)
    s = re.sub(r"\bXOR\b", "^", s, flags=re.I)
    s = s.replace("+", "|")     # 数字电路里 + 常表示或

    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as ex:
        raise LogicError("表达式无法解析：%r（%s）" % (expr_text, ex))

    from sympy.logic.boolalg import Xor

    def conv(node):
        if isinstance(node, ast.Expression):
            return conv(node.body)
        if isinstance(node, ast.Name):
            if node.id in vars_:
                return symbols(node.id)
            raise LogicError("表达式里出现未声明的变量 %r（已声明：%s）"
                             % (node.id, " ".join(vars_)))
        if isinstance(node, ast.Constant):
            if node.value in (True, 1):
                return true
            if node.value in (False, 0):
                return false
            raise LogicError("表达式里出现非法常量 %r" % (node.value,))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Invert, ast.Not)):
            return Not(conv(node.operand))
        if isinstance(node, ast.BinOp):
            a, b = conv(node.left), conv(node.right)
            if isinstance(node.op, ast.BitAnd):
                return And(a, b)
            if isinstance(node.op, ast.BitOr):
                return Or(a, b)
            if isinstance(node.op, ast.BitXor):
                return Xor(a, b)
            raise LogicError("表达式里出现不支持的运算符 %r（只支持 & | ^ ~）"
                             % type(node.op).__name__)
        if isinstance(node, ast.BoolOp):
            vals = [conv(v) for v in node.values]
            return And(*vals) if isinstance(node.op, ast.And) else Or(*vals)
        raise LogicError("表达式里有不支持的写法：%s" % type(node).__name__)

    return conv(tree)


def _assign(vars_):
    return list(itertools.product([0, 1], repeat=len(vars_)))


def _idx(bits):
    n = 0
    for b in bits:
        n = n * 2 + int(b)
    return n


def _ev(e, vars_, bits):
    env = dict(zip([symbols(v) for v in vars_], [bool(b) for b in bits]))
    r = e.subs(env)
    return bool(r)


def _gate_count(e):
    """统计与/或/非门个数（常量与单文字不计门）。"""
    if isinstance(e, And):
        n = 1 if len(e.args) > 1 else 0
        return (n + sum(_gate_count(a)[0] for a in e.args),
                sum(_gate_count(a)[1] for a in e.args),
                sum(_gate_count(a)[2] for a in e.args))
    if isinstance(e, Or):
        n = 0
        a2 = 1 if len(e.args) > 1 else 0
        sub = [0, 0, 0]
        for a in e.args:
            g = _gate_count(a)
            sub = [sub[0] + g[0], sub[1] + g[1], sub[2] + g[2]]
        return (sub[0], sub[1] + a2, sub[2])
    if isinstance(e, Not):
        inner = e.args[0]
        g = _gate_count(inner)
        return (g[0], g[1], g[2] + 1)
    return (0, 0, 0)


def _kmaps(vars_, ones, dc):
    """生成卡诺图 ASCII。只支持 2/3/4 变量。"""
    n = len(vars_)
    dc = set(dc)
    ones = set(ones)
    if n == 2:
        rows = ["0", "1"]
        cols = ["0", "1"]
        def cell(r, c):
            return _idx([int(r), int(c)])
    elif n == 3:
        rows = ["0", "1"]
        cols = ["00", "01", "11", "10"]
        def cell(r, c):
            bit = {"00": (0, 0), "01": (0, 1), "11": (1, 1), "10": (1, 0)}[c]
            return _idx([int(r), bit[0], bit[1]])
    elif n == 4:
        rows = ["00", "01", "11", "10"]
        cols = ["00", "01", "11", "10"]
        def cell(r, c):
            rb = {"00": (0, 0), "01": (0, 1), "11": (1, 1), "10": (1, 0)}[r]
            cb = {"00": (0, 0), "01": (0, 1), "11": (1, 1), "10": (1, 0)}[c]
            return _idx([rb[0], rb[1], cb[0], cb[1]])
    else:
        return ["（卡诺图只画 2~4 变量）"]

    # 行变量 / 列变量
    if n == 2:
        row_lab, col_lab = vars_[0], vars_[1]
    elif n == 3:
        row_lab, col_lab = vars_[0], "%s%s" % (vars_[1], vars_[2])
    else:
        row_lab, col_lab = "%s%s" % (vars_[0], vars_[1]), "%s%s" % (vars_[2], vars_[3])

    w = max([len(c) for c in cols + rows] + [2]) + 2
    head = " " * (len(row_lab) + 3) + "".join(c.rjust(w) for c in cols)
    out = [head]
    out.append("%s \\ %s" % (row_lab.rjust(len(row_lab)), col_lab))
    for r in rows:
        line = [r.rjust(len(row_lab) + 2)]
        for c in cols:
            g = cell(r, c)
            mark = "X" if g in dc else ("1" if g in ones else "0")
            line.append(mark.rjust(w))
        out.append("".join(line))
    return out


# ----------------------------------------------------------------- 组合逻辑
def analyze_combo(card):
    vars_ = card["vars"]
    meta = card["meta"]
    if not vars_:
        raise LogicError("组合逻辑题必须写「变量: A B C ...」")
    n = len(vars_)
    syms = [symbols(v) for v in vars_]
    total = 1 << n

    ones = _ints(meta["最小项"]) if meta.get("最小项") else None
    dc = _ints(meta["无关项"]) if meta.get("无关项") else []
    expr_text = meta.get("表达式")

    if ones is not None and expr_text:
        raise LogicError("「最小项」与「表达式」只能给一个")
    if ones is None and not expr_text:
        raise LogicError("组合逻辑题需要「最小项:」或「表达式:」之一")

    if expr_text:
        e0 = _sym(expr_text, vars_)
        ones = [g for g in range(total) if _ev(e0, vars_, _bits(g, n))]
        source = "表达式 %s" % expr_text
    else:
        source = "最小项 m(%s)%s" % (
            ",".join(map(str, ones)),
            (" + d(%s)" % ",".join(map(str, dc))) if dc else "")

    for g in ones + dc:
        if not (0 <= g < total):
            raise LogicError("最小项 %d 超出 %d 变量范围 (0..%d)" % (g, n, total - 1))
    bad = set(ones) & set(dc)
    if bad:
        raise LogicError("这些编号同时出现在最小项与无关项里：%s" % sorted(bad))

    want = meta.get("形式", "SOP").upper()
    if want not in ("SOP", "POS"):
        raise LogicError("形式只能是 SOP 或 POS")

    sop = _sop(syms, ones, dc)
    pos = _pos(syms, ones, dc)
    main = sop if want == "SOP" else pos

    # 穷举校验：最小项必须为 1，非最小项非无关项必须为 0，无关项不约束
    viol = []
    for bits in _assign(vars_):
        g = _idx(bits)
        got_sop = _ev(sop, vars_, bits)
        got_pos = _ev(pos, vars_, bits)
        if g in ones:
            if not got_sop:
                viol.append(("SOP 该为 1", g))
            if not got_pos:
                viol.append(("POS 该为 1", g))
        elif g not in dc:
            if got_sop:
                viol.append(("SOP 该为 0", g))
            if got_pos:
                viol.append(("POS 该为 0", g))

    ga, go, gn = _gate_count(main)
    return {"source": source, "ones": ones, "dc": dc, "sop": sop, "pos": pos,
            "main": main, "form": want, "viol": viol, "gates": (ga, go, gn),
            "total_gates": ga + go + gn, "vars": vars_,
            "nand": _nand_form(sop, vars_)}


def _bits(g, n):
    return [(g >> (n - 1 - i)) & 1 for i in range(n)]


def _sop(syms, ones, dc):
    if not ones:
        return false
    if len(ones) + len(dc) == (1 << len(syms)):
        return true
    return SOPform(syms, ones, dc)


def _pos(syms, ones, dc):
    if not ones:
        return false
    if len(ones) + len(dc) == (1 << len(syms)):
        return true
    return POSform(syms, ones, dc)


from sympy import SOPform, POSform  # noqa: E402


def _nand_form(expr, vars_):
    """把 SOP 最简式写成两级与非实现。

    原理：F = P1 + P2 + … = NAND(¬P1, ¬P2, …)，最后一级与非门的每个输入
    必须是某个乘积项的**补**：
      · Pi 含多个字面量 → ¬Pi 正好是与非门输出，直接用；
      · Pi = ¬x（单字面量）→ ¬Pi = x，原变量直接当输入，不加门；
      · Pi = x（单字面量）→ ¬Pi = ¬x，需要一个与非门做反相器。
    """
    if expr in (true, false):
        return "常量，无需门"
    d = to_dnf(expr, force=True)
    terms = list(d.args) if isinstance(d, Or) else [d]
    lines, neg = [], []
    cnt = [0]

    def new():
        cnt[0] += 1
        return "N%d" % cnt[0]

    def lit_sig(l):
        """把一个字面量变成与非门的输入信号名（需要时先造反相器）。"""
        if isinstance(l, Not):
            x = l.args[0]
            n = new()
            lines.append("%-4s = NAND(%s,%s)  反相器，得 ¬%s" % (n, x, x, x))
            return n
        return str(l)

    for t in terms:
        if isinstance(t, And):
            sig = [lit_sig(l) for l in t.args]
            n = new()
            lines.append("%-4s = NAND(%s)  → ¬(%s)" % (n, ",".join(sig), "·".join(sig)))
            neg.append(n)
        elif isinstance(t, Not):
            # Pi = ¬x ⇒ ¬Pi = x
            neg.append(str(t.args[0]))
        else:
            # Pi = x ⇒ ¬Pi = ¬x
            n = new()
            x = str(t)
            lines.append("%-4s = NAND(%s,%s)  反相器，得 ¬%s" % (n, x, x, x))
            neg.append(n)

    if len(neg) == 1:
        # F = Pi 单项：最后一级做两次取反
        lines.append("%-4s = NAND(%s,%s)  → F" % ("F", neg[0], neg[0]))
    else:
        lines.append("%-4s = NAND(%s)  → F" % ("F", ",".join(neg)))
    lines.append("")
    lines.append("与非门总数：**%d**（其中反相器 %d 个）"
                 % (cnt[0] + 1, sum(1 for s in lines if "反相器" in s)))
    return "\n".join(lines)


# ----------------------------------------------------------------- 时序逻辑
FF_TABLE = {
    # 触发器: (现态 q, 次态 qn) -> 输入, 描述
    "D": {(0, 0): "D=0", (0, 1): "D=1", (1, 0): "D=0", (1, 1): "D=1"},
    "T": {(0, 0): "T=0", (0, 1): "T=1", (1, 0): "T=1", (1, 1): "T=0"},
    "JK": {(0, 0): "J=0 K=X", (0, 1): "J=1 K=X", (1, 0): "J=X K=1", (1, 1): "J=X K=0"},
    "RS": {(0, 0): "R=X S=0", (0, 1): "R=0 S=1", (1, 0): "R=1 S=0", (1, 1): "R=0 S=X"},
}


def analyze_seq(card):
    meta = card["meta"]
    ff = (meta.get("触发器") or "").upper()
    qseq = meta.get("Q序列")
    trans = meta.get("状态转移")

    if ff and qseq:
        if ff not in FF_TABLE:
            raise LogicError("触发器只能是 D / JK / T / RS，收到 %r" % ff)
        seq = _ints(qseq)
        if any(x not in (0, 1) for x in seq):
            raise LogicError("Q序列 只能是 0 和 1")
        rows = []
        for i in range(len(seq) - 1):
            q, qn = seq[i], seq[i + 1]
            rows.append((i + 1, q, qn, FF_TABLE[ff][(q, qn)]))
        return {"mode": "激励", "ff": ff, "seq": seq, "rows": rows}

    if trans:
        pairs = []
        for chunk in trans.split("/"):
            chunk = chunk.strip()
            if not chunk:
                continue
            nums = [int(x) for x in re.split(r"[\s,，>→>=-]+", chunk) if x.strip().lstrip("-").isdigit()]
            if len(nums) < 2:
                raise LogicError("状态转移的每段要写成「现态 次态」，收到 %r" % chunk)
            pairs.append((nums[0], nums[1]))
        if not pairs:
            raise LogicError("状态转移为空")
        cur = [p[0] for p in pairs]
        if "初态" in meta:
            s = int(meta["初态"])
        else:
            s = min(cur)
        seen, seq = [], []
        while s not in seen:
            seen.append(s)
            seq.append(s)
            nxt = dict(pairs).get(s)
            if nxt is None:
                break
            s = nxt
        # 自启动：从所有未在闭环内的编码出发能否回到闭环
        loop = set(seq[seq.index(s):]) if s in dict(pairs) or True else set(seq)
        cyc_start = seen.index(s) if s in seen else 0
        cyc = seen[cyc_start:]
        reach = {}
        for st in sorted(set(cur) | {p[1] for p in pairs}):
            x, path = st, []
            for _ in range(len(pairs) + 2):
                path.append(x)
                if x in cyc:
                    break
                x = dict(pairs).get(x)
                if x is None:
                    break
            reach[st] = (x is not None and x in cyc, path)
        return {"mode": "状态表", "pairs": pairs, "cycle": cyc,
                "reach": reach, "start": seq[0], "walk": seq}

    raise LogicError("时序题需要「触发器:」+「Q序列:」，或「状态转移:」")


# ----------------------------------------------------------------- 报告
def report(card):
    L = []
    meta = card["meta"]
    L.append("# %s" % card["title"])
    if meta.get("备注"):
        L.append("> %s" % meta["备注"])
    L.append("")

    if card["kind"] == "组合":
        r = analyze_combo(card)
        L.append("## 一、题目给定的函数")
        L.append("")
        L.append("- 变量：%s（共 %d 个，%d 种输入）" % (" ".join(r["vars"]), len(r["vars"]), 1 << len(r["vars"])))
        L.append("- 来源：%s" % r["source"])
        L.append("")
        L.append("## 二、卡诺图")
        L.append("")
        L.append("```")
        L.extend(_kmaps(r["vars"], r["ones"], r["dc"]))
        L.append("```")
        L.append("")
        L.append("## 三、最简式")
        L.append("")
        L.append("- **最简与或式（SOP）：** `F = %s`" % r["sop"])
        L.append("- **最简或与式（POS）：** `F = %s`" % r["pos"])
        L.append("")
        L.append("## 四、门数统计（按 %s 式）" % r["form"])
        L.append("")
        L.append("| 与门 | 或门 | 非门 | 合计 |")
        L.append("|---|---|---|---|")
        L.append("| %d | %d | %d | **%d** |" % (r["gates"][0], r["gates"][1], r["gates"][2], r["total_gates"]))
        L.append("")
        L.append("## 五、两级与非实现")
        L.append("")
        L.append("```")
        L.append(r["nand"])
        L.append("```")
        L.append("")
        L.append("## 六、穷举校验")
        L.append("")
        if r["viol"]:
            L.append("- **未通过**，违例 %d 项：%s" % (len(r["viol"]), r["viol"][:8]))
        else:
            L.append("- **通过**：%d 种输入逐点代入，最小项全为 1、非最小项全为 0，SOP 与 POS 各自成立（无关项不参与约束）" % (1 << len(r["vars"])))
        return "\n".join(L), (not r["viol"])

    r = analyze_seq(card)
    L.append("## 一、题意")
    L.append("")
    if r["mode"] == "激励":
        L.append("- 触发器类型：%s" % r["ff"])
        L.append("- 目标 Q 序列：%s" % r["seq"])
    else:
        L.append("- 状态转移对：%s" % r["pairs"])
    L.append("")
    if r["mode"] == "激励":
        L.append("## 二、逐拍激励（由现态与次态查激励表反推）")
        L.append("")
        L.append("| 拍 | Qⁿ | Qⁿ⁺¹ | 需要的输入 |")
        L.append("|---|---|---|---|")
        for t, q, qn, need in r["rows"]:
            L.append("| %d | %d | %d | `%s` |" % (t, q, qn, need))
        L.append("")
        L.append("## 三、校验")
        L.append("")
        L.append("- 每一拍都用对应触发器的激励表反查，逐拍可复核；Q 序列首尾相接处即一次状态转移")
        return "\n".join(L), True
    else:
        L.append("## 二、状态序列")
        L.append("")
        L.append("- 从初态出发的走法：%s" % " → ".join(map(str, r["walk"])))
        L.append("- 进入的闭环：%s" % " → ".join(map(str, r["cycle"] + [r["cycle"][0]])))
        L.append("")
        L.append("## 三、自启动检查")
        L.append("")
        L.append("| 起始编码 | 能否回到闭环 | 路径 |")
        L.append("|---|---|---|")
        for st in sorted(r["reach"]):
            ok, path = r["reach"][st]
            L.append("| %d | %s | %s |" % (st, "能" if ok else "**不能（挂死）**", " → ".join(map(str, path))))
        L.append("")
        allok = all(v[0] for v in r["reach"].values())
        L.append("- 结论：%s" % ("全部编码都能自启动" if allok else "存在无法回到闭环的编码，电路不能自启动"))
        return "\n".join(L), allok


def main(argv=None):
    # Windows 控制台默认 GBK，报告里有 ¬ 等字符会直接抛 UnicodeEncodeError。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("用法：python tools/logic.py netlists\\xxx.logic [--outdir out\\logic] [--selftest]",
              file=sys.stderr)
        return 2
    outdir, selftest = None, "--selftest" in argv
    paths = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--outdir":
            outdir = argv[i + 1]
            i += 2
            continue
        if a.startswith("--"):
            i += 1
            continue
        if os.path.isdir(a):
            paths.extend(sorted(os.path.join(a, f) for f in os.listdir(a) if f.endswith(".logic")))
            i += 1
            continue
        paths.append(a)
        i += 1
    if not paths:
        print("没有找到 .logic 题目卡", file=sys.stderr)
        return 2
    bad = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            card = parse_card(f.read(), os.path.basename(p))
        try:
            md, ok = report(card)
        except LogicError as e:
            print("[失败] %s：%s" % (p, e), file=sys.stderr)
            bad += 1
            continue
        if not ok:
            bad += 1
        if outdir:
            os.makedirs(outdir, exist_ok=True)
            stem = os.path.splitext(os.path.basename(p))[0]
            with open(os.path.join(outdir, stem + ".md"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(md + "\n")
        else:
            print(md)
            print()
            print("-" * 70)
    if selftest:
        if bad:
            print("自检未通过 %d 项" % bad, file=sys.stderr)
            return 1
        print("自检全部通过：%d 张数字电路卡" % len(paths))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
