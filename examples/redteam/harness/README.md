# redteam/ — 奖励函数红队模拟（离线纸面）

> **边界**：只用 AI 角色、toy 内容；不涉及真人、真钱、真数据、未发表课题或组内保密材料。  
> 证明的是**策略空间存在性**（规则允许 + 裁判付钱），不是真实同学的行为预测。  
> 主报告：[../2026-10-18_奖励函数红队模拟_报告与v0.2修订.md](../2026-10-18_奖励函数红队模拟_报告与v0.2修订.md)

## 怎么跑

```bash
cd "26 summer/DeSci/redteam"
python3 verify_all.py            # 主报告引用的全部数字，一次复算
python3 score.py baseline.jsonl  # v0 诚实对照：R = 9.450
python3 score_v2.py baseline_v2.jsonl  # v0.2 诚实对照：R_asof = 7.050 / R_final = 6.300
```

两份裁判都是**冻结**的：`score.py`（v0，sha256 `7d0ba019…443998332`）与 `score_v2.py`（v0.2）。改裁判会让所有日志不可比，**不要改**；如需新规则请新建 `score_v3.py`。

## v0（原草案）

| 文件 | 内容 |
|---|---|
| `RULES_v0.md` | 草案的字面化转写 + 事件 JSON 接口 + 裁判不执行的约束清单 |
| `score.py` | 冻结裁判（480 行）；`--h-unit` / `--f-mode` / `--cap-mode` / `--cmax` 是"官方读法"开关 |
| `baseline.jsonl` | 4 人 2 轮诚实对照，R = 9.450 |
| `rt1_volume/` | 体量套利：R = **92.997**；12 微事件、验证通胀、`c_max` 不封顶团队 |
| `rt2_fail2earn/` | 失败套利：R = **47.450**；F 自报无上限（附录 F=1e6 → R=1e6）、junk→reject、challenge 农场、veto-DoS |
| `rt3_paperwork/` | 文书剧场：R = **26.000**；p 无指称、q 自报、merge 零权重、AI 标记零后果、retract 洗白 |
| `rt4_enforcement/` | 测量/执法层：R = **16.000**；自报惩罚、H 单位 60×、ratchet、A↔B 互审、读法矩阵、δ\* 推导 |

每份攻击目录都含：`events.jsonl`（合法，`EXIT=0`）、`score.txt`（裁判原始输出）、`report.md`（机制 + 数字 + 合法性依据 + 最小补丁 + "已演示 / 推测"分层）。

## v0.2（修订）与 v0.2.1（整段试验级）

| 文件 | 内容 |
|---|---|
| `RULES_v0.2.md` | 修订规则：merge 结算、预注册加权标准、自报量出局、clawback；含 **v0.2.1** 整段试验级修正 |
| `score_v2.py` | 冻结裁判；逐轮 `as-of`/`final` 双口径 + `trial`（整段试验级）口径 |
| `baseline_v2.jsonl` | 诚实对照：逐轮和 7.050 / 6.300；**trial 5.050 / 4.300** |
| `rt5_attack_v2/` | 第二轮攻击：6 轮空内容，逐轮和 **21.000**、trial **6.000**；证明 `P̃≡1`（白送 2.0）与"1 轮 6 事件约 5.5 分钟打满" |
| `rt6_honest_v2/` | 第二轮诚实组员：真实 3 任务 pilot，trial **6.000/5.500**（与空内容同分或更低）；`friction.md` + 可复跑 `artifacts/` |

**v0.2.1 一句话**：`P̃`、`F̃` 是逐轮量、每轮都能重新拿满，所以逐轮求和的总 R 仍随轮数无界；官方分数改为
`R_trial = 3Ṽ + 2P̃ + F̃ ∈ [0,6]`（`P̃`/`F̃` 全试验只结算一次），与轮数无关。复算：

```bash
python3 score_v2.py rt5_attack_v2/events.jsonl   # 逐轮和 21.000，trial 6.000
python3 score_v2.py rt6_honest_v2/events.jsonl   # 诚实 3 任务：trial 6.000 / 5.500
python3 verify_all.py                            # 含 P̃≡1 检查与 n=2/6/12 轮的轮数不变性
```

**v0.2.2 提议（未实现，见 `RULES_v0.2.md` §2.2）**：删掉恒为 1 的 `P̃`、`supersedes` 重结算、冻结 `|T|`、commit-reveal checker、外部难度权重 `d_c`。前几条只改刻度；只有 `d_c` 能反转"零工作 > 诚实"的排序，但它是一次人审（可被合谋/俘获）。

## 裁判的已知实现注记（不是设计漏洞，冻结不改）

> 这些是**冻结后的勘误**：为了让 8 份日志与对应 `score.txt` 可复现，裁判不再修改；未来从头写 `score_v3.py` 时再修。

- `score.py` 曾在 12:15 被修过一次：`--json` 参数死循环（少写 `i += 1`）。修复前生成的读数不可用；`verify_all.py` 用当前版本重算全部。
- `score.py` 的轮次倒退检查是死代码（先排序再比较，恒不成立）——不影响任何读数。
- `PROVENANCE_FULL = 0.95`（`p ≥ 0.95` 得 +1 点）是裁判自定阈值，草案未写；已在 `RULES_v0.md` 的"不执行"清单外单独说明。
- `F_derived` 按 (事件, 轮) 计数：同一事件跨轮被再次 challenge 会再计一次 F。这是**读法选择**，不是 bug；`--f-mode reported` 可绕开。
- `reproduce` 不是七类操作，被实现成 `verify.mode=reproduce`（b=3）；这是接口映射，草案未定义。
- **`score_v2.py`：`P̃ ≡ 1`**——`_op_produce` 的合法性检查严格蕴含 `_prov_ok`，所以任何合法日志的 provenance gate 都满分；`R_trial = 3Ṽ + F̃ + 2`，白送 2.0。
- `score_v2.py`：`R_asof` 用最终 `len(tasks)` 作分母（后加任务会追溯稀释历史轮）。
- `score_v2.py`：`R_trial` 由已四舍五入的分轮值相加，`n=6` 会出现 6.001。
- `score_v2.py`：`merge` 会把未解决 challenge 自动标 resolved；权重容差 1e-3 允许 `Σw=1.0009`（上限 6.0027）。

## 复现口径

1. 只算合法日志：`EXIT=0` 且输出含「合法性: 通过」。
2. 非法事件只证明机械约束有效，不作漏洞；各报告附录已单列。
3. 横向比较必须在同一份裁判版本下重跑（`verify_all.py` 就是干这个的）。
