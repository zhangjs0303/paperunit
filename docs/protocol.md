# 审计协议（protocol）

> 版本：v1.0（2026-10-19）｜适用 schema：`paperunit/v1`，报告格式：`paperunit/report/v1`
> 关联文档：[OPS.md](../OPS.md)（运营与治理）、[ethics.md](ethics.md)（措辞与法律红线）、[checker-authoring.md](checker-authoring.md)（检查器开发）
>
> 本协议规定"一次审计怎么做、证据怎么留、结论怎么措辞、争议怎么处理"。
> 它不构成法律意见；涉及具体法律风险时按 OPS.md 的法务 playbook 处理。

## 0. 一页版

```text
论文 claim
  → 准入检查（公开 / 低风险 / CPU 可跑 / 无 COI）
  → 预注册 audit.json（claim + 命令 + 期望 + 容差 / 等价边界 margin，先提交再运行）
  → 运行（记录 commit / 环境 / 输出 hash）
  → Reproduction note（中性观测，不写结论）
  → Audit report（verdict + 证据 + scope + limits + 作者回应位）
  → 第二签署 → 通知作者（14–30 天）→ 收录回应
  → 发布（registry PR + CI 复跑）→ 第三方 verify → 必要时更正/撤回
```

三条不可交易的原则：

1. **一切 verdict 必须绑定可执行的证据**，没有可执行证据就写 `NOT_RUN` / `INCONCLUSIVE`，不写判断。
2. **优先通知作者、优先收录回应**。作者回应权是永久的，不因期刊更正或时间推移而消失。
3. **报告是对工件的观测，不是对人的裁决**。措辞规则见 [ethics.md](ethics.md)。

## 1. 审计对象与准入条件

### 1.1 审计单位

一篇论文 = 一个审计目录（`registry/audits/<slug>/`）。同一篇论文可以被多次审计，每次审计独立成目录并保留历史，不覆盖旧报告。

### 1.2 准入条件（全部满足才立项）

| 条件 | 判定 | 不满足时 |
|---|---|---|
| 论文公开可获取 | arXiv / OpenReview / 期刊公开版 / 有 DOI | 不做 |
| 检查对象公开 | 代码或复现包公开，或作者书面提供；数据可获取或可合成替代 | 只对可获取部分建档，其余 `NOT_RUN` |
| CPU 可跑 | 单条命令在 30 分钟内跑完（默认 timeout 120 秒，可覆盖） | 降级为 `INCONCLUSIVE` + 人审说明，或不做 |
| 不涉及敏感数据 | 无患者数据、无未成年人数据、无未发表组内资料 | 不做 |
| 无直接利益冲突 | 审计者与被审论文无同机构/同导师/合作关系（见 §9） | 换人或只发复现记录 |
| 有明确可检验 claim | 至少 1 条 A/B/C 类 claim（见下表） | 不做，或只做可检验性普查记录 |

### 1.3 claim 可检验性分类

| 类型 | 例子 | 第一版支持 | 说明 |
|---|---|---|---|
| A 数值 | "test accuracy 92.3%" | 是 | 复跑 + 解析 + 预注册容差 |
| B 性质 | "causal mask 无未来泄漏"、"张量形状契约"、"训练/测试无重叠" | 是（checker 逐步补齐） | 属性测试 / Z3 / 静态检查 |
| C 数学 | "定理 3.1 的收敛率为 O(1/T)" | 第二阶段（Lean 4 旗舰） | 编译通过才算证据 |
| D 经验/算力 | "8×H100 训练 3 天" | 否 | `NOT_RUN` / `INCONCLUSIVE` + 人审说明；不推断 |

报告可以统计 A/B/C/D 的覆盖比例，但**不得**把比例解释为论文质量或作者能力。

## 2. 范围与预注册

### 2.1 预注册（preregistration）

开始运行前，必须先提交 `audit.json`（可以只在本地仓库提交，发布时一并公开）：

- `target`：title、paper、repo_commit、audited_by、date；
- `scope.tested` / `scope.not_tested`：明确写出覆盖与不覆盖的内容；
- 每条 claim：`id`、`text`（引用或转述论文原文）、`kind`、`check.cmd`、`check.cwd`（可选）、`check.timeout_s`（可选）、`check.expect`、`preregistered`；数值/统计 claim 另写 `check.equivalence_margin`（留空即默认 `paper_precision`，见 §2.3）；
- 写明第一条命令将运行的 commit / 版本；如果只能在运行后才知道 commit（例如作者更新仓库），记录两个 commit 并说明。

