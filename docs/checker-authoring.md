# 检查器开发指南（checker authoring）

> 版本：v1.0（2026-10-19）｜接口文件：[paperunit/checkers/base.py](../paperunit/checkers/base.py)
> 关联：[protocol.md](protocol.md)、[OPS.md](../OPS.md)
>
> 一个 checker 把**一条论文 claim + 一个预注册检查**映射到一个 `Outcome`（verdict + 理由 + 证据）。
> checker 只报告证据局部的结论，**永远不计算聚合分数或排名**。

## 1. 一次审计在代码里怎么走

```text
audit.json
  → schema 校验（paperunit/schema.py）
  → engine.run_claims：按 claim["kind"] 找 checker → checker.check(ctx) → Outcome
  → claim 记录（verdict / reason / evidence / uncertainty）
  → build_report → audit_report.json + report.md
  → verify：重跑并对比 report_sha256 与逐 claim verdict
```

找不到 checker、checker 抛异常 → 该 claim 记为 `INCONCLUSIVE`，不影响其他 claim。
这是有意的：**一个坏 checker 不能毁掉整次审计**。

## 2. 接口（base.py）

### 2.1 核心类型

```python
Runner = Callable[[str, Path, float], RunResult]   # (cmd, cwd, timeout_s) -> RunResult

@dataclass
class RunResult:
    cmd: str; cwd: str; timeout_s: float
    exit_code: int | None; timed_out: bool; duration_s: float
    stdout: str; stderr: str
    # 便捷属性：stdout_sha256 / stderr_sha256 / evidence_sha256
    # 方法：summary() -> dict（含截断后的 stdout/stderr 摘要，适合放进 evidence）

@dataclass
class Outcome:
    verdict: str                     # SUPPORTED / REFUTED / INCONCLUSIVE / NOT_RUN
    reason: str                      # 人读的一句话，必须与证据一致
    evidence: dict = {}              # 必须是 JSON-serialisable
    uncertainty: dict | None = None  # 可选的统计/解析不确定性

@dataclass
class CheckContext:
    claim: dict; audit: dict; audit_dir: Path
    runner: Runner; policy: dict = {}
    # 属性：timeout_s（默认 120 秒，可被 policy / claim 覆盖）
    # 方法：check_dir()（claim["check"]["cwd"] 相对 audit_dir 解析）
```

`Outcome.__post_init__` 会做两件事：校验 verdict 合法性；对 `evidence` / `uncertainty`
做一次 JSON round-trip（不可序列化会直接报错）。所以：

- 证据里只能放 str / int / float / bool / None / list / dict；
- 不要放 `Path`、`datetime`、异常对象、numpy 标量（需要时先转 `int()` / `float()` / `str()`）；
- 大输出先用 `truncate()`（base.py 提供）截断，或只存 hash + 摘要。

### 2.2 最小 checker

```python
"""A checker for one narrow claim family. English comments only."""

from __future__ import annotations

from .base import CheckContext, Outcome


class ExampleChecker:
    kind = "example"

    def check(self, ctx: CheckContext) -> Outcome:
        check = ctx.claim.get("check") or {}
        cmd = check.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            return Outcome(
                verdict="INCONCLUSIVE",
                reason="check.cmd is missing or not a string",
                evidence={"claim_id": ctx.claim.get("id")},
            )

        run = ctx.runner(cmd, ctx.check_dir(), ctx.timeout_s)
        evidence = {"run": run.summary()}

        if run.timed_out:
            return Outcome("INCONCLUSIVE", f"command timed out after {run.timeout_s}s", evidence)
        if run.exit_code != 0:
            return Outcome("INCONCLUSIVE", f"command exited {run.exit_code}", evidence)

        expected = check.get("expect", {}).get("stdout_contains")
        if not isinstance(expected, str):
            return Outcome("INCONCLUSIVE", "expect.stdout_contains is missing", evidence)
        if expected in run.stdout:
            return Outcome("SUPPORTED", f"stdout contains {expected!r}", evidence)
        return Outcome("REFUTED", f"stdout does not contain {expected!r}", evidence)
```

规则：

- `reason` 必须能独立读懂：写明期望、观测、差异；不要写"失败"两个字。
- 建议在 evidence 里放 `run.summary()`（含命令、cwd、exit code、stdout/stderr hash 与截断摘要），这样第三方可以复跑核对。
- `INCONCLUSIVE` 的 reason 必须写清卡点（工具链缺失 / 超时 / 解析失败 / 依赖不可得 / 期望配置非法），不要用"未知错误"。

## 3. external 协议（接任何工具）

不想写 Python checker 时，用 `kind: "external"`：在 `check.cmd` 里跑任意脚本，脚本在
**stdout 最后一行非空文本**输出一个 JSON 对象。

```json
{"verdict": "SUPPORTED", "reason": "...", "uncertainty": null, "evidence": {"...": "..."}}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `verdict` | 是 | `SUPPORTED` / `REFUTED` / `INCONCLUSIVE`（`NOT_RUN` 也可，语义同其他 checker） |
| `reason` | 是 | 人读的一句话；与证据一致 |
| `evidence` | 否 | JSON 对象；checker 会自动附加运行摘要 |
| `uncertainty` | 否 | JSON 对象或 null |

失败处理（协议内置）：stdout 为空、最后一行不是合法 JSON、缺少 verdict、verdict 非法、
命令超时/非零退出 → `INCONCLUSIVE`，reason 说明原因。**不要**在脚本里假装成功。

示例脚本：

```python
"""External checker template: print one JSON line as the last stdout line."""

import json
import sys


