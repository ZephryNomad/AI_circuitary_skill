"""netlist.py —— 电路题目卡 ↔ SPICE 网表 双向转换 + 独立复算

为什么要这个模块
    电路原理的题目（戴维宁、节点法、网孔法……）本质是"拓扑 + 元件值"。
    把题目写成网表后，机器就能算：不用手推，也不会因为一处符号错导致全盘错。
    但"转成网表"这一步如果靠人眼抄，抄错的概率与手推一样高，
    所以这里做成可往返(round-trip)的：题目卡 -> 网表 -> 再解析回来 -> 求解 -> 比对。

三层
    题目卡(.dsl)  人写，中文友好，一行一个元件
    SPICE 网表    机器/仿真器读，标准 SPICE3 直流语法
    内部模型      [(kind, n1, n2, ...)]，与 tools/mna.py 的元件元组格式一致

题目卡语法（# 或 * 开头为注释）
    题名: 例3 不平衡电桥
    端口: 2 3                       # 戴维宁端口 a=2, b=3（可省略）
    求: R3                          # 求 R3 由 n1 流向 n2 的电流（可写多条）
    求: V(3)                        # 求节点 3 的电压
    V Us 1 0 12V                    # 电压源：V(1)-V(0)=12，1 是 + 极
    R 1 2 1Ω                        # 电阻
    I Is 0 1 2A                     # 电流源：2A 由 0 经源流向 1
    E E1 3 0 2 0 2                  # VCVS：V(3)-V(0)=2*(V(2)-V(0))
    G G1 3 0 2 0 1                  # VCCS：由 3 经源流向 0 的电流 = 1*(V(2)-V(0))
    H H1 3 0 Us 4                   # CCVS：V(3)-V(0)=4*I(Us)
    F F1 3 0 Us 2                   # CCCS：由 3 经源流向 0 的电流 = 2*I(Us)

数值写法：整数 12 / 小数 0.5 / 分数 3/2 / 后缀 2k=2000、1M=1000000；
可带单位 V A Ω ohm 伏 安 欧（只做剥除，不做换算）。
"""
import re
from fractions import Fraction

NUM_RE = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+)(?:/\d+(?:\.\d+)?)?)([kKM]?)$")
UNIT_RE = re.compile(r"(?:V|A|Ω|ohm|Ohm|OHM|伏|安|欧|欧姆|v|a|ω)$")
SUFFIX = {"": 1, "k": 1000, "K": 1000, "M": 1000000}

KINDS = ("R", "V", "I", "E", "G", "H", "F")
DESIGNATOR = {"R": "R", "V": "V", "I": "I", "E": "E", "G": "G", "H": "H", "F": "F"}
KIND_CN = {"R": "电阻", "V": "独立电压源", "I": "独立电流源",
           "E": "VCVS 电压控制电压源", "G": "VCCS 电压控制电流源",
           "H": "CCVS 电流控制电压源", "F": "CCCS 电流控制电流源"}
# SPICE 里需要一个直流工作点分析才会给出各节点电压
TAIL = [".op", ".end"]


class CardError(ValueError):
    """题目卡/网表里的语法或语义错误，带行号，便于定位。"""


def parse_number(tok):
    """把 '12' '0.5' '3/2' '2k' '12V' '1Ω' 解析成精确 Fraction。"""
    s = tok.strip().replace("−", "-").replace("，", ",")
    s = UNIT_RE.sub("", s)
    m = NUM_RE.match(s)
    if not m:
        raise CardError("无法解析数值 %r" % tok)
    body, suf = m.group(1), m.group(2)
    mult = SUFFIX[suf]
    if "/" in body:
        a, b = body.split("/")
        f = Fraction(a) / Fraction(b)
    else:
        f = Fraction(body)
    return f * mult


def fmt_number(v):
    """Fraction -> SPICE 文本。能精确表达就写精确十进制，否则给 12 位有效数字。"""
    v = Fraction(v)
    den = v.denominator
    d = den
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d == 1:                       # 有限小数
        q = float(v)
        if q == int(q):
            return str(int(q))
        s = repr(q)
        return s
    return "%.12g" % float(v)


