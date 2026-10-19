#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 / c2 的 artifact：为"P(z1=1) 对 W 严格递增"搜索最小反例。

模型：2 节点 Ising 族  p(z1,z2) ∝ exp(b1 z1 + b2 z2 + W z1 z2)，z ∈ {0,1}^2。
待检验命题：对任意 b1,b2,W ∈ R，P(z1=1) 关于 W 严格递增。

做法（全部 float64，log-space，避免 exp 溢出）：
  log P(z1=1) = logsumexp[b1, b1+b2+W] - logsumexp[b1, b1+b2+W, 0, b2]
  对网格上每点比较 logP(W+delta) - logP(W)：
    > 1e-16         → 支持命题
    in (0, 1e-16]   → 不可判定（float 分辨率不足，如实记为 unverifiable，不算通过也不算违反）
    <= 0            → 反例候选
同时给出闭式导数 dP/dW = C*B/(A+C+B)^2（A=e^b1, B=1+e^b2, C=A e^{b2+W}）的 log 值，
用于分辨"数值差为 0 是命题为假还是 float 不够"。
用法：python3 artifacts/t2_search.py
"""
import math

B_GRID = [-700.0, -50.0, -10.0, -1.0, -0.1, 0.0, 0.5, 1.0, 5.0, 50.0, 700.0]
W_GRID = [-10.0, -5.0, -1.0, 0.0, 1.0, 5.0, 10.0]
DELTA = 1e-3


def logsumexp(xs):
    m = max(xs)
    if m == -math.inf:
        return -math.inf
    return m + math.log(math.fsum(math.exp(x - m) for x in xs))


def log_p_z1(b1, b2, w):
    return logsumexp([b1, b1 + b2 + w]) - logsumexp([b1, b1 + b2 + w, 0.0, b2])


def log_dP_dW(b1, b2, w):
    """闭式导数在 log 空间的值；用于区分 '真的不增' 与 '看不了'。"""
    log_c = b1 + b2 + w
    log_b = math.log1p(math.exp(b2)) if b2 < 700 else b2  # B = 1 + e^{b2}
    log_num = log_c + log_b
    log_den = 2.0 * logsumexp([b1, b1 + b2 + w, 0.0, b2])
    return log_num - log_den


def main():
    viol, unver, checked = [], [], 0
    min_gap, min_gap_at = math.inf, None
    for i, b1 in enumerate(B_GRID):
        for j, b2 in enumerate(B_GRID):
            for w in W_GRID:
                gap = log_p_z1(b1, b2, w + DELTA) - log_p_z1(b1, b2, w)
                checked += 1
                if gap <= 0.0:
                    viol.append((abs(b1) + abs(b2) + abs(w), b1, b2, w, gap))
                elif gap <= 1e-16:
                    unver.append((b1, b2, w, gap))
                if gap < min_gap:
                    min_gap, min_gap_at = gap, (b1, b2, w)
    viol.sort()
    print(f"grid = {len(B_GRID)}x{len(B_GRID)}x{len(W_GRID)} = {checked} 点 (delta={DELTA})")
    print("n_violations =", len(viol))
    print("n_unverifiable (0 < gap <= 1e-16) =", len(unver))
    print("unverifiable 的 |b| 取值 =", sorted({abs(x[0]) for x in unver} | {abs(x[1]) for x in unver}))
    print("min logP-gap =", f"{min_gap:.6e}", "at (b1,b2,W) =", min_gap_at)
    if viol:
        smallest = viol[0]
        print("最小反例候选（按 |b1|+|b2|+|W| 排序）: ", smallest)
    else:
        print("最小反例: 不存在（网格内 0 违反）")
    # 不可判定点上，闭式导数是否仍然 > 0
    bad = [u for u in unver if log_dP_dW(u[0], u[1], u[2]) > -700]
    print("不可判定点中闭式 log dP/dW > -700（导数确实为正）的比例 =",
          f"{len(bad)}/{len(unver)}")


if __name__ == "__main__":
    main()
