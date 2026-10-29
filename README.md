# circuitary

电路原理题目的**精确求解与交叉验证**工具链，外加一份自编的戴维宁定理讲义，
以及一个可以整包拷走的求解技能 [`skill/circuit-solving`](skill/circuit-solving)。

核心主张只有一句：**电路题不该靠"算两遍看起来一样"来确认，而该由四条互不依赖的通道相互证伪。**

| 通道 | 实现 | 它独立在哪 |
|---|---|---|
| ① 精确有理数 MNA | `tools/mna.py`（sympy `Rational`） | 全程 `p/q`，舍入误差为零，误差只能来自列式错误 |
| ② 纯 `fractions` 独立实现 | `selftest` 内建 | 不用 sympy、不用符号线性代数，主元消元自己写 |
| ③ 真实 ngspice | `tools/spice_check.py` | 第三方 SPICE 内核，牛顿迭代 + 浮点，与①②的失效方式完全不同 |
| ④ 外部答案 | `tools/answer_key.py` + 讲义写定值 | 人手算的结果，与任何程序无关 |

另有两条**物理约束**当守门员：功率平衡（特勒根定理，Σu·i 必须严格为 0）与
换参考点复算（所有节点间电压差必须逐项不变）。它们拦的是"数值自洽但物理可疑"的解——
最典型的是支路电流全为 0 这种看似收敛的退化解。

## 实测结果

以下都是在本仓库里跑出来的，不是设计目标：

```
15 张题目卡   往返转换 15/15 一致，求解 15/15 一致
ngspice 校验  15/15 逐节点电压相同
讲义答案比对  4/4 完全一致
sympy vs Fraction  15/15 逐值相同（证明零依赖路线可行）
skill 自测    299 项通过，0 项失败（约 6 秒，纯标准库）
```

## 三个可独立使用的部分

### 1. `skill/circuit-solving` —— 给模型用的求解技能

单文件、纯标准库（imports 只有 `fractions / itertools / json / math / os / re / sys`），
不需要 sympy、numpy、ngspice 或联网。覆盖四类题：

- 线性直流（含四种受控源 E/G/H/F，戴维宁 / 诺顿 / 最大功率）
- 正弦稳态相量（RLC，复数阻抗，精确到 `a/b + c/d·i`）
- 一阶 / 二阶瞬态（RC、RL、RLC，后向欧拉 + 步长减半收敛性验证）
- 数字逻辑（组合 Quine-McCluskey 最简式 + 卡诺图 + 穷举校验，时序 JK/D/T/SR 激励与自启动）

```bash
python skill/circuit-solving/circuit.py selftest        # 先跑自测，全绿再干活
python skill/circuit-solving/circuit.py card 题.card    # 直流 + 戴维宁
python skill/circuit-solving/circuit.py ac   题.card    # 相量
python skill/circuit-solving/circuit.py tran 题.card    # 瞬态
python skill/circuit-solving/circuit.py logic 题.logic  # 数字逻辑
```

整包拷到任意目录都能跑；只拷 `circuit.py` 一个文件也能跑（自测降级为 25 项内置对拍）。

### 2. `docs/题目怎么给我.md` —— 输入规范

电路题出错，绝大多数不是算错而是**读错**。这份文档规定发题时必须交代的五件事：
电压源正极在哪端、电流源箭头朝哪、受控源参考极性、待求量的参考方向、到底求什么。
里面有一条真实代价：习题 4-14 的受控源极性读反，`P_max` 从 108 W 变成 84.5 W，
`R_eq` 从 3 Ω 变成 2 Ω——两个答案都"算得通"，只有极性交代清楚才能分辨。

### 3. `out/讲义/` —— 戴维宁定理讲义

8 章正文、18 张手绘风格插图、5 道精讲例题、4 道习题，`.docx` 与 `.pdf` 两版。
正文源文件在 `src/`，插图由 `tools/make_*.py` 生成。

## 目录

