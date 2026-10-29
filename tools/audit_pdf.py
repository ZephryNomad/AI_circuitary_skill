"""PDF 成品体检：扫 LaTeX 残留、乱码、空白页、图片数、字体。"""
import os
import re
import sys

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(ROOT, "out", "讲义", "戴维宁定理讲义.pdf")

BAD = {
    "反斜杠命令": r"\\[a-zA-Z]+",
    "美元符": r"\$",
    "花括号": r"\{|\}",
    "和号实体": r"&[a-z]+;",
    "替换符U+FFFD": "\ufffd",
    "问号方块": r"\u25a1",
}

with pymupdf.open(PDF) as doc:
    pages = [p.get_text() for p in doc]
    n = len(doc)
    imgs = [len(p.get_images()) for p in doc]
    fonts = sorted({f[3] for p in doc for f in p.get_fonts()})

print("pages =", n, " total_images =", sum(imgs))
print("fonts  =", len(fonts))

for label, pat in BAD.items():
    hits = []
    for i, t in enumerate(pages):
        for m in re.finditer(pat, t):
            hits.append((i + 1, m.group(0)))
    print(f"{label:12} {len(hits):3d}", hits[:8])

# 空白页检查（几乎无文字且无图）
for i, (t, k) in enumerate(zip(pages, imgs), 1):
    if len(t.strip()) < 12 and k == 0:
        print("BLANK page", i, repr(t[:40]))

# 逐页字数，便于发现断页异常
print("chars/page:", [len(t.strip()) for t in pages])
