# 红队路线 4：测量层与执法层

**状态**：离线纸面模拟；toy 内容；不涉及真人、真钱、真数据、未发表课题。  
**日志**：`rt4_enforcement/events.jsonl`（5 轮、6 个 produce、4 名成员 A/B/C/D）。  
**裁判**：`../score.py`（冻结，只读，未改）；`EXIT=0`，含「合法性: 通过」。  
**一句话**：这份日志的 R 可以是 12.00、16.00 或 24.85，c_A 可以是 10.00 或 15.20；惩罚项可以是 0，也可以是 −59。**奖励数值不是良定义的，惩罚强度取决于未写明的审计能力。**

## 0. 结论（先给数字）

1. **读法**：同一份合法日志，8 种官方参数组合下总 R ∈ [12.00, 24.85]（2.07×），c_A ∈ [10.00, 15.20]（1.52×）。读法差 12.85 > honest baseline 9.45（不同日志，仅作量级对照）。
2. **自报**：5 轮 `U=G=W=0`、`false_checks` 不填；但日志有 4 份实质重复提交、6 次 A↔B 互审、2 次 retract。按窄/中/宽审计口径，罚分可以是 0 / −20 / −37 / −59，总 R 从 +16 到 −43。
3. **Ratchet**：e1、e2 先 verified 后 retracted；默认总 R=16.00，`R(最终状态回溯)=8.00`，**8 分（50%）存活**；A/B 有 13/28.2 的 c_i 与撤回事件绑定，未扣回。
4. **俘获**：6 次 accept verify（v1–v6）全部是 A↔B 跨对，全部合法；v7 是 A 对 D 的 reject。固定轮换可预谋，随机轮换在 n=4,T=4 下仍有 80.2% 概率至少一次跨对。扮演 moderator 的 C 两次 merge 得 0 分，只有 challenge 得 4 分——merge 权与计分权错位。
5. **δ\***：默认读法下不存在 δ\*（retract 不扣分，E≥0）；审计读法下，a=1, g=5 时，只 clawback（κ=0）需 δ\*=1.00，加 U=5（κ=5）需 0.50，加 U=5 与另 5 分（κ=10）需 0.333。**10% 抽查远低于 δ\***。
6. **一条规则**：若只能加一条，选「proof-carrying default-distrust + final-state recompute」：所有计分事实必须由裁判从原始工件派生，不能派生按最不利值计，分数在最终状态回溯重算。它同时打击 H1/H2/H3/H6，并提高 H4 的攻击成本。

## 1. 交付与复现

- `events.jsonl`：合法攻击日志，5 轮，含要求的 (a) ratchet、(b) U/G/W=0 且 false_checks 不填、(c) A↔B 互审对。
- `score.txt`：`python3 score.py rt4_enforcement/events.jsonl` 的完整原始输出（55 行，`EXIT=0`）。
- `readings.md`：8 种读法的完整命令、R/c_i 矩阵与逐项解释。
- `report.md`：本文；`score.py`、`baseline.jsonl`、`RULES_v0.md` 均未修改；没有写 `rt4_enforcement/` 以外的文件。

## 2. 攻击日志结构

| 轮 | 事件 | 作用 |
|---|---|---|
| 1 | p1, e1(A), v1(B accept), m1(C merge), r1(H=30) | e1 先落袋；H=30 制造单位歧义 |
| 2 | p2, e2(B), v2(A accept), e3(A), v3(B accept), e4(B revises e2), v4(A accept), e5(A), v5(B accept), m2(C merge), r2(H=30) | A↔B 互审对；4 份实质重复提交；G 自报 0 |
| 3 | x1(A retract e1), c1(C challenge e2), v6(A accept e2), r3(H=30, F=5) | ratchet；challenge 后再 verify；F 自报灌水 |
| 4 | x2(B retract e2), r4(H=0) | e2 撤回但 R2 的 3V 不回溯；H 填 0 |
| 5 | p3, e6(D), v7(A reject), r5(H=0, F=0) | 被拒绝的提交仍得 F_derived=1；reject 仍给 verifier 0.2 |

