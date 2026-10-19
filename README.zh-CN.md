# paperunit（中文概览）

**可执行的论文审计。** 给每条论文 claim 绑一条任何人能重跑的命令，并让审计报告本身也能被再次验证。

审计只产出**证据局部**的判定——`SUPPORTED` / `REFUTED` / `INCONCLUSIVE` / `NOT_RUN`——**没有分数、没有排名、没有排行榜**。它检验的是工件（代码、数据、形式化陈述）在某个 commit、某个环境下的表现，不是对论文科学价值的裁决。

详细英文说明见 [README.md](README.md)；长期运营见 [OPS.md](OPS.md)；审计协议与伦理红线见 [docs/protocol.md](docs/protocol.md)、[docs/ethics.md](docs/ethics.md)。

## 快速开始

要求 Python 3.11+，核心零第三方依赖。在 `paperunit/` 目录下：

```bash
python3 -m paperunit validate --audit examples/toy_paper/audit.json
python3 -m paperunit run    --audit examples/toy_paper/audit.json --out out/toy
python3 -m paperunit verify --audit examples/toy_paper/audit.json --report out/toy/audit_report.json
python3 -m unittest discover -s tests -v
```

`run` 写出 `audit_report.json`（含报告摘要，可机读）与 `report.md`（人读：范围、判定、证据、不确定性、限制）。`run` 即使有 `REFUTED` 也返回 0；`verify` 对 `REPRODUCIBLE` 返回 0，`DRIFT`/`TAMPERED` 返回 1，`INCONCLUSIVE` 返回 2。

## 七种 checker

| kind | 检验什么 | 信任来源 |
|---|---|---|
| `numeric` | 声称的数字 vs 命令输出 | 可复跑 + 预注册容差 |
| `stdout` / `exit` | 声称的输出 / 命令成功与否 | 可复跑 |
| `statistics` | 声称的数值/效应 vs 多种子重复实验 | 区间估计 + 等价边界 |
| `lean4` | 形式化陈述 + Lean 4 证明检查 | 证明检查器 |
| `external` | 任意工具（Z3、性质测试、自定义脚本） | 取决于外部工具 |
| `human` | 不可机械判定的判断 | 人审，记为 `NOT_RUN`、不评分 |

## 可选工具链（z3 / Lean 4）

核心零依赖。`z3` 与 `lean4` checker 需要外部工具：

```bash
python3 -m venv .venv && .venv/bin/pip install z3-solver   # z3
# Lean 4：安装 toolchain，使 `lean --version` / `lake --version` 可用（如 elan）
```

本工作区已把两者装在 `.venv/` 与 `.toolchains/`（均 gitignore），用 wrapper 运行：

```bash
scripts/with-toolchains.sh python3 -m paperunit run --audit examples/lean_demo/audit.json --out out/lean
scripts/with-toolchains.sh python3 -m paperunit run --audit examples/z3_demo/audit.json --out out/z3
```

缺少工具链时 checker 返回 `INCONCLUSIVE`（设计如此，绝不假阳性），`verify` 相应报 `INCONCLUSIVE`/`DRIFT`。

## 统计：报告"分辨率"，不是"论文错的概率"

统计 checker 按预注册 seeds 重复实验，报告区间估计与分辨率：

- `SUPPORTED`：声称值与审计估计之差 ≤ 预注册等价边界；
- `REFUTED`：差 > 边界，**且**声称值落在置信区间之外；
- `INCONCLUSIVE`：其余，典型是"差 > 边界但 CI 仍包含声称值"——数据不足以分辨。报告会写明 CI、最小可检测效应与效应量，让读者看到**这份数据能承受多少怀疑**。

seeds、边界、置信水平都写在审计文件里，事后不能改。默认边界是 `paper_precision`：允许偏差最多为论文自己最后一位有效数字（0.923 → 0.001）；也可用显式数值（`fixed`）或版本化政策文件（`policy_ref`，未来 DAO/评议会只治理该文件，不治理 verdict）。

## 形式化：证明买到了什么、没买到什么

1. **证明通过**（`lean4` → `SUPPORTED`）：形式化陈述与证明编译通过且无 `sorry`；形式化文件随报告一起发布，结论只强到"这份形式化"为止。
2. **找到反例**（`external` + Z3/性质测试 → `REFUTED`）：有界域内性质被违反，报告附反例。
3. **确定性复跑**（`numeric`/`stdout`/`exit`）：输出一致或不一致。
4. **区间估计**（`statistics`）：带不确定性的估计。
5. **人审**（`human` → `NOT_RUN`）：只记录，不评分。

Lean 构建失败记为 `INCONCLUSIVE`——"审计方的形式化没走通"不是论文有问题的证据；只有反例或失败的可执行检查才能 `REFUTE`。

## 谁在维护

项目以化名 **无常** 维护；报告与 registry 以该名字署名，真实姓名与法律联络方式由第二名维护者私下保管（见 [docs/ethics.md](docs/ethics.md)）。本项目是独立仓库。

## 状态与限制

- v0.3.1：可运行引擎 + 生成式静态站点（Liquid Glass 风格，落地页 / 检索 / 每份审计的详情页）；目前 registry 里是 demo 审计，尚无真实论文的公开审计；下一步是 5–10 篇真实论文。
- checker 会执行 shell 命令，审计文件是"可执行输入"：只运行你信任的审计（沙盒在路线图上）。
- 统计 checker 暂按独立 seeds、单一指标处理；跨 claim 的多重比较校正在路线图上。
- Lean 目前只验证了"工具链缺失"路径；带真实 Lean 的 CI 与 Z3 可选依赖在路线图上。
- 审计可能出错：报告可更正、可重跑（`verify`），发现错误请开 issue。

## 许可

代码 Apache-2.0；审计报告与文档 CC-BY-4.0（另有说明除外）；registry 索引数据 CC0。
