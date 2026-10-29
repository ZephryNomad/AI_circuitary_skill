import sys
sys.path.insert(0, r"%TEMP%\lctest")   # 改成你自己放 lcapy 的目录
from lcapy import Circuit

# 例4（含 E 受控源）原样
c2 = Circuit("""V1 1 0 12
R1 1 2 2
R2 2 0 2
R3 2 3 1
R4 3 4 6
E1 4 0 2 0 2""")
print("case4 node3 v =", c2[3].v, " node4 v =", c2[4].v)

# 例5（含 G 受控源）
c3 = Circuit("""V1 1 0 12
R1 1 2 2
R2 2 0 2
R3 2 3 3
G1 3 0 2 0 1""")
print("case5 node3 v =", c3[3].v)