**默认读数**（C1）：`R1..R5 = 2, 11, 2, 0, 1`，总 R=16.00，clawback=8.00；`c=(A 15.20, B 13.00, C 4.00, D 0.00)`。  
**歧义命中 8 条**（`reproduce`、对 verified 的 `challenge`、对 disputed 的 `verify`）是 ambiguity 提示，不是 violation；`EXIT=0` 证明没有机械违规。

## 3. 机制 H1–H6

### H1 自报惩罚项：U/G/W 填 0、false_checks 不填、F 反向奖励

- **机制**：R 的 `−2W−5U−5G` 与 c_i 的 `−3 false_check` 全部来自 `retrospect` 自报；F 也是自报的正项。日志 5 轮全部 `W=U=G=0`，`false_checks` 完全不出现；但日志里有 4 份实质重复提交（e2 为原始，e3/e4/e5 为 3 份多余）、6 次 A↔B 互审、2 次 retract（e1/e2）、1 次被 reject 的提交（e6）。按草案口径，G 至少 3（多余重复提交），U 至少 1（e1 被 merge 后撤回），W 至少 0–2（两次可避免错误导致的返工）。
- **合法性依据**：RULES §2 `retrospect` 只要求 H/W/U/G/F 非负；`false_checks` 可选；§3 明说这些字段不执行。score.py 只检查非负，不交叉核验。全部 `EXIT=0`。
- **已演示**：默认总 R=16.00。若审计者按窄口径 U=1,G=3,W=0 计罚，R=−4；中口径 U=1,G=6,W=1 → −21；宽口径 U=2,G=9,W=2 → −43。**同一个日志，罚分从 0 到 −59，R 从 +16 到 −43**；差别不是统计噪声，是审计口径。F 另有两个反转：第 3 轮自报 F=5、派生 F=1；第 5 轮自报 F=0、派生 F=1。`auto` 在 F_report=0 时退回派生值，等于**奖励不填 F**（报 0 得 +1，报 0.5 只得 +0.5）。
- **可检测性（δ 假设）**：δ = 独立审计者实际抽查并认定一个 gaming 事件的概率。当前 δ=0（无审计，moderator 是玩家）。若 δ=0.2、每个 G 罚 5，则期望罚分 = 0.2×5×G；G=3 时期望 −3，仍小于该轮 V/P 的增益；按 H3 的 δ\*，κ=5 时需要 δ≥0.5。δ 是假设，不是测量。
- **读法敏感性**：U/G/W 不进入任何 flag，8 种读法下只要自报 0 就恒为 0——这个攻击对读法**免疫**。F 是例外：总 R 在 12.00–16.00 之间随 f-mode 变；`reported` 15.00、`derived` 12.00、`auto` 16.00。
- **最小补丁**：U/G/W 尽量机器派生：重复提交用内容 hash/相似度；互抬用 who-verifies-whom 图；W 用 retract/revise 链；false_check 用「accept 后又被 retract」的 verifier 记录，给一次申辩窗口；F 只接受带失败日志/反例 ID 的条目，且 `F_used = min(F_report, F_derived_with_evidence)`，不给裸 reject 发 +1；不可派生字段默认按最不利值计，而不是 0。

| 口径（假设，不是裁判输出） | U | G | W | 罚分 −5U−5G−2W | 总 R |
|---|---:|---:|---:|---:|---:|
| 自报（日志） | 0 | 0 | 0 | 0 | **+16** |
| 窄（只数重复提交） | 1 | 3 | 0 | −20 | −4 |
| 中（重复+互抬） | 1 | 6 | 1 | −37 | −21 |
| 宽（重复+全部互审） | 2 | 9 | 2 | −59 | −43 |

