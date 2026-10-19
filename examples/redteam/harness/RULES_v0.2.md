# 红队模拟规则 v0.2（修订版裁判字面化）

本文是实现 `score_v2.py` 的规则说明。v0.2 由 v0 红队结果驱动，**只改动奖励与结算结构，不新增操作类型**。

> 边界同上：离线模拟、AI 成员、toy 内容；不涉及真人/真钱/隐私/未发表课题。正式人体 pilot 仍需 `research_contract.md`。

## 0. v0 → v0.2 改了什么

| # | v0 | v0.2 | 针对的红队发现 |
|---|---|---|---|
| 1 | 结算在 `verify`，`merge` 不进目标函数 | 结算在 `merge`；verify 只解锁 merge | merge gate 只是装饰，奖励在 verify 就落袋 |
| 2 | `V_t` = 事件数，无上界 | `Ṽ_t` = **预注册加权验收标准**的完成比例，∈[0,1] | 拆任务/微事件把 V_t 拉满 |
| 3 | `P_t` = p_e 均值，加分项；p_e 是自报数字 | `P̃_t` = 字段齐备率，**gate**，不齐不扣分 | provenance 可以填模板拿满 |
| 4 | `F_t` = 自报失败数，无上界 | `F̃_t` = min(1, 独立 reject 次数/2)，每轮有界 | 自报 F=12 直接刷 |
| 5 | `H/W/U/G` 自报，线性罚分 | **全部移出目标函数**；只留文字复盘 | 惩罚项填 0；H 单位差 60 倍 |
| 6 | 撤回不回溯，先落袋 | `retract` 回溯（as-of 与 final 两套读数） | 先 verified 后 retracted 分数不变 |
| 7 | 个体点数 = 角色权重 b×q，有 c_max | 个体 = criterion 权重 × 0.5/0.5 fate-sharing，无角色权重 | q 自报；复核通胀；cap 饱和 |
| 8 | 无 challenge 结算 | challenge 不计分（保留操作，用于触发修正/撤回） | challenge 每次 +2，不需要正确 |

**v0.2 的可证伪主张（红队要检验的就是这四条）**：
- **C1**：增加 criterion 数量、增加同一 criterion 的 artifact 数量，都不能把 `R_t` 抬高（幂等 + 权重归一）。
- **C2**：自报 `H/W/U/G/F` 与 `p_e` 不再影响任何分数。
- **C3**：先 merge 后 retract，`R_final` 会下降（回溯生效）。
- **C4**：provenance 字段不齐只会让 `P̃` 变低，不会成为可刷的加分项。

## 1. 操作与接口（JSONL，一行一个事件）

通用字段：`round`(int)、`id`(唯一)、`op`、`actor`。`//`/`#` 行忽略。

### propose —— 冻结验收标准（不能改）
```json
{"round":1,"id":"pQ1","op":"propose","actor":"A","task":"Q1","question":"可选：研究问题一句话",
 "criteria":[
   {"id":"c1","w":0.5,"kind":"rerun","test":"python3 check_q1.py 输出平稳分布，hash 与 artifact 一致"},
   {"id":"c2","w":0.5,"kind":"prediction","test":"预测 W=0 时 |pi P - pi|_1 < 1e-12",
    "threshold":"|pi P - pi|_1 < 1e-12"}]}
```
- `kind ∈ {rerun, prediction, counterexample}`；`w > 0` 且 `Σw = 1`（容差 1e-3，便于手写 3 位小数）；`test` ≥ 10 字符。
- 同一 `task` 只能 propose 一次；**标准一旦提出不可修改**（要改就开新 task）。

### produce —— 一个 artifact 对应一个 criterion
```json
{"round":1,"id":"e1","op":"produce","actor":"A","task":"Q1","criterion":"c1",
 "artifact":{"type":"script","hash":"sha256:aaa","cmd":"python3 check_q1.py","seed":0},
 "prov":{"sources":["https://example.org/method"],"ai_share":0.4,"version":1}}
```
- `rerun`/`counterexample`：`artifact` 必须含 `hash` 与 `cmd`。
- `prediction`：`artifact` 必须含 `prediction` 与 `threshold`。
- `prov.sources` 非空字符串列表；`prov.ai_share ∈ [0,1]`；`prov.version` 整数。
- 同一 criterion 可以有多个 artifact（修订），但**只有第一个 merge 的计分**（幂等）。

