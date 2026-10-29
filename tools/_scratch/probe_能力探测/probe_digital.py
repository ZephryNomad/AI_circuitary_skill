"""探针：数字电路各类典型题能否处理（sympy.logic + 自写时序推演）"""
import itertools
from sympy import symbols, SOPform, POSform, simplify_logic, sympify
from sympy.logic.boolalg import truth_table

print("=" * 70)
print("A. 组合逻辑化简：4 变量带无关项（教材典型题）")
print("=" * 70)
A, B, C, D = symbols("A B C D")
ones = [0, 1, 2, 5, 8, 9, 10]
dc = [3, 11, 14, 15]
sop = SOPform([A, B, C, D], ones, dc)
pos = POSform([A, B, C, D], ones, dc)
print("最小项 m:", ones, " 无关项 d:", dc)
print("SOP =", sop)
print("POS =", pos)


def ev(e, v):
    return bool(e.subs(dict(zip([A, B, C, D], v))))


bad = []
for v in itertools.product([0, 1], repeat=4):
    g = v[0] * 8 + v[1] * 4 + v[2] * 2 + v[3]
    got = ev(sop, v)
    if g in ones and not got:
        bad.append(("应为1却得0", v))
    if g not in ones and g not in dc and got:
        bad.append(("应为0却得1", v))
print("逐点复核违例数 =", len(bad), "→", "通过" if not bad else bad)

print()
print("=" * 70)
print("B. 真值表生成（3 变量，验证表达式与卡诺图一致性）")
print("=" * 70)
x, y, z = symbols("x y z")
f = (x & y) | (~x & z)
rows = list(truth_table(f, [x, y, z]))
print(" x y z | F")
for vals, res in rows:
    print(" %s | %d" % (" ".join(map(str, vals)), 1 if res else 0))

print()
print("=" * 70)
print("C. 时序电路：JK 触发器状态推演（自写转移表，非 sympy）")
print("=" * 70)
# JK: 00保持 01清0 10置1 11翻转
JK = {
    (0, 0): lambda q: q,
    (0, 1): lambda q: 0,
    (1, 0): lambda q: 1,
    (1, 1): lambda q: 1 - q,
}
J = [1, 1, 0, 1, 0, 1]
K = [0, 1, 1, 0, 1, 0]
q = 0
seq = [q]
for i, (j, k) in enumerate(zip(J, K), 1):
    q = JK[(j, k)](q)
    seq.append(q)
print("时钟拍:", list(range(len(J) + 1)))
print("J    :", J)
print("K    :", K)
print("Q    :", seq)
print("末态 Q =", seq[-1])

print()
print("=" * 70)
print("D. 状态机：由状态转移表求状态方程（3 状态，Mealy）")
print("=" * 70)
# 一个 2 位计数器（模 3），检查自启动
def nxt(s):
    return (s + 1) % 3

print("现态 -> 次态")
for s in range(4):  # 含非法状态 3
    print("  %d -> %d %s" % (s, nxt(s), "(非法态进入 → 可自启动)" if s == 3 else ""))
