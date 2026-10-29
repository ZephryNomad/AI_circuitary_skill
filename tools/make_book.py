"""合稿 + 静态目录 + 后处理 + 两段转换出 PDF。

目录方案：LibreOffice 不填充 TOC 域，所以目录改成静态表格。
页码通过"构建 → 回读 PDF 实测 → 修正目录 → 再构建"的迭代求得，直到页码稳定。
目录页用页眉特征（含"内容"表头）识别并在搜索时跳过。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymupdf
from build_book import pandoc, lo_convert
from postprocess import postprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "out", "讲义")

PARTS = ["p1.md", "p2.md", "p3.md", "p4.md", "p5.md", "p6.md"]
TOC_MARK = "页码"
FINAL = "戴维宁定理讲义"


def read_parts():
    body = []
    for name in PARTS:
        p = os.path.join(SRC, name)
        if not os.path.exists(p):
            print("MISSING", p)
            sys.exit(1)
        with open(p, encoding="utf-8") as f:
            body.append(f.read().rstrip() + "\n")
    return "\n".join(body)


def headings(md):
    out = []
    for line in md.splitlines():
        m = re.match(r"^(#{1,2})\s+(.*)$", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def build_pdf(md_path, stem):
    docx, odt, pdf = stem + ".docx", stem + ".odt", stem + ".pdf"
    pandoc(md_path, docx,
           extra=["--from", "markdown+tex_math_dollars+pipe_tables",
                  "--resource-path", ROOT])
    postprocess(docx)
    lo_convert(docx, odt)
    lo_convert(odt, pdf)
    return pdf


def _flat(s):
    """归一化：去掉空白、LaTeX 语法字符，只留中日韩文字与字母数字，便于跨格式匹配。"""
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = re.sub(r"[{}$\\^_~]", "", s)
    return re.sub(r"[^\u4e00-\u9fff0-9A-Za-z]", "", s)


def measure(pdf, heads):
    """回读 PDF：区分目录页与正文页，返回 ({标题: 页码}, 总页数, 目录页数)。"""
    with pymupdf.open(pdf) as doc:
        raw = [p.get_text() for p in doc]
        n = len(doc)
    flat = [_flat(t) for t in raw]
    # 目录页：第一页出现"页码"表头的开始，连续含该表头的页都算目录
    first = next((i for i, t in enumerate(flat) if TOC_MARK in t), None)
    ntoc = 0
    if first is not None:
        j = first
        while j < len(flat) and TOC_MARK in flat[j]:
            j += 1
        ntoc = j - first
    body_start = (first + ntoc) if first is not None else 0
    res = {}
    for level, h in heads:
        needle = _flat(h)[:10]
        res[h] = None
        for i in range(body_start, len(flat)):
            if needle and needle in flat[i]:
                res[h] = i + 1
                break
    return res, n, ntoc


def toc_block(heads, pm):
    lines = ["# 目录", "", "| 内容 | 页码 |", "|:---|:---:|"]
    for level, h in heads:
        name = h if level == 1 else "　　" + h
        page = pm.get(h)
        lines.append(f"| {name} | {page if page else '—'} |")
    lines += ["", PAGEBREAK.strip(), ""]
    return "\n".join(lines)


PAGEBREAK = ('\n\n```{=openxml}\n'
             '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
             '```\n\n')


def assemble(body, heads, pm, path):
    idx = body.find("# 第 0 章")
    cover = body[:idx].rstrip()
    # 封面单独占一页：标题块与目录之间插入真正的分页符（raw openxml，pandoc 才会保留）
    md = cover + PAGEBREAK + toc_block(heads, pm) + "\n" + body[idx:]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)


def main():
    os.makedirs(OUT, exist_ok=True)
    body = read_parts()
    heads = headings(body)
    final_md = os.path.join(SRC, "book.md")
    stem = os.path.join(OUT, FINAL)

    # 第 0 轮：所有页码先填 1，得到结构与目录页数
    pm = {h: 1 for _, h in heads}
    for rnd in range(1, 6):
        assemble(body, heads, pm, final_md)
        pdf = build_pdf(final_md, stem)
        pm2, n, ntoc = measure(pdf, heads)
        diff = [h for _, h in heads if pm2.get(h) != pm.get(h)]
        print(f"round {rnd}: pages={n} toc_pages={ntoc} changed={len(diff)}")
        missing = [h for _, h in heads if pm2.get(h) is None]
        if missing:
            print("  UNMATCHED:", missing)
        if not diff:
            print("TOC stable.")
            break
        pm = pm2
    else:
        print("WARN: TOC 页码未收敛")

    for level, h in heads:
        print(f"  {'  ' if level == 2 else ''}{h} -> {pm.get(h)}")
    print("PDF:", pdf)


if __name__ == "__main__":
    main()
