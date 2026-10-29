import sys, zipfile, os
sys.stdout.reconfigure(encoding="utf-8")
p = sys.argv[1] if len(sys.argv) > 1 else os.path.expandvars(r"%TEMP%\sina.zip")
z = zipfile.ZipFile(p)
want_readme = []
for i in z.infolist():
    f = i.filename
    if f.lower().endswith(".md"):
        want_readme.append((f, i.file_size))
for f, s in sorted(want_readme):
    print("%-100s %7d" % (f, s))