### verify —— 复核并给出自己的复跑记录
```json
{"round":1,"id":"v1","op":"verify","actor":"B","target":"e1","decision":"accept",
 "evidence":"≥20 字符：我做了什么检查、看到什么结果",
 "rerun":{"ok":true,"own_hash":"sha256:bbb"}}
```
- `actor ≠ 生产者`；`target` 状态为 `draft`/`disputed`；`evidence` ≥ 20 字符。
- `rerun`/`counterexample` 类必须给 `rerun{ok, own_hash}`。
- 多个 accept 者都算 checker，0.5 的 checker 份额在它们之间平分。

### challenge —— 不计分，只触发修正
```json
{"round":2,"id":"c1","op":"challenge","actor":"D","target":"e1",
 "claim":"≥20 字符的具体疑点","evidence":"≥20 字符的证据/推理"}
```
- 把 target 置为 `disputed`；**不影响任何已结算 credit**（除非后续 retract）。

### merge —— 唯一结算点
```json
{"round":1,"id":"m1","op":"merge","actor":"C","target":"e1",
 "own_words":"≥40 字符：假设、证据、局限，用自己的话"}
```
- target 必须 `verified`；`actor ≠ 生产者`；每个 artifact 只能 merge 一次。

### retract —— 回溯扣分
```json
{"round":3,"id":"t1","op":"retract","actor":"A","target":"e1","reason":"≥10 字符"}
```
- target 可为 `draft`/`verified`/`disputed`；置为 `retracted`。

### retrospect —— 只写文字
```json
{"round":1,"id":"r1","op":"retrospect","actor":"A","notes":"耗时、返工、教训"}
```
- `H/W/U/G/F` 等数字字段**不参与计分**（出现会记为歧义提示，但不影响分数）。

## 2. 计分

```
Ṽ_t  = (1/|T|) · Σ_{task∈T} Σ_{c∈criteria(task)} w_c · 1[c 在本轮首次 merge 且未撤回]
P̃_t  = 本轮 merge 的 artifact 中，prov 字段齐备的比例        ∈ [0,1]
F̃_t  = min(1, 本轮独立 reject 次数 / 2)                     ∈ [0,1]
R_t   = 3·Ṽ_t + 2·P̃_t + 1·F̃_t                              ∈ [0,6]

个体贡献: 每个被结算的 criterion，权重 w_c/|T|
          生产者 0.5·w_c/|T|；accept checker 平分另外 0.5·w_c/|T|
          撤回后：final 口径下归零
```
- 报两套读数：`R_asof`（每个 merge 轮记账，不回溯）与 `R_final`（按最终状态重算）。
- 诊断指标（**不是奖励项**）：`events_per_criterion`、`n_reject`、`n_challenge`、`n_retract`、`n_merge`。

## 2.1 v0.2.1 修正：整段试验级口径（由第二轮回攻暴露）

v0.2 的 `P̃`、`F̃` 是**逐轮**量：每轮 merge 一件 artifact 就能把 `P̃` 拿满（+2），每轮 2 次 reject 就能把 `F̃` 拿满（+1）。轮数由成员自己决定，所以**逐轮求和的总 R 仍随轮数无界**——第二轮回攻用 6 轮把总 R 刷到 **21.0**（`rt5_attack_v2/events.jsonl`），而内容全空。

修正 v0.2.1：官方分数改为**试验级**，`P̃`、`F̃` 只结算一次：

```
Ṽ      = Σ_t Ṽ_t                       # 已按预注册标准幂等，Σ_t Ṽ_t ≤ 1
P̃      = 全试验 merge 的 artifact 中 prov 齐备的比例
F̃      = min(1, 全试验独立确认的 reject 总数 / 2)
R_trial = 3·Ṽ + 2·P̃ + F̃  ∈ [0, 6]     # 与轮数无关
```

