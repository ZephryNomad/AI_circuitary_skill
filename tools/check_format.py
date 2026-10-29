"""清点并归一化仓库内文本文件的格式（BOM / CRLF / 行尾空白 / 末尾换行）。

用法：
    python tools/check_format.py            # 只报告
    python tools/check_format.py --apply    # 报告并就地修正

规则与取舍（都要能说清理由）：
  · BOM：一律去掉。UTF-8 BOM 是 Windows 记事本的遗留，GitHub 上会让首行
    字段名带上不可见字符，解析器容易踩坑（本项目 circuit.py 的 _strip_bom
    就是为兼容它而写的）。去掉后由 UTF-8 无 BOM 统一。
  · CRLF -> LF：统一成 LF。仓库里 git 的 autocrlf 已能处理检出侧，
    存进库里应当只有 LF，否则同一文件在不同机器上反复显示为整文件改动。
  · 行尾空白：**.md 文件不动**。Markdown 里"行末两个空格"是硬换行语义，
    删掉会把两行并成一行，属于改内容而不是改格式。其余文件（.py/.cir/.card/
    .logic/.json/.txt/.yaml）的行尾空白一律删除。
  · **out/ 下的 .svg 不动**（见 is_generated_svg 的说明）。
  · 末尾换行：统一补一个。POSIX 文本文件应以换行结尾，缺了会在 diff 里显示
    "\\ No newline at end of file"。
  · 不做的事：不改行内空白、不重排、不折行、不动缩进——
    这些都可能改变语义。
  · 范围：跳过 vendor/、.mplcache/、__pycache__/、.git/、build/、
    tools/_scratch/crops_*/（一次性取证裁片，不入库）、_upload/（手动上传用的
    暂存副本，内容与原件逐字节相同，扫进来只会把同一个文件报告两遍）。
"""
import os
import sys

# 本文件在 tools/ 下，仓库根是它的上一级。
# 不直接写 dirname(__file__)：那样扫的就只有 tools/ 自己，
# 报告会"全绿"——一个看起来成功、实际什么都没检查的假阳性。
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = _HERE if os.path.basename(_HERE) != "tools" else os.path.dirname(_HERE)
TEXT_EXT = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".cir", ".card",
            ".logic", ".csv", ".svg", ".xml", ".bat", ".gitignore", ".toml"}
SKIP_DIRS = {"vendor", ".mplcache", "__pycache__", ".git", "build", "_upload"}
NO_STRIP_EXT = {".md"}   # 见文件头：Markdown 行末两空格是硬换行


def is_generated_svg(rel):
    """out/ 下的 .svg 是 matplotlib 直接写出的产物，一律不动。

    理由：matplotlib 的路径数据是"每个坐标命令一行、行末带一个空格"的格式
    （实测 p2_3_题图.svg 有 303 处），删掉这些空格不会改变渲染，
    但下次重新生成又会原样长回来——每跑一次绘图就是一次无意义的整文件 diff。
    这类产物的跨平台换行差异交给 .gitattributes 的 eol=lf 处理。
    """
    r = rel.replace("\\", "/").lower()
    return r.startswith("out/") and r.endswith(".svg")


def text_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith("crops_")]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in TEXT_EXT or f == ".gitignore":
                yield os.path.join(base, f)


def analyze(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if b"\x00" in raw[:4096]:
        return None
    try:
        txt = raw.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        return {"path": path, "bad_encoding": True}
    bom = raw.startswith(b"\xef\xbb\xbf")
    orig = txt                      # 原样（BOM 可能还在，换行可能还是 CRLF）
    if bom:
        txt = txt.lstrip("\ufeff")
    crlf = raw.count(b"\r\n")
    # 先归一化换行再数行尾空白。不这么做的话，CRLF 文件的每一行都以 \r 结尾，
    # 会被误判成"整篇都有行尾空白"（本工具第一版就踩了这个坑：1827 行的 SVG
    # 报出 1827 处行尾空白，其实一处都没有）。
    norm = txt.replace("\r\n", "\n").replace("\r", "\n")
    rel = os.path.relpath(path, ROOT)
    skip_strip = os.path.splitext(path)[1].lower() in NO_STRIP_EXT or is_generated_svg(rel)
    trailing = 0
    if not skip_strip:
        trailing = sum(1 for l in norm.split("\n") if l != l.rstrip())
    # 生成的 SVG 也不补末尾换行：重新生成时又会变回去
    missing_eof = bool(norm) and not norm.endswith("\n") and not is_generated_svg(rel)
    return {"path": path, "enc": enc, "bom": bom, "crlf": crlf,
            "trailing": trailing, "missing_eof": missing_eof,
            "text": norm, "orig": orig,
            "skip_strip": skip_strip, "skip_eof": is_generated_svg(rel)}


def fix(info):
    """把信息里的规范化文本与"原始字节解码结果"比较，而不是与已有的规范文本比较。

    第一版这里写的是 `if out != txt`，而 txt 已是规范化过的（见 analyze），
    于是判定永远为"没变化"——报告列出 21 个 BOM 文件，却只改写 4 个。
    这类"报告与动作不一致"的缺陷比直接报错更糟：它看起来是成功的。
    """
    txt = info["text"]
    lines = txt.split("\n")
    if not info["skip_strip"]:
        lines = [l.rstrip() if l.strip() else "" for l in lines]
    out = "\n".join(lines)
    if out and not out.endswith("\n") and not info["skip_eof"]:
        out += "\n"
    if out != info["orig"]:
        with open(info["path"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
        return True
    return False


def main(argv):
    apply = "--apply" in argv
    rows = []
    bad = []
    for p in sorted(text_files()):
        info = analyze(p)
        if info is None:
            continue
        if info.get("bad_encoding"):
            bad.append(os.path.relpath(p, ROOT))
            continue
        info["path"] = os.path.relpath(p, ROOT)
        info["abs"] = p
        rows.append(info)
    bom = [r for r in rows if r["bom"]]
    crlf = [r for r in rows if r["crlf"]]
    tr = [r for r in rows if r["trailing"]]
    eof = [r for r in rows if r["missing_eof"]]

    print("扫描文本文件：%d 个" % len(rows))
    print("  含 BOM      : %d" % len(bom))
    print("  含 CRLF     : %d" % len(crlf))
    print("  行尾空白    : %d 个文件 / %d 行" % (len(tr), sum(r["trailing"] for r in tr)))
    print("  缺末尾换行  : %d" % len(eof))
    if bad:
        print("  非 UTF-8    : %d -> %s" % (len(bad), bad[:5]))

    def show(name, items, key=None):
        if not items:
            return
        print("\n--- %s ---" % name)
        for r in items:
            extra = ""
            if key:
                extra = " (%s)" % r[key]
            print("  %s%s" % (r["path"], extra))

    show("含 BOM", bom)
    show("含 CRLF", crlf, "crlf")
    show("行尾空白", tr, "trailing")
    show("缺末尾换行", eof)

    if not apply:
        print("\n（只报告。加 --apply 就地修正。）")
        return 0

    n = 0
    for r in rows:
        if fix(r):
            n += 1
    print("\n已改写 %d 个文件" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