规则：

- **预注册之后不得修改 `expect` 的目标值与等价边界 margin**（§2.3）。只能新增 claim，并标 `preregistered: false`（说明是事后补充的观察）。
- 任何"先看结果、再调容差"的行为都视为违反协议，即使方向是让结论更保守。
- 预注册文件随报告一起公开；它的提交历史就是预注册的证明。

### 2.2 容差（tolerance）规则

容差不允许拍脑袋，也不能为标准：

| 情形 | 容差取法 |
|---|---|
| 论文报告单一数值、无方差信息 | 默认 `paper_precision`：margin = 10^(-d)，d 为声称值小数点后位数（0.923 → 0.001）；报告里写明取法与 margin_source（§2.3） |
| 论文报告均值 ± 标准差 / 多种子 | 用 statistics checker 计算 CI；margin 默认 paper_precision；不要把 CI 当成"论文必须落入"的区间（判定见 §2.3） |
| 计时 / 硬件相关 | 只在同一机器、同环境对比；否则 `INCONCLUSIVE`；不把耗时差异写成 REFUTED |
| 依赖随机种子 | 固定 seed 或跑多个 seed；单 seed 差异不足以 REFUTED |
| 无法确定合理容差 | `INCONCLUSIVE`，并在 limits 里写"无法确定容差" |

**硬规则**：如果因为容差太紧而产生 REFUTED，第一条处理是复查环境与命令，第二条是复查论文原文是否被你误读，第三条才是维持结论。报告必须写出"我们如何排除环境差异"。

### 2.3 等价边界（margin）与预注册

数值与统计 claim 在预注册时必须确定**等价边界（equivalence margin）**：观测值与论文声称值相差多少以内算"达到论文自己的精度"。留空即使用默认的 `paper_precision`；换用其他取法必须显式写进 `audit.json` 并说明理由。margin 是审计工具的参数，不是对论文质量的判断；它决定 REFUTED 的门槛，因此必须**先于运行**写入 `audit.json`，运行后不得再改。

三种写法（统计 claim 位于 `check.claim.equivalence_margin`，也接受写在 `check` 顶层；`margin_factor` 同理；解析逻辑见 `paperunit/margin.py` 的 `resolve_margin`；政策文件格式见 `policies/README.md`）：

| 模式 | 写法 | 含义 | 什么时候用 |
|---|---|---|---|
| `paper_precision` | 缺省，或字符串 `"paper_precision"` | margin = 10^(-d)，d 为论文声称值按十进制书写的小数点后位数（0.923 → d=3 → margin=0.001）；可选 `margin_factor`（默认 1.0，须为正数）乘上去；evidence 记 `margin_source: paper_precision` | v0.2 起的**默认**；语义是"允许偏差最多为论文自己最后一位有效数字" |
| `fixed` | 数字，如 `0.002`（或对象 `{"mode": "fixed", "value": 0.002}`） | 显式固定边界，兼容旧行为；`margin_mode` 记为 `fixed`，`margin_source` 标明显式数值来源 | 领域惯例或作者声明给出的边界；论文精度过粗需要人工指定时 |
| `policy_ref` | 对象 `{"mode": "policy_ref", "path": "policies/margin/v1.json", "decision_id": "..."}` | 从版本化政策文件读取边界；`decision_id` 原样记录，`margin_source` 记录 policy 文件路径 | 未来治理流程（评议会/DAO）统一边界时；接入点见 [OPS.md](../OPS.md) §4.7 |

规则：

1. **默认语义**：paper_precision 的含义是"允许偏差最多为论文自己最后一位有效数字"。例：声称 0.923 → margin = 0.001；声称 0.918 → margin = 0.001。
2. **整数声称值**：没有小数位时 d = 0 → margin = 1，分辨率过粗。报告必须标注"分辨率过粗"（解析结果的 `margin_note` 会写明），并建议改用显式边界（`fixed`）或 `policy_ref`。
3. **什么时候算 REFUTED**：统计 claim 只有在**差异 > margin 且区间（CI）排除声称值**时才写 REFUTED；差异 > margin 但区间仍包含声称值 → INCONCLUSIVE（本次扫描分辨率不足）；差异 ≤ margin → SUPPORTED。margin 是"允许的差异"，不是"论文必须落入的区间"。
4. **不可事后调整**：预注册之后修改 margin 视为违反协议；只能按 OPS §4.7 记录 `margin_exception`（理由、影响的 claim、批准人），并保留原 margin 与原 verdict。
5. **报告必须显示**：margin 数值（报告 uncertainty 中的 `equivalence_margin`）、`margin_mode`、`margin_source`、`margin_decision_id`；使用 `policy_ref` 时 `margin_source` 为 policy 文件路径，并显示 `decision_id`。第三方复跑按报告记录的 margin 与 policy 文件执行。
6. **解析失败不猜默认值**：policy 文件缺失、`decision_id` 不存在、mode 未知、声称值无法解析时，该 claim 记 `INCONCLUSIVE`（evidence 里写 `spec_error`），不得退回默认 margin 继续跑。
7. **与 §2.2 的关系**：§2.2 规定不同情形怎么取容差，本节规定它在 `audit.json` 里怎么声明、如何参与判定；两者不是两套标准。

