# circuit-solving（可整包拷走的电路题求解技能）

一个自包含的技能包：`SKILL.md` 教判读方法，`circuit.py` 负责精确计算并自证，
`golden/` 是 19 张金题回归。

## 怎么用（三种方式，任选）

**1. 直接当工具用**（不装成技能也能用）

```bash
python circuit.py selftest        # 先跑一次，全绿再干活
python circuit.py card  题.card
```

**2. 装成 DSH / Codex / Claude 技能**

把整个 `circuit-solving/` 目录放进技能根即可，目录名就是技能名：

| 环境 | 技能根 |
|---|---|
| DSH | `%DSH_HOME%\skills\`（默认 `C:\Users\<你>\.dsh\skills\`） |
| 公共 Agent | `%DSH_AGENTS_HOME%\skills\`（默认 `~/.agents/skills/`） |
| Claude Code | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |

放好后目录形如 `.../skills/circuit-solving/SKILL.md`，重开会话即被发现。

**3. 当成给模型的说明书**

只把 `SKILL.md` 贴给模型（约 2600 汉字），模型就掌握了判读五步法、题目卡语法、
五段式回复模板与踩坑清单——即使它没有能力跑 `circuit.py`，也仍然按这套流程做题。

## 依赖

只要 Python 3（标准库即可，**不需要 sympy / numpy / ngspice / 联网**）。

已验证：`python -S -E circuit.py selftest` 在禁用 site-packages 的情况下通过，
imports 只有 `fractions / itertools / json / math / os / re / sys`。

## 自证

```
$ python circuit.py selftest
自测：299 项通过，0 项失败          # 约 6 秒
```

299 项 = 15 张金卡的逐节点电压/逐支路电流/待求量/戴维宁三参数（与母项目
`summary.json` 逐值相同）+ 19 项"每张卡自身的机器校验" + 相量解析式对拍 +
RC 低通频响四点 + 一阶 RC/RL 与二阶 RLC 的解析解对拍（含步长减半收敛性）+
运放有限增益精确解 + 叠加定理 + 四种受控源语义逐条对拍 + 逻辑穷举与最简式。

## 内容

```
circuit-solving/
├── SKILL.md          判读方法、题目卡语法、命令速查、回复模板、踩坑清单
├── circuit.py        求解器本体（单文件，纯标准库）
├── golden/           15 张直流金卡 + 4 张逻辑金卡 + expected.json 期望值
└── demo/             3 个最小可跑示例（相量、瞬态、非自启动状态机）
```

## 边界

只做**线性**电路。非线性器件（二极管、晶体管工作点）做不了；运放只能用
VCVS 建有限增益模型；图片不能直读（必须由人转成文字卡）。
