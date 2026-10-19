# 因果掩码的 prefix invariance：一个测试型审计 fixture

> **Fixture 警告：** 这不是一篇真实论文，也不报告真实实验。它是 `paperunit`
> 中 `external` checker 的自包含演示，用于说明"可执行审计"如何把一条关于
> 注意力掩码的声明变成第三方可复跑的证据。请勿引用。

## 声明

一个正确的因果（causal）注意力掩码必须满足 **prefix invariance**：如果只改变
位置 `k` 之后的 suffix token，那么位置 `0..k` 的隐状态必须保持不变。直觉很
直接——前缀位置的注意力看不到未来，未来 token 就不能影响它。

本 fixture 提供两个权重完全相同的单头注意力实现：

- `causal_ok`：标准因果掩码，位置 `i` 只能注意 `j <= i`；
- `causal_broken`：完全漏掉未来 mask，所有位置双向注意。

审计脚本 `code/audit_mask.py` 对固定 seed 的输入做两次前向：第一次用原始
输入，第二次把 suffix token 替换成确定性的新值，然后比较 prefix 输出。若
差异超过容差（默认 `1e-9`），则报告 REFUTED 并给出反例位置与两侧输出。

## 方法出处

prefix invariance 的审计思路参考 **The Mask Is Not the Model**（arXiv:2608.22876）
中"改变未来输入不应改变已经生成的 prefix"这一检验方式。本 fixture 复用的是
这一 *测试思想*，不是该工作的结论。

## 这是"测试型审计"，不是证明

必须明确：本审计只检查**一个固定 seed、一个固定输入长度、一个固定替换方式**
下的 prefix invariance。它提供的是关于这个输入的可复跑证据；它**不构成**对
"该实现对所有输入都是因果的"这一命题的证明。真正的符号化检查（对位置对
做全称量化、找不到未来边）放在 `examples/z3_demo`。

这也是 paperunit 的信任模型：审计只报告"在这个预注册检查下，声明是否成立"，
不把一次通过的测试当作普遍定理，也不把工具失败当作论文造假的证据。

## 期望结果

| claim | 变体 | 期望 verdict | 说明 |
| --- | --- | --- | --- |
| M1 | `causal_ok` | SUPPORTED | prefix 输出逐位相同（max abs diff = 0.0） |
| M2 | `causal_broken` | REFUTED | 自测：坏实现必须被抓住，反例位置为 0 |

M1 是真正的声明；M2 是 detector self-test，`preregistered` 为 false。如果
M2 没有 REFUTED，说明审计本身失效，而不是论文有问题。

复跑方式（在本目录下）：

```
python3 code/audit_mask.py --variant causal_ok
python3 code/audit_mask.py --variant causal_broken
```

两个命令都返回 0，并在最后一行输出 JSON；verdict 由 payload 决定，不由退出
码决定（见 `paperunit.checkers.external` 的协议）。
