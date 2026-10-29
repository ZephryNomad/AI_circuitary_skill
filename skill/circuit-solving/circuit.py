#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""circuit.py —— 电路题求解器（单文件 / 只用 Python 标准库 / 无需联网 / 无需装包）

为什么是单文件
    给"什么都没装"的环境用：复制这一个 .py 就能跑，只用 Python 标准库。
    直流与相量两条通道全部走 fractions.Fraction（精确有理数），不做浮点近似
    —— 于是"算错"只可能来自题型判读（拓扑/极性/参考方向），不可能来自数值
    误差，排查范围因此缩到唯一一个可疑环节。瞬态例外，用浮点：它是指数逼近，
    理由与精度保证见 analyze_tran 的注释。

四条通道
    card  线性直流：节点法(MNA) + 戴维宁/诺顿 + 功率平衡自检
    ac    正弦稳态相量：把 jωL、1/(jωC) 当阻抗，同一套 MNA
    tran  瞬态：后向欧拉逐步积分（C/L 用伴随模型），与解析解对照收敛
    logic 数字逻辑：真值表穷举 + Quine-McCluskey 最简式 + 卡诺图 + 时序激励

命令
    python circuit.py selftest [--verbose]
    python circuit.py card  题.card [--rl 3] [--json]
    python circuit.py ac    题.card [--w 1000 | --f 50] [--sweep 10,1e5,20]
    python circuit.py tran  题.card [--dt 1e-5 --tstop 5e-3 --at 1e-3,5e-3 --ic C1=0]
    python circuit.py logic 题.logic
    python circuit.py deck  题.card          # 打印 SPICE 网表，可喂 ngspice 当第二意见

