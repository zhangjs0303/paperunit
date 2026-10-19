# rt1_volume 红队报告：V_t 与 c_i 的体量套利

> 离线纸面模拟：无真人、真钱、真数据；所有 content 都是 toy/行政占位字符串。本文不声称真实同学一定会这样，只报告冻结裁判下的可复现读数与机制。
> 数据标签：**[裁]** = `score.py` 原始输出；**[报]** = 日志自报、裁判未核验；**[假]** = 作者假设；**[算]** = 由 [裁]+[假] 算术得到。攻击者 A，日志用 A/B/C/D 四个可合谋（或一人多角色）的 actor。

## 0. 结论摘要

- 主日志：37 个 produce（25 个进入 verified、12 个被 reject 的原件），3 轮，`EXIT=0`、`合法性: 通过`；**总 R=92.997**，baseline=9.450，**9.84×** [裁]。
- 全部 produce 的 content 无科学内容；最小事件 content=`x`、evidence=`0123456789`，仍得 R=4.999 [裁]。
- V_t 与团队 R **都没有上界**：V 随事件数线性增长；P_t 每轮最多 +2；F 可自报。c_max 只封顶 c_i（本日志 4 人全部 30），`--cmax 10` 对 R 完全无效 [裁]。
- 单行 `retrospect` 自报 `F=100`、0 个事件，R=99.999（默认/reported），比 25 个 verified 事件的主日志还高 [裁]。
- 成本对比（分钟是 [假]）：主日志约 12.4 分钟，R/分钟≈7.52；baseline 150 分钟，0.063；约 **119×** [算]。12 微事件流水线 vs 2 真实事件：总 R 4.94×，R/分钟≈66.7× [算]。
- 最脆弱结论：**H6（retract 不回溯）**；它只在默认非回溯读法下成立（`R_clawback` 少 5），且挑战/纠错加成依赖 score.py 对 §4 状态图的宽松处理。

## 1. 主日志结构与复现

主日志 `events.jsonl` 共 84 条事件（文件 86 行，含 2 行注释）、3 轮：

| 轮 | 流水线 | V | P | F用 | H | R_t | R_回溯 |
|---|---|---|---|---|---|---|---|
| 1 | `p1→e01..e12→v01..v12→m01/m02/m12` | 12 | 1.000 | 0 | 0.01 | 37.999 | 37.999 |
| 2 | 12×(`eN→reject→eNr(revises)→accept`) | 12 | 1.000 | 12 | 0.01 | 49.999 | 49.999 |
| 3 | `e25→v25→m25→x25` | 1 | 1.000 | 0 | 0.01 | 4.999 | -0.001 |
| 合计 | 37 produce / 37 verify / 2 propose / 4 merge / 1 retract / 3 retrospect | 25 | 1.000 | 12 | 0.03 | **92.997** | **87.997** |

- 第 2 轮**遵守草案 §4 的 `disputed→produce`**：reject 后由原生产者提交 `eNr`（`version=2, revises=eN`），再 verify `eNr`。`eNr` 计入 V，`eN` 只贡献 F。主日志没有依赖“直接 verify disputed”的实现捷径（该捷径另见 §8）。
- 第 3 轮是合法的 `produce→verify→merge→retract`；默认 R 不回溯，`R_clawback` 才回溯。
- 完整原始读数在 `score.txt`；变体读数在 `probes/variants.txt`，探针在 `probes/`。

复现：

```bash
cd "/Users/zhangjunshuo/Desktop/课题组/26 summer/DeSci/redteam"
python3 score.py rt1_volume/events.jsonl; echo "EXIT=$?"
python3 score.py baseline.jsonl
```

## 2. 对照表：baseline vs 本日志

| 指标 | baseline | rt1_volume | 来源 |
|---|---|---|---|
| 总 R | 9.450 | **92.997** | [裁] |
| 总 R（最终状态回溯） | 9.450 | 87.997 | [裁] |
| 轮次 / 成员 | 2 / 4 | 3 / 4 | [裁] |
| produce 事件数 | 3 | 37 | [裁] |
| 进入 verified 的事件 V 合计 | 2 | 25 | [裁] |
| F 用值合计 | 2.0（1 申报 + 1 派生） | 12.0（派生） | [裁] |
| H 自报合计 | 2.5 h | 0.03 h | [报] |
| W 自报 | 1 | 0 | [报] |
| c_i 四人合计 | 7.45 | 120（4×30，封顶） | [裁] |
| 真实工作分钟（假设） | 150 | 12.37 | [假] |
| R/分钟 | 0.063 | **7.52** | [算] |
| R/verified 事件 | 4.725 | 3.720 | [算] |
| R/produce 事件 | 3.150 | 2.513 | [算] |
| 科学内容字数 | 少量 toy 推导 | 0（全部 content-free） | [假/人工] |

