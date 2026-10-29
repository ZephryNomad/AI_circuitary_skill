import io
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

buf = io.StringIO()
old = sys.stdout
sys.stdout = buf
try:
    runpy.run_path(os.path.join(ROOT, "tools", "verify_examples.py"),
                   run_name="__main__")
finally:
    sys.stdout = old

text = buf.getvalue()
out = os.path.join(ROOT, "out", "讲义", "验算输出.txt")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print("wrote", out, len(text), "chars", text.count("=" * 72), "blocks")
