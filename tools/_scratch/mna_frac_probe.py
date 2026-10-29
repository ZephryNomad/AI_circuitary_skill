"""可行性探针：零第三方依赖（只用 fractions）的精确 MNA。

目的：验证"单文件、无 sympy/ngspice 也能精确解线性直流"这条路线是否成立，
以便向空白 DSH 交付时给出有依据的体积与正确性承诺。
只做最小实现，不解戴维宁，仅验证节点电压与支路电流。
"""
from fractions import Fraction as F

NET = [
    ("V", 1, 0, 8, "Us"),
    ("R", 1, 2, 4),
    ("R", 2, 0, 4),
    ("R", 2, 3, 1),
    ("R", 3, 4, 2),
    ("V", 4, 0, 10, "U2"),
    ("R", 3, 5, 2),
    ("I", 0, 5, 2),
]

EXPECT_V = {1: F(8), 2: F(8), 3: F(10), 4: F(10), 5: F(14)}
EXPECT_I = {"Us": F(0), "U2": F(0)}


def solve(net, ground=0):
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
    vs = [e for e in net if e[0] == "V"]
    kof = {id(e): i for i, e in enumerate(vs)}
    n, m = len(order), len(vs)
    N = n + m
    A = [[F(0)] * N for _ in range(N)]
    b = [F(0)] * N

    for e in net:
        t = e[0]
        if t == "R":
            g = F(1) / F(e[3])
            i, j = idx.get(e[1]), idx.get(e[2])
            if i is not None:
                A[i][i] += g
            if j is not None:
                A[j][j] += g
            if i is not None and j is not None:
                A[i][j] -= g
                A[j][i] -= g
        elif t == "I":
            i, j = idx.get(e[1]), idx.get(e[2])
            v = F(e[3])
            if i is not None:
                b[i] -= v
            if j is not None:
                b[j] += v
        elif t == "V":
            k = n + kof[id(e)]
            i, j = idx.get(e[1]), idx.get(e[2])
            if i is not None:
                A[i][k] += 1
                A[k][i] += 1
            if j is not None:
                A[j][k] -= 1
                A[k][j] -= 1
            b[k] = F(e[3])

    # 带部分主元的高斯消元（精确分数，无浮点）
    for c in range(N):
        p = next(r for r in range(c, N) if A[r][c] != 0)
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
    for name, i in idx.items():
        V[name] = x[i]
    I = {}
    for e in vs:
        I[e[4]] = x[n + kof[id(e)]]
    return V, I


if __name__ == "__main__":
    V, I = solve(NET)
    print("V =", {k: str(v) for k, v in sorted(V.items())})
    print("I =", {k: str(v) for k, v in I.items()})
    print("I(R3) =", V[2] - V[3], "A")   # R3 由 2 流向 3
    ok_v = all(V[k] == v for k, v in EXPECT_V.items())
    ok_i = all(I[k] == v for k, v in EXPECT_I.items())
    ok_r3 = (V[2] - V[3]) == F(-2)
    print("节点电压一致:", ok_v, "| 支路电流一致:", ok_i, "| I(R3)=-2A:", ok_r3)
    print("总判定:", "PASS" if (ok_v and ok_i and ok_r3) else "FAIL")