# ----------------------------------------------------------------- 题目卡
def _split_asks(s):
    """把 '求:' 后面的文本切成待求量列表，括号内的分隔符不切。

    'R3 V(2,3) I(Us)'  ->  ['R3', 'V(2,3)', 'I(Us)']
    """
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


def parse_card(text, title_fallback="untitled"):
    """解析题目卡文本 -> dict(title, port, elements, meta)。"""
    # Windows 记事本 / PowerShell 5 的 Set-Content -Encoding utf8 会写 UTF-8 BOM，
    # 不去掉会让首行的 "题名:" 变成 "\ufeff题名:" 而被判为未知元件类型。
    if text.startswith("\ufeff"):
        text = text[1:]
    title = title_fallback
    port = None
    elements = []
    meta = {}
    counters = {k: 0 for k in KINDS}
    used = set()

    def new_name(kind):
        while True:
            counters[kind] += 1
            nm = "%s%d" % (DESIGNATOR[kind], counters[kind])
            if nm not in used:
                used.add(nm)
                return nm

    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#")[0].split("*")[0].strip()
        if not line:
            continue
        # 中英文字段写法：题名: xxx / 端口: a b / title: xxx
        m = re.match(r"^(题名|题目|title)\s*[:：]\s*(.+)$", line, re.I)
        if m:
            title = m.group(2).strip()
            continue
        m = re.match(r"^(端口|port)\s*[:：]\s*(.+)$", line, re.I)
        if m:
            parts = [p for p in re.split(r"[\s,，=]+", m.group(2).strip()) if p]
            if len(parts) != 2:
                raise CardError("第 %d 行：端口需要两个节点，例如 '端口: 2 3'" % ln)
            port = (parts[0], parts[1])
            continue
        m = re.match(r"^(备注|note)\s*[:：]\s*(.+)$", line, re.I)
        if m:
            meta["note"] = m.group(2).strip()
            continue
        # 求: R3  /  求: V(3)   —— 指定要算的支路电流或节点电压，可多条
        m = re.match(r"^(求|求取|find)\s*[:：]\s*(.+)$", line, re.I)
        if m:
            # 一行可写多个待求量（空格分隔）。括号内的逗号是 V(2,3) 的分隔符，
            # 不能当列表分隔符，否则 V(2,3) 会被劈成 "V(2" 和 "3)"。
            meta.setdefault("asks", []).extend(
                [x for x in _split_asks(m.group(2)) if x])
            continue

        tok = re.split(r"[\s,，]+", line)
        kind = tok[0].upper()
        if kind not in KINDS:
            raise CardError("第 %d 行：未知元件类型 %r（可用 %s）"
                            % (ln, tok[0], "/".join(KINDS)))
        try:
            if kind in ("R", "V", "I"):
                # 三种写法：[R] n1 n2 value  或  [V] name n1 n2 value
                if len(tok) == 4:
                    n1, n2, val = tok[1], tok[2], tok[3]
                    name = None
                elif len(tok) == 5:
                    name, n1, n2, val = tok[1], tok[2], tok[3], tok[4]
                else:
                    raise CardError("字段数不对")
                elements.append({"kind": kind, "n1": n1, "n2": n2,
                                 "value": parse_number(val), "name": name,
                                 "line": ln, "_src": raw.strip()})
            elif kind in ("E", "G"):
                # kind [name] n+ n- nc+ nc- gain   —— tok 含开头的 kind，故为 7 或 6
                if len(tok) == 7:
                    name, np_, nm, cp, cm, gain = tok[1:]
                elif len(tok) == 6:
                    name = None
                    np_, nm, cp, cm, gain = tok[1:]
                else:
                    raise CardError("字段数不对（受控源应为「E 名称 n+ n- c+ c- 系数」）")
                elements.append({"kind": kind, "n1": np_, "n2": nm,
                                 "c1": cp, "c2": cm,
                                 "value": parse_number(gain), "name": name,
                                 "line": ln, "_src": raw.strip()})
            else:  # H / F
                # kind [name] n+ n- 控制源 gain  —— tok 含开头的 kind，故为 6 或 5
                if len(tok) == 6:
                    name, np_, nm, ctrl, val = tok[1:]
                elif len(tok) == 5:
                    name = None
                    np_, nm, ctrl, val = tok[1:]
                else:
                    raise CardError("字段数不对（受控源应为「H 名称 n+ n- 控制源 系数」）")
                elements.append({"kind": kind, "n1": np_, "n2": nm,
                                 "ctrl": ctrl, "value": parse_number(val),
                                 "name": name, "line": ln,
                                 "_src": raw.strip()})
        except CardError as e:
            raise CardError("第 %d 行：%s —— %r" % (ln, e, raw.strip()))

    # 补全元件名（SPICE 必须有名字；H/F 的控制源要用电压源名）
    # 先把所有显式名登记进 used，避免自动名与后面出现的显式名撞车
    used.update(e["name"] for e in elements if e["name"])

    # SPICE 用行首字母判定元件类型，所以显式名也必须以对应位号开头。
    # 用户写 Us 这种"人话名字"时自动补前缀成 VUs，原标签记在 _orig 里供报告显示。
    rename = {}
    for e in elements:
        old = e["name"]
        if not old:
            continue
        want = DESIGNATOR[e["kind"]]
        if not old[:1].upper() == want:
            new = want + old
            n, i = new, 1
            while n in used:
                i += 1
                n = "%s%d" % (new, i)
            used.add(n)
            rename[old] = n
            e["name"] = n
            e["_orig"] = old
    for e in elements:
        if e.get("ctrl") in rename:
            e["ctrl"] = rename[e["ctrl"]]

    for e in elements:
        if not e["name"]:
            e["name"] = new_name(e["kind"])
    dup = [n for n in {e["name"] for e in elements}
           if sum(1 for e in elements if e["name"] == n) > 1]
    if dup:
        raise CardError("元件名重复：%s" % "、".join(sorted(dup)))
    # 名字全部就位后再校验控制源（否则自动命名的电压源无法被引用）
    vnames = {e["name"] for e in elements if e["kind"] == "V"}
    for e in elements:
        if e["kind"] in ("H", "F"):
            if e["ctrl"] not in vnames:
                raise CardError("%s 的控制源 %r 必须是一个具名的独立电压源 V"
                                % (e["name"], e["ctrl"]))
            if e["ctrl"] == e["name"]:
                raise CardError("%s 不能控制自己" % e["name"])
    return {"title": title, "port": port, "elements": elements, "meta": meta}


