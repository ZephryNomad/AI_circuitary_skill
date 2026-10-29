"""spice_check.py —— 用真实 ngspice 交叉校验本工程的 MNA 求解结果

为什么要有这一层
    tools/mna.py 是我自己写的精确 MNA，tools/netlist.py 是我自己写的网表生成器。
    自己写的生成器 + 自己写的求解器，两边同时错成一致是完全可能的。
    所以必须请第三方（ngspice，工业级 SPICE3 实现）来算一遍同一张网表：
    节点电压对得上，才能说"这张网表真的是那道题"。

做法
    1. 题目卡 -> SPICE 网表（netlist.to_spice）
    2. 在网表里插入 .print op v(所有节点)，交给 ngspice -b 批处理
    3. 解析 ngspice 输出里的节点电压，与本工程 mna.solve 的结果逐个比对
       容差：相对 1e-9（ngspice 是双精度浮点，本工程是精确有理数）
"""
import os
import re
import subprocess
import sys
import tempfile
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mna
import netlist as NL

def _extra_candidates():
    """常见安装位置，全部由环境变量拼出来，不含任何写死的用户路径。"""
    out = []
    for env, sub in (("ProgramFiles", ("ngspice", "bin")),
                     ("ProgramFiles(x86)", ("ngspice", "bin")),
                     ("LOCALAPPDATA", ("ngspice", "bin"))):
        base = os.environ.get(env)
        if base:
            out.append(os.path.join(base, *sub, "ngspice_con.exe"))
    return out


def _find_ngspice():
    cands = []
    # 1. 环境变量直接指定
    if os.environ.get("NGSPICE"):
        cands.append(os.environ["NGSPICE"])
    # 2. conda 临时环境（README 里那条 conda create 装到这里）
    cands.append(os.path.join(os.environ.get("TEMP", "/tmp"), "ngsenv",
                              "Library", "bin", "ngspice_con.exe"))
    # 3. 常见安装位置
    cands.extend(_extra_candidates())
    # 4. PATH
    cands.extend(["ngspice_con", "ngspice"])
    for c in cands:
        if os.path.isabs(c):
            if os.path.isfile(c):
                return c
        else:
            from shutil import which
            w = which(c)
            if w:
                return w
    return None


def run_ngspice(net_text, timeout=60):
    """把网表交给 ngspice 跑 .op，返回 {节点: float}。失败抛 RuntimeError。

    用 .control 块里的 op + print all，原因是：
      - 批处理模式下 .print op 输出的是"Index  v(1)  v(2)"的表格，解析脆弱；
      - 控制模式的 print 给的是 "v(1) = 5.000000e+00" 稳定的键值行。
    节点 0 是参考地，ngspice 不提供 v(0)，所以跳过。
    """
    exe = _find_ngspice()
    if not exe:
        raise RuntimeError("找不到 ngspice_con 可执行文件")
    body = []
    for raw in net_text.splitlines():
        s = raw.strip()
        low = s.lower()
        if low.startswith(".op") or low.startswith(".end") or low.startswith(".print"):
            continue
        body.append(s)
    body.append(".control")
    body.append("set numdgt=12")   # 默认只印 6 位有效数字，会把 16/3 截成 5.33333
    body.append("op")
    body.append("print all")
    body.append(".endc")
    body.append(".end")

    fd, path = tempfile.mkstemp(suffix=".cir", text=True)
    os.close(fd)
    try:
        with open(path, "w", encoding="ascii", errors="replace") as f:
            f.write("\n".join(body) + "\n")
        r = subprocess.run([exe, "-b", path], capture_output=True, text=True,
                           timeout=timeout, errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        vals = {}
        for m in re.finditer(r"\bv\(([^)\s]+)\)\s*=\s*([-+0-9.eE]+)", out):
            nd = m.group(1).strip()
            if nd in ("0",):
                continue
            try:
                vals[nd] = float(m.group(2))
            except ValueError:
                pass
        if not vals:
            raise RuntimeError("ngspice 没有输出节点电压：\n%s" % out[-1500:])
        return vals, out
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def check_card(card, tol=1e-9):
    """返回 (本工程解, ngspice 解, 差异列表)。差异为空即两个引擎一致。"""
    txt = NL.to_spice(card)
    nodes = NL.nodes_of(card["elements"])
    ground = "0" if "0" in nodes else nodes[0]
    mine, _ = mna.solve(NL.to_mna(card["elements"]), ground=ground)
    theirs, _raw = run_ngspice(txt)

    diff = []
    for nd, v_mine in mine.items():
        if nd == ground:
            continue
        if nd not in theirs:
            diff.append("节点 %s：ngspice 未报告" % nd)
            continue
        a = float(Fraction(v_mine))
        b = theirs[nd]
        scale = max(abs(a), abs(b), 1.0)
        if abs(a - b) / scale > tol:
            diff.append("节点 %s：本工程 %s，ngspice %.12g（相对差 %.3e）"
                        % (nd, v_mine, b, abs(a - b) / scale))
    for nd in theirs:
        if nd not in mine:
            diff.append("节点 %s：ngspice 报了但本工程没有" % nd)
    return mine, theirs, diff


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("用法：python tools/spice_check.py netlists\\ex1.card [...]",
              file=sys.stderr)
        return 2
    exe = _find_ngspice()
    print("ngspice = %s" % (exe or "未找到"))
    if not exe:
        print("本层交叉校验需要 ngspice 才能进行。安装方式任选其一：", file=sys.stderr)
        print("  conda create -y -q -p \"$env:TEMP\\ngsenv\" -c conda-forge ngspice", file=sys.stderr)
        print("  （或把你已有的 ngspice_con 路径写进环境变量 NGSPICE）", file=sys.stderr)
        print("查找顺序：NGSPICE 环境变量 -> %TEMP%\\ngsenv -> Program Files -> PATH", file=sys.stderr)
        return 3
    bad = 0
    for p in argv:
        with open(p, encoding="utf-8") as f:
            card = NL.parse_card(f.read(),
                                 title_fallback=os.path.basename(p))
        try:
            mine, theirs, diff = check_card(card)
        except (RuntimeError, NL.CardError) as e:
            print("[失败] %s：%s" % (p, e))
            bad += 1
            continue
        print("\n== %s ==" % card["title"])
        for nd in sorted(theirs, key=lambda x: (x != "0", x)):
            print("  V(%s): 本工程 %-10s ngspice %.12g"
                  % (nd, mine.get(nd, "?"), theirs[nd]))
        if diff:
            bad += 1
            for d in diff:
                print("  [不一致] " + d)
        else:
            print("  [一致] 全部节点电压与 ngspice 相符")
    print("\n%d/%d 张卡与 ngspice 一致" % (len(argv) - bad, len(argv)))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
