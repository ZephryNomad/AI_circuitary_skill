"""把正文里的 ASCII 双引号换成中文引号“ ”。

跳过：LaTeX 公式内（$...$ / $$...$$）、pandoc 属性花括号 {...} 内、代码块内。
配对规则：正文中出现的每个引号按出现顺序交替成 “ 与 ”。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")
FILES = ["p1.md", "p2.md", "p3.md", "p4.md", "p5.md", "p6.md"]


def convert(text):
    out = []
    i = 0
    n = len(text)
    in_math = False   # 单个 $...$
    in_dmath = False  # $$...$$
    in_attr = 0       # { } 深度（pandoc 属性）
    in_code = False
    open_next = True
    while i < n:
        ch = text[i]
        if ch == "`":
            in_code = not in_code
            out.append(ch)
            i += 1
            continue
        if not in_code and ch == "$" and not in_math:
            if text.startswith("$$", i):
                in_dmath = not in_dmath
                out.append("$$")
                i += 2
                continue
            elif not in_dmath:
                in_math = True
                out.append(ch)
                i += 1
                continue
        elif not in_code and ch == "$" and in_math:
            in_math = False
            out.append(ch)
            i += 1
            continue
        if not in_code and not in_math and not in_dmath:
            if ch == "{":
                in_attr += 1
            elif ch == "}":
                in_attr = max(0, in_attr - 1)
            elif ch == '"' and in_attr == 0:
                out.append("\u201c" if open_next else "\u201d")
                open_next = not open_next
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out), open_next


def main():
    for name in FILES:
        p = os.path.join(SRC, name)
        s = open(p, encoding="utf-8").read()
        t, balanced = convert(s)
        if t != s:
            open(p, "w", encoding="utf-8").write(t)
        left = t.count('"')
        print(f"{name}: quotes_left={left} paired_ok={balanced}")
    # 自检：不应再残留正文 ASCII 引号
    for name in FILES:
        p = os.path.join(SRC, name)
        s = open(p, encoding="utf-8").read()
        bad = [l for l in s.splitlines() if '"' in l and "custom-style" not in l
               and not re.search(r"\{\s*[a-zA-Z]+=", l)]
        for b in bad:
            print("  REMAIN:", name, b[:100])


if __name__ == "__main__":
    main()