```
circuitary/
├─ skill/circuit-solving/   可整包拷走的求解技能（单文件求解器 + 19 张金卡 + 3 个示例）
├─ docs/题目怎么给我.md      电路/模拟/数字三类题的输入规范
├─ tools/                   题目卡 ↔ 网表 ↔ 求解 ↔ 校验的完整工具链
│  ├─ netlist.py            纯文本层：题目卡 ↔ SPICE 网表双向转换
│  ├─ mna.py                纯求解层：sympy 精确 MNA + 戴维宁参数提取
│  ├─ convert.py            驱动层：报告、往返自检、功率平衡校验
│  ├─ spice_check.py        第三方校验：调 ngspice 求解并逐节点比对
│  ├─ answer_key.py         与讲义写定的答案逐题比对
│  ├─ logic.py              数字电路：组合化简 + 时序分析
│  ├─ spice_run.py          非线性 / .tran / .ac / .dc 交给 ngspice
│  ├─ check_format.py       编码与换行体检：BOM / CRLF / 行尾空白 / 末尾换行
│  └─ _scratch/             一次性探针脚本与能力探测网表（留档备查）
├─ netlists/                题目卡（.card）与数字电路卡（.logic）
├─ src/ figs/ out/          讲义正文、插图与全部产物
└─ .gitattributes .gitignore LICENSE README.md
```

## 依赖

- **求解技能**：只要 Python 3，无第三方依赖。
- **完整工具链**：Python 3.13 + sympy、numpy、matplotlib、pymupdf、python-docx。
- **ngspice 交叉校验（可选）**：`conda create -y -q -p "$env:TEMP\ngsenv" -c conda-forge ngspice`。
  `spice_check.py` 会依次在 `NGSPICE` 环境变量、`%TEMP%\ngsenv`、`Program Files` 与 `PATH` 里查找，
  找不到会明确报出而不是静默跳过。
- **讲义排版（可选）**：LibreOffice 与 pandoc，路径通过 `PANDOC` / `NODE` / `LO_CLI` 环境变量指定。

## 常用命令

```bash
# 全部题目：批量求解 + 往返自检 + 写报告
python tools/convert.py netlists --all --selftest --outdir out/netlists --json out/netlists/summary.json

# ngspice 交叉校验（需要显式列出卡片路径）
python tools/spice_check.py $(ls netlists/*.card)          # bash
python tools/spice_check.py (Get-ChildItem netlists\*.card).FullName   # PowerShell

# 与讲义答案比对
python tools/answer_key.py --verbose

# 数字电路：卡诺图 / 最简式 / 门数 / 穷举校验 / 时序自启动
python tools/logic.py netlists/logic --selftest --outdir out/logic

# 编码与换行体检（应全为 0；--apply 就地修正）
python tools/check_format.py
```

## 已知边界

- `convert.py` 的精确求解只覆盖**线性直流**。相量请用技能的 `ac` 子命令，
  瞬态与非线性请用 `spice_run.py` 交给 ngspice。
- 含三极管/MOS 的**工作点设计题**不套用 `convert.py`：题目卡语法不适合表达器件模型参数，
  需按 `tools/design_5_2_5.py` 那种「闭式解 + 回代残差 + 另一条代数路径 + ngspice」四段式单独建脚本。
- 数字电路覆盖组合化简与时序激励/状态表；**带输入条件的状态表**（`S0, X=0 → S0`）不支持，
  需写成两列的「现态 次态」。
- 题目卡是**人工结构化**的，不做图片自动识别。图片→网表的实测结论见
  `docs/题目怎么给我.md` 第七节：在教材风格插图上按元件计数的召回是 78.3%（36/46），
  横平竖直的图 20/20、斜置电桥 2/10，且只认 10 类元件、不含受控源。
  结论是「图片是给人看的，不是给模型看的」——所以要有一套输入规范。

## 关于 `vendor/`

上游第三方项目 SINA（MEDAL Research Group，MIT，论文编号 2607.01609）的源码与
YOLO 权重曾作为留档放在 `vendor/sina/`，**本仓库不收录**：体积约 40 MB，其中权重自带
Ultralytics AGPL-3.0 条款，且含上游作者的训练配置与邮箱。基于它得出的实测结论保留在
`docs/题目怎么给我.md` 与 `tools/probe_sina.py`，需要复现时请按上游仓库的 README 自行获取。

## 许可

[MIT](LICENSE)。讲义正文与插图同样适用；本仓库不含任何 Ultralytics YOLO 权重。