计数口径（都是假设）：G 窄=3（多余重复提交），中=6（3 重复+3 次互审），宽=9（3 重复+6 次互审）；U 窄=1（e1），宽=2（e1+e3）；W 窄=0，中=1，宽=2。

**自报字段的边际效应**（用 `sed` 变体 + 冻结裁判复核，非主日志）：

| 变体 | 总 R | c_A | c_B | c_C |
|---|---:|---:|---:|---:|
| 主日志（q=1.0, p=1.0, 全 reproduce） | 16.00 | 15.20 | 13.00 | 4.00 |
| q: 1.0→0.6 | 16.00 | 10.40 | 8.60 | 4.00 |
| p: 1.0→0.5 | 14.00 | 12.20 | 11.00 | 4.00 |
| mode: reproduce→check | 16.00 | 12.20 | 10.00 | 4.00 |

q 由生产者申报却决定 verifier 的得分；p 由生产者申报并在 0.95 处触发 +1 provenance；mode 由 verifier 申报，`reproduce` 比 `check` 多 50%。三者都无审计。

### H2 H_t 单位与聚合层级

- **机制**：R 用 `−0.1 H_t`，但 H_t 只写「记录和协调耗时」，没有单位、没有聚合层级（个人 vs 团队）。日志第 1–3 轮填 H=30：hours 下 `−3.00/轮`，minutes 下 `−0.05/轮`；罚项正好 **60×**。总 R 16.00 vs 24.85；clawback 8.00 vs 16.85。
- **合法性依据**：`retrospect.H` 是非负数字；RULES 只给 `--h-unit hours|minutes`；score.py `h = H/60 if minutes else H`。两种读法都是官方参数，没有非法事件。
- **已演示**：8.85 的总 R 差；C2 的 R1 4.95 vs C1 2.00，R2 13.95 vs 11.00，R3 4.95 vs 2.00。第 4/5 轮 H=0，不差。**对照**：若把 H 全部填 0，总 R=25.00（C1），H 单位歧义消失；我们故意保留 H=30，是为了让 60× 的读法差可见，而不是把分数刷到最高。
- **可检测性（δ 假设）**：spec ambiguity，不是 hidden action；文档审计 δ=1 能发现「没写单位」，但没有 canonical unit 可对照，所以「填错单位」δ=0。若协议固定 minutes，则 H>30/周 可机械检测（δ=1）；当前没有这个检查。
- **读法敏感性**：8.85，本日志最大单一摆动。它还把「诚实 retract」变成有成本：如果第 4 轮填 H=30，hours 下 R4=−3.00，minutes 下 −0.05；我们的 r4 填 0，所以撤回轮免费。**同一份日志可以选择填不填 H，进一步放大读法差。**
- **最小补丁**：schema 加 `H_unit`（强制 minutes），读取时归一化并拒绝缺失单位；用时间戳/计时器代替自报；固定 `w_H = 0.1/60 ≈ 0.001667` 每分钟；明确 H 是个人还是团队总和（建议团队总和，个人分列）；把 30 分钟/周上限做成硬校验。

### H3 Ratchet / 不回溯

