"""核对第 5 章"错误做法"的具体数值，保证讲义里给出的对比数字真实。"""
from sympy import Rational
from mna import thevenin

# 例 5 原网络
net5 = [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
        ("R", 2, 3, 3), ("VCCS", 3, 0, 2, 0, Rational(1))]
r = thevenin(net5, 3, 0)
print("例5 正确 R_eq =", r["R_eq"], " u_oc =", r["u_oc"])

# 错误做法：把受控源删掉
net5_bad = [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
            ("R", 2, 3, 3)]
rb = thevenin(net5_bad, 3, 0)
print("例5 删掉VCCS后 R_eq =", rb["R_eq"], " u_oc =", rb["u_oc"])

# 例 4 原网络
net4 = [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
        ("R", 2, 3, 1), ("R", 3, 4, 6),
        ("VCVS", 4, 0, 2, 0, Rational(2), "E1")]
r4 = thevenin(net4, 3, 0)
print("例4 正确 R_eq =", r4["R_eq"], " u_oc =", r4["u_oc"])

# 错误做法：把受控电压源当短路删成 0V 导线
net4_bad = [("V", 1, 0, 12, "Us"), ("R", 1, 2, 2), ("R", 2, 0, 2),
            ("R", 2, 3, 1), ("R", 3, 4, 6), ("V", 4, 0, 0, "bad")]
r4b = thevenin(net4_bad, 3, 0)
print("例4 把VCVS短路后 R_eq =", r4b["R_eq"], " u_oc =", r4b["u_oc"])

# 负阻是否存在：VCCS 向端口节点注入电流时的端口电阻
neg = [("R", 1, 0, 2), ("VCCS", 0, 1, 1, 0, Rational(3, 2))]
rn = thevenin(neg, 1, 0)
print("负阻例 R_eq =", rn["R_eq"])
