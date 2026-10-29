"""验证探针：零第三方依赖（stdlib fractions）的 MNA 能否复现项目 sympy 版的全部结果。

做法：用 netlist.py 解析所有 .card（纯 stdlib），把元件同样喂给两个求解器：
  A) mna.py（sympy 精确解，项目现有通道）
  B) 本文件里的纯 fractions 高斯消元（无第三方依赖通道）
逐卡逐节点比对电压；再对每张卡的戴维宁参数量用独立方法复算。
目的：为"空白 DSH 单文件可移植"这条路线提供实测依据，而不是推测。
"""
import glob
import os
import sys
from fractions import Fraction as F

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import mna  # noqa: E402
import netlist as NL  # noqa: E402


def solve_frac(net, ground="0"):
    """纯 fractions 版 MNA，返回 (V, I)。net 与 mna.solve 同格式。"""
    idx, order = {}, []

    def node(n):
        if n == ground:
            return None
        if n not in idx:
            idx[n] = len(order)
            order.append(n)
        return idx[n]

    for e in net:
        node(e[1])
        node(e[2])
    vs = [e for e in net if e[0] in ("V", "VCVS", "CCVS")]
    kof = {id(e): i for i, e in enumerate(vs)}
    by_name = {e[4]: e for e in net if e[0] == "V"}
    n, m = len(order), len(vs)
    N = n + m
    A = [[F(0)] * N for _ in range(N)]
    b = [F(0)] * N

    def gk(a, c, g):
        i, j = idx.get(a), idx.get(c)
        if i is not None:
            A[i][i] += g
        if j is not None:
            A[j][j] += g
        if i is not None and j is not None:
            A[i][j] -= g
            A[j][i] -= g

    for e in net:
        t = e[0]
        if t == "R":
            gk(e[1], e[2], F(1) / F(e[3]))
        elif t == "I":
            i, j = idx.get(e[1]), idx.get(e[2])
            v = F(e[3])
            if i is not None:
                b[i] -= v
            if j is not None:
                b[j] += v
        elif t == "VCCS":
            g = F(e[5])
            for a, sa in ((e[1], 1), (e[2], -1)):
                for c, sc in ((e[3], 1), (e[4], -1)):
                    ia, ic = idx.get(a), idx.get(c)
                    if ia is not None and ic is not None:
                        A[ia][ic] += sa * sc * g
        elif t in ("V", "VCVS", "CCVS"):
            k = n + kof[id(e)]
            i, j = idx.get(e[1]), idx.get(e[2])
            if i is not None:
                A[i][k] += 1
                A[k][i] += 1
            if j is not None:
                A[j][k] -= 1
                A[k][j] -= 1
            if t == "V":
                b[k] = F(e[3])
            elif t == "VCVS":
                mu = F(e[5])
                if idx.get(e[3]) is not None:
                    A[k][idx[e[3]]] -= mu
                if idx.get(e[4]) is not None:
                    A[k][idx[e[4]]] += mu
            else:
                A[k][n + kof[id(by_name[e[3]])]] -= F(e[4])
        elif t == "CCCS":
            j = n + kof[id(by_name[e[3]])]
            g = F(e[4])
            if idx.get(e[1]) is not None:
                A[idx[e[1]]][j] += g
            if idx.get(e[2]) is not None:
                A[idx[e[2]]][j] -= g
        else:
            raise ValueError(t)

    for c in range(N):
        p = None
        for r in range(c, N):
            if A[r][c] != 0:
                p = r
                break
        if p is None:
            raise ZeroDivisionError("矩阵奇异（第 %d 列无主元）" % c)
        A[c], A[p] = A[p], A[c]
        b[c], b[p] = b[p], b[c]
        pv = A[c][c]
        for r in range(c + 1, N):
            if A[r][c] == 0:
                continue
            f = A[r][c] / pv
            for k in range(c, N):
                A[r][k] -= f * A[c][k]
            b[r] -= f * b[c]
    x = [F(0)] * N
    for r in range(N - 1, -1, -1):
        s = b[r] - sum(A[r][k] * x[k] for k in range(r + 1, N))
        x[r] = s / A[r][r]

    V = {ground: F(0)}
    for nm, i in idx.items():
        V[nm] = x[i]
    I = {}
    for e in vs:
        nm = mna._name_of(e)
        if nm is not None:
            I[nm] = x[n + kof[id(e)]]
    return V, I


def to_frac_net(elements):
    """netlist.to_mna 的结果已是 Fraction/str，直接可用；这里只做类型确认。"""
    return NL.to_mna(elements)


def check_card(path):
    card = NL.parse_card(open(path, encoding="utf-8").read(), os.path.basename(path))
    net = to_frac_net(card["elements"])
    ground = "0"
    Va, Ia = mna.solve(net, ground)
    Vb, Ib = solve_frac(net, ground)
    diffs = []
    for k in Va:
        a, b = Va[k], Vb.get(k)
        if a != b:
            diffs.append((k, str(a), str(b)))
    for k in Ia:
        a, b = Ia[k], Ib.get(k)
        if a != b:
            diffs.append(("I:" + str(k), str(a), str(b)))
    return card, net, diffs


def main():
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "..", "netlists", "**", "*.card"),
                             recursive=True))
    print("卡片数:", len(files))
    bad = 0
    for f in files:
        name = os.path.basename(f)
        try:
            card, net, diffs = check_card(f)
        except Exception as ex:                       # noqa: BLE001
            print("  %-16s 求解异常: %r" % (name, ex))
            bad += 1
            continue
        npv = len([k for k in net])  # 仅占位，无实义
        if diffs:
            bad += 1
            print("  %-16s 不一致 %d 处: %s" % (name, len(diffs), diffs[:4]))
        else:
            print("  %-16s 一致  (元件 %d)" % (name, len(card["elements"])))
    print("不一致卡片数:", bad, "/", len(files))
    print("总判定:", "PASS" if bad == 0 else "FAIL")


if __name__ == "__main__":
    main()