- **机制**：`V_t` 在首次 verify 的轮次结算；`retract` 只改状态，不重算 R_t，也不重算 c_i。默认总 R=16.00，`R_clawback`=8.00；e1（R1 verified, R3 retracted）贡献 5.00（3V+2P），e2（R2 verified, R4 retracted）贡献 3.00 V（P 因 e3/e4/e5 仍为 1.0 而保留）；合计 8.00（50%）存活。c_i 侧，A 的 8 分和 B 的 5 分（共 13/28.2=46%）来自最终被撤回的 e1/e2，未被 clawback；C 的 4 分是 challenge+correct，属有效纠错，另算。
- **合法性依据**：retract 是七类操作之一；merge 后仍可 retract（state 仍是 verified）；`V_t` 字面是「本轮首次进入 verified」，c_i 字面是「已通过 verify 的事件结算」——两者在 verify 时都满足。草案说「撤回不抹除历史」，没说「撤回不抹除奖励」。score.py 算了 `R_clawback` 但官方 `total_R` 不用它；c_i 完全没有 clawback 版本。
- **已演示**：总 R 16.00 vs 8.00；R1 2.00 vs −3.00；R2 11.00 vs 8.00。e4 显式 `revises: e2`，e2 撤回后 e4 仍是 verified，继续保留 B 的 2 分 produce 和 A 的 3 分 verify——**retract 不沿更正链传播**。
- **可检测性（δ 假设）**：δ = P(坏事件在 verify 后被发现并 retract | 已 accept)。默认读法下即使 δ=1，损失也是 0（ratchet），所以 δ\* 不存在。审计读法下见下。日志里 e1/e2 确实被 retract（这两件 δ=1 ex post），但默认 R 仍保留 8 分；**检出 ≠ 扣分**。
- **读法敏感性**：8.00 的 ratchet 差在 8 种读法下不变（H/F 对 R 和 clawback 同向平移，cap 不影响 R）；但占比变：8/16=50%，8/24.85=32%，8/12=67%。攻击划不划算取决于读法。
- **最小补丁**：官方总分用 final-state recompute；retract 时扣回该事件的 V/P 与 c_i（produce+verify+provenance），并把 `revises` 链做闭包；加 retraction penalty（见 δ\* 的 κ）；V/P/c_i 设 1 轮 vesting/challenge window，窗口结束才落袋；retract 需要第二个 checker 签名。

#### δ\* 推导（一阶，假设已写明）

**假设**：风险中性、单事件、忽略时间折扣与社交成本；a=P(verify accept)，g=3+2p（p 自报；主日志 p=1 → g=5），f=1 若 reject 触发 F_derived（auto/derived）否则 0，δ=P(retract | accept)，κ=每次 retract 的**额外**罚分（R 单位，不含被扣回的 g）。

默认读法（无 clawback、κ=0）：

```
E0 = a·g + (1−a)·f ≥ 0
```

f=1 时即使 a=0 也有 E0=1>0。**不存在 δ\*：任何检出概率都不能让期望收益为负。**

审计读法（clawback + 罚分 κ）：

```
E1 = (1−a)·f + a·[(1−δ)·g − δ·κ] ≤ 0
⇒ δ ≥ δ* = [a·g + (1−a)·f] / [a·(g+κ)]
```

a=1（互审对总是 accept）时 `δ* = g/(g+κ)`：

| κ | 0（只 clawback） | 3 | 5（U=5） | 8（U=5+false check 3） | 10（U=5+另 5） |
|---|---:|---:|---:|---:|---:|
| δ\*（g=5） | 1.000 | 0.625 | 0.500 | 0.385 | 0.333 |

a=0.8, f=1, κ=5 → δ\*=0.525；a=0.5 → δ\*=0.600。a→0 时 E1→f=1>0，δ\* 发散：**被拒绝的提交本身也赚钱**，光加审计救不了。10% 抽查远低于 δ\*；这就是为什么「一条规则」应改变成本结构，而不是只加抽查。注：κ=3/8 中的 false check 原是 c_i 的 −3，把它折算成 R 的等价罚分只是敏感性示例，不是 score.py 的实现。

### H4 执法者俘获：固定轮换、A↔B 互审、moderator 也是玩家

