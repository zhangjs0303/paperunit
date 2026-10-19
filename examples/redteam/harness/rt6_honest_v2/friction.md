# friction.md —— v0.2 诚实 pilot 的真实摩擦清单

**日志**：`events.jsonl`（36 事件 / 4 轮 / 3 任务；3 次真实 reject、3 次真返工、1 次真撤回）
**裁判**：`score_v2.py` sha256 `2fe75ade…0e07`；`RULES_v0.2.md` sha256 `c321ff21…ae35`（含 12:25 加入的 v0.2.1 试验级口径）
**读数**：逐轮 10.500 / 10.000；试验级 6.000 / 5.500；个体 A .500/.417、B .167/.167、C .167/.083、D .167/.167
**口径说明**：本 pilot 由 AI 单人串演 A–D，没有真人计时。下文的"字符/步骤"是**可复算的实测值**，"分钟"是按 25 字/分 + 1 min/机械步骤换算的**估计**，已标注。

## 汇总表

| # | op | 实测额外成本 | 是否改变行为 | 最小修补 |
|---|---|---|---|---|
| F1 | propose | 6 条 test 共 662 字；权重先于难度冻结；1 次措辞歧义 → 1 个 reject 轮次 | 会：逼我们写宽标准 | test 拆成结构化 `metric/comparator/scale` |
| F2 | produce(prediction) | 推导只需 104+45 字自由文本，无 hash/cmd/rerun | 会：动机从"给证据"变成"写信" | `prediction` 必填 `proof_artifact{hash}` |
| F3 | merge | 7 次 × 95–134 字 = 794 字（下限 280），其中 1 次白写 | 会：能推就推给别人 | 三栏结构化 `assumption/evidence/limit` |
| F4 | propose/merge | 个体贡献 0；A 拿 final 的 50%，C 仅 8.3% | 会：理性选择只当 checker | `merge_share`=0.1×w，`propose_credit` 每 task 一次 |
| F5 | retrospect | 记录 ≈157 min vs 任务 150 min；H 已移出目标函数 | 会：系统看不见就不报 | `retrospect.minutes` 必填，只进诊断 |
| F6 | challenge | 176 字，0 分，且有效 challenge 让团队 −0.5 | 会：真实团队不会写 | 有条件小额结算：触发 retract/新版才给 0.1×w |
| F7 | abstain | 机械非法：EXIT=2，两条 violation | 会：不确定性被逼成 reject | `verify.decision` 加 `abstain`（不计 F̃） |
| F8 | （流程） | pilot 期间 `score_v2.py` 18→21 KB、RULES 7.0→8.3 KB | 会：数字对不上是必然 | 输出首行打印裁判 sha256 |

## F1 预注册标准的成本（propose）

- **发生在**：`propose`（3 次）。`Σw=1` 是硬约束，`test ≥10 字`，标准一旦提出不可修改。
- **额外成本**：6 条 criterion 的 `test` 合计 662 字（最短 66、最长 165）；权重必须在**看到难度之前**分配（Q1 我给了 c1 0.55 / c2 0.45）。事后看完全反了：c1 含一次真实返工（转置 bug），c2 只是两段字符串。
- **真实代价**：Q3/c1 的 `test` 我写的是"绝对误差 max|dpi|_inf < 1e-13"，C 实现时读成 `math.isclose(rel_tol=1e-13)` → 一个完整 reject 轮次（produce+verify+返工≈15 min）。标准没错，错的是**冻结的自由文本可以被两种合理读法解释，而解释权在事后**。
- **是否改变行为**：会。我因此在 Q3/c2 里做了**防御性预注册**：把锐利预测 P1（k*=3）降级为 exploratory，只把稳健的 P2 当验收条件（见 `artifacts/prereg_q3_predictions.txt`）。若标准可改，我会先测再定。
- **最小修补**：把 `test` 里的判据拆成 `{"metric":"max|dpi|_inf","comparator":"<","value":1e-13,"scale":"abs"}`；自由文本只留说明。`scale` 一栏就能消掉这次的整次返工。

## F2 推导类工作没有 hash/cmd，会被迫变成什么形态？