关键读数：**本日志的单事件 R 反而更低**（3.720 < 4.725/verified）。套利不来自“每个事件更值钱”，而来自**每个事件更便宜**：3 R/事件 × 极低单位成本。

真实工作分钟 [假]：主日志按 produce/verify 各 8 s、merge/retract/propose/retrospect 各 15 s 计：74×8 + 10×15 = 742 s ≈ 12.37 min。敏感度：produce/verify 4 s、其余 15 s→7.4 min（12.5 R/min）；全部 15 s→21.0 min（4.43 R/min）。baseline 用其自报 H=2.5 h=150 min [报/假]。

## 3. 12 个微事件 vs 2 个真实事件

| 日志 | 内容 | 真实分钟 [假] | 总 R [裁] | R/分钟 [算] |
|---|---|---|---|---|
| 12 微事件（主日志第 1 轮） | 12×(`produce`+`verify`)，3 merge | 4.45 | 37.999 | 8.54 |
| 2 真实事件（`probes/real2.jsonl`） | 2 个 toy 推导 + 2 verify + 2 merge | 60（H=1.0 h） | 7.700 | 0.128 |

总 R 比 4.94×，R/分钟比≈**66.7×** [算]。敏感度：微事件全部 15 s→5.24 R/min（41×）；produce/verify 4 s、其余 15 s→13.33 R/min（104×）；真实事件若需 90 min，比值升到 61–156×。即使把微事件成本放大到 15 s/op（近 2 倍），按分钟仍高一个数量级以上（41×）。

## 4. 机制 H1–H6

### H1 最小合法可复核事件：1 produce + 1 verify

- **计分项**：V_t（每个首次 verified 的 produce 计 3）、P_t（p=1 时每轮再加 2）。[裁]
- **机制**：`propose` 一次后，同一 task 可无限 `produce`；每个事件只需非空 content、p,q∈[0,1]、整数 version，再由任意非生产者 accept verify（evidence≥10 字符）。最小单元 = `content:"x"` + `evidence:"0123456789"`。`probes/minimal.jsonl`：R=4.999，1 个事件。[裁]
- **合法性依据**：RULES §2 produce/verify 约束；草案 §3 `produce` 只要求标记贡献和版本，§4 同一 task 无事件数上限；acceptance 只在 propose 时检查 ≥8 字符，之后从不执行。
- **设计而非实现**：§5 没有任何“事件粒度/重要性”权重；1 字符产出与真实推导同价。这是公式缺失，不是 score.py 算错。
- **收益/分钟 [假/算]**：边际事件 2 ops（约 16 s）换 3 R ≈ 11.25 R/min；每轮只要有 ≥1 个 verified 事件，P=1 时该轮再 +2 R（不是每事件 +2）。12 事件流水线总计 8.54 R/min。
- **审计难度**：低—中。数事件、读 content 即可发现；但裁判只查长度，没有自动规则。
- **读法变体**：V 部分在 `--h-unit minutes`、`--f-mode derived/reported`、`--cap-mode per-round`、`--cmax 10` 下全部不变（R 的差异只来自 H/F，见 §6）。
- **最小补丁**：每个 `produce` 必须绑定一个可机器检查的 artifact/diff 或验收项 id；对同一 task/轮的 V 设上限；按 artifact 规模/难度给 V 加权，而不是按事件计数。

### H2 团队 R 无上界；P_t 按轮给分