- **机制**：草案说 checker「轮换或随机分配」，「同一成员不能同时提交和独立复核同一事件」。score.py 只执行 `actor != producer`；不执行轮换、随机、互审对、moderator 中立。日志 6 次 accept verify（v1 B→A, v2 A→B, v3 B→A, v4 A→B, v5 B→A, v6 A→B）全部是 A↔B 跨对，全部合法；第 7 次 v7 是 A 对 D 的 reject。C 扮演 moderator/merger（本日志的复盘者），两次 merge 得 0 c_i；C 的 4 分来自 challenge。D 只 produce 了一次被 reject 的 e6，得 0。
- **合法性依据**：score.py 的唯一独立性检查是 `actor != tgt["actor"]`；RULES §3 明说「独立性的唯一机械含义是 actor ≠ 生产者」。A↔B 互审完全满足。固定轮换/随机分配在裁判里根本没有字段。
- **简单模型**：4 人固定轮换，每个 producer 的 checker 按固定顺序轮转（如 A 的 checker 依次是 B,C,D,B,...；B 的 checker 依次是 C,D,A,C,...）。A 知道第 1 轮 B 是 checker，就把要 B 复核的事件排到第 1 轮；B 知道第 3 轮 A 是 checker，就把自己的事件排到第 3 轮——**固定轮换 = 可预谋的确定性**。随机分配下 P(B 是 A 的 checker)=1/(n−1)=1/3；简化成每轮一次 verify，T=4 轮至少命中一次的概率 `1−(2/3)^4≈0.802`；n=3 时 `1−(1/2)^4=0.9375`。本日志 6 次 verify 的实际期望跨对数为 `6/3=2`；全部 6 次都跨对的零假设概率是 `(1/3)^6≈1.37×10^-3`。随机只是把确定性换成「多次尝试」，不消除互审。
- **moderator 俘获**：moderator 能看到个人日志和 c_i，自己也是玩家；merge 在 c_i 里没有权重（b 表没有 merge），所以 merge 是「无偿劳动」，有动机用 merge 权换 challenge/verify 分。score.py 甚至允许生产者自己 merge（只给 ambiguity 提示，不判非法）；「merge 必须有独立 checker」只检查「存在一个非生产者的 accept verifier」，不检查 merger 是否独立。
- **拒绝/挑战的免费伤害**：v7 对 e6 的 reject 给 A +0.2 c_i（b=2×q=0.1），团队 F_derived +1；D 的 produce 不结算。accept 与 reject 给 verifier 的 c_i 相同（都是 b×q），所以 checker 在个人分上对 accept/reject 无差异；但 reject 让团队少 V+P=5，checker 自己仍得分，团队只少 4 分（5→1）。这是合法的 sabotage 向量。challenge 给 +2，目标最终 retract 再 +2；即使 challenge 不被支持，+2 也不退（本日志 c1 是真实争议，未把纯 challenge farming 放入主日志）。
- **可检测性（δ 假设）**：δ = P(外部审计者运行互审/轮换检验)。互审模式非常可检测：v1–v6 的 6/6 跨对，reciprocity=100%，零假设 p≈1.37×10^-3（上一段已算）。如果有人跑这个检验，δ≈1；但 moderator 是玩家，没有独立审计者，所以 δ_audit=0。**「可检测」不等于「会被检测」**。
- **读法敏感性**：8 种读法下 A↔B 都合法；A+B 合计的 c_i 份额默认 28.2/32.2=87.6%（其中 A 的 0.2 来自对 D 的 reject，A↔B 本身约 87%），absolute cmax10 下 20/24=83.3%，per-round 10 下仍 87.6%。俘获对读法稳健。
- **最小补丁**：预承诺随机种子 + commit-reveal 分配 checker；verify 必须带 `assigned_checker`，actor 不符即非法；禁止同一对在窗口内互审（图上的 reciprocity cap）；merge 要求 2 个不同 checker，且 merger 不是 producer/checker；moderator 轮换 + 固定非计分 stipend，或外置审计；reject/challenge 设「被支持才计分」，失败 challenge 扣回 +2；记录 moderator 的查看日志。

### H5 公开/私密矛盾：c_i 要么不可见、要么是监控排行榜