def nodes_of(elements):
    out = []
    for e in elements:
        for k in ("n1", "n2", "c1", "c2"):
            if k in e and e[k] not in out:
                out.append(e[k])
    return out


# --------------------------------------------------------------- 网表输出
def to_spice(card, header_extra=None):
    """题目卡 -> SPICE 网表文本。"""
    el = card["elements"]
    nodes = nodes_of(el)
    ground = "0" if "0" in nodes else None
    lines = ["* %s" % card["title"],
             "* 由 circuitary/tools/netlist.py 生成；元件语义与 SPICE3 一致"]
    if ground:
        lines.append("* 参考节点(地) = 0")
    lines.append("* 节点清单: " + ", ".join(nodes))
    if card["port"]:
        a, b = card["port"]
        lines.append("* 戴维宁端口: a=%s  b=%s（开路电压 u_oc = V(a)-V(b)）" % (a, b))
    if header_extra:
        for k, v in header_extra.items():
            lines.append("* %s: %s" % (k, v))
    lines.append("*")
    for e in el:
        k = e["kind"]
        if k in ("R", "V", "I"):
            lines.append("%-6s %-4s %-4s %s" % (e["name"], e["n1"], e["n2"],
                                                fmt_number(e["value"])))
        elif k in ("E", "G"):
            lines.append("%-6s %-4s %-4s %-4s %-4s %s"
                         % (e["name"], e["n1"], e["n2"], e["c1"], e["c2"],
                            fmt_number(e["value"])))
        else:
            lines.append("%-6s %-4s %-4s %-4s %s"
                         % (e["name"], e["n1"], e["n2"], e["ctrl"],
                            fmt_number(e["value"])))
    lines.extend(TAIL)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------- 网表解析
