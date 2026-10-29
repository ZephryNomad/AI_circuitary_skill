"""spice_run.py —— 把网表交给真实 ngspice 跑，取回结果

为什么需要它
    tools/mna.py 只做**线性直流**：电阻 + 独立源 + 四种受控源。
    下面这些它在原理上就做不了，必须交给真 SPICE：
        · 非线性器件：二极管、三极管、MOS 管（要 .model 和工作点迭代）
        · 瞬态：.tran（电容充放电、整流波形、开关过程）
        · 交流：.ac（相量、频率响应、谐振、滤波）
        · 直流扫描：.dc（伏安特性、传输特性）

    所以分工是：
        线性直流题  →  tools/convert.py（精确有理数 + 往返自检 + ngspice 交叉）
        其余一切    →  本脚本（直接喂 ngspice，双精度浮点）

用法
    python tools/spice_run.py 网表.cir
    python tools/spice_run.py 网表.cir --measure vmax max v(2)
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def _extra_candidates():
    """常见安装位置，全部由环境变量拼出来，不含任何写死的用户路径。"""
    out = []
    for env, sub in (("ProgramFiles", ("ngspice", "bin")),
                     ("ProgramFiles(x86)", ("ngspice", "bin")),
                     ("LOCALAPPDATA", ("ngspice", "bin"))):
        base = os.environ.get(env)
        if base:
            out.append(os.path.join(base, *sub, "ngspice_con.exe"))
    return out


def find_ngspice():
    cands = []
    # 1. 环境变量直接指定
    if os.environ.get("NGSPICE"):
        cands.append(os.environ["NGSPICE"])
    # 2. conda 临时环境（README 里那条 conda create 装到这里）
    cands.append(os.path.join(os.environ.get("TEMP", "/tmp"), "ngsenv",
                              "Library", "bin", "ngspice_con.exe"))
    # 3. 常见安装位置
    cands.extend(_extra_candidates())
    # 4. PATH
    cands.extend(["ngspice_con", "ngspice"])
    for c in cands:
        if os.path.isabs(c):
            if os.path.isfile(c):
                return c
        else:
            from shutil import which
            w = which(c)
            if w:
                return w
    return None


def run(cir_text, timeout=180, extra_control=None):
    """跑一段网表，返回 ngspice 的完整 stdout+stderr。

    若网表里已有 .control 块，原样执行；否则自动补一个 .op。
    """
    exe = find_ngspice()
    if not exe:
        raise RuntimeError(
            "找不到 ngspice_con 可执行文件。装法：\n"
            "  conda create -y -q -p \"$env:TEMP\\ngsenv\" -c conda-forge ngspice\n"
            "或把你已有的 ngspice_con 路径写进环境变量 NGSPICE。\n"
            "查找顺序：NGSPICE -> %TEMP%\\ngsenv -> Program Files -> PATH")
    text = cir_text
    if ".control" not in text.lower():
        lines = [l for l in text.splitlines()
                 if not l.strip().lower().startswith((".op", ".end", ".print"))]
        lines += [".control", "set numdgt=12"]
        if extra_control:
            lines += list(extra_control)
        else:
            lines += ["op", "print all"]
        lines += [".endc", ".end"]
        text = "\n".join(lines) + "\n"

    fd, path = tempfile.mkstemp(suffix=".cir", text=True)
    os.close(fd)
    try:
        with open(path, "w", encoding="ascii", errors="replace") as f:
            f.write(text)
        r = subprocess.run([exe, "-b", path], capture_output=True, text=True,
                           timeout=timeout, errors="replace")
        return (r.stdout or "") + (r.stderr or ""), r.returncode
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def measures(out):
    """从输出里抽出 meas 结果：{'名字': 数值}。"""
    d = {}
    for m in re.finditer(r"^\s*([A-Za-z_][\w]*)\s*=\s*([-+0-9.eE]+)", out, re.M):
        try:
            d[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    return d


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("用法：python tools/spice_run.py 网表.cir", file=sys.stderr)
        return 2
    path = argv[0]
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    try:
        out, rc = run(text)
    except RuntimeError as e:
        print("[失败] %s" % e, file=sys.stderr)
        return 3
    print(out)
    ms = measures(out)
    if ms:
        print("\n--- 抽出的 meas 结果 ---")
        for k, v in ms.items():
            print("  %-12s = %g" % (k, v))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
