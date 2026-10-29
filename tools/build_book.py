"""共用转换工具：pandoc + LibreOffice Kit 两段转换（DOCX→ODT→PDF）。

外部程序路径不写死，按以下顺序解析：
  1. 环境变量  PANDOC / NODE / LO_CLI
  2. PATH 上的 pandoc / node
  3. （LO_CLI 无 PATH 兜底，必须显式给出）
"""

import os
import shutil
import subprocess
import sys


def _tool(env_name, exe):
    """环境变量优先，其次 PATH，最后返回裸命令名交给系统再找一次。"""
    value = os.getenv(env_name)
    if value:
        return value
    return shutil.which(exe) or exe


PANDOC = _tool("PANDOC", "pandoc")
NODE = _tool("NODE", "node")
# LibreOffice Kit 的 cli.js 不是可执行文件，无法从 PATH 推断，只能显式配置。
# 形如 <...>/node_modules/@deepseek-ai/libreoffice-kit/lib/cli.js
CLI = os.getenv("LO_CLI", "")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def lo_convert(src, dst):
    if not CLI:
        print("未配置 LO_CLI：请把 LibreOffice Kit 的 cli.js 路径写入环境变量 LO_CLI")
        sys.exit(2)
    if os.path.exists(dst):
        os.remove(dst)          # LibreOffice Kit 拒绝覆盖已存在文件（EEXIST）
    r = _run([NODE, CLI, "convert", "--input", src, "--output", dst])
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        print("LO FAIL", src, "->", dst, out, (r.stderr or "").strip()[:400])
        sys.exit(1)
    return out


def pandoc(md, docx, ref=None, extra=None):
    cmd = [PANDOC, md, "-o", docx]
    if ref:
        cmd += ["--reference-doc", ref]
    if extra:
        cmd += extra
    r = _run(cmd)
    if r.returncode != 0:
        print("PANDOC FAIL", (r.stderr or "").strip()[:800])
        sys.exit(1)
    if (r.stderr or "").strip():
        print("[pandoc warnings]", (r.stderr or "").strip()[:800])
    return docx


def build(md, stem, ref=None, extra=None, dpi=150):
    import pymupdf
    docx = f"{stem}.docx"
    odt = f"{stem}.odt"
    pdf = f"{stem}.pdf"
    pandoc(md, docx, ref, extra)
    lo_convert(docx, odt)
    lo_convert(odt, pdf)
    d = pymupdf.open(pdf)
    for i, p in enumerate(d):
        p.get_pixmap(dpi=dpi).save(f"{stem}_{i}.png")
    print(f"{pdf}: pages={len(d)}")
    return pdf, len(d)
