# 用 z3 符号化检查因果掩码：反例型审计 demo

> **Fixture 警告：** 这不是一篇真实论文。它演示 paperunit 的 `external`
> checker 如何接入一个 SMT 求解器，把"掩码构造是因果的"这一声明变成
> **可判定的符号化检查**，并说明为什么 REFUTED 必须来自反例而不是报错。

## 检查内容

`code/check_mask_z3.py` 把掩码构造编码成谓词 `allows(i, j)`，位置用 5 位无
符号位向量表示，因此取值范围是 `0..31`，覆盖所有 `T <= 32` 的序列长度。要
验证的性质是：

```
forall i, j in [0, 32): i < j  =>  not allows(i, j)
```

脚本让 z3 求解该性质的**否命题**——即是否存在一对 `i < j` 使得掩码允许从
`i` 注意到未来的 `j`：

- `--variant correct`：标准因果掩码 `allows(i, j) := j <= i`。否命题 unsat，
  z3 证明不存在未来边 → **SUPPORTED**；
- `--variant broken`：故意漏掉 mask，`allows(i, j) := true`。否命题 sat，
  z3 给出反例（如 `i=0, j=1`）→ **REFUTED**，并把 counterexample 写进 evidence。

这正是 paperunit 对"形式化/半形式化声明"的信任模型：**REFUTED 来自反例
搜索**（找到具体的违反实例），而不是来自 Lean 构建失败或工具崩溃。

## 可选依赖与 INCONCLUSIVE

z3 不是默认依赖，通过可选 extra 安装：

```
pip install 'paperunit[z3]'
```

没有安装 z3 时，脚本输出 `verdict = INCONCLUSIVE` 的 JSON 并说明"solver 缺失"，
`external` checker 会原样接受这一 verdict。**solver 缺失不是论文有问题的证据**，
也不是"声明成立"的证据；它只是说这次符号检查没有运行。

## 与 causal_mask 示例的关系

- `examples/causal_mask` 是**测试型**审计：对固定输入做两次前向，检查 prefix
  invariance，能给出具体反例位置，但不是全称证明；
- 本示例是**符号化**审计：对编码后的掩码构造做全称量化检查（T <= 32），
  得到 unsat 或 sat 的确定结论。

两者的方法出处都参考 **The Mask Is Not the Model**（arXiv:2608.22876）中
关于 mask 与 prefix invariance 的讨论；本 fixture 复用的是检验思想，不是其结论。

## 期望结果

| 环境 | Z1 (correct) | Z2 (broken) |
| --- | --- | --- |
| 有 z3-solver | SUPPORTED | REFUTED（含 counterexample） |
| 无 z3-solver（本机默认） | INCONCLUSIVE | INCONCLUSIVE |

复跑方式（在本目录下）：

```
python3 code/check_mask_z3.py --variant correct
python3 code/check_mask_z3.py --variant broken
```

两个命令都返回 0，并在最后一行输出 JSON；verdict 由 payload 决定，不由退出
码决定。
