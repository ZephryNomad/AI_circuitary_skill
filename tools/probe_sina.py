"""probe_sina.py —— 用 SINA 的真实权重在讲义插图上做一次实测

目的
    不能只复述论文的 96.67%。用户手上是教材风格的原理图，必须亲自跑一遍，
    看它的检测器到底认得几个元件，才知道这条路对他是否可用。

做法
    直接调 ultralytics 加载 SINA 的 IC best.pt，对 figs/ 下所有图做推理，
    打印每张图检测到的元件类别与数量，并与讲义实际元件数对照。
"""
import os
import sys
from collections import Counter

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
W = os.path.join(ROOT, "vendor", "sina", "models", "ic_best.pt")

# 讲义各图的实际元件数（人工从正文数出来的，作为对照基准）
TRUTH = {
    "fig06_ex1": {"Voltage_src": 1, "Resistor": 4},
    "fig07_ex2": {"Current_src": 1, "Resistor": 3},
    "fig08_ex3": {"Voltage_src": 1, "Resistor": 4},
    "fig09_ex4": {"Voltage_src": 2, "Resistor": 4},   # 含 1 个受控电压源
    "fig10_ex5": {"Voltage_src": 1, "Resistor": 3},   # 含 1 个受控电流源
    "fig11_hw1": {"Voltage_src": 1, "Resistor": 6},
    "fig12_hw2": {"Voltage_src": 1, "Resistor": 4},
    "fig13_hw3": {"Voltage_src": 2, "Resistor": 4},
    "fig17_hw4": {"Current_src": 1, "Resistor": 3},
}


def main():
    if not os.path.isfile(W):
        print("缺少权重：%s" % W)
        return 2
    m = YOLO(W)
    print("模型类别：", m.names)
    print()
    figs = os.path.join(ROOT, "figs")
    names = sorted(n for n in os.listdir(figs) if n.lower().endswith(".png"))
    tot_hit = tot_true = 0
    for n in names:
        base = os.path.splitext(n)[0]
        p = os.path.join(figs, n)
        r = m.predict(p, conf=0.25, verbose=False)[0]
        got = Counter(m.names[int(b.cls)] for b in r.boxes)
        truth = TRUTH.get(base)
        line = "%-22s 检测 %-42s" % (base, dict(got) if got else "无")
        if truth:
            nh = sum(min(got.get(k, 0), v) for k, v in truth.items())
            nt = sum(truth.values())
            tot_hit += nh
            tot_true += nt
            line += " 真值 %-34s 命中 %d/%d" % (dict(truth), nh, nt)
        print(line)
    if tot_true:
        print("\n检测召回：%d/%d = %.1f%%（按元件计数，conf=0.25）"
              % (tot_hit, tot_true, 100.0 * tot_hit / tot_true))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
