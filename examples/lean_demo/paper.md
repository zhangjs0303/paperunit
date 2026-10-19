# Lean 4 证明检查 demo

> **Fixture 警告：** 这不是一篇真实论文。它演示 paperunit 的 `lean4` checker
> 如何把"定理已被机器验证"这一声明绑定到可复跑的 `lake build` 上，以及在没有
> Lean 工具链的机器上如何优雅地降级为 INCONCLUSIVE。

## 内容

`lean_project/` 是一个最小的 Lean 4 库：

- `lakefile.toml`：包名 `paperunit_demo`，默认目标 `PaperunitDemo`；
- `PaperunitDemo.lean`：三个算术定理（`Nat.add_comm`、`rfl`、`Nat.zero_add`），
  全部由核心引理或定义相等完成，**不含 `sorry`**。

`audit.json` 中的 claim `L1` 要求：构建成功，且（因为 `allow_sorry: false`）
源码中没有独立的 `sorry` 占位符。checker 还会把请求的定理
`PaperunitDemo.add_comm_demo` 是否存在于源码中记录到 evidence 里；这一步只是
信息记录，不强制要求（构建本身才是检查）。

## 两种环境下的期望结果

| 环境 | 期望 verdict | 说明 |
| --- | --- | --- |
| 没有 Lean 工具链（本机） | INCONCLUSIVE | reason 含 "Lean toolchain not found" |
| 有 Lean 工具链且 `lake build` 成功 | SUPPORTED | 构建成功且无 `sorry` |
| 有 Lean 工具链但构建失败/超时 | INCONCLUSIVE | 审计方的形式化没走通 |

最后一行是关键，也是 paperunit 的信任模型：

> Lean 构建失败意味着**审计方的形式化没有走通**，它不是论文造假的证据，也
> 不是论文结论错误的证据。只有成功的证明检查才能 SUPPORTED；REFUTED 只能
> 来自反例搜索（例如 `examples/z3_demo` 的 SMT 反例），不能来自构建报错。

## 复跑方式

本机没有安装 Lean 时，`paperunit audit` 会对 L1 给出 INCONCLUSIVE，并在
evidence 中记录两次工具链探测（`lean --version`、`lake --version`）的输出。
安装了 Lean 4（含 `lake`）之后，在 `examples/lean_demo/` 下执行：

```
cd lean_project && lake build
```

应当成功。若需要在 CI 中真正跑 Lean，需要额外安装 elan/lake 并固定
`lean-toolchain`；本项目默认不引入这一重依赖，因此该示例默认走
INCONCLUSIVE 路径。