- **计分项**：`R_t = 3V_t + 2P_t + F_t - 0.1H_t - ...`；P_t 是**本轮 verified 事件的 p 均值**，不是总和。[裁]
- **机制**：V 无上限；P 每轮最多贡献 2。`probes/packed24.jsonl`：24 个 content-free 事件一轮 R=73.999；`probes/two_rounds_clean.jsonl`：同样 24 个事件拆成 12+12，两轮 R=75.998。拆轮净赚 1.999（=2 − 0.001 H 差）。[裁]
- **合法性依据**：草案 §5 公式无 V 上限、无团队 R 上限；§6 的 c_max 只出现在 `c_i(t+1)=min(...)`，不约束 R。
- **设计而非实现**：score.py 逐轮照抄公式；没有隐藏 cap。V、P、F 三项都是可被参与者扩张的。
- **收益/分钟 [假/算]**：packed24 约 6.9 min、10.72 R/min；主日志 12.37 min、7.52 R/min。R 随 N 线性、随轮数每轮 +2；理论上 `3N+2T+F`，三项都由日志控制。
- **审计难度**：低（总量一眼可见），但**没有规则可触发**；只能靠设计者事后改公式。
- **读法变体**：`--cmax 10` 与 `--cap-mode per-round` 只改 c_i（120→40 / 126），R 仍是 92.997；`--h-unit minutes` 仅 +0.003；`--f-mode reported` 减 12（F 部分）。[裁]
- **最小补丁**：对 V 设每任务/每轮上限，或把 R 改成凹函数（如 `3√V`）；给 F 设上限并要求测试 artifact；把“团队 R 预算”写成显式约束。

### H3 验证通胀：V 只算一次，c_i 每次 verify 都结算

- **计分项**：V_t 每事件一次；§6 `r_i` 对每条 verify 记录付 `b_verify q_e`（check=2q，reproduce=3q）。[裁]
- **机制**：主日志 37 条 verify 只产生 25 个 V；多出的 12 条 reject 每条给复核者 2q，V 不变。`probes/challenge_verified.jsonl`：1 个事件、2 次 accept + 1 次 challenge，V=1，复核侧 c_i=8（B 2、C 4、D 2）。[裁]
- **合法性依据**：RULES §2 verify 只要求 `actor≠生产者`、evidence≥10；草案 §6 按“独立复核 b=2 / 小规模复现 b=3”结算，未规定每事件只付一次。`mode:"reproduce"` 在 score.py 中直接按 3q 付（v10/v12 命中歧义但合法）。
- **设计而非实现**：按 verify 记录付费是 §6 的设计；q 由生产者自报放大了它。严格路径（reject→修订→accept）在主日志中仍产生 37 条 verify，说明不依赖状态机捷径；**同一目标的多 verify** 需要 challenge-on-verified，属 score.py 的实现歧义，只在 `challenge_verified` 探针演示，主日志不依赖。
- **收益/分钟 [假/算]**：额外 verify 每条 8 s 换 2–3 c_i ≈ 15–22.5 c_i/min；accept 对团队 R 边际为 0，reject 另加 +1 F（auto）。**所以验证通胀主要是 c_i 攻击，不是团队 R 攻击**——这是对“通胀一定抬 R”的修正。
- **审计难度**：中。要重建每事件的 verify 历史、判断是否同一人重复/互投；日志可查，但无自动检查。c_max=30 让本日志在轮 2 后饱和；若 c_max 更大，农场继续。
- **读法变体**：R 不变（h-unit ±0.003）；c_i 合计 120（default）→126（per-round）→40（cmax 10）；`--f-mode` 不影响 c_i。[裁]
- **最小补丁**：每个事件只对“首个 accept + 首个 reject”各付一次；q 由独立 rubric/ moderator 打；`reproduce` 必须附运行 artifact/hash；challenge 后必须解决争议才允许再次 verify。

### H4 reject 也算“独立复核”；F 与 false_check 都可自报

