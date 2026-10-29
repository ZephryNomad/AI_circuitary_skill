"""pandoc 输出 docx 的后处理：页面、字体、行距、图注、表格边框、页眉页脚。

用法：postprocess(path, toc_entries=None)
不依赖 reference-doc，避免 pandoc 表格结构被破坏。
"""
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CN_BODY = "宋体"
CN_HEAD = "黑体"
EN_BODY = "Times New Roman"
EN_HEAD = "Arial"
INK = RGBColor(0x1F, 0x29, 0x33)
ACCENT = RGBColor(0x2F, 0x5D, 0x8A)


def _fonts(style, cn, en):
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    rf.set(qn("w:ascii"), en)
    rf.set(qn("w:hAnsi"), en)
    rf.set(qn("w:eastAsia"), cn)
    rf.set(qn("w:cs"), en)


def _style(doc, name, cn, en, size, bold=None, color=None, before=None, after=None,
           spacing=None, indent=None, align=None, keep_next=None):
    try:
        s = doc.styles[name]
    except KeyError:
        return
    _fonts(s, cn, en)
    f = s.font
    f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if color is not None:
        f.color.rgb = color
    pf = s.paragraph_format
    if before is not None:
        pf.space_before = Pt(before)
    if after is not None:
        pf.space_after = Pt(after)
    if spacing is not None:
        pf.line_spacing = spacing
    if indent is not None:
        pf.first_line_indent = Pt(indent)
    if align is not None:
        pf.alignment = align
    if keep_next is not None:
        pf.keep_with_next = keep_next


def _borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "6")
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "9AA5B1")
        b.append(e)
    tblPr.append(b)


def _shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), hexcolor)
    tcPr.append(sh)


def _field(par, instr, size=9):
    r1 = par.add_run()
    r1.font.size = Pt(size)
    fc = OxmlElement("w:fldChar")
    fc.set(qn("w:fldCharType"), "begin")
    r1._r.append(fc)

    r2 = par.add_run()
    r2.font.size = Pt(size)
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    r2._r.append(it)

    r3 = par.add_run()
    r3.font.size = Pt(size)
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    r3._r.append(sep)

    r4 = par.add_run("1")
    r4.font.size = Pt(size)

    r5 = par.add_run()
    r5.font.size = Pt(size)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    r5._r.append(end)


def _block_style(doc, name, fill, edge, size=10.2, bold_head=False):
    """给 Example / Tip / Warn 这类提示块加左侧色条 + 浅底色。"""
    try:
        s = doc.styles[name]
    except KeyError:
        return False
    _fonts(s, CN_BODY, EN_BODY)
    s.font.size = Pt(size)
    s.font.bold = bold_head or None
    pf = s.paragraph_format
    pf.left_indent = Cm(0.30)
    pf.right_indent = Cm(0.10)
    pf.first_line_indent = Pt(0)
    pf.space_before = Pt(5)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.5

    pPr = s.element.get_or_add_pPr()
    for old in pPr.findall(qn("w:pBdr")):
        pPr.remove(old)
    pbdr = OxmlElement("w:pBdr")
    for edge_name, sz, color in (("left", "18", edge), ("top", "4", fill),
                                 ("bottom", "4", fill), ("right", "4", fill)):
        e = OxmlElement(f"w:{edge_name}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), sz)
        e.set(qn("w:space"), "6")
        e.set(qn("w:color"), color)
        pbdr.append(e)
    pPr.append(pbdr)

    for old in pPr.findall(qn("w:shd")):
        pPr.remove(old)
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), fill)
    pPr.append(sh)
    return True


