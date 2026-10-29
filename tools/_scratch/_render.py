import os, sys, pymupdf
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
src = os.path.join(ROOT, "out", "讲义", "戴维宁定理讲义.pdf")
out = os.path.join(ROOT, "build", "pv")
os.makedirs(out, exist_ok=True)
d = pymupdf.open(src)
print("pages", len(d))
pages = [int(x) for x in sys.argv[1:]] or list(range(1, len(d) + 1))
for i in pages:
    p = d[i - 1]
    pix = p.get_pixmap(dpi=110)
    f = os.path.join(out, f"p{i:02d}.png")
    pix.save(f)
    print(f, pix.width, pix.height)
d.close()
