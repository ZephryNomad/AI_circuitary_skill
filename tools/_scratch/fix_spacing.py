"""把源文件里被 OMML 吞掉的 \\qquad / \\quad 换成全角空格（\text{　}）。

背景：LibreOffice 导入 OMML 时 \\qquad、\\quad、\\hspace 全部丢失，
导致「a=1,b=2」紧贴。经渲染电池验证，\\text{　}（全角空格）能保留可见间距。
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUB = [(r"\qquad", r"\text{　　}"), (r"\quad", r"\text{　}")]

total = 0
for path in sorted(glob.glob(os.path.join(ROOT, "src", "p*.md"))):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    before = text
    for old, new in SUB:
        # 只替换数学环境内的（源文件里这些命令只出现在 $$...$$ 与 $...$ 中）
        text = text.replace(old, new)
    n = sum(before.count(old) for old, _ in SUB)
    if text != before:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(os.path.basename(path), "replaced", n)
        total += n
    else:
        print(os.path.basename(path), "clean")
print("total replaced:", total)