### 2.4 运行纪律

- 只读被审对象：不修改论文仓库代码；需要安装依赖、打补丁、设置环境变量时，逐条写进报告 `limits`。
- 记录环境：Python 版本、操作系统、关键依赖版本（无 lockfile 时记录 `pip freeze` 摘要或依赖清单 hash）、CPU/内存概要。报告 `environment` 字段由 engine 自动写入，人写部分补充论文要求的特殊条件。
- 不以"跑不通"为结论：跑不通 → `INCONCLUSIVE`，并写清卡在哪一步（依赖缺失 / 数据不可得 / 代码报错），这是对复现性的观测，不是对论文的指控。
- 不隐藏失败：故意加入一条已知为假的期望作为检测器自检（R4 模式）时，报告必须标注 `preregistered: false` 并说明这是自检。

## 3. 三层输出（把"指控"降级为"观测"）

| 层 | 名称 | 内容 | 谁能发 | 能否引用为"审计结论" |
|---|---|---|---|---|
| L1 | Reproduction note（复现记录） | 中性观测：在 commit X、命令 Y、环境 Z 下，得到输出 W；记录差异与限制。不含 verdict 之外的评价 | 任何参与者，经 editor 过目 | 否 |
| L2 | Audit report（审计报告） | L1 + 逐 claim verdict + scope + limits + 作者回应 + 审计者署名 + 报告 hash + 第二签署 | 第二签署 + editor 同意 | 是，按版本引用 |
| L3 | Referral（转介） | 只原样引用正式机构调查结论（大学、期刊、资助方、撤稿声明），附 URL 与日期，不做二次判断 | 仅 editor | 只能引用被转介的官方结论本身 |

升级规则：

- L1 → L2 必须满足：claim 有可执行检查、报告通过第二签署、作者已收到通知且在窗口内。
- L2 → L3 只能由 editor 决定；**任何人不得主动寻找、推测或"补完"官方调查**。
- 任何把 L1 当 L2 传播的行为（例如在社交媒体写"我们审计发现某论文是错的"）按 OPS.md 行为准则处理。

复现记录模板（L1，30 行以内）：

```text
对象：<论文标题>（<DOI / arXiv ID>）
commit/版本：<hash 或 release tag>
环境：<OS, Python, 关键依赖>
命令：<完整命令 + cwd>
观测：<stdout 关键行 / exit code / 耗时>
差异：<与论文报告值的差，含容差>
未覆盖：<没测的部分>
联系：<是否已通知作者，日期>
```

## 4. verdict 语义

| verdict | 定义 | 不等于 |
|---|---|---|
| `SUPPORTED` | 检查已运行，全部预注册期望满足 | 不等于"论文正确"；只覆盖被检查的 claim 与范围 |
| `REFUTED` | 检查已运行，至少一项预注册期望未满足；统计 claim 需"差异 > margin 且区间排除声称值"（§2.3） | 不等于"造假"；不等于"论文错误"；必须写清差异幅度、margin 与环境 |
| `INCONCLUSIVE` | 检查无法判定：工具链缺失、超时、统计功效不足、形式化未通过、数据不可得 | 不等于"失败"，这是对可复现性的观测 |
| `NOT_RUN` | 该 claim 没有可执行检查（仅人审记录，或 D 类算力依赖） | 不等于"不支持" |

硬规则：

- **宁可 `INCONCLUSIVE`，不要错误的 `REFUTED`**。无法排除环境差异时，必须降级为 `INCONCLUSIVE`。
- 不允许任何聚合分数（百分比、加权分、总分、"复现度"）。`verdict_counts` 只是计数，展示时必须附"不是质量分"的声明。
- 任何排序（含 registry 的日期排序）都不是质量排序；registry 只有日期序。
- 报告首页必须包含声明：**"本报告不构成对论文科学价值、作者能力或研究诚信的裁决。"**

