"""MNA + 戴维宁参数提取（重写，逻辑更直接）。

数值类型说明
    电阻值可以是 int / Fraction / float，也可以是**复数**（用 sympy 的 I 表示），
    后者用于正弦稳态相量分析：把 C 写成 1/(jωC)、L 写成 jωL 当作"阻抗"传进来即可。
    这样同一套 MNA 既解直流，也解相量，不必维护两套。
"""
from sympy import Matrix, Rational, zeros, simplify, sympify


def _val(x):
    """把元件数值转成 sympy 能精确处理的数（支持整数、分数、复数、符号）。"""
    if isinstance(x, (int, Rational)):
        return x
    return sympify(x)


def _name_of(e):
    """取元件自带的名字字段（V/VCVS/CCVS 各自位置不同）。没有名字返回 None。"""
    t = e[0]
    if t == "V":
        return e[4] if len(e) > 4 else None
    if t == "VCVS":
        return e[6] if len(e) > 6 else None
    if t == "CCVS":
        return e[5] if len(e) > 5 else None
    return None


def solve(net, ground=0):
    """返回 (节点电压字典, 电压源型支路电流字典{name: I})。

    net 元素：
      ('R', n1, n2, R)             r = 1/R 导纳
      ('V', n1, n2, value, name)   电压源 V(n1)-V(n2)=value，name 用于取电流/受控引用
      ('I', n1, n2, value)         电流源，电流由 n1 经源流向 n2
      ('VCVS', n1, n2, c1, c2, mu, name)   V(n1)-V(n2)=mu*(V(c1)-V(c2))
      ('VCCS', n1, n2, c1, c2, g)         电流 n1->n2 = g*(V(c1)-V(c2))
      ('CCVS', n1, n2, src, r, name)      V(n1)-V(n2)=r*I(src)
      ('CCCS', n1, n2, src, k)            电流 n1->n2=k*I(src)
    约定：电压源支路电流 I>0 表示电流由 n1 经电源流向 n2。
    """
    names, order = {}, []

    def node(n):
        if n == ground:
            return None
        if n not in names:
            names[n] = len(order)
            order.append(n)
        return names[n]

    for e in net:
        node(e[1])
        node(e[2])
    vs = [e for e in net if e[0] in ("V", "VCVS", "CCVS")]
    k_of = {id(e): i for i, e in enumerate(vs)}
    by_name = {e[4]: e for e in net if e[0] == "V"}
    n, m = len(order), len(vs)
    A = zeros(n + m, n + m)
    b = zeros(n + m, 1)

    def gk(n1, n2, g):
        i, j = names.get(n1), names.get(n2)
        if i is not None:
            A[i, i] += g
        if j is not None:
            A[j, j] += g
        if i is not None and j is not None:
            A[i, j] -= g
            A[j, i] -= g

    for e in net:
        t = e[0]
        if t == "R":
            gk(e[1], e[2], 1 / _val(e[3]))
        elif t == "I":
            i, j = names.get(e[1]), names.get(e[2])
            val = _val(e[3])
            if i is not None:
                b[i, 0] -= val
            if j is not None:
                b[j, 0] += val
        elif t == "VCCS":
            _, n1, n2, c1, c2, g = e
            g = _val(g)
            for a, sa in ((n1, 1), (n2, -1)):
                for c, sc in ((c1, 1), (c2, -1)):
                    ia, ic = names.get(a), names.get(c)
                    if ia is not None and ic is not None:
                        A[ia, ic] += sa * sc * g
        elif t in ("V", "VCVS", "CCVS"):
            k = k_of[id(e)]
            i, j = names.get(e[1]), names.get(e[2])
            if i is not None:
                A[i, n + k] += 1
                A[n + k, i] += 1
            if j is not None:
                A[j, n + k] -= 1
                A[n + k, j] -= 1
            if t == "V":
                b[n + k, 0] = _val(e[3])
            elif t == "VCVS":
                mu = _val(e[5])
                if names.get(e[3]) is not None:
                    A[n + k, names[e[3]]] -= mu
                if names.get(e[4]) is not None:
                    A[n + k, names[e[4]]] += mu
            else:
                A[n + k, n + k_of[id(by_name[e[3]])]] -= _val(e[4])
        elif t == "CCCS":
            ctrl = by_name[e[3]]
            j = n + k_of[id(ctrl)]
            k_cccs = _val(e[4])
            if names.get(e[1]) is not None:
                A[names[e[1]], j] += k_cccs
            if names.get(e[2]) is not None:
                A[names[e[2]], j] -= k_cccs
        else:
            raise ValueError(t)

    sol = A.LUsolve(b)
    V = {ground: 0}
    for name, idx in names.items():
        V[name] = simplify(sol[idx, 0])
    # 三类"电压源型"支路（V / VCVS / CCVS）都带一条待求支路电流，
    # 全部按各自的 name 字段暴露出来。只给 V 会让求 VCVS 支路电流时 KeyError。
    I = {}
    for e in vs:
        nm = _name_of(e)
        if nm is not None:
            I[nm] = simplify(sol[n + k_of[id(e)], 0])
    return V, I


def thevenin(net, a, b=0, rl=None):
    """返回 u_oc、i_sc、R_eq(除源外加 1A)、以及接 rl 时的解。"""
    g = b
    V1, _ = solve(net, ground=g)
    uoc = simplify(V1[a] - V1[b])

    shorted = net + [("V", a, b, 0, "SC")]
    V2, I2 = solve(shorted, ground=g)
    isc = simplify(I2["SC"])          # I>0: 由 a 经短路线流向 b

    # 除源网络：独立电压源 -> 0 V 源；独立电流源 -> 断开；受控源保留
    dp = []
    for e in net:
        if e[0] == "V":
            dp.append(("V", e[1], e[2], 0, e[4]))
        elif e[0] == "I":
            continue
        else:
            dp.append(e)
    dp = dp + [("I", b, a, 1)]        # 外加 1 A 由 b 注入 a
    V3, _ = solve(dp, ground=g)
    req = simplify(V3[a] - V3[b])

    out = {"u_oc": uoc, "i_sc": isc, "R_eq": req}
    if isc != 0:
        out["u_oc/i_sc"] = simplify(uoc / isc)
    if rl is not None:
        V4, _ = solve(net + [("R", a, b, rl)], ground=g)
        ul = simplify(V4[a] - V4[b])
        out.update({"R_L": rl, "u_L": ul, "i_L": simplify(ul / rl),
                    "P_L": simplify(ul ** 2 / rl)})
        out["P_max"] = simplify(uoc ** 2 / (4 * req))
    return out


def show(title, net, a=1, b=0, rl=None):
    r = thevenin(net, a, b, rl)
    print("=" * 74)
    print(title)
    for k, v in r.items():
        print("   %-10s = %s" % (k, v))
    return r
