"""修掉 "$+$"/"$-$" 这种空操作数公式（LibreOffice 渲染成乱码 ＋¿）。"""
import os
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")
PAIRS = [('"$+$"', "\u201c+\u201d"), ('"$-$"', "\u201c\u2212\u201d"),
         ("$+$/$-$", "+\uff0f\u2212")]
for p in ["p1.md", "p2.md", "p3.md", "p4.md", "p5.md", "p6.md"]:
    f = os.path.join(SRC, p)
    s = open(f, encoding="utf-8").read()
    o = s
    for a, b in PAIRS:
        s = s.replace(a, b)
    if s != o:
        open(f, "w", encoding="utf-8").write(s)
        print("patched", p)
print("remaining:", sum(open(os.path.join(SRC, p), encoding="utf-8").read().count("$+$")
                        for p in ["p1.md", "p2.md", "p3.md", "p4.md", "p5.md", "p6.md"]))