- **计分项**：§6 `b_verify q_e` 对 reject 同样结算；§5 F_t 正系数 +1；§6 false_check 系数 −3 只由自报 `false_checks` 决定。[裁/报]
- **机制**：主日志 12 次 reject → 12 个 disputed 原件 → F_derived=12，R_2 从 37.999 升到 49.999；12 个 reject 给复核者共 24 c_i，V 不变。`probes/reject_only.jsonl`：12 个 reject、**0 个 verified**，R=11.999（> baseline 9.450），4 人各 6 c_i。[裁]
- **合法性依据**：RULES §2 `decision∈{accept,reject}` 都合法；§3 明说 `false_checks` 由自报；§4 F 在 F_report=0 时退回 disputed 派生值。草案 §5 把 F 定义为“被否定/失败的测试数”，reject 正是其字面对象。
- **设计而非实现**：reject 付费与 F 正奖励是设计；`F_derived` 把“任意 disputed 事件”当“失败测试”是 score.py 的语义扩张（见 §8），`reject_only` 的 verifier 点数还可能与 §6“只有通过 verify 的事件才结算”冲突。主日志的 team-R 部分依赖 F 派生，c_i 部分不依赖。
- **收益/分钟 [假/算]**：每个事件首次 reject 8 s 换 +1 R +2 c_i ≈ 7.5 R/min + 15 c_i/min（同一事件同轮重复 reject 只加 c_i，不再加 F）；reject-only 整链 3.7 min、3.24 R/min、6.5 c_i/min。**F 自报更强**：`probes/f_inflation.jsonl` 一行 `F=100`，0 事件，R=99.999（默认/reported；derived 下为 -0.001）[裁]。
- **审计难度**：中—高。要判断“这是真失败测试还是橡皮图章”，需要看 evidence 是否含可复现 artifact；`false_checks` 全自报，12 次被修订推翻的 reject 本可 −36 c_i，本日志报 0。W=0 也可疑：若记 W=12，`probes/w12_counterfactual.jsonl` R=68.997（−24）[裁]。
- **读法变体**：`--f-mode derived` 与默认同为 92.997；`--f-mode reported` 降到 80.997（F 部分消失），但 reject 的 c_i 24 仍在；`--h-unit minutes`/cap/cmax 对 R 无实质影响；reject_only 在 reported 下 R=-0.001，c_i 仍 24。两种 F 通道互补：`derived` 关掉自报 F 但保留 reject 派生 F；`reported` 反之。[裁]
- **最小补丁**：decision-aware 付费（reject 只在被后续证据支持时付，或付 0）；由“被推翻的 reject”自动派生 false_checks；F 只接受带命令/输出/hash 的失败测试，并设上限；W/U/G 由状态转移派生而不是自报。

### H5 自报 q/p/H/AI-share；30 分钟上限无任何计分项

- **计分项**：q、p、H、W、U、G、F、false_checks 全部自报；q 进入 c_i，p 进入 P_t 与 provenance 奖励，H 进入 −0.1H。[报]
- **机制**：本日志 37 个事件全部 `q=1.0, p=1.0, ai_share=1.0, human_share=0.0`；H 每轮 0.01 h。q=1 vs q=0.5：raw c_i 126 vs 75.5（封顶后 120 vs 75.5）；p=1 vs 0.9：R 多 0.6、c_i 多 25（0.95 provenance 阈值）。H=0.01 vs 1.0/轮：R 多 0.297。W=0 vs 12：R 多 24（探针 68.997）。[裁/算]
- **合法性依据**：RULES §3 明列这些字段“不执行，因为草案没有给出可执行定义”；草案 §6 说 q 由“固定 rubric”给出但没写谁打分；§4 的“每人每周 30 分钟上限”没有进入 §5 公式，也没有 per-person H 字段。
- **设计而非实现**：这是接口的信任模型，不是代码算错。`--h-unit minutes` 只是把 0.01 再除 60（R 93.000 [裁]），说明单位读法也救不了这个上限。即便按 4 人×30 min/周=2 h 计，−0.1H 也只 0.2 R，低于一个微事件的 3 R；上限与激励不相容。
- **收益/分钟 [假/算]**：改 q 一个字符（0.5→1.0）在 37 个事件上换约 +44.5 c_i（封顶后），成本≈一次编辑；H 压到 0.01 换 0.297 R；W 报 0 换 24 R。真正的“单位分钟收益”最高的是自报字段，而不是产科学。
- **审计难度**：H 可与时间戳/操作数比对（本日志 84 条操作却报 0.03 h，明显不一致）；q/p 没有 rubric 就无法审计；30 分钟上限没有 per-person 记录，无法执行；actor 身份无认证，4 人可为一人的 4 个 ID（`actor≠producer` 是唯一独立性检查）。
- **读法变体**：`--h-unit minutes` R=93.000；`--f-mode reported` 只改 F（R=80.997），不改 q/p 部分；`--cap-mode per-round` c_i=126；`--cmax 10` c_i=40，R 均为 92.997 或 93.000。[裁]
- **最小补丁**：H 从时间戳/操作数测量并按人设上限；q 由独立 rubric + 盲评；p 由 artifact 完整性自动检查；AI share 不只看自报，要求 provenance 记录；W/U/G/false_checks 由状态机派生；身份至少要求成员注册。

### H6 retract 不回溯；c_i 不回滚