def parse_spice(text):
    """SPICE 网表文本 -> (elements, port)。独立实现，不复用题目卡解析器。"""
    body = []
    for ln, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s[0] in "*#":
            continue
        low = s.lower()
        if low.startswith(".end"):
            break
        if low.startswith("."):
            continue
        body.append((ln, s))

    elements = []
    ports = []
    for ln, s in body:
        tok = re.split(r"[\s,]+", s)
        head = tok[0]
        kind = head[0].upper()
        if kind not in KINDS:
            raise CardError("第 %d 行：无法识别的元件 %r" % (ln, head))
        if len(tok) < 4:
            raise CardError("第 %d 行：字段不足 %r" % (ln, s))
        name = head
        if kind in ("R", "V", "I"):
            if kind == "R" and len(tok) == 4 and tok[3].upper() in ("DC",):
                raise CardError("第 %d 行：不支持 DC 关键字" % ln)
            n1, n2, val = tok[1], tok[2], tok[3]
            elements.append({"kind": kind, "n1": n1, "n2": n2,
                             "value": parse_number(val), "name": name})
        elif kind in ("E", "G"):
            if len(tok) < 6:
                raise CardError("第 %d 行：受控源需要 5 个参数 %r" % (ln, s))
            elements.append({"kind": kind, "n1": tok[1], "n2": tok[2],
                             "c1": tok[3], "c2": tok[4],
                             "value": parse_number(tok[5]), "name": name})
        else:
            if len(tok) < 5:
                raise CardError("第 %d 行：受控源需要 4 个参数 %r" % (ln, s))
            elements.append({"kind": kind, "n1": tok[1], "n2": tok[2],
                             "ctrl": tok[3], "value": parse_number(tok[4]),
                             "name": name})
    return {"title": "parsed", "port": ports[0] if ports else None,
            "elements": elements, "meta": {}}


# ------------------------------------------------- 内部模型 <-> mna 元组
def to_mna(elements):
    """转成 tools/mna.py 的元件元组列表 + 电压源名映射。"""
    net = []
    for e in elements:
        k = e["kind"]
        if k == "R":
            net.append(("R", e["n1"], e["n2"], e["value"]))
        elif k == "V":
            net.append(("V", e["n1"], e["n2"], e["value"], e["name"]))
        elif k == "I":
            net.append(("I", e["n1"], e["n2"], e["value"]))
        elif k == "E":
            net.append(("VCVS", e["n1"], e["n2"], e["c1"], e["c2"],
                        e["value"], e["name"]))
        elif k == "G":
            net.append(("VCCS", e["n1"], e["n2"], e["c1"], e["c2"], e["value"]))
        elif k == "H":
            net.append(("CCVS", e["n1"], e["n2"], e["ctrl"], e["value"],
                        e["name"]))
        elif k == "F":
            net.append(("CCCS", e["n1"], e["n2"], e["ctrl"], e["value"]))
    return net


def netlist_table(card):
    """生成"题目 -> 网表"的人读对照表（markdown 表格行）。"""
    rows = []
    for e in card["elements"]:
        k = e["kind"]
        if k in ("R", "V", "I"):
            spice = "%s %s %s %s" % (e["name"], e["n1"], e["n2"],
                                     fmt_number(e["value"]))
            desc = "%s 接在 %s-%s 之间，值 %s" % (KIND_CN[k], e["n1"], e["n2"],
                                                 fmt_number(e["value"]))
        elif k in ("E", "G"):
            spice = "%s %s %s %s %s %s" % (e["name"], e["n1"], e["n2"], e["c1"],
                                           e["c2"], fmt_number(e["value"]))
            desc = "%s：输出端 %s-%s，受 %s-%s 的电压控制，系数 %s" % (
                KIND_CN[k], e["n1"], e["n2"], e["c1"], e["c2"],
                fmt_number(e["value"]))
        else:
            spice = "%s %s %s %s %s" % (e["name"], e["n1"], e["n2"], e["ctrl"],
                                        fmt_number(e["value"]))
            desc = "%s：输出端 %s-%s，受 %s 的电流控制，系数 %s" % (
                KIND_CN[k], e["n1"], e["n2"], e["ctrl"], fmt_number(e["value"]))
        rows.append((e["name"], KIND_CN[k], desc, spice))
    return rows