def postprocess(path, header_text="戴维宁定理讲义", dpi_note=True):
    doc = Document(path)

    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.3)
    sec.right_margin = Cm(2.3)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.0)

    _style(doc, "Normal", CN_BODY, EN_BODY, 10.5, color=INK,
           before=0, after=5, spacing=1.55, indent=0)
    _style(doc, "Body Text", CN_BODY, EN_BODY, 10.5, color=INK,
           before=0, after=6, spacing=1.55, indent=21)
    _style(doc, "First Paragraph", CN_BODY, EN_BODY, 10.5, color=INK,
           before=0, after=6, spacing=1.55, indent=21)
    _style(doc, "Compact", CN_BODY, EN_BODY, 10.5, color=INK,
           before=0, after=2, spacing=1.45, indent=0)

    _style(doc, "Heading 1", CN_HEAD, EN_HEAD, 17, bold=True, color=ACCENT,
           before=20, after=9, spacing=1.2, indent=0, keep_next=True)
    _style(doc, "Heading 2", CN_HEAD, EN_HEAD, 13.5, bold=True, color=INK,
           before=14, after=6, spacing=1.25, indent=0, keep_next=True)
    _style(doc, "Heading 3", CN_HEAD, EN_HEAD, 11.5, bold=True, color=INK,
           before=11, after=5, spacing=1.3, indent=0, keep_next=True)
    _style(doc, "Heading 4", CN_HEAD, EN_HEAD, 10.5, bold=True, color=INK,
           before=9, after=4, spacing=1.3, indent=0, keep_next=True)

    _style(doc, "Title", CN_HEAD, EN_HEAD, 26, bold=True, color=INK,
           before=0, after=8, spacing=1.2, indent=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style(doc, "Subtitle", CN_BODY, EN_BODY, 12.5, bold=False, color=ACCENT,
           before=0, after=6, spacing=1.3, indent=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style(doc, "Author", CN_BODY, EN_BODY, 11, color=INK,
           before=10, after=4, spacing=1.3, indent=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style(doc, "Date", CN_BODY, EN_BODY, 11, color=INK,
           before=0, after=4, spacing=1.3, indent=0, align=WD_ALIGN_PARAGRAPH.CENTER)

    _style(doc, "Image Caption", CN_BODY, EN_BODY, 9, color=RGBColor(0x47, 0x55, 0x69),
           before=3, after=10, spacing=1.2, indent=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style(doc, "Table Caption", CN_BODY, EN_BODY, 9, color=RGBColor(0x47, 0x55, 0x69),
           before=3, after=4, spacing=1.2, indent=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style(doc, "Captioned Figure", CN_BODY, EN_BODY, 10.5,
           before=6, after=2, spacing=1.2, indent=0, align=WD_ALIGN_PARAGRAPH.CENTER)
    _style(doc, "Block Text", CN_BODY, EN_BODY, 10, color=RGBColor(0x33, 0x41, 0x55),
           before=4, after=8, spacing=1.45, indent=0)
    _style(doc, "TOC Heading", CN_HEAD, EN_HEAD, 15, bold=True, color=ACCENT,
           before=6, after=10, spacing=1.2, indent=0)

    # 提示块（pandoc custom-style）
    _block_style(doc, "Example", "F3F7FC", "2F5D8A")
    _block_style(doc, "Tip", "F1F8F4", "2E7D52")
    _block_style(doc, "Warn", "FDF3F3", "BE123C")

    # 封面三块（无边框，纯文字排布）
    _style(doc, "CoverLead", CN_HEAD, EN_HEAD, 13, bold=True, color=ACCENT,
           before=54, after=16, spacing=1.4, indent=0,
           align=WD_ALIGN_PARAGRAPH.CENTER)
    _style(doc, "CoverNote", CN_BODY, EN_BODY, 11, color=RGBColor(0x33, 0x41, 0x55),
           before=0, after=10, spacing=1.9, indent=0,
           align=WD_ALIGN_PARAGRAPH.LEFT)
    doc.styles["CoverNote"].paragraph_format.left_indent = Cm(3.3)
    doc.styles["CoverNote"].paragraph_format.right_indent = Cm(3.0)
    _style(doc, "CoverMeta", CN_BODY, EN_BODY, 9.5, color=RGBColor(0x7A, 0x88, 0x99),
           before=0, after=0, spacing=1.5, indent=0,
           align=WD_ALIGN_PARAGRAPH.CENTER)

    # 引用块左侧缩进
    for name in ("Block Text",):
        try:
            doc.styles[name].paragraph_format.left_indent = Cm(0.75)
        except KeyError:
            pass

    # 表格：边框 + 表头底色 + 居中 + 字号
    for t in doc.tables:
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        _borders(t)
        for i, row in enumerate(t.rows):
            # 行内禁止跨页断开，避免出现"半行 + 空行"的断表
            trPr = row._tr.get_or_add_trPr()
            if trPr.find(qn("w:cantSplit")) is None:
                trPr.append(OxmlElement("w:cantSplit"))
            if i == 0:
                # 表头跨页重复
                if trPr.find(qn("w:tblHeader")) is None:
                    trPr.append(OxmlElement("w:tblHeader"))
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.first_line_indent = Pt(0)
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)
                    p.paragraph_format.line_spacing = 1.25
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for r in p.runs:
                        r.font.size = Pt(9.5)
                if i == 0:
                    _shade(cell, "EAF1F8")
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.bold = True

    # 图片段落居中
    for p in doc.paragraphs:
        if p._p.findall(".//" + qn("w:drawing")):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)

    # 页眉
    hp = sec.header.paragraphs[0]
    hp.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hr = hp.add_run(header_text)
    hr.font.size = Pt(8.5)
    hr.font.color.rgb = RGBColor(0x7A, 0x88, 0x99)
    _fonts_run(hr, CN_BODY, EN_BODY)
    # 页眉下细线
    pPr = hp._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "C8D2DD")
    pbdr.append(bottom)
    pPr.append(pbdr)

    # 页脚页码
    fp = sec.footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _field(fp, " PAGE ")

    # 封面页不显示页眉页脚
    sec.different_first_page_header_footer = True
    for part in (sec.first_page_header, sec.first_page_footer):
        for p in part.paragraphs:
            p.text = ""
        pPr0 = part.paragraphs[0]._p.get_or_add_pPr()
        for old in pPr0.findall(qn("w:pBdr")):
            pPr0.remove(old)

    doc.save(path)
    return path


def _fonts_run(run, cn, en):
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    rf.set(qn("w:ascii"), en)
    rf.set(qn("w:hAnsi"), en)
    rf.set(qn("w:eastAsia"), cn)
    rf.set(qn("w:cs"), en)