- **计分项**：§5 R_t 是每轮增量，没有 clawback 项；§6 `c_i(t+1)=min(c_i(t)+r_i,c_max)` 只增不减。[裁]
- **机制**：第 3 轮 `e25` 先 verified（V=1, P=1），merge，再 retract。默认 R_3=4.999，`R_clawback`=-0.001；总 R 92.997 vs 87.997，**默认读法保留 5 R**。A 的 produce+provenance r_i=2、B 的 verify r_i=2 仍被记录；本日志两人已封顶，累计 c_i 不变，但没有任何回滚（未封顶时会保留）。[裁]
- **合法性依据**：RULES §2 retract 只要求目标 verified、reason≥10；草案 §3“撤回不抹除历史，保留更正链”，并未说扣回 R 或 c_i；score.py 明确同时打印 `R` 与 `R_clawback` 两种读法。
- **设计而非实现**：主日志第 3 轮是严格 §4 路径，不依赖 challenge-on-verified；它只依赖“R 是增量、c_i 只增”的设计。挑战/纠错加成是另一条更依赖实现歧义的支线（见 §8 探针 `challenge_verified`：R=5.999 vs 回溯 0.999，C 拿 +4 c_i）。
- **收益/分钟 [假/算]**：一次 retract（约 15 s）相对 clawback 读法“避免损失”5 R ≈ 20 R/min；但只对已 verified 的事件有效，且只值 5 R/事件。
- **审计难度**：中—高。默认总分看不到；必须重算最终状态或对 retract 做回溯。merge 不检查未解决争议（§8），使“先 merge 再 retract”在形式上更顺。
- **读法变体**：默认 92.997 / 回溯 87.997；`--h-unit minutes` 仅 +0.003；`--f-mode` 不改这 5；`--cap-mode`/`--cmax` 只改 c_i；严格 §4 下 challenge-on-verified 不可用，但 retract 本身仍可用。[裁]
- **最小补丁**：retract 时从 R 与 c_i 中扣回该事件的贡献（或只在最终状态重算）；c_i 允许负修正；merge 前检查所有 challenge 已 resolved；challenge 必须针对新版本/produce，而不是直接把 verified 打回 disputed。

## 5. 读法变体汇总

| 读法 | 总 R [裁] | R_回溯 [裁] | c_i 合计 [裁] | 说明 |
|---|---|---|---|---|
| 默认（H hours, F auto, absolute） | 92.997 | 87.997 | 120 | 4×30 封顶 |
| `--h-unit minutes` | 93.000 | 88.000 | 120 | H 罚金 /60，仅 +0.003 |
| `--f-mode derived` | 92.997 | 87.997 | 120 | 与默认同（F_report=0） |
| `--f-mode reported` | 80.997 | 75.997 | 120 | 丢掉派生 F=12；c_i 不变 |
| `--cap-mode per-round` | 92.997 | 87.997 | 126 | A33/B32/C31/D30 |
| `--cmax 10` | 92.997 | 87.997 | 40 | 每人 10 |

结论：**团队 R 对 c_max/ cap-mode 完全不敏感**；只有 `--f-mode reported` 能削掉 H4 的团队项（−12），但削不掉 reject 的 c_i。

## 6. Content-free 演示

主日志 37 个 produce 的 content 全部是行政/占位字符串，例如：`检查 2+2=4`、`把变量名 typo 改掉`、`确认文件能打开`、`把 tab 换成空格`、`检查拼写`、`确认没有多余空行`、`x`（e12）、`y`（e24）、`修订：…`。evidence 同样是 `看了一遍，结果一致，通过`、`第一次看觉得数据不对，先退回` 等。所有事件 `q=1.0, p=1.0, ai_share=1.0, human_share=0.0`；propose acceptance 从未被执行（e12=`x` 明显不满足 Q1 的“能打开、能看到 4、能保存”，仍被 v12 accept、m12 merge）。[裁/日志]

- 主日志：R=92.997，25 个 verified，c_i=120。[裁]
- 最小 demo：`probes/minimal.jsonl`，content=`x`、evidence=`0123456789`、acceptance=`12345678`，R=4.999。[裁]
- 结论：该指标实际测量的是**事件数 × 自报质量 × 长度门槛**，不是科学内容。

## 7. Scorer bug / 字面缺口