## 5. 作者回应流程

### 5.1 时间线

| 时间 | 动作 | 负责人 |
|---|---|---|
| T0 | 报告草稿完成、内部第二签署完成，记录通讯作者公开联系方式 | auditor |
| T0 + 1~3 工作日 | 发送通知邮件：附草稿、说明审计范围与证据、给出 14–30 天回应窗口、说明作者可要求更正或补充信息 | editor |
| T0 + 14 天（默认窗口） | 作者回应的最后期限；复杂案例可延长到 30 天，延期只批准一次并记录 | editor |
| 窗口结束 | 收录回应（原文，不删改）→ auditor 再回应（仅限事实）→ 最终第二签署 → 发布 | auditor + editor |
| 发布后 | 作者永久保留回应权；新回应可追加到 `author_response.md`（或报告 `README.md`），不覆盖历史 | editor |

### 5.2 回应收录规则

- 作者回应**原文收录**（可同时提供翻译），不删改、不摘要替代。若回应包含个人信息或攻击性内容，可只保留与审计事实相关的部分并注明"已按隐私规则删减"。
- auditor 的再回应最多 2 轮，只回应事实与证据，不评价作者动机。
- 作者提供可复跑的反证时，必须重新运行；结论可能改为 `SUPPORTED` 或 `INCONCLUSIVE`，并保留原结论与更正记录。
- 作者明确反对发布时：
  - 反对理由是个人信息/隐私/法律威胁 → editor 暂停发布，走 OPS.md 法务 playbook；
  - 仅不同意结论 → 照常发布，收录反对声明，前提是第二签署确认证据与措辞没问题；
  - 作者能指出事实错误 → 更正或撤回，见 §6。
- 作者未回应：报告中写"已通过公开通讯方式于 YYYY-MM-DD 通知作者，截至 YYYY-MM-DD 未收到回应"，不公开个人邮箱与电话。

### 5.3 通知邮件要点（模板）

1. 我们是谁（项目定位一句话 + 仓库链接）；
2. 我们检查了什么：论文标题、DOI、claim 列表、使用的 commit、命令、环境；
3. 我们观察到什么：中性陈述 + 附草稿链接；
4. 这不构成对论文价值或作者的评价；我们的流程要求先通知作者；
5. 请在 14–30 天内回应；可要求更正、提供反证或补充材料；
6. 作者回应将原样收录；
7. 联系方式与保密承诺（不公开个人邮箱）。

## 6. 更正与撤回

| 情形 | 处理 | 时限 |
|---|---|---|
| 措辞问题（不改变结论） | 修订措辞，`README.md` 记 changelog，报告正文标注"rev N" | 3 个工作日内 |
| 证据/结论错误（例如环境问题导致误判） | 重跑 → 更正 verdict → 旧版本保留可访问 → changelog 写清原因 | 7 个工作日内 |
| 结论整体不成立 | 撤回：报告顶部加"RETRACTED"横幅与撤回理由，保留历史版本；registry 仍显示条目但标注撤回 | 7 个工作日内 |
| 作者要求下架且理由涉及隐私/法律 | 先隐藏公开副本，保存内部记录，走 OPS.md 法务 playbook | 24 小时内 |
| 报告格式/registry 元数据问题 | 重新构建 registry，不改报告内容 | 1 个工作日内 |

硬规则：

- **不删除历史**。更正保留旧版本与 hash；撤回保留撤回声明。唯一例外是隐私/法律要求的临时下架（内部留档）。
- 更正、撤回都要经过 editor；撤回还需 maintainer 知情。
- 已发布报告引用的 checker 被弃用后，报告不改 verdict，只在报告里标注"该 checker 已弃用（见 CHANGELOG），证据保留"。

## 7. 发布前第二签署（必读清单）

发布 L2 报告前，第二签署人（未参与本审计的 editor / auditor / maintainer）逐条确认：

```text
[ ] 每条 verdict 都能在报告里找到对应命令、输出与 hash
[ ] scope.tested / scope.not_tested 完整，没有暗示未测内容
[ ] 措辞通过 ethics.md 的关键词自检（无"造假/学术不端/篡改"定性，无动机推测，无夸张形容词）
[ ] 已通知作者，通知日期与窗口记录在案；作者回应已原样收录（或注明未回应）
[ ] 报告首页有"不构成科学价值裁决"声明
[ ] 审计者 COI 声明（无冲突 / 已披露）
[ ] AI 使用声明（是否用 LLM 辅助抽 claim、写了哪部分；verdict 是否全部来自可执行检查）
[ ] 引用的论文图表/原文符合最小引用与署名要求
[ ] 每条数值/统计 claim 的 margin 与 margin_source 已记录（policy_ref 时含 policy 文件路径与 decision_id），且与 audit.json 一致
[ ] report_sha256 可由第三方用 `paperunit verify` 复跑核对
[ ] registry 条目元数据（title/audited_by/date）与报告一致
```

