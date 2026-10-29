"""打印讲义 PDF 前几页的文本，用于核对有没有渲染丢失。"""
import os
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pdf = os.path.join(ROOT, "out", "讲义", "戴维宁定理讲义.pdf")

d = pymupdf.open(pdf)
print("pages", len(d))
for i in range(4):
    t = d[i].get_text()
    print("=" * 20, "page", i + 1)
    print(repr(t[:600]))
d.close()