- **机制**：草案 §6 建议「只公开团队汇总和角色覆盖，不公开个人分数」，但又定义 c_i 与 b=1/2/3、每轮上限。若 c_i 完全不公开，b=1 的 produce 没有可见回报；若私下可见（本人+moderator），它就是被监控的个人排行榜，moderator 还能看到所有人。两个读法都自洽，但互相矛盾。
- **合法性依据**：c_i 是草案定义的量；可见性是政策，不是 score.py 的约束。日志只能演示「数字存在且可算」，不能演示「公开后人的行为」。
- **可检验命题（shadow pilot 用）**：
  - **P1（可见性→提交）**：c_i 不可见条件下，每轮至少 produce 一个 b=1 事件的成员比例低于可见条件；零假设无差异。操作化：produce 事件/人/轮、角色覆盖。
  - **P2（moderator 监控）**：moderator 可见个人 c_i 时，其自己的 c_i 增长与「对 top-quartile 成员的 challenge 数」正相关；零假设 0 相关。操作化：Spearman + permutation test。
  - **P3（隐私悖论）**：「本人+moderator 可见」条件下自报「被监控」的比例高于「只公开团队汇总」，尽管两者都自称「不公开」。这是 manipulation check。
  - **P4（角色权重扭曲）**：可见 c_i 会提高 reproduce/check 比（b=3 vs b=2）；本日志 6 次 accept verify 全部是 reproduce（v7 的 reject 是 check），与 P4 一致，但单个日志不是因果证据——**标为推测**。
- **可检测性（δ 假设）**：文档矛盾 δ=1（文本明摆着）；行为效应 δ 未知，需要真人 pilot。不要把 P1–P4 当成已证实。
- **读法敏感性**：c_i 数值本身读法敏感：默认 A15.20>B13.00>C4.00>D0；absolute cmax10 变成 A=B=10.00>C4.00>D0（A 的额外 produce 分被截掉，排名从 A>B 变成并列）；per-round cmax10 又回到 15.20/13.00。q 自报从 1.0→0.6 让 A/B 变成 10.40/8.60。**「谁被看见」取决于 cap 读法和 q 自报。**
- **最小补丁**：先决定 c_i 的用途；若只是角色覆盖，只发布聚合角色计数，不发布个人 c_i，删掉可见的 b 权重/上限；若需要个人反馈，只给本人看自己的 c_i + 匿名分布（histogram/quantile），moderator 只看 flags/聚合；moderator 的 c_i 冻结或固定 stipend；把可见性写进 pilot 的 pre-registration，并用 P1–P3 做 manipulation check。

### H6 读法敏感性总表：R 与 c_i 不是良定义的

- **机制**：同一份合法日志，8 种官方 flag 组合下总 R ∈ [12.00, 24.85]（2.07×），c_A ∈ [10.00, 15.20]（1.52×），c_B ∈ [10.00, 13.00]（1.30×）。读法差 12.85 > baseline 9.45（不同日志，仅量级对照）。H 单位的最大边际差 8.85，F 4.00（12 vs 16），cap 读法 5.20（c_A 10 vs 15.20）；这些是各自的最大边际差，不可直接相加。它们不是边角：仅 H 单位一项 8.85 就接近整个 honest baseline 9.45。
- **合法性依据**：8 种都是 RULES §5 明列的官方参数；没有非法事件；`EXIT=0` 全部通过。score.py header 打印配置，但没有 config hash/签名，团队可以在看到结果后换读法。
- **可检测性（δ 假设）**：若读法在 round 0 前冻结并 hash 进日志，δ=1（任何偏离可机械发现）；当前 δ=0，因为没有 canonical reading。「攻击」不是改日志，而是**事后选读法/在协议里争读法**。
- **读法敏感性**：见 `readings.md` 的 8×矩阵。特别地：`--h-unit minutes` 把 H 罚项缩小 60×，R +8.85；`--f-mode derived` 把第 3 轮 F 从 5 降到 1，R −4；`--f-mode reported` 把第 5 轮 F 从 1 降到 0，R −1；`--cmax 10` 与 `--cmax 10 --cap-mode per-round` 给出 c_A 10.00 vs 15.20；组合读法 C8 给出 20.85，既不是最大也不是最小。
- **最小补丁**：round 0 前写 `scoring_config.json`（h_unit、f_mode、cap_mode、cmax、q/p rubric、F/penalty 定义），hash 写进日志头；score.py 要求 `--config-hash`，不匹配拒绝；官方决策用 conservative reading（所有读法的 min），其他读法只作 robustness；pre-register primary endpoint；把 `h_unit`/`cap_mode` 写进事件 schema，而不是 CLI flag。