- **发生在**：`produce`（Q2/c1，`kind=prediction`）。T2 的核心是 3 行闭式导数 `dP/dW = C·B/(A+C+B)² > 0`。
- **形态**：它唯一的合法容器是 `prediction` + `threshold` 两个自由字符串（我写了 104 + 45 字）。`prediction` 不要求 `hash`/`cmd`，`verify` 对 prediction **不要求 `rerun`**。所以整条 T2/c1 链条上没有任何可寻址对象。
- **会不会被挤出积分**：不会，反而**更容易结算**。对比成本：T1/c1（w=0.55）需要脚本 + sha256 + 独立复跑；T2/c1（w=0.6，全日志最难的推导）只需要两段散文。被挤出的不是推导，是**证据**——证明过程只活在 `verify.evidence`（195 字）和 `merge.own_words`（114 字）里，裁判器不读。
- **反向激励**：真正让 T2 站住的是 A 自选写的 `t2_checker.py`（6 点枚举 + 中心差分），但它对团队分**贡献为 0**（团队分只看 criterion 是否 merge），对 A 的个体分与"只读文字就 accept"完全相同。所以诚实的边际收益为零。
- **是否改变行为**：会。作为 D，我的真实动机是"把推导写成一段能过 merge 的文字"，而不是"留下可复跑证据"。
- **最小修补**：`prediction` 增加必填 `proof_artifact: {hash, path}`（裁判器不验证数学，只强制"证明有可寻址对象"）；或新增 `kind:"proof"`，与 `rerun` 同等地要求 hash。

## F3 每个 merge 的 `own_words ≥ 40` × 结算数量

- **发生在**：`merge`（7 次 = 6 次结算 + 1 次重做被忽略）。实测 95–134 字/次，合计 **794 字**（schema 下限 7×40=280，实际 2.8 倍）。
- **累计成本**：每次 merge 要读 artifact + 读 checker evidence + 用自己的话写假设/证据/局限，估 4–5 min → 7 次 ≈ **30 min**；其中 m7 完全白写（裁判器不结算，还记一条"规则歧义"）。
- **是否改变行为**：会。因为 merge 不计个体贡献（F4），理性成员会把它推给别人。日志里 B 做 3 次、C 做 4 次，**A 一次都没做**（A 只检查）。
- **最小修补**：改成三栏结构化 `{"assumption":≥12,"evidence":≥12,"limit":≥12}`，总量不低于现在但可机检、可复用 producer 草稿；merger 只需 accept 或改一栏。

## F4 propose 与 merge 不计个体贡献：谁愿意做？

- **实测个体分（final）**：A 0.417（只 produce Q1 + 检查 6 个 criterion）；B 0.167（propose Q2 + merge 3 次 + challenge 1 次，全部 0）；C 0.083（produce Q3 + merge 4 次 + 撤回，merge 部分 0）；D 0.167（produce Q2 + propose Q3，propose 部分 0）。
- **A 一个人拿走 final 的 50%**；只做 checker 也能拿 4/6 criterion 的检查份额 ≈ 0.333，高于任何 producer 的 0.167。
- **free-riding 风险**：已实现。理性策略是"不 propose、不 produce、只 accept"——A 就是这条路径的样本，且全日志唯一"全 accept 也能拿同样分"的结构意味着**严格检查与放水检查的个体回报完全相同**（A 的 v5/v7 是 reject，v4/v6/v8/v9 是 accept，个体分一样）。
- **是否改变行为**：会。C 在 R4 的真实想法（写进了 retrospect 的动机）是"下次我不想当 producer"。
- **最小修补**：`merge_share = 0.1·w_c/|T|`（从 producer 的 0.5 里扣）+ 每 task 一次性 `propose_credit = 0.05`。两者都是幂等的（每个 artifact/task 只结算一次），总额仍被 criterion 权重封顶，开不了刷分口子。

## F5 记录耗时是否可能超过 §8 的 10–15% 停止条件？

