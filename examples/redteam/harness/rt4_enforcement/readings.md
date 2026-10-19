# readings.md — 同一份 `events.jsonl` 的 8 种读法

**日志**：`rt4_enforcement/events.jsonl`（5 轮、6 个 produce、4 名成员 A/B/C/D）。  
**裁判**：`../score.py`（冻结，只读；未改）。**全部 8 条命令 `EXIT=0`；`--json` 输出 `violations=[]`，去掉 `--json` 即打印「合法性: 通过」。**

> 下表的 `--json` 只用于抽取字段；去掉 `--json` 即得完整表格。C1 的完整原始输出见 `score.txt`。

## 完整命令（均在 `redteam/` 下运行）

```bash
cd "/Users/zhangjunshuo/Desktop/课题组/26 summer/DeSci/redteam"

# C1 默认：hours / auto / absolute / cmax=30
python3 score.py rt4_enforcement/events.jsonl --json

# C2 H 按分钟
python3 score.py rt4_enforcement/events.jsonl --h-unit minutes --json

# C3 F 只用申报值
python3 score.py rt4_enforcement/events.jsonl --f-mode reported --json

# C4 F 只用派生值（进入 disputed 的事件数）
python3 score.py rt4_enforcement/events.jsonl --f-mode derived --json

# C5 上限改为每轮
python3 score.py rt4_enforcement/events.jsonl --cap-mode per-round --json

# C6 绝对上限 10
python3 score.py rt4_enforcement/events.jsonl --cmax 10 --json

# C7 每轮上限 10
python3 score.py rt4_enforcement/events.jsonl --cmax 10 --cap-mode per-round --json

# C8 组合读法
python3 score.py rt4_enforcement/events.jsonl \
  --h-unit minutes --f-mode derived --cap-mode per-round --cmax 10 --json
```

## 读数矩阵（R 为每轮 R_t；clawback 为裁判的 `R_回溯` 诊断列）

| # | 读法 | R1 | R2 | R3 | R4 | R5 | 总 R | clawback | c_A | c_B | c_C | c_D |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C1 | 默认 hours/auto/absolute/30 | 2.00 | 11.00 | 2.00 | 0.00 | 1.00 | **16.00** | 8.00 | 15.20 | 13.00 | 4.00 | 0.00 |
| C2 | `--h-unit minutes` | 4.95 | 13.95 | 4.95 | 0.00 | 1.00 | **24.85** | 16.85 | 15.20 | 13.00 | 4.00 | 0.00 |
| C3 | `--f-mode reported` | 2.00 | 11.00 | 2.00 | 0.00 | 0.00 | **15.00** | 7.00 | 15.20 | 13.00 | 4.00 | 0.00 |
| C4 | `--f-mode derived` | 2.00 | 11.00 | -2.00 | 0.00 | 1.00 | **12.00** | 4.00 | 15.20 | 13.00 | 4.00 | 0.00 |
| C5 | `--cap-mode per-round`（cmax=30） | 2.00 | 11.00 | 2.00 | 0.00 | 1.00 | **16.00** | 8.00 | 15.20 | 13.00 | 4.00 | 0.00 |
| C6 | `--cmax 10`（absolute） | 2.00 | 11.00 | 2.00 | 0.00 | 1.00 | **16.00** | 8.00 | 10.00 | 10.00 | 4.00 | 0.00 |
| C7 | `--cmax 10 --cap-mode per-round` | 2.00 | 11.00 | 2.00 | 0.00 | 1.00 | **16.00** | 8.00 | 15.20 | 13.00 | 4.00 | 0.00 |
| C8 | minutes + derived + per-round + 10 | 4.95 | 13.95 | 0.95 | 0.00 | 1.00 | **20.85** | 12.85 | 15.20 | 13.00 | 4.00 | 0.00 |

**F 与 H 的实际输入**（供逐项核对）：

| # | F_used（每轮） | H_hours（每轮） |
|---|---|---|
| C1/C5/C6/C7 | 0, 0, 5, 0, 1 | 30, 30, 30, 0, 0 |
| C2 | 0, 0, 5, 0, 1 | 0.5, 0.5, 0.5, 0, 0 |
| C3 | 0, 0, 5, 0, 0 | 30, 30, 30, 0, 0 |
| C4 | 0, 0, 1, 0, 1 | 30, 30, 30, 0, 0 |
| C8 | 0, 0, 1, 0, 1 | 0.5, 0.5, 0.5, 0, 0 |

## 读法差异（同一日志，未改一个字符）

1. **H 单位**：`H=30` 在 hours 下是 `-0.1×30=-3.00/轮`，在 minutes 下是 `-0.1×0.5=-0.05/轮`；罚项差 **60×**，总 R 从 16.00 变 24.85（**+8.85**）。这是本日志最大的单一读法摆动，约等于 baseline 总 R 的 94%。
2. **F 取值**：第 3 轮自报 `F=5`、派生 `F=1`；第 5 轮自报 `F=0`、派生 `F=1`。auto 用 `5+1`，reported 用 `5+0`，derived 用 `1+1`；总 R 为 16.00 / 15.00 / 12.00。**auto 不是简单的 max**：若自报 0.5、派生 1，auto 得 0.5（小于派生）；若自报 0，auto 退回派生 1（奖励"不填"）。
3. **上限读法**：`--cap-mode per-round` 在 cmax=30 时无影响（C5=C1）；在 cmax=10 时，absolute 把 A、B 截到 10.00/10.00（C6），per-round 容许累计超过 10（C7 仍为 15.20/13.00）。同一个 `c_max=10`，两种读法让 c_A 差 **5.20**（1.52×）。
4. **clawback 不是官方总分**：默认 `总 R=16.00`，而 `R(最终状态回溯)=8.00`；C2 下为 24.85 vs 16.85。裁判把 clawback 放在诊断列，`total_R` 仍是不回溯的读法。**撤回两个事件（e1、e2）没有扣掉 8.00 分。**
5. **总摆动**：总 R 从 **12.00 到 24.85**（2.07×）；c_A 从 **10.00 到 15.20**（1.52×）；c_B 从 **10.00 到 13.00**（1.30×）。读法本身造成的差（12.85）大于 baseline 的 9.45（不同日志，仅量级对照）。
6. **合法性不受读法影响**：8 种组合都 `EXIT=0`、无 `!` 行；差异全部来自参数，不来自非法事件。8 条 "规则歧义命中"（`reproduce`、对 verified 的 `challenge`、对 disputed 的 `verify`）是 RULES 的 ambiguity 提示，不是 violation。

## 复现核对

- C1 原始输出：`score.txt`，最后一行 `合法性: 通过（未触发任何机械约束）`，`EXIT=0`。
- 所有 c_i 为第 5 轮结束后的累计值；c_D=0 是因为 D 只 produce 了 e6 且被 reject（produce 本身不结算正式点数）。
- `R_回溯` 只重算 R 的 V/P，不重算 c_i，也不施加 U/W 罚分；它是诊断列，不是官方 `total_R`。
