import sys, zipfile, os
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
p = sys.argv[1] if len(sys.argv) > 1 else os.path.expandvars(r"%TEMP%\sina.zip")
dst = os.path.join(ROOT, "vendor", "sina", "src")
z = zipfile.ZipFile(p)
n = 0
skip_dirs = ("Database/",)
for i in z.infolist():
    f = i.filename
    if f.startswith(skip_dirs):
        continue
    if i.is_dir():
        continue
    low = f.lower()
    if low.endswith((".pt", ".pth", ".onnx", ".jpg", ".png", ".jpeg", ".zip", ".npz", ".npy")):
        continue
    if "/model_training/data/" in f or "/Model training/data/" in f:
        continue
    if "/out/" in f or "/Results/" in f or "/Test results/" in f:
        continue
    out = os.path.join(dst, f.replace("/", os.sep))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(z.read(i))
    n += 1
print("extracted", n, "files to", dst)
