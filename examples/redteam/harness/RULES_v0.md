# 红队模拟规则 v0（裁判字面化）

本文把《AI 协作科研系统：操作子集与奖励函数草案》（`../2026-10-18_AI协作科研系统_操作子集与奖励函数草案.md`）**转写成可执行接口**，供红队模拟使用。

> **边界**：这是离线模拟的裁判器，不是试用平台。只用 AI 成员、只用 toy 内容、不涉及任何真人、真钱、代币、课程评价、未发表课题或组内保密材料。正式的人体 shadow pilot 仍需单独的 `research_contract.md` 并经用户批准。

## 1. 成员与轮次

- 成员 ID 用大写字母或短名（`A`、`B`、`C`、`D`、`m1` …），至少 2 人，建议 3–5 人。
- 轮次 `round` 为非负整数。日志按 `(round, 行序)` 回放。
- 每个成员每轮可以提交任意多条事件。

## 2. 事件接口（JSONL，一行一个 JSON）

通用字段：`round`(int)、`id`(str, 全局唯一)、`op`(七类之一)、`actor`(str)。
`//` 或 `#` 开头的行会被忽略，可作注释。

### propose
```json
{"round":1,"id":"p1","op":"propose","actor":"A","task":"Q1","acceptance":"≥8 字符的可执行验收条件"}
```
裁判约束：`task` 非空；`acceptance` ≥ 8 字符；同一 `task` 不能重复 propose。

### produce（创建一个事件，初始状态 draft）
```json
{"round":1,"id":"e1","op":"produce","actor":"A","task":"Q1","content":"产出内容",
 "p":0.9,"q":0.85,"human_share":0.6,"ai_share":0.4,"version":1,"revises":null}
```
裁判约束：`task` 必须先 propose；`p,q ∈ [0,1]`；`human_share + ai_share = 1`；`version` 为整数；`content` 非空。
`revises` 可选，指向被修订的旧事件 id。

### verify
```json
{"round":1,"id":"v1","op":"verify","actor":"B","target":"e1","decision":"accept",
 "v":0.8,"mode":"check","evidence":"≥10 字符的检查记录/运行记录/反例"}
```
裁判约束：`target` 存在且状态为 `draft` 或 `disputed`；`actor ≠ 生产者`；`decision ∈ {accept,reject}`；`v ∈ [0,1]`；`evidence` ≥ 10 字符；`mode ∈ {check,reproduce}`。
`accept → verified`，`reject → disputed`。

### challenge
```json
{"round":2,"id":"c1","op":"challenge","actor":"C","target":"e1",
 "claim":"≥20 字符的具体疑点","evidence":"≥20 字符的证据/推理"}
```
裁判约束：`target` 存在且未撤回；`claim`、`evidence` 各 ≥ 20 字符（"我感觉不对"会被拒绝）。目标事件进入 `disputed`。

### merge
```json
{"round":1,"id":"m1","op":"merge","actor":"C","target":"e1",
 "own_words":"≥40 字：假设、证据、局限（用自己的话）"}
```
裁判约束：目标状态必须为 `verified`；至少有 1 名 `accept` 复核者且不是生产者；`own_words` ≥ 40 字符；同一事件只能 merge 一次。

### retract
```json
{"round":3,"id":"x1","op":"retract","actor":"A","target":"e1","reason":"≥10 字符的理由"}
```
裁判约束：目标状态必须为 `verified`；撤回后状态为 `retracted`，历史保留。

### retrospect
```json
{"round":1,"id":"r1","op":"retrospect","actor":"A","H":1.5,"W":0,"U":0,"G":0,"F":1,
 "false_checks":{"B":0},"notes":"可选"}
```
`H/W/U/G/F` 为非负数字；同一轮多个成员的 retrospect **求和**。`false_checks` 是可选 dict（成员 → 次数）。

## 3. 裁判执行与不执行的约束

**机械执行（违反即非法事件、不计分）**：上节各 op 的约束、状态转移、`actor ≠ 生产者`、merge 必须有独立 checker。

**不执行（因为草案没有给出可执行定义）**：
- `p_e`（provenance 完整度）由**生产者自己申报**；
- `v_e`（复核信号）由**复核者自己申报**；
- `q_e`（rubric 质量分）由**生产者在 produce 时申报**，草案未规定谁打分；
- `H/W/U/G/F` 由**retrospect 自己申报**；
- `false_checks`（−3 项）由**自报**决定；
- challenge 是否"具体"、`own_words` 是否"自己的话"，只做长度检查；
- 独立性的唯一机械含义是 `actor ≠ 生产者`。

## 4. 计分

（照抄草案 §5、§6）

```
V_t = 本轮首次进入 verified 的 produce 事件数
P_t = 这些事件的 p_e 均值
F_t = 本轮"有清晰记录但被否定/失败的测试数"
R_t = 3 V_t + 2 P_t + F_t - 0.1 H_t - 2 W_t - 5 U_t - 5 G_t
```
个体点数：`r_i = Σ b_{r(e)} q_e + 2 n_i^challenge + 1 n_i^provenance - 3 n_i^false_check`，
`b` 取 `produce=1(verify 后才结算), verify=2, reproduce=3, correct=2, provenance=1`；
`c_i(t+1) = min(c_i(t) + r_i(t), c_max)`，默认 `c_max=30`。

## 5. 裁判器参数（同一个日志可以有不同读法）

```bash
cd "26 summer/DeSci/redteam"
python3 score.py baseline.jsonl                        # 默认读法
python3 score.py baseline.jsonl --h-unit minutes       # H 按分钟解释
python3 score.py baseline.jsonl --f-mode derived       # F 只用"进入 disputed 的事件数"
python3 score.py baseline.jsonl --cap-mode per-round   # c_i 改为每轮上限
python3 score.py baseline.jsonl --cmax 10 --json       # JSON 输出
```
默认读法：`H` 以小时计、`F` 优先用申报值（为 0 时退回派生值）、`c_i` 上限为绝对上限。

**注意**：`score.py` 是冻结裁判。如果你认为它**实现错了**（与草案字面不符），单独写进 `scorer_bug.md`；不要改 `score.py`。设计漏洞与实现 bug 是两类不同的结论。

## 6. 红队日志的合法性自检

提交前必须自己跑一遍：

```bash
cd "26 summer/DeSci/redteam"
python3 score.py <你的目录>/events.jsonl; echo "EXIT=$?"
```
`EXIT=0` 且输出里"合法性: 通过"才算合法日志。有 `!` 行就是非法事件，会被 Lead 打回。

**对照基准**：`baseline.jsonl` 是同一裁判下的"诚实小团队"日志，总 `R=9.450`（2 轮、4 人、3 个 produce 事件、1 次真实失败、1 次真实返工）。你的攻击收益请与它比较，而不是与 0 比较。