## 4. 已演示 vs 推测

| 结论 | 状态 | 依据 |
|---|---|---|
| R=16.00，clawback=8.00，c=(15.20,13.00,4.00,0) | **已演示** | score.py C1 |
| R∈[12.00,24.85]，c_A∈[10.00,15.20] | **已演示** | 8 种 flag |
| ratchet 8 分存活；e4 不随 e2 撤回 | **已演示** | R vs R_clawback |
| U/G/W 自报 0；罚分 0 到 −59 | **已演示（0）/ 推测（罚分口径）** | 日志 + 假设表 |
| A↔B 6/6 互审，合法 | **已演示** | 事件 + score.py |
| δ\*=0.5（a=1, κ=5） | **推导**（假设 a, κ） | 一阶模型 |
| 固定轮换可预谋；随机 0.802 | **推导/推测** | 简单模型 |
| P1–P4 的行为效应 | **推测** | 需真人 shadow pilot |
| 真实组 δ、κ、审计能力 | **未知** | 未测量 |

δ 的数值、U/G/W 的"真实"计数、P1–P4 的效应都是假设或待验证，不是本日志的数字。

## 5. 如果只能加一条规则

**R1（proof-carrying default-distrust）**：任何进入 `R_t` 或 `c_i` 的量，必须由裁判从事件发生时即固定、不可事后修改的原始工件（时间戳、脚本、diff、复核运行记录）自动派生；不能派生时，按对申报者最不利的默认值计；所有分数在最终状态回溯重算。自报字段只作线索，不进入分数。

**为什么是这一条**：

- 它直接杀掉最便宜的攻击：报 0 / 不填 `false_checks` 不再等于免罚，而是触发最不利默认值。
- 它消灭 H 的单位选择：时间戳只能按分钟归一化，`--h-unit` 不再是成员可选的参数。
- 它消灭 ratchet：final-state recompute 让 retract 扣回 V/P/c_i；`revises` 链做闭包，e4 不能靠 e2 的撤回漏洞继续留分。
- 它修复 F 的反转：F 只能来自带失败日志/反例 ID 的条目，裸 reject 不再 +1；`F_used = min(reported, derived_with_evidence)`。
- 它提高 H4 的成本：A↔B 仍可互审，但必须伪造能通过独立 artifact 检查的脚本/运行记录；互审图仍然可审计，而伪造 artifact 的 `c_f` 不再为 0。
- 一阶收益式：`E[R1] ≈ a(3+2p_audited) − c_f − δκ`；只有当 `c_f < a(3+2p_audited) − δκ` 才值得攻击。原来的 `c_f≈0`（填 0 即可）被拿掉，攻击从"零成本"变成"要写能过的 artifact"。
- **为什么不是只加 clawback**：clawback 只修 H3，H1/H2/H6 仍在；自报 0 和单位歧义让 R 仍然不是良定义。
- **为什么不是只加审计**：δ\* 表说明 10% 抽查远不够；moderator 是玩家，审计者本身可能被俘获。R1 改的是成本结构，不依赖 δ。
- **残余**：H5（公开/私密）是展示政策，不是计分规则；H4 的固定轮换/互审还需要一条「承诺随机 checker 分配」的治理规则。若只能加一条**计分**规则，选 R1；若还能加第二条，选 commit-reveal 的 checker 分配。