题目卡语法见同目录 SKILL.md；一句话：一行一个元件，方向靠节点顺序表达。
"""

import json
import math
import os
import re
import sys
from fractions import Fraction

TAU2PI = Fraction(3141592653589793, 10 ** 15)   # π 的 15 位有理近似，f→ω 用


# ============================================================ 精确复数
class Q(object):
    """a + b·i，a、b 都是 Fraction。直流时 b 恒为 0，相量时才有虚部。"""

    __slots__ = ("re", "im")

    def __init__(self, re=0, im=0):
        self.re = _frac(re)
        self.im = _frac(im)

    @staticmethod
    def of(x):
        return x if isinstance(x, Q) else Q(x)

    def __add__(s, o):
        o = Q.of(o)
        return Q(s.re + o.re, s.im + o.im)

    __radd__ = __add__

    def __sub__(s, o):
        o = Q.of(o)
        return Q(s.re - o.re, s.im - o.im)

    def __rsub__(s, o):
        return Q.of(o) - s

    def __mul__(s, o):
        o = Q.of(o)
        return Q(s.re * o.re - s.im * o.im, s.re * o.im + s.im * o.re)

    __rmul__ = __mul__

    def __truediv__(s, o):
        o = Q.of(o)
        d = o.re * o.re + o.im * o.im
        if d == 0:
            raise ZeroDivisionError("除以零：检查是否有 R=0 或短路支路")
        return Q((s.re * o.re + s.im * o.im) / d, (s.im * o.re - s.re * o.im) / d)

    def __rtruediv__(s, o):
        return Q.of(o) / s

    def __neg__(s):
        return Q(-s.re, -s.im)

    def __eq__(s, o):
        o = Q.of(o)
        return s.re == o.re and s.im == o.im

    def __ne__(s, o):
        return not s.__eq__(o)

    def __hash__(s):
        return hash((s.re, s.im))

    def __bool__(s):
        return not (s.re == 0 and s.im == 0)

    def is0(s):
        return s.re == 0 and s.im == 0

    def __abs__(s):
        return math.hypot(float(s.re), float(s.im))

    def __float__(s):
        if s.im != 0:
            raise TypeError("复数量不能转成 float（虚部 %s 不为 0）" % s.im)
        return float(s.re)

    def conj(s):
        return Q(s.re, -s.im)

    def __repr__(s):
        return "Q(%s,%s)" % (s.re, s.im)


def _frac(x):
    """把输入收进 Q 的实部/虚部。

    注意 float 会被「原样保留」而不是转成 Fraction：直流与相量两条通道里永远只
    出现 Fraction（精确），而瞬态必须用浮点——见 analyze_tran 里的说明。
    """
    if isinstance(x, (Fraction, float)):
        return x
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, Q):
        if x.im != 0:
            raise TypeError("这里需要实数，给的是复数")
        return x.re
    if isinstance(x, str):
        return Fraction(x)
    raise TypeError("无法转成有理数：%r" % (x,))


def _fs(v):
    if isinstance(v, float):
        return fd(v)
    v = Fraction(v)
    if v.denominator == 1:
        return str(v.numerator)
    return "%d/%d" % (v.numerator, v.denominator)


def fs(x):
    """精确字符串：12 / -3/2 / 500/9 / 1/3 + 2/5i"""
    q = Q.of(x)
    if q.im == 0:
        return _fs(q.re)
    if q.re == 0:
        return _fs(q.im) + "i"
    return "%s %s %si" % (_fs(q.re), "+" if q.im > 0 else "-", _fs(abs(q.im)))


def fd(x, sig=6):
    """十进制近似，便于核对答案量级。"""
    q = Q.of(x)

    def one(v):
        f = float(v)
        if f != 0 and (abs(f) >= 1e6 or abs(f) < 1e-4):
            return "%.*e" % (sig - 1, f)
        return "%.*g" % (sig, f)

    if q.im == 0:
        return one(q.re)
    if q.re == 0:
        return one(q.im) + "i"
    return "%s %s %si" % (one(q.re), "+" if q.im > 0 else "-", one(abs(q.im)))


def fnum(x):
    """精确值 + 近似值：'500/9 ≈55.5556'（整数只给精确值）"""
    q = Q.of(x)
    if q.im == 0 and q.re.denominator == 1:
        return _fs(q.re)
    return "%s ≈%s" % (fs(q), fd(q))


# ============================================================ 数值解析
_MUL = {"": Fraction(1),
        "k": Fraction(1000), "K": Fraction(1000),
        "M": Fraction(10 ** 6), "meg": Fraction(10 ** 6), "MEG": Fraction(10 ** 6),
        "Meg": Fraction(10 ** 6), "Meg": Fraction(10 ** 6),
        "m": Fraction(1, 10 ** 3),
        "u": Fraction(1, 10 ** 6), "µ": Fraction(1, 10 ** 6), "μ": Fraction(1, 10 ** 6),
        "n": Fraction(1, 10 ** 9),
        "p": Fraction(1, 10 ** 12)}
_UNITS = ("ohm", "Ohm", "OHM", "欧姆", "欧", "伏", "安",
          "Ω", "Hz", "V", "A", "F", "H", "W", "s")


class CardError(ValueError):
    pass


def parse_number(tok):
    """'12' '0.5' '3/2' '2k' '1M' '1meg' '1mH' '100µF' '12V' '3Ω' '1e-6' -> 精确 Fraction。

    两步：先反复剥掉尾部的物理单位（只是剥离，不做换算），再解析「数字 + 倍率」。
    M/meg = 10^6，m = 10^-3，u/µ = 10^-6，n = 10^-9，p = 10^-12。
    小写 m 永远是千分之一：1mH = 10^-3 H；兆只能写 M 或 meg。
    """
    s = tok.strip().replace("−", "-").replace("，", ",").replace(" ", "")
    end = len(s)
    while True:
        cut = None
        for u in _UNITS:
            if end > len(u) and s[:end].endswith(u):
                cut = u
                break
        if not cut:
            break
        end -= len(cut)
    body = s[:end]
    m = re.match(r"^([-+]?(?:\d+(?:\.\d*)?|\.\d+))"
                 r"(?:[eE]([-+]?\d+))?"
                 r"(?:\s*/\s*(\d+(?:\.\d*)?))?"
                 r"([A-Za-zµμ]{0,3})$", body)
    if not m:
        raise CardError("无法解析数值 %r（写法：12 / 0.5 / 3/2 / 2k / 1M / 1mH / 100µF / 1e-6）"
                        % tok)
    a, ex, div, suf = m.group(1), m.group(2), m.group(3), m.group(4) or ""
    v = Fraction(a)
    if ex:
        v = v * Fraction(10) ** int(ex)
    if div:
        v = v / Fraction(div)
    if suf not in _MUL:
        if len(suf) == 1 and suf.isalpha():
            raise CardError("数值 %r 的后缀 %r 不是合法倍率（可用 k/M/meg/m/u/n/p；"
                            "M 是兆，m 是毫）" % (tok, suf))
        raise CardError("无法识别的后缀 %r（在 %r 中）" % (suf, tok))
    return v * _MUL[suf]


def split_asks(s):
    """'R3 V(2,3) I(Us)' -> ['R3','V(2,3)','I(Us)']（括号里的逗号不切）"""
    out, buf, depth = [], [], 0
    for ch in s:
        if ch in "（(［[":
            depth += 1
        elif ch in "）)］]":
            depth = max(0, depth - 1)
        if depth == 0 and ch in " \t,，、;；":
            if buf:
                out.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


# ============================================================ 题目卡
KINDS = ("R", "V", "I", "E", "G", "H", "F", "C", "L")
DESIG = dict((k, k) for k in KINDS)
KIND_CN = {"R": "电阻", "V": "独立电压源", "I": "独立电流源",
           "E": "VCVS 压控电压源", "G": "VCCS 压控电流源",
           "H": "CCVS 流控电压源", "F": "CCCS 流控电流源",
           "C": "电容", "L": "电感"}
_HEAD = {
    "title": r"^(?:题名|题目|title)",
    "port": r"^(?:端口|port)",
    "note": r"^(?:备注|note)",
    "ask": r"^(?:求|求取|find)",
    "type": r"^(?:类型|type)",
    "vars": r"^(?:变量|vars|variables)",
    "minterms": r"^(?:最小项|minterms)",
    "dc": r"^(?:无关项|dontcare)",
    "expr": r"^(?:表达式|expr|expression)",
    "form": r"^(?:形式|form)",
    "ff": r"^(?:触发器|ff|flipflop)",
    "qseq": r"^(?:Q序列|qseq|序列)",
    "trans": r"^(?:状态转移|状态表|trans)",
    "omega": r"^(?:ω|w|omega|角频率)",
    "freq": r"^(?:f|freq|频率)",
    "dt": r"^(?:步长|dt)",
    "tstop": r"^(?:时长|tstop)",
    "times": r"^(?:时刻|输出时刻|at)",
    "ic": r"^(?:初值|ic)",
}


def _split_colon(line):
    """按最早出现的冒号（半角或全角）切一刀。不能偏好全角：正文里常有全角冒号。"""
    best = None
    for sep in ("：", ":"):
        i = line.find(sep)
        if i >= 0 and (best is None or i < best):
            best = i
    if best is None:
        return None, None
    return line[:best].strip(), line[best + 1:].strip()


def parse_card(text, fallback="未命名"):
    """题目卡文本 -> dict(title, port, elements, meta)"""
    if text.startswith("\ufeff"):
        text = text[1:]
    card = {"title": fallback, "port": None, "elements": [], "meta": {}}
    meta = card["meta"]
    counters = dict((k, 0) for k in KINDS)
    used = set()

    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#")[0].split("*")[0].strip()
        if not line:
            continue

        head, body = _split_colon(line)
        if head is not None:
            key = None
            for k, pat in _HEAD.items():
                if re.match(pat + r"$", head, re.I):
                    key = k
                    break
            if key is not None:
                if key == "title":
                    card["title"] = body
                elif key == "port":
                    parts = [p for p in re.split(r"[\s,，=]+", body) if p]
                    if len(parts) != 2:
                        raise CardError("第 %d 行：端口要两个节点，如「端口: 2 3」，收到 %r"
                                        % (ln, body))
                    card["port"] = (parts[0], parts[1])
                elif key == "note":
                    meta.setdefault("note", []).append(body)
                elif key == "ask":
                    meta.setdefault("asks", []).extend([x for x in split_asks(body) if x])
                elif key == "type":
                    meta["type"] = {"直流": "dc", "dc": "dc", "DC": "dc",
                                    "相量": "ac", "交流": "ac", "ac": "ac", "AC": "ac",
                                    "瞬态": "tran", "暂态": "tran", "tran": "tran"}.get(body, body)
                elif key == "form":
                    meta["form"] = body.upper()
                elif key == "omega":
                    meta["omega"] = parse_number(body)
                elif key == "freq":
                    meta["freq"] = parse_number(body)
                elif key == "dt":
                    meta["dt"] = parse_number(body)
                elif key == "tstop":
                    meta["tstop"] = parse_number(body)
                elif key == "times":
                    meta["times"] = [parse_number(x) for x in re.split(r"[\s,，]+", body) if x]
                elif key == "ic":
                    for tok in re.split(r"[\s,，]+", body):
                        if not tok:
                            continue
                        kv = tok.split("=")
                        if len(kv) != 2:
                            raise CardError("第 %d 行：初值写法「初值: C1=5V L1=2A」，收到 %r"
                                            % (ln, tok))
                        meta.setdefault("ic", {})[kv[0].strip()] = parse_number(kv[1])
                else:
                    meta[key] = body
                continue

        tok = [x for x in re.split(r"[\s,，]+", line) if x]
        kind = tok[0].upper()
        if kind not in KINDS:
            raise CardError("第 %d 行：不认识的写法 %r\n"
                            "  元件行格式：类型 [名字] n1 n2 数值\n"
                            "  字段行必须带冒号：题名:/端口:/求:/备注:\n"
                            "  元件类型只有 %s" % (ln, line, "/".join(KINDS)))
        e = {"kind": kind, "line": ln}
        try:
            if kind in ("R", "V", "I", "C", "L"):
                if len(tok) == 4:
                    _, n1, n2, val = tok
                    name = None
                elif len(tok) == 5:
                    _, name, n1, n2, val = tok
                else:
                    raise CardError("字段数不对，应为「%s [名字] n1 n2 数值」" % kind)
            elif kind in ("E", "G"):
                if len(tok) == 7:
                    _, name, n1, n2, c1, c2, val = tok
                elif len(tok) == 6:
                    _, n1, n2, c1, c2, val = tok
                    name = None
                else:
                    raise CardError("字段数不对，应为「%s [名字] n+ n- c+ c- 系数」" % kind)
                e["c1"], e["c2"] = c1, c2
            else:
                if len(tok) == 6:
                    _, name, n1, n2, ctrl, val = tok
                elif len(tok) == 5:
                    _, n1, n2, ctrl, val = tok
                    name = None
                else:
                    raise CardError("字段数不对，应为「%s [名字] n+ n- 控制电压源 系数」" % kind)
                e["ctrl"] = ctrl
            e.update({"n1": n1, "n2": n2, "value": parse_number(val), "name": name})
        except CardError as exc:
            raise CardError("第 %d 行（%r）：%s" % (ln, raw.strip(), exc))
        if kind == "R" and e["value"] == 0:
            raise CardError("第 %d 行：R=0 不能直接写。短路请用 0V 电压源 "
                            "（V VSC a b 0V），这样电流才可求、矩阵也不奇异" % ln)
        card["elements"].append(e)

    if not card["elements"]:
        raise CardError("题目卡里一个元件都没有")

    # --- 名字：显式名补位号前缀（Us -> VUs，原名记在 _orig 以便「求: I(Us)」仍可用）
    for e in card["elements"]:
        if e["name"]:
            used.add(e["name"])
    rename = {}
    for e in card["elements"]:
        old = e["name"]
        if not old:
            continue
        want = DESIG[e["kind"]]
        if old[:1].upper() != want:
            new, i = want + old, 1
            while new in used:
                i += 1
                new = "%s%d" % (want + old, i)
            used.add(new)
            rename[old] = new
            e["name"] = new
            e["_orig"] = old
    for e in card["elements"]:
        if e.get("ctrl") in rename:
            e["ctrl"] = rename[e["ctrl"]]
    # --- 自动编号
    for e in card["elements"]:
        if not e["name"]:
            while True:
                counters[e["kind"]] += 1
                nm = "%s%d" % (DESIG[e["kind"]], counters[e["kind"]])
                if nm not in used:
                    used.add(nm)
                    break
            e["name"] = nm
    names = [e["name"] for e in card["elements"]]
    dup = sorted(set(n for n in names if names.count(n) > 1))
    if dup:
        raise CardError("元件名重复：%s" % "、".join(dup))
    # --- H/F 的控制量必须是具名独立电压源的电流
    vnames = set(e["name"] for e in card["elements"] if e["kind"] == "V")
    for e in card["elements"]:
        if e["kind"] in ("H", "F"):
            if e["ctrl"] not in vnames:
                raise CardError(
                    "%s 的控制量 %r 必须是一个具名独立电压源 V。\n"
                    "  若原题控制量是某支路电流，就在该支路串一个 0V 取样源：\n"
                    "    V VI1 5 0 0V     （串在 5 与 0 之间，电流由 5 流向 0 为正）\n"
                    "    H H1 3 1 VI1 2   （用 I(VI1) 做控制量）"
                    % (e["name"], e["ctrl"]))
            if e["ctrl"] == e["name"]:
                raise CardError("%s 不能以自己的电流为控制量" % e["name"])
    for e in card["elements"]:
        for k in ("n1", "n2", "c1", "c2"):
            nd = e.get(k)
            if nd is not None and not re.match(r"^[^\s:：]+$", nd):
                raise CardError("第 %d 行：节点名 %r 不合法" % (e["line"], nd))
    return card


def nodes_of(card):
    out = []
    for e in card["elements"]:
        for k in ("n1", "n2", "c1", "c2"):
            nd = e.get(k)
            if nd is not None and nd not in out:
                out.append(nd)
    return out


def load_card(path):
    with open(path, encoding="utf-8") as fh:
        return parse_card(fh.read(), fallback=os.path.basename(path))


# ============================================================ 网表（MNA 输入）
def to_net(card, mode="dc", w=None, h=None, uC=None, iL=None):
    """题目卡 -> MNA 元件元组表。四种分析共用同一套语义。"""
    out = []
    for e in card["elements"]:
        k, n1, n2, v = e["kind"], e["n1"], e["n2"], e["value"]
        if k == "R":
            out.append(("R", n1, n2, Q(v)))
        elif k == "V":
            out.append(("V", n1, n2, Q(v), e["name"]))
        elif k == "I":
            out.append(("I", n1, n2, Q(v)))
        elif k == "E":
            out.append(("VCVS", n1, n2, e["c1"], e["c2"], Q(v), e["name"]))
        elif k == "G":
            out.append(("VCCS", n1, n2, e["c1"], e["c2"], Q(v)))
        elif k == "H":
            out.append(("CCVS", n1, n2, e["ctrl"], Q(v), e["name"]))
        elif k == "F":
            out.append(("CCCS", n1, n2, e["ctrl"], Q(v)))
        elif k == "L":
            if mode == "ac":
                out.append(("R", n1, n2, Q(0, w * v)))                    # jωL
            elif mode == "tran":
                out.append(("Lb", n1, n2, Q(v / h), Q((iL or {})[e["name"]]), e["name"]))
            else:
                raise CardError("直流分析不能含电感 %s。直流下 L 是短路——把它换成 0V 电压源；"
                                "要做瞬态请用 tran 子命令" % e["name"])
        elif k == "C":
            if mode == "ac":
                out.append(("R", n1, n2, Q(1) / Q(0, w * v)))             # 1/(jωC)
            elif mode == "tran":
                g = Q(v / h)                                             # 伴随：g = C/h
                out.append(("R", n1, n2, Q(1) / g))
                out.append(("I", n2, n1, g * Q((uC or {})[e["name"]])))
            else:
                raise CardError("直流分析不能含电容 %s。直流下 C 是开路——直接删掉这一行；"
                                "要做瞬态请用 tran 子命令" % e["name"])
        else:
            raise CardError("未知元件类型 %r" % k)
    return out


_NAME_AT = {"V": 4, "VCVS": 6, "CCVS": 5, "Lb": 5}


def name_of(e):
    i = _NAME_AT.get(e[0])
    return e[i] if i is not None and len(e) > i else None


class SingularError(ArithmeticError):
    pass


def solve_linear(A, b):
    """精确有理数高斯消元（部分主元）。全程无浮点，解就是精确解。"""
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for k in range(n):
        piv, best = None, None
        for r in range(k, n):
            if not M[r][k].is0():
                m = abs(M[r][k])
                if best is None or m > best:
                    best, piv = m, r
        if piv is None:
            raise SingularError("矩阵奇异：第 %d 列无主元" % (k + 1))
        if piv != k:
            M[k], M[piv] = M[piv], M[k]
        pk = M[k][k]
        for r in range(k + 1, n):
            f = M[r][k] / pk
            if f.is0():
                continue
            for c in range(k, n + 1):
                M[r][c] = M[r][c] - f * M[k][c]
    x = [Q(0)] * n
    for i in range(n - 1, -1, -1):
        s = M[i][n]
        for j in range(i + 1, n):
            s = s - M[i][j] * x[j]
        x[i] = s / M[i][i]
    return x


def solve(net, ground="0"):
    """MNA 求解。

    节点名一律 str() 后再比较。这是个真坑：若 ground 传整数 0 而网表里存字符串 '0'，
    同一节点会被当成两个，矩阵当场奇异（父项目 tools/mna.py 就踩过）。
    """
    ground = str(ground)
    idx, order = {}, []

    def node(n):
        n = str(n)
        if n == ground:
            return None
        if n not in idx:
            idx[n] = len(order)
            order.append(n)
        return idx[n]

    for e in net:
        node(e[1])
        node(e[2])
    br = [e for e in net if e[0] in ("V", "VCVS", "CCVS", "Lb")]
    kof = dict((id(e), i) for i, e in enumerate(br))
    vby = dict((e[4], e) for e in net if e[0] == "V")
    n, m = len(order), len(br)
    A = [[Q(0) for _ in range(n + m)] for _ in range(n + m)]
    b = [Q(0) for _ in range(n + m)]

    def stamp_g(n1, n2, g):
        a, c = idx.get(str(n1)), idx.get(str(n2))
        if a is not None:
            A[a][a] = A[a][a] + g
        if c is not None:
            A[c][c] = A[c][c] + g
        if a is not None and c is not None:
            A[a][c] = A[a][c] - g
            A[c][a] = A[c][a] - g

    for e in net:
        t = e[0]
        if t == "R":
            z = e[3]
            if z.is0():
                raise CardError("存在 0 欧姆电阻：短路请用 0V 电压源")
            stamp_g(e[1], e[2], Q(1) / z)
        elif t == "I":
            a, c = idx.get(str(e[1])), idx.get(str(e[2]))
            if a is not None:
                b[a] = b[a] - e[3]
            if c is not None:
                b[c] = b[c] + e[3]
        elif t == "VCCS":
            _, n1, n2, c1, c2, g = e
            for x, sx in ((n1, 1), (n2, -1)):
                for y, sy in ((c1, 1), (c2, -1)):
                    ix, iy = idx.get(str(x)), idx.get(str(y))
                    if ix is not None and iy is not None:
                        A[ix][iy] = A[ix][iy] + g * (sx * sy)
        elif t in ("V", "VCVS", "CCVS", "Lb"):
            k = kof[id(e)]
            a, c = idx.get(str(e[1])), idx.get(str(e[2]))
            if a is not None:
                A[a][n + k] = A[a][n + k] + Q(1)
                A[n + k][a] = A[n + k][a] + Q(1)
            if c is not None:
                A[c][n + k] = A[c][n + k] - Q(1)
                A[n + k][c] = A[n + k][c] - Q(1)
            if t == "V":
                b[n + k] = e[3]
            elif t == "VCVS":
                mu = e[5]
                i1, i2 = idx.get(str(e[3])), idx.get(str(e[4]))
                if i1 is not None:
                    A[n + k][i1] = A[n + k][i1] - mu
                if i2 is not None:
                    A[n + k][i2] = A[n + k][i2] + mu
            elif t == "CCVS":
                src = vby.get(e[3])
                if src is None:
                    raise CardError("CCVS %s 的控制源 %r 不是独立电压源" % (name_of(e), e[3]))
                kk = kof[id(src)]
                A[n + k][n + kk] = A[n + k][n + kk] - e[4]
            else:                                        # Lb：后向欧拉伴随模型
                Lh, iprev = e[3], e[4]
                A[n + k][n + k] = A[n + k][n + k] - Lh
                b[n + k] = -Lh * iprev
        elif t == "CCCS":
            src = vby.get(e[3])
            if src is None:
                raise CardError("CCCS 的控制源 %r 不是独立电压源" % e[3])
            col = n + kof[id(src)]
            a, c = idx.get(str(e[1])), idx.get(str(e[2]))
            if a is not None:
                A[a][col] = A[a][col] + e[4]
            if c is not None:
                A[c][col] = A[c][col] - e[4]
        else:
            raise CardError("未知元件类型 %r" % t)

    x = solve_linear(A, b)
    V = {ground: Q(0)}
    for nm, i in idx.items():
        V[nm] = x[i]
    I = {}
    for e in br:
        nm = name_of(e)
        if nm is not None:
            I[nm] = x[n + kof[id(e)]]
    return V, I


def branch_current(e, V, I, mode="dc", w=None):
    """「由 n1 经元件流向 n2」为正的支路电流 —— 全套符号约定只有这一个出口。

    相量模式下标量关系仍成立，只是阻抗变复数：I_C = (u)·jωC，I_L = u/(jωL)。
    """
    k = e["kind"]
    u = V[e["n1"]] - V[e["n2"]]
    if k == "R":
        return u / Q(e["value"])
    if k == "C":
        if mode == "ac":
            return u * Q(0, w * e["value"])
        return u / Q(e["value"])
    if k == "L":
        if mode == "ac":
            return u / Q(0, w * e["value"])
        return I[e["name"]]
    if k in ("V", "E", "H"):
        return I[e["name"]]
    if k == "I":
        return Q(e["value"])
    if k == "G":
        return Q(e["value"]) * (V[e["c1"]] - V[e["c2"]])
    if k == "F":
        return Q(e["value"]) * I[e["ctrl"]]
    raise CardError("未知元件类型 %r" % k)


def powers(card, V, I, mode="dc", w=None):
    """逐元件 p = u·i（u = V(n1)−V(n2)，i 由 n1 流向 n2）。Σp 必须严格为 0（特勒根）。"""
    rows, total = [], Q(0)
    for e in card["elements"]:
        i = branch_current(e, V, I, mode, w)
        u = V[e["n1"]] - V[e["n2"]]
        p = u * i
        total = total + p
        rows.append({"name": e["name"], "kind": e["kind"], "n1": e["n1"],
                     "n2": e["n2"], "u": u, "i": i, "p": p})
    return rows, total


# ============================================================ 戴维宁
def thevenin(net, a, b="0", rl=None):
    """u_oc（开路电压）、i_sc（短路电流）、R_eq（除源外加 1A），可选接 R_L。"""
    a, b = str(a), str(b)
    V1, _ = solve(net, b)
    uoc = V1.get(a, Q(0)) - V1.get(b, Q(0))
    V2, I2 = solve(net + [("V", a, b, Q(0), "SC__")], b)
    isc = I2["SC__"]
    dp = []
    for e in net:
        if e[0] == "V":
            dp.append(("V", e[1], e[2], Q(0), e[4]))       # 电压源置 0 = 短路
        elif e[0] == "I":
            continue                                        # 电流源置 0 = 开路
        else:
            dp.append(e)                                    # 受控源必须保留
    V3, _ = solve(dp + [("I", b, a, Q(1))], b)
    req = V3.get(a, Q(0)) - V3.get(b, Q(0))
    out = {"u_oc": uoc, "i_sc": isc, "R_eq": req}
    if not isc.is0():
        out["u_oc/i_sc"] = uoc / isc
    if rl is not None:
        rl = Q(rl)
        V4, I4 = solve(net + [("R", a, b, rl)], b)
        ul = V4.get(a, Q(0)) - V4.get(b, Q(0))
        out.update({"R_L": rl, "u_L": ul, "i_L": ul / rl, "P_L": ul * ul / rl,
                    "P_max": (uoc * uoc / (4 * req)) if not req.is0() else None})
    return out


# ============================================================ 求什么答什么
def resolve_asks(card, V, I, ref, mode="dc", w=None):
    out = []
    for raw in card["meta"].get("asks", []):
        tok = raw.strip()
        m = re.match(r"^[VUv]\(\s*([^,)\s]+)\s*(?:,\s*([^,)\s]+)\s*)?\)$", tok)
        if m:
            n1 = m.group(1)
            n2 = m.group(2) or ref
            for nd in (n1, n2):
                if nd not in V:
                    raise CardError("求: %s —— 节点 %r 不存在（现有节点：%s）"
                                    % (tok, nd, "、".join(sorted(V))))
            if m.group(2) is None:
                out.append(("V(%s)" % n1, V[n1] - V[n2], "V"))
            else:
                out.append(("V(%s)-V(%s)" % (n1, n2), V[n1] - V[n2], "V"))
            continue
        m = re.match(r"^[Ii]\(\s*(.+?)\s*\)$", tok)
        nm = m.group(1) if m else tok
        e = None
        for cand in card["elements"]:
            if cand["name"] == nm or cand.get("_orig") == nm:
                e = cand
                break
        if e is None:
            raise CardError("求: %s —— 找不到名为 %r 的元件（现有：%s）"
                            % (tok, nm, "、".join(x["name"] for x in card["elements"])))
        out.append(("I(%s) 由 %s 流向 %s" % (e["name"], e["n1"], e["n2"]),
                    branch_current(e, V, I, mode, w), "A"))
    return out


# ============================================================ 校验（答案对不对的机器证据）
def verify(card, V, I, th, ref, net):
    res = []
    rows, total = powers(card, V, I)
    res.append(("功率平衡 Σui=0", total.is0(),
                "Σu·i = %s（特勒根定理：精确解必须严格为 0；不为 0 就是网表写错了）" % fs(total)))

    nodes = [str(x) for x in nodes_of(card)]
    alt = next((x for x in nodes if x != ref), None)
    if alt is None:
        res.append(("换参考点复算", True, "只有一个节点，跳过"))
    else:
        ok, why = True, ""
        try:
            V2, _ = solve(net, alt)
            for i in nodes:
                for j in nodes:
                    if V[i] - V[j] != V2[i] - V2[j]:
                        ok, why = False, "节点 %s 与 %s 之间的电压差变了" % (i, j)
                        break
                if not ok:
                    break
            if ok:
                why = "改以节点 %s 为参考点重算，%d 个节点两两电压差逐项相同" % (alt, len(nodes))
        except Exception as exc:                                  # noqa: BLE001
            ok, why = False, "换参考点后无法求解（%s）" % exc
        res.append(("换参考点复算", ok, why))

    if th:
        sc = th.get("u_oc/i_sc")
        if sc is not None:
            res.append(("u_oc / i_sc == R_eq", sc == th["R_eq"],
                        "u_oc/i_sc = %s，R_eq = %s —— 两条互不依赖的算法给出同一个等效电阻"
                        % (fs(sc), fs(th["R_eq"]))))
        req = th["R_eq"]
        if not req.is0():
            a, b = str(card["port"][0]), str(card["port"][1])
            rl = req
            pred_u = th["u_oc"] * rl / (rl + req)
            V5, _ = solve(net + [("R", a, b, rl)], b)
            got_u = V5.get(a, Q(0)) - V5.get(b, Q(0))
            res.append(("戴维宁等效 ≈ 原网络", pred_u == got_u,
                        "接 R_L=R_eq=%s Ω：等效电路预测 u_L=%s V，"
                        "把 R_L 真的接进原网络解得 %s V" % (fs(rl), fs(pred_u), fs(got_u))))
    return res


def to_spice(card):
    """题目卡 -> SPICE 网表（装了 ngspice 时可做完全独立的第二意见）。"""
    lines = ["* %s" % card["title"], "* generated by circuit.py"]
    for e in card["elements"]:
        k, v = e["kind"], e["value"]
        val = _fs(v) if v.denominator == 1 else repr(float(v))
        if k in ("R", "V", "I", "C", "L"):
            lines.append("%-6s %-5s %-5s %s" % (e["name"], e["n1"], e["n2"], val))
        elif k in ("E", "G"):
            lines.append("%-6s %-5s %-5s %-5s %-5s %s"
                         % (e["name"], e["n1"], e["n2"], e["c1"], e["c2"], val))
        else:
            lines.append("%-6s %-5s %-5s %-5s %s"
                         % (e["name"], e["n1"], e["n2"], e["ctrl"], val))
    lines += [".op", ".end"]
    return "\n".join(lines) + "\n"


def parse_spice(text):
    """把 to_spice 的输出读回来（往返自检用）。"""
    card = {"title": "deck", "port": None, "elements": [], "meta": {}}
    for raw in text.splitlines():
        line = raw.split("*")[0].strip()
        if not line or line.startswith("."):
            continue
        tok = re.split(r"\s+", line)
        kind = tok[0][0].upper()
        if kind not in KINDS:
            raise CardError("网表里不认识的元件 %r" % line)
        e = {"kind": kind, "name": tok[0], "line": 0}
        if kind in ("R", "V", "I", "C", "L"):
            e.update({"n1": tok[1], "n2": tok[2], "value": parse_number(tok[3])})
        elif kind in ("E", "G"):
            e.update({"n1": tok[1], "n2": tok[2], "c1": tok[3], "c2": tok[4],
                      "value": parse_number(tok[5])})
        else:
            e.update({"n1": tok[1], "n2": tok[2], "ctrl": tok[3],
                      "value": parse_number(tok[4])})
        card["elements"].append(e)
    return card


# ============================================================ 分析入口
def _ref_of(nodes):
    return "0" if "0" in nodes else nodes[0]


def analyze_dc(card, rl=None):
    net = to_net(card, "dc")
    nodes = nodes_of(card)
    port = card["port"]
    if port:
        for nd in port:
            if nd not in nodes:
                raise CardError("端口节点 %r 没接到任何元件上" % nd)
    ref = _ref_of(nodes)
    try:
        V, I = solve(net, ref)
    except SingularError:
        raise CardError("节点法矩阵奇异。常见原因：两个理想电压源并联、只有电压源的回路、"
                        "节点悬空、或端口正好跨在一个理想电压源两端。")
    th = None
    if port:
        try:
            th = thevenin(net, port[0], port[1], rl)
        except SingularError:
            raise CardError("戴维宁求解奇异：端口 %s-%s 之间正好跨着理想电压源，"
                            "短路后变成两个电压源并联。换一个端口位置再问。"
                            % (port[0], port[1]))
    sol = {"mode": "dc", "V": V, "I": I, "ref": ref, "thevenin": th, "port": port,
           "branches": [], "asks": [], "powers": [], "total": Q(0), "checks": []}
    sol["branches"] = [{"name": e["name"], "kind": e["kind"], "n1": e["n1"],
                        "n2": e["n2"], "i": branch_current(e, V, I)}
                       for e in card["elements"]]
    sol["asks"] = resolve_asks(card, V, I, ref)
    sol["powers"], sol["total"] = powers(card, V, I)
    sol["checks"] = verify(card, V, I, th, ref, net)
    try:
        back = parse_spice(to_spice(card))
        V2, I2 = solve(to_net(back, "dc"), ref)
        ok = all(V[k] - V[ref] == V2[k] - V2[ref] for k in V)
        sol["checks"].append(("网表往返", ok,
                              "导出 SPICE 网表再解析回来重解，%d 个节点电压逐项相同" % len(V)))
    except Exception as exc:                                      # noqa: BLE001
        sol["checks"].append(("网表往返", False, "往返失败：%s" % exc))
    return sol


def analyze_ac(card, w=None):
    if w is None:
        if "omega" in card["meta"]:
            w = card["meta"]["omega"]
        elif "freq" in card["meta"]:
            w = card["meta"]["freq"] * 2 * TAU2PI
        else:
            raise CardError("相量分析需要角频率：写「ω: 1000」(rad/s) 或「f: 50」(Hz)")
    w = Q(_frac(w))
    net = to_net(card, "ac", w=_frac(w))
    nodes = nodes_of(card)
    ref = _ref_of(nodes)
    try:
        V, I = solve(net, ref)
    except SingularError:
        raise CardError("相量法矩阵奇异：检查是否端口跨着电压源、或某节点悬空。")
    port = card["port"]
    th = None
    if port:
        try:
            th = thevenin(net, port[0], port[1])
        except (SingularError, ZeroDivisionError):
            th = None
    sol = {"mode": "ac", "V": V, "I": I, "ref": ref, "w": w, "thevenin": th,
           "port": port, "branches": [], "asks": [], "powers": [], "total": Q(0)}
    sol["branches"] = [{"name": e["name"], "kind": e["kind"], "n1": e["n1"],
                        "n2": e["n2"], "i": branch_current(e, V, I, "ac", _frac(w))}
                       for e in card["elements"]]
    sol["asks"] = resolve_asks(card, V, I, ref, "ac", _frac(w))
    rows, total = [], Q(0)
    for e in card["elements"]:
        i = branch_current(e, V, I, "ac", _frac(w))
        u = V[e["n1"]] - V[e["n2"]]
        rows.append({"name": e["name"], "u": u, "i": i, "p": u * i})
        total = total + u * i
    sol["powers"], sol["total"] = rows, total
    sol["checks"] = [("相量功率平衡 Σui=0", total.is0(),
                      "Σu·i = %s（复功率守恒，KCL 的直接推论）" % fs(total))]
    return sol


def analyze_tran(card, dt=None, tstop=None, times=None, ic=None):
    """瞬态：后向欧拉逐步积分。

    这里的数值刻意用浮点，不跟直流/相量走精确分数。原因很实在：瞬态本来
    就是指数逼近，每步都要重算伴随模型，若沿用 Fraction，分母会一步步膨胀
    （h=1e-7 时 5000 步就会出现几万位的分数），几秒内变成跑不完。精度改用
    「步长减半、误差应同步变小」这条收敛性检查来保证，见 selftest。
    """
    meta = card["meta"]
    dt = _frac(dt if dt is not None else meta.get("dt"))
    tstop = _frac(tstop if tstop is not None else meta.get("tstop"))
    if dt is None or tstop is None:
        raise CardError("瞬态分析需要步长与时长：写「步长: 1e-5」「时长: 5e-3」，"
                        "或命令行 --dt 1e-5 --tstop 5e-3")
    times = [_frac(t) for t in (times if times is not None else (meta.get("times") or [tstop]))]
    ic = ic if ic is not None else (meta.get("ic") or {})
    ic = dict((k, _frac(v)) for k, v in ic.items())
    h = float(dt)
    uC, iL = {}, {}
    for e in card["elements"]:
        if e["kind"] == "C":
            uC[e["name"]] = float(ic.get(e["name"], 0))
        elif e["kind"] == "L":
            iL[e["name"]] = float(ic.get(e["name"], 0))
    steps = int(math.ceil(float(tstop) / h))
    if steps <= 0:
        raise CardError("步数算出来是 0：时长必须大于步长")
    nodes = nodes_of(card)
    ref = _ref_of(nodes)
    targets = sorted(float(t) for t in times)
    recs, ti, V = [], 0, None
    for s in range(1, steps + 1):
        net = to_net(card, "tran", h=h, uC=uC, iL=iL)
        V, I = solve(net, ref)
        for e in card["elements"]:
            if e["kind"] == "C":
                uC[e["name"]] = float(V[e["n1"]] - V[e["n2"]])
            elif e["kind"] == "L":
                iL[e["name"]] = float(I[e["name"]])
        t = h * s
        while ti < len(targets) and t >= targets[ti] - h / 2:
            recs.append({"t": t, "V": dict(V), "uC": dict(uC), "iL": dict(iL)})
            ti += 1
    return {"mode": "tran", "dt": dt, "tstop": tstop, "nodes": nodes, "ref": ref,
            "recs": recs, "V": V, "uC": uC, "iL": iL}


# ============================================================ 数字逻辑
class LogicError(ValueError):
    pass


def _ints(s):
    return [int(x) for x in re.findall(r"-?\d+", s)]


_LOGIC_HEAD = {
    "title": r"^(?:题名|题目|title)",
    "type": r"^(?:类型|type)",
    "vars": r"^(?:变量|vars|variables)",
    "minterms": r"^(?:最小项|minterms)",
    "dc": r"^(?:无关项|dontcare)",
    "expr": r"^(?:表达式|expr|expression)",
    "form": r"^(?:形式|form)",
    "ff": r"^(?:触发器|ff|flipflop)",
    "qseq": r"^(?:Q序列|qseq|序列)",
    "trans": r"^(?:状态转移|状态表|trans)",
    "note": r"^(?:备注|note|说明)",
}


def parse_logic(text, fallback="未命名"):
    if text.startswith("\ufeff"):
        text = text[1:]
    card = {"title": fallback, "kind": None}
    for raw in text.splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        head, body = _split_colon(line)
        if head is None:
            raise LogicError("不认识的行 %r（每个字段都要写成「名字: 内容」）" % raw.strip())
        key = None
        for k, pat in _LOGIC_HEAD.items():
            if re.match(pat + r"$", head, re.I):
                key = k
                break
        if key is None:
            raise LogicError("不认识的字段 %r（可用：类型/变量/最小项/无关项/表达式/形式/"
                             "触发器/Q序列/状态转移）" % head)
        if key == "title":
            card["title"] = body
        elif key == "type":
            card["kind"] = "combo" if body in ("组合", "组合逻辑", "combo", "comb") else "seq"
        elif key == "vars":
            card["vars"] = [x for x in re.split(r"[\s,，]+", body) if x]
        elif key == "minterms":
            card["minterms"] = _ints(body)
        elif key == "dc":
            card["dc"] = _ints(body)
        elif key == "expr":
            card["expr"] = body
        elif key == "form":
            card["form"] = body.upper()
        elif key == "ff":
            card["ff"] = body.upper()
        elif key == "qseq":
            card["qseq"] = _ints(body)
        elif key == "trans":
            pairs = []
            for part in re.split(r"[/;；\n]+", body):
                nums = re.findall(r"\d+", part)
                if len(nums) >= 2:
                    pairs.append((int(nums[0]), int(nums[1])))
            card["trans"] = pairs
        elif key == "note":
            card.setdefault("note", []).append(body)
    if card["kind"] is None:
        card["kind"] = "combo" if ("minterms" in card or "expr" in card) else "seq"
    return card


# --- 布尔表达式：递归下降（不 eval 用户输入）
_TOK = re.compile(r"\s*([A-Za-z_][A-Za-z_0-9]*|[~!&|·*+^⊕¬∧∨()'])")
_KEYWORDS = (("AND", "&"), ("and", "&"), ("OR", "|"), ("or", "|"),
             ("XOR", "^"), ("xor", "^"), ("NOT", "~"), ("not", "~"))


def _tokenize(s):
    for a, b in _KEYWORDS:
        s = s.replace(a, b)
    out, i = [], 0
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        m = _TOK.match(s, i)
        if not m:
            raise LogicError("表达式里无法识别的字符 %r（位置 %d）" % (s[i], i))
        out.append(m.group(1))
        i = m.end()
    return out


class _P(object):
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def eat(self, *vals):
        v = self.peek()
        if v in vals:
            self.i += 1
            return v
        return None

    def expr(self):
        node = self.xor()
        while self.eat("|", "+", "∨"):
            node = ("|", node, self.xor())
        return node

    def xor(self):
        node = self.and_()
        while self.eat("^", "⊕"):
            node = ("^", node, self.and_())
        return node

    def and_(self):
        node = self.unary()
        while self.eat("&", "·", "*", "∧"):
            node = ("&", node, self.unary())
        return node

    def unary(self):
        if self.eat("~", "!", "¬"):
            return ("~", self.unary())
        return self.atom()

    def atom(self):
        v = self.peek()
        if v == "(":
            self.i += 1
            node = self.expr()
            if not self.eat(")"):
                raise LogicError("括号没配平")
            return node
        if v and re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", v):
            self.i += 1
            return ("var", v)
        raise LogicError("表达式在 %r 处缺操作数" % (v,))

    def parse(self):
        node = self.expr()
        if self.i != len(self.t):
            raise LogicError("表达式末尾多余 %r" % (self.t[self.i],))
        return node


def _ev(node, env):
    op = node[0]
    if op == "var":
        if node[1] not in env:
            raise LogicError("表达式里的变量 %r 没在「变量:」里声明" % node[1])
        return env[node[1]]
    if op == "~":
        return 0 if _ev(node[1], env) else 1
    a, b = _ev(node[1], env), _ev(node[2], env)
    if op == "&":
        return 1 if (a and b) else 0
    if op == "|":
        return 1 if (a or b) else 0
    return 1 if a != b else 0


def _expr_vars(node, acc):
    if node[0] == "var":
        if node[1] not in acc:
            acc.append(node[1])
    elif node[0] == "~":
        _expr_vars(node[1], acc)
    else:
        _expr_vars(node[1], acc)
        _expr_vars(node[2], acc)
    return acc


def _covers(val, dc, t, nvars):
    """蕴含项 (val, dc) 是否覆盖最小项 t。

    位表示：第 i 位（从低位起）是变量 vars[nvars-1-i] 的取值。
    dc 为 1 的位表示该变量已消去（任意），比较时把这些位屏蔽掉。
    """
    mask = ((1 << nvars) - 1) & ~dc
    return (t & mask) == (val & mask)


def _qm_primes(terms, n):
    """Quine-McCluskey：返回全部质蕴含项 (val, dc)。

    terms 必须把无关项一起传进来，否则无关项无法起到化简作用（QM 标准做法）。
    """
    cur = set((t, 0) for t in terms)
    primes = set()
    while cur:
        lst = sorted(cur)
        nxt, used = set(), set()
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                a, b = lst[i], lst[j]
                if a[1] != b[1]:
                    continue                      # 已消去的变量集不同，不能合并
                x = a[0] ^ b[0]
                if x and (x & (x - 1)) == 0:      # 只差一个变量
                    nxt.add((a[0] & b[0], a[1] | x))
                    used.add(a)
                    used.add(b)
        primes |= (cur - used)
        cur = nxt
    return primes


def _min_cover(primes, need, nvars):
    """最简覆盖：先比乘积项个数，再比文字总数；规模小，直接精确搜索。"""
    import itertools
    prim = sorted(primes, key=lambda p: (bin(p[1]).count("1"), p[0]))
    if not need:
        return []
    if not prim:
        raise LogicError("覆盖搜索没有可用质蕴含项（内部错误）")
    for k in range(1, len(prim) + 1):
        best = None
        for combo in itertools.combinations(prim, k):
            if all(any(_covers(v, d, t, nvars) for (v, d) in combo) for t in need):
                lits = sum(nvars - bin(d).count("1") for (v, d) in combo)
                if best is None or lits < best[0]:
                    best = (lits, list(combo))
        if best is not None:
            return best[1]
    raise LogicError("覆盖搜索失败：最小项组合过于复杂，无法穷举（内部错误）")


def _lits(val, dc, vars_):
    """一个蕴含项 -> 文字列表；dc 位表示该变量被消去。"""
    out, n = [], len(vars_)
    for i, v in enumerate(vars_):
        bit = 1 << (n - 1 - i)
        if dc & bit:
            continue
        out.append(v if (val & bit) else "~" + v)
    return out


def _sop(cover, vars_):
    terms = [" & ".join(_lits(o, d, vars_)) or "1" for (o, d) in cover]
    return " | ".join(terms) if terms else "0"


def _pos(cover, vars_):
    """对反函数求最简与或，再用德摩根转成或与式。"""
    sums = []
    for (o, d) in cover:
        lits = ["~" + x if not x.startswith("~") else x[1:] for x in _lits(o, d, vars_)]
        sums.append(" | ".join(lits) or "0")
    return " & ".join("(%s)" % s for s in sums) if sums else "1"


def _kmap(n, ones, dc):
    """卡诺图（n<=4）：行=高位变量，列=低位变量，格雷码排布。"""
    if n == 4:
        rows = [((0, 0), "AB=00"), ((0, 1), "AB=01"), ((1, 1), "AB=11"), ((1, 0), "AB=10")]
        cols = [(0, 0), (0, 1), (1, 1), (1, 0)]
        colhdr = "CD"
    elif n == 3:
        rows = [((0,), "A=0"), ((1,), "A=1")]
        cols = [(0, 0), (0, 1), (1, 1), (1, 0)]
        colhdr = "BC"
    else:
        rows = [((0,), "A=0"), ((1,), "A=1")]
        cols = [(0,), (1,)]
        colhdr = "B"
    lines = ["      " + "   ".join(colhdr + "=" + "".join(map(str, c)) for c in cols)]
    for rb, lab in rows:
        cells = []
        for cb in cols:
            idx = 0
            for bit in list(rb) + list(cb):
                idx = (idx << 1) | bit
            cells.append("X" if idx in dc else ("1" if idx in ones else "0"))
        lines.append("%-6s %s" % (lab, "   ".join("%s" % c for c in cells)))
    return "\n".join(lines)


def analyze_combo(card):
    vars_ = card.get("vars")
    if "expr" in card:
        node = _P(_tokenize(card["expr"])).parse()
        evars = _expr_vars(node, [])
        if not vars_:
            vars_ = evars
        n = len(vars_)
        extra = [v for v in evars if v not in vars_]
        if extra:
            raise LogicError("表达式里的变量 %s 没在「变量:」里声明" % "、".join(extra))
        ones = []
        for idx in range(1 << n):
            env = dict((v, (idx >> (n - 1 - i)) & 1) for i, v in enumerate(vars_))
            if _ev(node, env):
                ones.append(idx)
        dc = []
    else:
        vars_ = vars_ or ["A", "B", "C", "D"]
        n = len(vars_)
        ones = sorted(card.get("minterms", []))
        dc = sorted(card.get("dc", []))
        for t in ones + dc:
            if not (0 <= t < (1 << n)):
                raise LogicError("最小项 %d 超出 %d 个变量的范围（0..%d）"
                                 % (t, n, (1 << n) - 1))
    # 无关项是"随便当 0 还是 1"的项：求与或式时它可以被当成 1 参与合并，
    # 求或与式（即对反函数求与或）时它也可以被当成 1。两侧都要把它喂进 QM。
    need = [t for t in ones if t not in dc]
    p1 = _qm_primes(sorted(set(need) | set(dc)), n) if need else set()
    cover = _min_cover(p1, need, n)
    zeros = [t for t in range(1 << n) if t not in ones and t not in dc]
    p0 = _qm_primes(sorted(set(zeros) | set(dc)), n) if zeros else set()
    pcover = _min_cover(p0, zeros, n)
    sop, pos = _sop(cover, vars_), _pos(pcover, vars_)

    def ev_sop(t):
        return 1 if any(_covers(v, d, t, n) for (v, d) in cover) else 0

    def ev_pos(t):
        return 0 if any(_covers(v, d, t, n) for (v, d) in pcover) else 1

    bad = []
    tested = 0
    for t in range(1 << n):
        if t in dc:
            continue
        tested += 1
        want = 1 if t in ones else 0
        if ev_sop(t) != want or ev_pos(t) != want:
            bad.append(t)
    neg = set()
    for (o, d) in cover:
        for i in range(n):
            bit = 1 << (n - 1 - i)
            if not (d & bit) and not (o & bit):
                neg.add(i)
    return {"mode": "logic", "kind": "combo", "title": card["title"], "vars": vars_,
            "ones": ones, "dc": dc, "need": need, "sop": sop, "pos": pos,
            "sop_products": len(cover),
            "sop_literals": sum(n - bin(d).count("1") for (o, d) in cover),
            "pos_sums": len(pcover),
            "pos_literals": sum(n - bin(d).count("1") for (o, d) in pcover),
            "gates": {"and": len(cover), "or": 1 if cover else 0, "not": len(neg),
                      "two_level_total": len(cover) + (1 if cover else 0) + len(neg)},
            "kmap": _kmap(n, ones, dc) if n in (2, 3, 4) else None,
            "verify": {"ok": not bad, "bad": bad, "tested": tested}}


_FF = {"JK": {(0, 0): "J=0 K=X", (0, 1): "J=1 K=X", (1, 0): "J=X K=1", (1, 1): "J=X K=0"},
       "D": {(0, 0): "D=0", (0, 1): "D=1", (1, 0): "D=0", (1, 1): "D=1"},
       "T": {(0, 0): "T=0", (0, 1): "T=1", (1, 0): "T=1", (1, 1): "T=0"},
       "SR": {(0, 0): "S=0 R=X", (0, 1): "S=1 R=0", (1, 0): "S=0 R=1", (1, 1): "S=1 R=0"}}
_FF_CN = {"JK": "JK 触发器", "D": "D 触发器", "T": "T 触发器",
          "SR": "SR 触发器", "RS": "SR 触发器"}


def analyze_seq(card):
    out = {"mode": "logic", "kind": "seq", "title": card["title"]}
    if "qseq" in card:
        q = card["qseq"]
        key = (card.get("ff") or "JK").upper()
        tab = _FF.get(key)
        if tab is None:
            raise LogicError("只支持 JK/D/T/SR 触发器，收到 %r" % card.get("ff"))
        rows = [{"beat": k + 1, "qn": q[k], "qn1": q[k + 1], "drive": tab[(q[k], q[k + 1])]}
                for k in range(len(q) - 1)]
        out.update({"ff": _FF_CN.get(key, key), "qseq": q, "drive": rows, "ok": True,
                    "note": "共 %d 拍；激励表是双向的，给次态可反查出应有输入" % len(rows)})
        return out
    if "trans" not in card:
        raise LogicError("时序卡需要「触发器: JK」+「Q序列: ...」，或「状态转移: 0 1 / 1 2 / ...」")
    pairs = card["trans"]
    nxt = {}
    for a, b in pairs:
        if a in nxt and nxt[a] != b:
            raise LogicError("状态 %d 有两条次态（%d 与 %d）：这不是确定的状态机" % (a, nxt[a], b))
        nxt[a] = b
    states = sorted(set([a for a, _ in pairs] + [b for _, b in pairs]))
    nbits = max(1, max(states).bit_length())
    universe = list(range(1 << nbits))

    def _canon(cyc):
        """闭环从最小状态起算，使 0→1→2 与 1→2→0 被认成同一个环。"""
        i = cyc.index(min(cyc))
        return cyc[i:] + cyc[:i]

    cycles, seen = [], set()
    for s in universe:
        if s in seen or s not in nxt:
            continue
        path, cur = [], s
        while cur is not None and cur not in path:
            path.append(cur)
            cur = nxt.get(cur)
        if cur is not None and cur in path:
            cyc = _canon(path[path.index(cur):])
            if cyc not in cycles:
                cycles.append(cyc)
            seen.update(cyc)
    incl = set(x for cyc in cycles for x in cyc)
    selfstart = []
    for s in universe:
        path, cur, ok = [], s, False
        while cur is not None and len(path) <= len(universe):
            if cur in incl:
                ok = True
                break
            path.append(cur)
            cur = nxt.get(cur)
        if ok:
            steps = " → ".join(map(str, path + [cur])) + "（从此处入环）"
        elif cur is None:
            steps = " → ".join(map(str, path)) + " → 断路（无次态）"
        else:
            steps = " → ".join(map(str, path))
        selfstart.append({"state": s, "ok": ok, "path": steps})
    out.update({"trans": pairs, "cycles": cycles, "selfstart": selfstart,
                "dead_end": [x for x in universe if x not in nxt], "nbits": nbits,
                "ok": all(x["ok"] for x in selfstart),
                "note": "编码 %d 位，全体 %d 个编码逐个试走（不是抽样）"
                        % (nbits, len(universe))})
    return out


# ============================================================ 报告
def report(sol):
    L = []
    mode = sol["mode"]
    head = {"dc": "直流", "ac": "正弦稳态相量", "tran": "瞬态"}.get(mode, mode)
    L.append("## 分析（%s，参考点 = %s）" % (head, sol.get("ref", "0")))
    if mode == "ac":
        L.append("- ω = %s rad/s = %s Hz"
                 % (fs(sol["w"]), fd(sol["w"] / (2 * TAU2PI))))
    ref = sol.get("ref")
    V = sol["V"]
    ns = [n for n in V if n != ref]
    L.append("- 节点电压：" + "，".join("V(%s) = %s V" % (n, fnum(V[n])) for n in ns))
    if sol.get("branches"):
        L.append("- 支路电流（由 n1 经元件流向 n2 为正）：" + "，".join(
            "I(%s) = %s A" % (b["name"], fnum(b["i"])) for b in sol["branches"]))
    if sol.get("asks"):
        L.append("- **待求量**：")
        for label, val, unit in sol["asks"]:
            L.append("  - %s = %s %s" % (label, fnum(val), unit))
    th = sol.get("thevenin")
    port = sol.get("port") or ("?", "?")
    if th:
        L.append("- 戴维宁（端口 %s-%s，以 %s 为参考）：u_oc = %s V，i_sc = %s A，R_eq = %s Ω"
                 % (port[0], port[1], port[1], fs(th["u_oc"]), fs(th["i_sc"]),
                    fs(th["R_eq"])))
        if "R_L" in th:
            L.append("  - 接 R_L = %s Ω：u_L = %s V，i_L = %s A，P_L = %s W"
                     % (fs(th["R_L"]), fnum(th["u_L"]), fnum(th["i_L"]), fnum(th["P_L"])))
        if th.get("P_max") is not None:
            L.append("  - 最大功率 P_max = u_oc²/(4R_eq) = %s W" % fnum(th["P_max"]))
    if sol.get("checks"):
        L.append("- 校验：")
        for name, ok, why in sol["checks"]:
            L.append("  - [%s] %s：%s" % ("通过" if ok else "**不通过**", name, why))
    return "\n".join(L)


def report_logic(res):
    L = []
    if res["kind"] == "combo" and "verify" in res:
        L.append("## 组合逻辑（%d 个变量，穷举 %d 种输入组合）"
                 % (len(res["vars"]), res["verify"]["tested"]))
        if res["kmap"]:
            L.append("```\n%s\n```" % res["kmap"])
        L.append("- 最简与或式：`%s`（%d 个乘积项，%d 个文字）"
                 % (res["sop"], res["sop_products"], res["sop_literals"]))
        L.append("- 最简或与式：`%s`（%d 个和项，%d 个文字）"
                 % (res["pos"], res["pos_sums"], res["pos_literals"]))
        L.append("- 两级门实现（与非门另算）：%d 个与门 + %d 个或门 + %d 个非门"
                 % (res["gates"]["and"], res["gates"]["or"], res["gates"]["not"]))
        L.append("- 穷举校验：%s —— %d 种输入逐点代入，最简与或式与最简或与式都与给定函数一致"
                 % ("通过" if res["verify"]["ok"] else "**不通过**", res["verify"]["tested"]))
    elif "drive" in res:
        L.append("## 时序逻辑：%s，共 %d 拍" % (res["ff"], len(res["drive"])))
        L.append("| 拍 | Qⁿ | Qⁿ⁺¹ | 激励 |")
        L.append("|---|---|---|---|")
        for r in res["drive"]:
            L.append("| %d | %d | %d | `%s` |" % (r["beat"], r["qn"], r["qn1"], r["drive"]))
        L.append("- " + res["note"])
    else:
        L.append("## 时序逻辑：状态表（%d 位编码，共 %d 个编码）"
                 % (res["nbits"], 1 << res["nbits"]))
        L.append("- 闭环：" + "；".join(" → ".join(map(str, c + [c[0]])) for c in res["cycles"]))
        L.append("| 编码 | 能否回到闭环 | 试走路径 |")
        L.append("|---|---|---|")
        for r in res["selfstart"]:
            L.append("| %d | %s | %s |" % (r["state"], "能" if r["ok"] else "**不能**", r["path"]))
        L.append("- 自启动：%s（每个编码都真的试走过，路径见上表）"
                 % ("全部能" if res["ok"] else "存在不能自启动的编码"))
    return "\n".join(L)


# ============================================================ 自测
def _golden_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")


def selftest(verbose=False):
    ok = fail = 0
    msgs = []

    def chk(name, cond, detail=""):
        nonlocal ok, fail
        if cond:
            ok += 1
        else:
            fail += 1
            msgs.append("FAIL  %s  %s" % (name, detail))
        if verbose:
            print(("[ok]   " if cond else "[FAIL] ") + name
                  + (("   " + detail) if (detail and not cond) else ""))

    gd = _golden_dir()

    def has_golden(fname):
        """金题目录可能不在（circuit.py 被单独拷走时）。

        这种情况下 selftest 仍然必须跑得完：只跑内置的解析式/定理对拍，
        跳过依赖 golden/ 的回归，并在结尾明确说一句跳过了什么。
        """
        return os.path.exists(os.path.join(gd, fname))

    exp_path = os.path.join(gd, "expected.json")
    if os.path.exists(exp_path):
        with open(exp_path, encoding="utf-8") as fh:
            exp = json.load(fh)
        for fname in sorted(exp):
            item = exp[fname]
            card = load_card(os.path.join(gd, fname))
            sol = analyze_dc(card)
            V = sol["V"]
            for nd, want in item["V"].items():
                chk("%s V(%s)" % (fname, nd), fs(V[nd]) == want,
                    "得到 %s，期望 %s" % (fs(V[nd]), want))
            for nm, want in item["branches"].items():
                got = [b["i"] for b in sol["branches"] if b["name"] == nm]
                chk("%s I(%s)" % (fname, nm), bool(got) and fs(got[0]) == want,
                    "得到 %s，期望 %s" % (got and fs(got[0]), want))
            for label, want in item["asks"]:
                hit = [v for l, v, _u in sol["asks"] if l == label]
                chk("%s 求:%s" % (fname, label), bool(hit) and fs(hit[0]) == want,
                    "得到 %s，期望 %s" % (hit and fs(hit[0]), want))
            th = sol["thevenin"]
            if item.get("u_oc") and th:
                chk("%s u_oc" % fname, fs(th["u_oc"]) == item["u_oc"],
                    "得到 %s，期望 %s" % (fs(th["u_oc"]), item["u_oc"]))
                chk("%s i_sc" % fname, fs(th["i_sc"]) == item["i_sc"],
                    "得到 %s，期望 %s" % (fs(th["i_sc"]), item["i_sc"]))
                chk("%s R_eq" % fname, fs(th["R_eq"]) == item["R_eq"],
                    "得到 %s，期望 %s" % (fs(th["R_eq"]), item["R_eq"]))
            for name, good, why in sol["checks"]:
                chk("%s 自检:%s" % (fname, name), good, why)

    # ---- 相量：RLC 串联，与解析式 Z = R + j(ωL − 1/ωC) 对拍
    ac_card = parse_card("题名: RLC 串联\n类型: 相量\nω: 1000\n求: I(Vs)\n"
                         "V Vs 1 0 1V\nR R1 1 2 50Ω\nL L1 2 3 1mH\nC C1 3 0 100µF\n")
    sol = analyze_ac(ac_card)
    w = 1000.0
    Z = complex(50.0, w * 1e-3 - 1.0 / (w * 100e-6))
    Iexp = 1.0 / Z
    V3exp = Iexp * (-1j / (w * 100e-6))
    got = sol["V"]["3"]
    chk("相量 V(3) vs 解析式",
        abs(complex(float(got.re), float(got.im)) - V3exp) < 1e-12 * max(1.0, abs(V3exp)),
        "得到 %s，解析 %s" % (fd(got), V3exp))
    Ifind = [v for l, v, _u in sol["asks"]][0]
    chk("相量 I(Vs) vs 解析式（含「由 n1 经源流向 n2」符号约定）",
        abs(complex(float(Ifind.re), float(Ifind.im)) + Iexp) < 1e-12 * max(1.0, abs(Iexp)),
        "得到 %s，解析 %s" % (fd(Ifind), -Iexp))
    chk("相量 功率平衡", sol["checks"][0][1], sol["checks"][0][2])

    # ---- 频响：RC 低通 |H| = 1/√(1+(ωRC)²)
    for ratio in (Fraction(1, 10), Fraction(1), Fraction(10), Fraction(100)):
        wq = Fraction(1000) * ratio
        c2 = parse_card("题名: RC低通\n类型: 相量\nω: %s\nV Vs 1 0 1V\n"
                        "R R1 1 2 1kΩ\nC C1 2 0 1µF\n" % fs(wq))
        s2 = analyze_ac(c2)
        wr = float(wq)
        mag_exp = 1.0 / math.sqrt(1.0 + (wr * 1e-3) ** 2)
        chk("RC低通 |H| @ω=%s" % fd(wq), abs(abs(s2["V"]["2"]) - mag_exp) < 1e-12,
            "得到 %s，解析 %s" % (fd(abs(s2["V"]["2"])), mag_exp))

    # ---- 瞬态：RC 充电 u_C = U(1−e^(−t/τ))
    rc = "题名: RC 充电\n类型: 瞬态\nV Vs 1 0 10V\nR R1 1 2 1kΩ\nC C1 2 0 1µF\n"
    tau = 1e-3
    errs = {}
    for h in ("1e-5", "5e-6"):
        r = analyze_tran(parse_card(rc), dt=h, tstop="5e-3",
                         times=["1e-3", "3e-3", "5e-3"])
        err = max(abs(float(rec["uC"]["C1"]) - 10 * (1 - math.exp(-float(rec["t"]) / tau)))
                  for rec in r["recs"])
        errs[h] = err
        chk("瞬态 RC 充电 误差 h=%s" % h, err < 0.05, "最大误差 %g V（量程 10V）" % err)
    chk("瞬态 后向欧拉阶数（步长减半误差应同减半）",
        errs["5e-6"] < errs["1e-5"] * 0.6,
        "h=1e-5 误差 %g，h=5e-6 误差 %g" % (errs["1e-5"], errs["5e-6"]))

    # ---- 瞬态：RL 串联 i = (U/R)(1−e^(−t/τ))，τ = L/R = 1e-4 s
    # 注意 R 必须与 L 串联：若 L 直接并在电压源两端，i_L 是线性爬升 (U/L)·t，不是指数。
    rl = "题名: RL 电流\n类型: 瞬态\nV Vs 1 0 5V\nR R1 1 2 10Ω\nL L1 2 0 1mH\n"
    r = analyze_tran(parse_card(rl), dt="1e-6", tstop="5e-4", times=["1e-4", "5e-4"])
    tau2 = 1e-4
    for rec in r["recs"]:
        t = float(rec["t"])
        want = 0.5 * (1 - math.exp(-t / tau2))
        got = float(rec["iL"]["L1"])
        chk("瞬态 RL i_L(t=%g)" % t, abs(got - want) < 0.02,
            "得到 %g，解析 %g" % (got, want))
    # 反向对照：L 直接并在电压源两端时电流必须是线性爬升 (U/L)·t，不是指数
    rl2 = "题名: L 并在源两端\n类型: 瞬态\nV Vs 1 0 5V\nL L1 1 0 1mH\n"
    r2 = analyze_tran(parse_card(rl2), dt="1e-6", tstop="1e-4", times=["5e-5", "1e-4"])
    for rec in r2["recs"]:
        t = float(rec["t"])
        chk("瞬态 L 直并源 i_L=(U/L)t (t=%g)" % t,
            abs(float(rec["iL"]["L1"]) - 5.0 / 1e-3 * t) < 1e-6,
            "得到 %g，解析 %g" % (float(rec["iL"]["L1"]), 5.0 / 1e-3 * t))

    # ---- 二阶：RLC 串联阶跃响应（欠阻尼），与解析解对拍
    # u_C(t) = 1 − e^(−αt)·[cos(ω_d t) + (α/ω_d)·sin(ω_d t)]，α=R/2L，ω_d=√(ω₀²−α²)
    rlc = ("题名: RLC 阶跃\n类型: 瞬态\nV Vs 1 0 1V\nR R1 1 2 10Ω\n"
           "L L1 2 3 1mH\nC C1 3 0 1µF\n")
    Rr, Ll, Cc = 10.0, 1e-3, 1e-6
    alpha = Rr / (2 * Ll)
    w0 = 1.0 / math.sqrt(Ll * Cc)
    wd = math.sqrt(w0 * w0 - alpha * alpha)
    ts2 = [1e-5, 1e-4, 2e-4, 5e-4]
    worst = {}
    for h in ("1e-7", "5e-8"):
        r3 = analyze_tran(parse_card(rlc), dt=h, tstop="5e-4", times=[str(t) for t in ts2])
        e = 0.0
        for rec in r3["recs"]:
            t = float(rec["t"])
            want = 1 - math.exp(-alpha * t) * (math.cos(wd * t) + (alpha / wd) * math.sin(wd * t))
            e = max(e, abs(float(rec["uC"]["C1"]) - want))
        worst[h] = e
        chk("瞬态 二阶 RLC 阶跃 误差 h=%s" % h, e < 0.01, "最大误差 %g V（量程 1V）" % e)
    chk("瞬态 二阶 步长减半误差同减半",
        worst["5e-8"] < worst["1e-7"] * 0.6,
        "h=1e-7 误差 %g，h=5e-8 误差 %g" % (worst["1e-7"], worst["5e-8"]))

    # ---- 逻辑
    gd_logic = os.path.join(gd, "logic")

    def _lc(name):
        with open(os.path.join(gd_logic, name), encoding="utf-8") as fh:
            return fh.read()

    if os.path.isdir(gd_logic):
        rs = analyze_combo(parse_logic(_lc("comb1.logic")))
        chk("comb1 穷举校验", rs["verify"]["ok"], str(rs["verify"]))
        chk("comb1 最简式 = 2 项 4 文字",
            rs["sop_products"] == 2 and rs["sop_literals"] == 4,
            "得到 %d 项 %d 文字：%s" % (rs["sop_products"], rs["sop_literals"], rs["sop"]))
        rs2 = analyze_combo(parse_logic(_lc("comb2.logic")))
        chk("comb2 穷举校验", rs2["verify"]["ok"], str(rs2["verify"]))
        chk("comb2 最简式 = 2 项 4 文字",
            rs2["sop_products"] == 2 and rs2["sop_literals"] == 4,
            "得到 %d 项 %d 文字：%s" % (rs2["sop_products"], rs2["sop_literals"], rs2["sop"]))
        rq = analyze_seq(parse_logic(_lc("seq1.logic")))
        want = ["J=1 K=X", "J=X K=1", "J=0 K=X", "J=1 K=X", "J=X K=1", "J=1 K=X"]
        got = [d["drive"] for d in rq["drive"]]
        chk("seq1 JK 逐拍激励表", got == want, "得到 %s" % got)
        rq2 = analyze_seq(parse_logic(_lc("seq2.logic")))
        chk("seq2 闭环 = 0→1→2→0 且全编码自启动",
            bool(rq2["cycles"]) and rq2["cycles"][0] == [0, 1, 2] and rq2["ok"],
            "闭环 %r，自启动 %s" % (rq2["cycles"], rq2["ok"]))

    # ---- 运放（VCVS 建模）：反相放大，增益趋近 −R2/R1
    # 用 VCVS 建模理想运放时，输出端 3 与地之间跨着受控源，端口不能取在那里。
    # 有限增益 A 的误差约为 1/A·(1+R2/R1)，所以这里校验的是「有限增益下的真值」，
    # 同时给出 A=1e5 时与理想 −10 的偏差确实很小这一事实。
    for gain, want in ((100000, "-1000000/100011"), (1000000, "-10000000/1000011")):
        op = ("题名: 反相放大\nV Vs 1 0 1V\nR R1 1 2 1kΩ\nR R2 2 3 10kΩ\n"
              "R RL 3 0 10kΩ\nE E1 3 0 0 2 %d\n" % gain)
        so = analyze_dc(parse_card(op))
        chk("运放 有限增益 A=%d 的精确解" % gain, fs(so["V"]["3"]) == want,
            "得到 %s，期望 %s" % (fs(so["V"]["3"]), want))
    op = ("题名: 反相放大\nV Vs 1 0 1V\nR R1 1 2 1kΩ\nR R2 2 3 10kΩ\n"
          "R RL 3 0 10kΩ\nE E1 3 0 0 2 100000\n")
    v3 = float(analyze_dc(parse_card(op))["V"]["3"])
    chk("运放 A=1e5 时与理想 −R2/R1=−10 的偏差 < 0.01",
        abs(v3 + 10) < 0.01, "得到 %g" % v3)

    # ---- 叠加定理：线性电路里两个源各自单独作用的响应之和 = 共同作用
    # 关掉电压源 = 换成 0V 源（不能直接删掉：删掉会让那条支路断开，电路都变了）
    def _v2(text):
        return analyze_dc(parse_card(text))["V"]["2"]

    both = "题名: 叠加\nV Vs 1 0 10V\nI Is 0 2 2A\nR R1 1 2 4Ω\nR R2 2 0 6Ω\n"
    only_v = "题名: 叠加\nV Vs 1 0 10V\nI Is 0 2 0A\nR R1 1 2 4Ω\nR R2 2 0 6Ω\n"
    only_i = "题名: 叠加\nV Vs 1 0 0V\nI Is 0 2 2A\nR R1 1 2 4Ω\nR R2 2 0 6Ω\n"
    vb, vv, vi = _v2(both), _v2(only_v), _v2(only_i)
    chk("叠加定理 V(2)：共同作用 = 各自作用之和 %s = %s + %s"
        % (fs(vb), fs(vv), fs(vi)), vb == vv + vi,
        "%s vs %s + %s" % (fs(vb), fs(vv), fs(vi)))

    # ---- 戴维宁：用两个不同负载实测 u_L/i_L 反推 R_eq，必须等于注入法算出的 R_eq
    if has_golden("ex6.card"):
        for rl1, rl2 in ((Fraction(1), Fraction(7)), (Fraction(5, 2), Fraction(40))):
            a = analyze_dc(load_card(os.path.join(gd, "ex6.card")), rl=rl1)["thevenin"]
            b = analyze_dc(load_card(os.path.join(gd, "ex6.card")), rl=rl2)["thevenin"]
            R_from_two = (a["u_L"] - b["u_L"]) / (b["i_L"] - a["i_L"])
            chk("戴维宁 R_eq 由两个负载实测反推（R_L=%s/%s）" % (rl1, rl2),
                R_from_two == a["R_eq"],
                "反推得 %s，注入法得 %s" % (fs(R_from_two), fs(a["R_eq"])))

    # ---- 四种受控源的语义逐条对拍：SKILL.md 里写的定义必须就是代码的行为
    # 这些是"读反了仍然自洽"的地方，所以每条都用构造好的小电路把它钉死。
    def _bi(sol, nm):
        return [b["i"] for b in sol["branches"] if b["name"] == nm][0]

    # E (VCVS)：V(n1)−V(n2) = k·(V(c1)−V(c2))
    se = analyze_dc(parse_card("题名: E\nV Vs 1 0 2V\nR R1 1 2 1Ω\nR R2 2 0 1Ω\n"
                               "R R3 3 0 1Ω\nE E1 3 0 0 2 10\n"))
    chk("受控源 E：V(3)−V(0) = 10·(V(0)−V(2))",
        se["V"]["3"] == -10 * se["V"]["2"],
        "V(3)=%s，V(2)=%s" % (fs(se["V"]["3"]), fs(se["V"]["2"])))
    # G (VCCS)：由 n1 经 G 流向 n2 的电流 = k·(V(c1)−V(c2))
    sg = analyze_dc(parse_card("题名: G\nV Vs 1 0 2V\nR R1 1 2 1Ω\nR R2 2 0 1Ω\n"
                               "R R3 0 3 1Ω\nG G1 3 0 2 0 0.5\n"))
    chk("受控源 G：I(G1) 由 3 流向 0 = 0.5·(V(2)−V(0))",
        _bi(sg, "G1") == Fraction(1, 2) * sg["V"]["2"],
        "I(G1)=%s，V(2)=%s" % (fs(_bi(sg, "G1")), fs(sg["V"]["2"])))
    # H (CCVS)：V(n1)−V(n2) = k·I(ctrl)
    sh = analyze_dc(parse_card("题名: H\nV Vs 1 0 2V\nR R1 1 0 1Ω\nR R2 3 0 1Ω\n"
                               "H H1 3 0 Vs 2\n"))
    chk("受控源 H：V(3)−V(0) = 2·I(Vs)",
        sh["V"]["3"] == 2 * _bi(sh, "Vs"),
        "V(3)=%s，I(Vs)=%s" % (fs(sh["V"]["3"]), fs(_bi(sh, "Vs"))))
    # F (CCCS)：由 n1 经 F 流向 n2 的电流 = k·I(ctrl)
    sf = analyze_dc(parse_card("题名: F\nV Vs 1 0 2V\nR R1 1 0 1Ω\nR R2 4 0 2Ω\n"
                               "F F1 4 0 Vs 3\n"))
    chk("受控源 F：I(F1) 由 4 流向 0 = 3·I(Vs)",
        _bi(sf, "F1") == 3 * _bi(sf, "Vs"),
        "I(F1)=%s，I(Vs)=%s" % (fs(_bi(sf, "F1")), fs(_bi(sf, "Vs"))))

    if not os.path.isdir(gd) or not os.path.exists(exp_path):
        print("（注意：找不到 golden/ 金题目录，本次只跑了内置的解析式与定理对拍，"
              "没有跑 15 张金卡回归。完整回归需要把 golden/ 一起拷过来。）")
    print("自测：%d 项通过，%d 项失败" % (ok, fail))
    for m in msgs:
        print("  " + m)
    return fail == 0


# ============================================================ CLI
def _jsonable(sol):
    out = {"mode": sol["mode"], "ref": sol.get("ref"), "V": {}, "branches": {},
           "asks": [], "checks": []}
    for k, v in sol["V"].items():
        out["V"][k] = fs(v)
    for b in sol.get("branches", []):
        out["branches"][b["name"]] = fs(b["i"])
    out["asks"] = [[l, fs(v), u] for l, v, u in sol.get("asks", [])]
    th = sol.get("thevenin")
    if th:
        out["thevenin"] = dict((k, fs(v)) for k, v in th.items() if v is not None)
    out["checks"] = [[n, bool(o), w] for n, o, w in sol.get("checks", [])]
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "selftest":
        return 0 if selftest(verbose=("--verbose" in rest or "-v" in rest)) else 1
    if not rest:
        print("缺少文件参数。用法：python circuit.py %s 题文件" % cmd)
        return 2
    path, opts, i = rest[0], {}, 1
    while i < len(rest):
        a = rest[i]
        if a.startswith("--"):
            key = a[2:]
            if "=" in key:
                key, val = key.split("=", 1)
            else:
                val = rest[i + 1] if i + 1 < len(rest) else ""
                i += 1
            opts[key] = val
        i += 1
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if cmd == "logic":
            card = parse_logic(text, os.path.basename(path))
            res = analyze_combo(card) if card["kind"] == "combo" else analyze_seq(card)
            print(report_logic(res))
            good = res["verify"]["ok"] if "verify" in res else res.get("ok", True)
            return 0 if good else 1
        card = parse_card(text, os.path.basename(path))
        if cmd == "card":
            sol = analyze_dc(card, rl=(parse_number(opts["rl"]) if "rl" in opts else None))
        elif cmd == "ac":
            if "sweep" in opts:
                parts = opts["sweep"].split(",")
                a, b = parse_number(parts[0]), parse_number(parts[1])
                npts = int(parts[2]) if len(parts) > 2 else 10
                node = opts.get("out")
                if node is None:
                    probe = analyze_ac(card, a)
                    node = sorted(probe["V"].keys(), key=lambda s: (len(s), s))[-1]
                print("ω(rad/s)\t|V(%s)|\t相位(deg)" % node)
                for k in range(npts):
                    w = a if npts == 1 else a * ((b / a) ** Fraction(k, npts - 1))
                    v = analyze_ac(card, w)["V"][node]
                    print("%s\t%s\t%.4f" % (fd(w), fd(abs(v)),
                                            math.degrees(math.atan2(float(v.im), float(v.re)))))
                return 0
            warg = None
            if "w" in opts:
                warg = parse_number(opts["w"])
            elif "f" in opts:
                warg = parse_number(opts["f"]) * 2 * TAU2PI
            sol = analyze_ac(card, warg)
        elif cmd == "tran":
            times = [parse_number(x) for x in opts["at"].split(",")] if "at" in opts else None
            ic = {}
            if "ic" in opts:
                for tok in opts["ic"].split(","):
                    kv = tok.split("=")
                    if len(kv) == 2:
                        ic[kv[0].strip()] = parse_number(kv[1])
            r = analyze_tran(card, dt=opts.get("dt"), tstop=opts.get("tstop"),
                             times=times, ic=ic or None)
            print("## 瞬态（后向欧拉，步长 %s，时长 %s）" % (fs(r["dt"]), fs(r["tstop"])))
            keep = [n for n in r["nodes"] if n != r["ref"]]
            print("t(s)\t" + "\t".join("V(%s)" % n for n in keep))
            for rec in r["recs"]:
                print("\t".join([fd(rec["t"])] + [fd(rec["V"][n]) for n in keep]))
            if r["uC"]:
                print("末态 uC：" + "，".join("%s = %s V" % (k, fd(v)) for k, v in r["uC"].items()))
            if r["iL"]:
                print("末态 iL：" + "，".join("%s = %s A" % (k, fd(v)) for k, v in r["iL"].items()))
            return 0
        elif cmd == "deck":
            print(to_spice(card))
            return 0
        else:
            print("未知子命令 %r（可用：card / ac / tran / logic / deck / selftest）" % cmd)
            return 2
    except (CardError, LogicError) as exc:
        print("题目卡有问题：\n  %s" % exc)
        return 2
    except SingularError as exc:
        print("求解失败：%s\n  检查：端口是否跨着理想电压源、是否有悬空节点、"
              "是否两个电压源并联。" % exc)
        return 2

    if "json" in opts:
        print(json.dumps(_jsonable(sol), ensure_ascii=False, indent=1))
    else:
        print(report(sol))
    return 0


if __name__ == "__main__":
    sys.exit(main())