任何一条无法确认 → 不发布，退回修改。

## 8. 报告模板字段（对应 engine 输出）

`audit_report.json` 由 engine 生成，审计者不要手改。字段：

| 字段 | 含义 |
|---|---|
| `schema` | `paperunit/report/v1` |
| `tool` | 生成报告的 paperunit 版本 |
| `target` | `title`, `paper`, `repo_commit`, `audited_by`, `date` |
| `scope` | `tested` / `not_tested` 列表（来自 audit.json） |
| `policy` | 生效的审计策略（超时等；margin 解析结果记录在 `claims[].evidence` / `uncertainty`，见 §2.3） |
| `environment` | 运行环境快照 |
| `generated_at` | 生成时间（仅记录，不参与 report hash） |
| `claims[]` | `id`, `kind`, `text`, `verdict`, `reason`, `evidence`（含命令、输出 hash、margin 解析结果 `margin_policy` 与 `resolution`）, `uncertainty`（含 `equivalence_margin`、`margin_mode`、`margin_source`、`margin_decision_id`） |
| `verdict_counts` | 四种 verdict 的计数（不是质量分） |
| `report_sha256` | 稳定视图的内容 hash（不含耗时与时间戳），用于防篡改与复跑对比 |
| `limits` | 报告局限，自动包含 `scope.not_tested` 与"不是科学价值裁决"声明 |

人写部分（放在审计目录里，随报告一起发布）：

```text
registry/audits/<slug>/
  audit.json          # 预注册文件（只读快照）
  audit_report.json   # engine 输出（机器可读）
  report.md           # engine 生成的报告（人读）
  README.md           # 导言、再回应、changelog、COI/AI 声明、第三方复跑记录
  author_response.md  # 作者回应原文（逐字收录；没有回应则不放）
  logs/               # 需要长期保留的完整日志（可选，注明 sha256）
```

`README.md` / `author_response.md` 是作者回应与更正的唯一入口；任何对报告的"文字修订"都写在这里，不修改 `audit_report.json`。作者回应的原文不动，审计者的再回应写在 `README.md`。

## 9. 独立复跑（verify）

- 复跑者要求：未参与本审计、使用干净 checkout、不看审计者的即时聊天记录（只读公开报告）。
- 命令：`paperunit verify --audit <audit.json> --report <audit_report.json>`。
- 退出码与状态：
  - `REPRODUCIBLE`（0）：报告 hash 未变且重跑 verdict 一致；
  - `DRIFT`（1）：报告未变但重跑结果与记录不一致（环境/随机性/依赖变化）；
  - `TAMPERED`（1）：报告内容 hash 与记录不符；
  - `INCONCLUSIVE`（2）：无法完成复跑。
- 复跑结果写进审计目录 `README.md` 的"第三方复跑"小节：复跑者署名、环境、日期、状态。同一报告可以有多条复跑记录。
- 复跑记录是 OPS.md 指标"外部复跑者数"的唯一依据；不把"看起来可复现"记为复跑。

## 10. 审计的审计（dogfood）

- 每个 release 前，用同一套工具审计本项目自己的报告与脚本，至少覆盖：`examples/toy_paper` 的 C1–C4、`examples/redteam` 的 R1–R4（其中 R4 是故意错误的期望，用于证明检测器有效）。
- 新 checker 或协议修改后，重跑 dogfood 并对比；出现意外差异先修工具，不修报告。
- dogfood 报告可以作为示例进入 registry，但必须标注 "dogfood / synthetic fixture"。

## 11. 协议版本与变更

- 协议版本用 semver：patch = 措辞与排版；minor = 新增流程/字段但不影响历史报告语义；major = verdict 语义、三层输出规则、发布规则、margin 默认值或判定门槛变化。
- major 变更需要 RFC issue 公开讨论 ≥ 2 周，editor + 两名 maintainer 同意；历史报告不追改，只标注"按 v1.0 协议撰写"。
- 任何协议变更都写进仓库根目录的 `CHANGELOG.md`（发布时创建）与本文件顶部版本号。