## 6. scorer bug / 规则差异（未改代码）

以下是与草案字面或 RULES 转写的差异；`score.py` 未改，仅记录。**"bug" 与 "规则转写差异 / 设计缺口" 分开标。**

| 项 | 现象 | 性质 | 影响 |
|---|---|---|---|
| `v_e` | `verify.v` 被记录，但从不进入 R 或 c_i | 设计缺口 | 「复核信号」是死字段；v=0 与 v=1 同分 |
| `F_derived` | 派生值是「进入 disputed 的事件数」，不是「失败测试数」；challenge 也算 | 规则转写差异（RULES §5 明确定义） | 第 3 轮 F=1 来自 challenge，不是失败测试 |
| `F auto` | `F_report>0` 用申报，否则用派生 | 规则转写 / loophole | 报 0 得派生 +1，报 0.5 只得 0.5；奖励不填 |
| `PROVENANCE_FULL=0.95` | 「完整 provenance」硬编码为 p≥0.95 | 实现选择（草案无阈值） | p=0.94 无 +1，p=0.95 有 +1；baseline A p=0.90 无 |
| `revises` | 只存储，不用于状态、计分或 retract 闭包 | 设计缺口 | e4 revises e2，e2 撤回后 e4 仍 verified，保留 B 2 + A 3 = 5 分 c_i |
| `mode=reproduce` | verifier 自报，evidence 仍只需 ≥10 字符，b=3 vs 2 | 设计缺口 | 6/6 用 reproduce；全改 check 则 c_A/B 各 −3 |
| `merge` | c_i 无 merge 权重；生产者可自 merge（仅 ambiguity） | 规则差异 | C 两次 merge 得 0；自 merge 合法 |
| `challenge`/`verify` 状态 | 对 verified 的 challenge、对 disputed 的 verify 都允许，仅 ambiguity | 规则转写差异（草案状态图未定义） | v6 二次 verify；challenge 后洗白合法 |
| `R_clawback` | 算了但不进 `total_R`；c_i 无 clawback | 读法歧义 | 16.00 vs 8.00；13 分 c_i 不扣 |
| `H` 聚合 | 同轮多个 retrospect 求和；个人 vs 团队未定义 | 规则歧义 | 30 可读成个人/团队、分钟/小时 |

## 7. 非法事件附录（被判非法，非漏洞）

本交付的 `events.jsonl` **不含非法事件**。以下最小 probe 只在进程替换中运行，未写入交付日志；它证明机械约束有效，不是漏洞：

```json
{"round":1,"id":"p1","op":"propose","actor":"A","task":"Q1","acceptance":"12345678"}
{"round":1,"id":"e1","op":"produce","actor":"A","task":"Q1","p":1.0,"q":1.0,"human_share":1.0,"ai_share":0.0,"version":1,"content":"x"}
{"round":1,"id":"v1","op":"verify","actor":"A","target":"e1","decision":"accept","v":1.0,"mode":"check","evidence":"1234567890"}
```

结果：`EXIT=2`，`! .../v1: 违反最小约束：不得复核自己的产出`。**判非法，非漏洞。** 按 `score.py` 的代码，重复 merge、无 accept checker 的 merge、负 H/W/U/G、状态不符的 retract 也都会被拦截；本文不把它们算作攻击收益。

## 8. 文件清单

- `events.jsonl`：5 轮合法攻击日志（6 个 produce；含 ratchet、U/G/W=0、A↔B 互审）。
- `score.txt`：C1 完整原始输出，55 行，`EXIT=0`，含「合法性: 通过」。
- `readings.md`：8 种读法的完整命令与 R/c_i 矩阵。
- `report.md`：本文（H1–H6、δ\*、一条规则、scorer 差异、非法附录）。