def main() -> int:
    # ... run the real check here, never reach the network in CI ...
    result = {
        "verdict": "SUPPORTED",
        "reason": "prefix invariance held for 192/192 injections",
        "evidence": {"injections": 192, "failures": 0},
        "uncertainty": None,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

适用场景：Z3 / Lean / 自定义静态分析 / 任何已有工具。注意：external 脚本是审计方的代码，
审计文件本身被当作可信输入（协议 §2.3）。

## 4. 如何注册

- **core checker**（numeric / stdout / exit / human）在 `paperunit/checkers/executables.py`
  与 `human.py`，由 `paperunit/checkers/__init__.py` 的 `_bootstrap()` 显式注册；
- **optional checker** 目前按模块名懒加载：`statistics`、`lean4`、`external`
  （见 `checkers/__init__.py` 的 `optional` 元组）；
- 新 checker 的流程：作者提交 `checkers/<name>.py`（class + `kind` + 测试 + 示例 audit）→
  在 PR 里说明接口与失败路径 → maintainer 在 `checkers/__init__.py` 注册（**不要自己改
  `__init__.py` / `base.py`**，避免与其他人的改动冲突）。
- `kind` 命名：小写、单词、唯一，例如 `numeric` / `causal_mask` / `shape_contract`；
  不要用版本号，行为变化通过 checker 弃用流程处理（OPS.md）。
- 接口需要改动时：先开 issue 说明动机，由 maintainer 决定；不要在 checker PR 里顺手改 base.py。

## 5. 测试要求（合并门槛）

每个新 checker 必须带 `tests/test_<name>.py`，至少覆盖：

1. **成功路径**：`SUPPORTED`（用 fake runner 构造 `RunResult`，不要真的跑子进程）；
2. **失败路径**：`REFUTED`（期望不满足）；
3. **无法判定**：`INCONCLUSIVE`（超时、非零退出、输出解析失败、依赖缺失、配置非法）；
4. **异常路径**：`check` 内部抛异常时，engine 会兜底成 `INCONCLUSIVE`（可单独测 engine 行为）；
5. **示例**：`examples/<name>/` 里至少一个可直接跑的 audit，并在 README 或测试里写明期望 verdict。

fake runner 示例：

```python
from pathlib import Path

from paperunit.checkers.base import CheckContext, RunResult


def fake_runner(stdout: str = "", exit_code: int = 0, timed_out: bool = False):
    def run(cmd: str, cwd: Path, timeout_s: float) -> RunResult:
        return RunResult(
            cmd=cmd, cwd=str(cwd), timeout_s=timeout_s,
            exit_code=exit_code, timed_out=timed_out, duration_s=0.0,
            stdout=stdout, stderr="",
        )
    return run


ctx = CheckContext(
    claim={"id": "C1", "kind": "example", "check": {"cmd": "true"}},
    audit={"schema": "paperunit/v1", "target": {}, "claims": []},
    audit_dir=Path("."),
    runner=fake_runner("accuracy=0.918\n"),
    policy={},
)
```

## 6. 约定（确定性 / 超时 / 隐私）

- **确定性**：checker 的输出必须可复现。固定 seed；不依赖当前时间、网络、随机端口、GPU 非确定性；
  排序遍历用 `sorted()`。只要 stdout 不稳定，`verify` 就会报 `DRIFT`。
- **超时**：默认 `DEFAULT_TIMEOUT_S = 120`，claim 的 `check.timeout_s` 可覆盖；
  命令应留出足够余量。子进程超时只杀 shell，可能留下后代进程（见 proto README 的已知限制），
  checker 不要依赖"超时一定清理干净"。
- **网络**：默认禁止。需要联网的检查（拉数据/模型）必须在报告 limits 里声明，且 CI 不跑这种 claim。
- **只读**：checker 不改被审仓库；必须写临时文件时写到 `tempfile.TemporaryDirectory()`，
  不要写到 `audit_dir` 之外。
- **不吞错误**：stderr 非空不等于失败，但重大错误要写进 reason/evidence；不要把 stderr 直接丢给读者。
- **证据隐私**：报告会公开。evidence 里不要放个人邮箱、token、绝对 home 路径、内部 IP；
  机器路径由 engine 环境字段承担，不要额外扩散。
- **不做聚合**：checker 不返回分数、不返回排名、不与其他 claim 比较、不引用其他 claim 的 verdict。
- **不推测动机**：reason 只写"在什么条件下观测到什么"，措辞按 [ethics.md](ethics.md)。

## 7. 可选依赖（例如 z3）

- 依赖声明加到 `pyproject.toml` 的 `[project.optional-dependencies]`（已有 `z3`）。
- checker 内用懒导入：`try: import z3 except ImportError: return Outcome("INCONCLUSIVE", "z3 not installed", ...)`。
- 测试在缺依赖时断言 `INCONCLUSIVE` 路径（`unittest.skipUnless` / `SkipTest`），有依赖时跑真验证。
- 不允许把可选依赖变成核心依赖；核心必须保持 stdlib-only。

## 8. 合并前 checklist

```text
[ ] class 有唯一 kind，check(ctx) 返回合法 Outcome
[ ] 所有失败路径返回 INCONCLUSIVE 并写清卡点（不抛异常、不静默）
[ ] evidence 全部 JSON-serialisable，且包含 run.summary()（如适用）
[ ] 有 SUPPORTED / REFUTED / INCONCLUSIVE 三类测试 + fake runner
[ ] 有可跑的 examples/<name>/audit.json 与期望 verdict 说明
[ ] 不联网、不改被审仓库、输出确定、命令在超时内
[ ] 无分数/排名/跨 claim 聚合
[ ] reason 与措辞通过 ethics.md 自检
[ ] 已报告 maintainer 注册 kind（不自行改 checkers/__init__.py 或 base.py）
```