- **实测部分**：自由文本 3317 字（`own_words 794 + verify evidence 1419 + tests 662 + challenge 176 + retrospect 266`），另有 4 条 prediction 字符串 447 字；机械步骤 24 个（7 个 artifact 脚本 + 9 个 checker 输出文件的 sha256、8 次脚本运行）。
- **换算（估计，非实测）**：24 步 ×1 min + 3317 字 ÷25 字/分 ≈ **157 min**；任务本体（3 个 toy：建 solver + 修 bug + 推导 + 反例搜索 + stiff sweep，各含一次返工）估计 150 min → **记录/任务 ≈ 105%**。乐观口径（40 字/分）也有 71%。
- **最低合规口径**：只写 schema 下限（merge 7×40 + verify 10×20 + challenge 40 + tests 60 + reason 10 ≈ 590 字）+ 24 步 ≈ **48 min**。要让这 48 min 落在 15% 以内，任务总时长必须 ≥320 min。
- **关键**：v0.2 改动 #5 把 `H` 移出目标函数，`retrospect` 里的数字字段被显式忽略（写了会记 ambiguity）。所以 §8 的停止条件在新系统里**不可测量**——我 4 条 retrospect 写了 6/5/—/9 分钟，裁判器一个都不读。
- **是否改变行为**：会，"看不见所以不报"。若 `minutes` 是必填且进诊断，我在 R3 就会报告"这一轮记录时间是任务的 2 倍"并触发暂停。
- **最小修补**：`retrospect` 必填 `minutes`（只进诊断、不加分）+ 输出 `recorded_minutes/estimated_task_minutes`，专门给 §8 用。

## F6 challenge 不计分，还有动力提反对意见吗？

- **实测**：ch1 写了 176 字（claim 89 + evidence 87），个体贡献 **0**，团队分**一分不变**（`grep -v challenge_e9` 后读数完全相同：10.500/10.000、6.000/5.500）。
- **更糟**：唯一"有效"的 challenge 路径是逼出 retract，而 retract 让 trial final 从 6.000 掉到 **5.500**。也就是"提对了反对意见"的净效果是团队 −0.5，谁提谁背锅。
- **结构问题**：想记录"第二个复核者同意"必须先 challenge——连续两个 accept 的第二个**直接非法**（实测 `verify 不能在状态 verified 上执行`）；而 challenge 退回 disputed 后第二个 accept 合法，两位 checker 平分 0.5：团队分不变，个人份额反而减半（A 0.500→0.450）。
- **是否改变行为**：会。ch1 是"知道不得分、但这是 pilot 且有报告要求"才写的；真实团队里我不会花这 10 分钟。
- **最小修补**：challenge 有条件小额结算——仅当 target 之后被 retract 或产生新版本时，给挑战者 `0.1·w_c/|T|`（从原生产者份额扣），每 artifact 最多 1 次。幂等 + 有条件，开不了 challenge farm。

## F7 `abstain` 在 v0.2 里有没有位置？

- **机械证据**：`diagnostics/abstain_probe.jsonl` → **EXIT=2**，两条非法：
  - `未知 op 'abstain'（允许: propose/produce/verify/challenge/merge/retract/retrospect）`
  - `verify.decision 必须是 accept/reject`
- 所以 v0 草案 §3 的"abstain 是任何操作的合法退出动作"在 v0.2 里**没有实现**，且 §0 的 8 条改动没有一条提到删除它。
- **唯一形态是沉默**，而沉默与"根本没检查"在日志上不可区分；更糟的是 checker 只有 accept/reject 两个按钮，而 reject 给团队 **+0.5 F̃**——不确定性被制度性地转换成**付费的否定**。
- **是否改变行为**：会。v7 那次我确实不确定（v1 的 PASS 结论巧合成立，只是判据口径不符）；若有 abstain 我会写 abstain，而不是用"判据不符"去否定别人的产出换 0.5。
- **最小修补**：`verify.decision` 加 `abstain`（不计 F̃、不改状态、需 ≥20 字理由），诊断加 `n_abstain`。abstain 不产生 credit，开不了刷分口子。

## F8（额外，真实遇到）冻结裁判在 pilot 期间变了

- 12:20 我读到的 `score_v2.py` 是 19452 B、`RULES_v0.2.md` 是 6978 B；12:26 再跑时变成 21511 B / 8310 B，多出 v0.2.1 试验级口径。
- 同一份日志：旧口径 10.500/10.000，新口径额外给 6.000/5.500。改动方向是对的（逐轮 P̃/F̃ 会被轮数刷），但"冻结裁判"没真冻结，Lead 复跑时"数字对不上"是必然。
- **最小修补**：输出第一行打印 `score_v2.py` 的 sha256 与规则版本号。
