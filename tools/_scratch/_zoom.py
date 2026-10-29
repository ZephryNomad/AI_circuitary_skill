"""局部放大：python tools/_scratch/_zoom.py <page> <x0> <y0> <x1> <y1> <out>
坐标以 910x1287 的 dpi=110 预览图为基准，脚本内部换算到 dpi=300。
"""
import os
import sys

import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pdf = os.path.join(ROOT, "out", "讲义", "戴维宁定理讲义.pdf")

page_no = int(sys.argv[1]) - 1
x0, y0, x1, y1 = [float(v) for v in sys.argv[2:6]]
out = sys.argv[6]

SCALE = 110 / 72.0   # 预览图 px -> PDF pt
with pymupdf.open(pdf) as doc:
    page = doc[page_no]
    clip = pymupdf.Rect(x0 / SCALE, y0 / SCALE, x1 / SCALE, y1 / SCALE)
    pix = page.get_pixmap(dpi=300, clip=clip)
    pix.save(out)
print(out, pix.width, pix.height)