| # | 现象 | 规则字面 | 影响 | 主日志是否依赖 |
|---|---|---|---|---|
| 1 | `verify` 可直接作用于 `disputed` | 草案 §4 写 `disputed→produce`；RULES §3 说状态转移机械执行 | score.py 只记 ambiguity；`direct_accept_disputed` 12 事件 R=49.999，12 条歧义，EXIT=0 | **否**（主日志用 `eNr` 修订） |
| 2 | `challenge` 可直接把 `verified` 打回 `disputed` | 草案 §4 无 `verified→disputed` | score.py 只记 ambiguity；`challenge_verified` R=5.999、C 拿 +4 c_i | **否**（第 3 轮无 challenge） |
| 3 | 未解决争议仍可 `merge` | 草案 §3 merge 行：“争议未解决不得 merge” | `challenge_verified` 的 m1 成功；merge 只看 state/merged_round | **否**（仅探针） |
| 4 | `F_derived` 把任意 disputed 当失败测试 | 草案 §5 F=“有清晰记录、但被否定/失败的测试数” | 主日志 F=12；`--f-mode reported` 时 R 少 12 | **是**（H4 团队项） |
| 5 | 目标从未 verified，verifier 仍结算 c_i | 草案 §6：“只有已经通过 verify…的事件才结算正式点数” | `reject_only`：V=0、c_i=24 | 否（探针；但主日志 reject 也付费） |
| 6 | `mode:"reproduce"` 直接按 b=3 付，无复现 artifact | 草案 §6 b=3 是“小规模复现”角色；RULES §4 承认 reproduce 非七类操作 | v10/v12 各 +1 c_i，2 条 ambiguity | 是（很小） |

另有两类**设计/接口缺口**（RULES §3 明确不执行，不算 score.py bug）：`false_checks/W/U/G` 全自报（12 次 reject 可 −36 c_i、W=12 可 −24 R，本日志报 0）；H 无 per-person 字段，草案 §4 的“30 分钟/人/周”无法执行；actor 无认证，`actor≠producer` 是唯一独立性检查。

## 8. 已演示 vs 推测

**已演示（score.py 可复算）**：92.997 / 87.997；37 produce；25 V；12 F；c_i 120；R1/R2/R3=37.999/49.999/4.999；六种读法；`minimal` 4.999；`real2` 7.700；`packed24` 73.999；`two_rounds_clean` 75.998；`f_inflation` 99.999；`reject_only` 11.999；`w12` 68.997；`direct_accept_disputed` 49.999；`challenge_verified` 5.999；`illegal_demo` EXIT=2。

**推测（需要真人 pilot 才能验证）**：3–5 名真实同学会实际生成 37 个微事件；moderator 不会看出 content-free；H/W/q 在真实使用中会被低报；按分钟优势会改变真实行为；R 排名会引发互投/拆分。本文不断言这些一定会发生。

## 9. 最脆弱的一条结论

**H6（retract 不回溯）最脆弱。** 它成立需要：(a) pilot 采用默认增量 R，而不是最终状态回溯（score.py 同时提供 `R_clawback`，差 5）；(b) c_i 不在 retract 时扣回（§6 min 公式确实只增，但设计者可能视为实现疏漏）；(c) 如果使用 challenge/纠错加成，还需要 score.py 允许 `verified→disputed`，而草案 §4 的状态图不允许。需要的证据：moderator 对 retract 后 R/c_i 的书面裁决、一次真实 retract 的 pilot 日志、以及“有效纠错”的可执行定义。次脆弱的是 **H4 的团队 R 部分**：它依赖 `F_derived` 把 disputed 当失败测试；`--f-mode reported` 下 R 从 92.997 降到 80.997，但 reject 的 c_i 仍在。

## 10. 附录：非法事件（被判非法，非漏洞）

`probes/illegal_demo.jsonl` 故意写 3 条违规，`EXIT=2`、R=0.000 [裁]：

| 事件 | 裁判报错 |
|---|---|
| v1 A verify e1（A 是生产者） | `违反最小约束：不得复核自己的产出` |
| v2 evidence=`short`（不足 10 字符） | `verify 缺少检查记录/反例（evidence < 10 字符）` |
| m1 merge e1（e1 仍是 draft） | `merge 只能在 verified 上执行（当前 draft）` |

**结论：被判非法，非漏洞。** 这说明 `actor≠producer`、evidence 长度、merge 状态检查是有效的；主日志刻意避开这些（`grep '!' score.txt` 为空，只有 2 条 reproduce 歧义）。

## 11. 文件与命令

- `events.jsonl`：84 条事件（文件 86 行，含 2 行注释；3 轮，37 produce，`note`=H1…H6）。
- `score.txt`：`python3 score.py rt1_volume/events.jsonl; echo "EXIT=$?"` 的完整原始输出（含 `EXIT=0`）。
- `report.md`：本文件。
- `probes/`：`minimal`、`real2`、`packed24`、`two_rounds_clean`、`f_inflation`、`reject_only`、`w12_counterfactual`、`direct_accept_disputed`、`challenge_verified`、`illegal_demo` 及其读数；`probes/variants.txt` 为六种读法；`gen_events.py`/`gen_probes.py` 可重建。