逐轮 `R_t` 只用于复盘展示，**不要求和当作总分**。读数（`score_v2.py` 现算）：

| 日志 | 逐轮求和 | 试验级 R (asof / final) |
|---|---:|---|
| `baseline_v2`（诚实） | 7.050 / 6.300 | **5.050 / 4.300** |
| `rt5_attack_v2`（6 轮空内容） | 21.000 / 21.000 | **6.000 / 6.000**（上界） |

即使按 v0.2.1，内容为空仍能到 6.0 上界——这再次说明"内容价值"不在可机械核验的量里；v0.2.1 只保证**分数不再随轮数膨胀**。

### 2.2 v0.2.2 提议（**未实现**，因为冻结裁判不再改）

第二轮回攻（`rt5_attack_v2`）证明：任何合法日志的 `P̃` 恒等于 1（`_op_produce` 的合法性检查严格蕴含 `_prov_ok`），所以 v0.2.1 的 `R_trial = 3Ṽ + F̃ + 2`，每份合法日志白送 2.0；1 轮 6 个事件约 5.5 分钟即可打满 6.000。诚实组员（`rt6_honest_v2`）的 3 任务真实 pilot 只有 6.000/5.500，且"撤回+重做"永久为 0。

因此提议 v0.2.2（下一版裁判 `score_v3.py` 再实现）：

1. **删掉 `P̃`**：`R_trial = 3Ṽ + F̃ ∈ [0,4]`。所有分数 −2，排序不变。
2. 允许被 retract 的 criterion 由新 artifact `supersedes` 重结算一次（ΣṼ ≤ 1 不变）。
3. round 0 冻结任务集与 `|T|`（消掉后加任务对历史 `R_asof` 的追溯稀释）。
4. checker 用 commit-reveal 分配；每 artifact ≤2 人，份额不因 co-checker 稀释。
5. `R_trial` 用未四舍五入值计算并 clamp；权重归一化。
6. **criterion 级外部难度权重 `d_c`**（非生产者在 produce 前 countersign）：唯一能反转"零工作 > 诚实"排序的补丁；但它是一次人审，可被合谋/俘获。
7. `retrospect.minutes` 必填、只进诊断，报告 `recorded/estimated`，供 §8 停止条件使用。
8. challenge 有条件小额结算（仅当触发 retract/新版，每 artifact 一次）。
9. `verify.decision` 增加 `abstain`（不计 F̃）。

第 1–5、7–9 条只改变刻度；第 6 条改变排序，但把"内容价值"换成了"人审判断"。**没有既机械又对内容敏感的选项。**

## 3. 裁判跑法

```bash
cd "26 summer/DeSci/redteam"
python3 score_v2.py baseline_v2.jsonl                 # 对照
python3 score_v2.py rt5_attack_v2/events.jsonl
python3 score_v2.py x.jsonl --json
```
`EXIT=0` 且输出含「合法性: 通过」才合法。

**对照基准**：`baseline_v2.jsonl` 是 v0.2 下诚实小团队的读数
`R_asof = 7.050`、`R_final = 6.300`（2 任务、3 criterion、1 次真实失败、1 次返工、1 次撤回）。
你的攻击收益与它比较。

## 4. 已知设计取舍（不是漏洞，是 v0.2 明知代价的取舍）

- **propose 与 merge 不计个体贡献**：提出好问题、做整合的人拿不到点。这是为了不让"提任务/当整合者"变成刷分岗位，但也可能造成 free-riding。
- **criterion 由 proposer 定、权重自定、不可修改**：这是为了让标准先于产出，但把风险转移到了"任务/标准选择"。
- **artifact 的 hash/own_hash 是自报字符串**：裁判器无法真的复跑。真实部署必须由某个执行器复跑；模拟里只能把它当作声明。
- **challenge 不计分**：避免 challenge 农场，但可能让反对意见供给不足。
