"""讲义最终例题表：一次跑出全部数据，输出直接进讲义附录。"""
from sympy import Rational
from mna import thevenin, solve

CASES = [
    # tag, net, a, b, rl
    ("例1 两级分压链", [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
                        ("R", 2, 3, 2), ("R", 3, 0, 6)], 3, 0, 2),
    ("例2 电流源激励", [("I", 0, 1, 2), ("R", 1, 0, 3), ("R", 1, 2, 3),
                        ("R", 2, 0, 12)], 2, 0, 4),
    ("例3 不平衡电桥", [("V", 1, 0, 12, "Us"), ("R", 1, 2, 1), ("R", 2, 0, 3),
                        ("R", 1, 3, 9), ("R", 3, 0, 3)], 2, 3, 6),
    ("例4 含VCVS", [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
                    ("R", 2, 3, 1), ("R", 3, 4, 6),
                    ("VCVS", 4, 0, 2, 0, Rational(2), "E1")], 3, 0, 2),
    ("例5 含VCCS", [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
                    ("R", 2, 3, 3), ("VCCS", 3, 0, 2, 0, Rational(1))], 3, 0, None),
    ("习题1 三节梯形", [("V", 1, 0, 24, "Us"), ("R", 1, 2, 3), ("R", 2, 0, 6),
                        ("R", 2, 3, 2), ("R", 3, 0, 12), ("R", 3, 4, 3),
                        ("R", 4, 0, 6)], 4, 0, 3),
    ("习题2 电桥", [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 4),
                    ("R", 1, 3, 8), ("R", 3, 0, 4)], 2, 3, 4),
    ("习题3 VCVS", [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
                    ("R", 2, 3, 2), ("R", 3, 4, 3),
                    ("VCVS", 4, 0, 2, 0, Rational(3, 2), "E1")], 3, 0, 3),
    ("习题4 电流源", [("I", 0, 1, 3), ("R", 1, 0, 2), ("R", 1, 2, 2),
                      ("R", 2, 0, 4)], 2, 0, 2),
]

for tag, net, a, b, rl in CASES:
    V, I = solve(net, ground=b)
    r = thevenin(net, a, b, rl=rl)
    print("=" * 72)
    print(tag)
    print("  节点电压 :", {k: str(v) for k, v in sorted(V.items())})
    print(f"  u_oc     = {r['u_oc']} V")
    print(f"  i_sc     = {r['i_sc']} A")
    print(f"  R_eq     = {r['R_eq']} ohm")
    chk = r.get("u_oc/i_sc")
    print(f"  校验 u_oc/i_sc = {chk}  {'OK' if chk == r['R_eq'] else 'MISMATCH'}")
    if rl is not None:
        print(f"  R_L={r['R_L']}: u_L={r['u_L']} V  i_L={r['i_L']} A  "
              f"P_L={r['P_L']} W  (P_max={r['P_max']} W @ R_L={r['R_eq']})")
