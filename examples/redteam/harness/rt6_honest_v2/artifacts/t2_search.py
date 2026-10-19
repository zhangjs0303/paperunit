#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 / c2 的 artifact（版本 2：修掉 v1 的分类错误）。

v1（t2_search_v1.py）真实运行报 n_violations=280，最小"反例"是 (b1=0,b2=-50,W=0)，
所有"反例"的 logP-gap 都恰好是 0.0 —— 那是 P 在 float64 里饱和到 0/1 之后
差值下溢，不是反例。v1 用 `gap <= 0` 判定，把 0 当成了违反；由 A 在 v5 reject 中指出。

v2 改动：
  - 用饱和判据先分类：若 P(W) 或 P(W+delta) 距 0/1 不足 1e-16 → saturated；
  - 只有真的 logP-gap < 0 才算 counterexample；
  - 对 saturated 点报告闭式 log dP/dW（证明命题仍成立但现在不可数值判定）；
  - 输出三分类计数 + 最小反例（按 |b1|+|b2|+|W| 排序）。

模型：p(z1,z2) ∝ exp(b1 z1 + b2 z2 + W z1 z2)，z ∈ {0,1}^2。
命题：对任意 b1,b2,W ∈ R，P(z1=1) 关于 W 严格递增（闭式导数 C*B/(A+C+B)^2 > 0）。
用法：python3 artifacts/t2_search.py
"""
import math

B_GRID = [-700.0, -50.0, -10.0, -1.0, -0.1, 0.0, 0.5, 1.0, 5.0, 50.0, 700.0]
W_GRID = [-10.0, -5.0, -1.0, 0.0, 1.0, 5.0, 10.0]
DELTA = 1e-3
SAT_EPS = 1e-16


def logsumexp(xs):
    m = max(xs)
    if m == -math.inf:
        return -math.inf
    return m + math.log(math.fsum(math.exp(x - m) for x in xs))


def log_p_z1(b1, b2, w):
    return logsumexp([b1, b1 + b2 + w]) - logsumexp([b1, b1 + b2 + w, 0.0, b2])


def log_dP_dW(b1, b2, w):
    log_c = b1 + b2 + w
    log_b = math.log1p(math.exp(b2)) if b2 < 700 else b2
    return log_c + log_b - 2.0 * logsumexp([b1, b1 + b2 + w, 0.0, b2])


def saturated(b1, b2, w):
    lp = log_p_z1(b1, b2, w)
    return lp > math.log1p(-SAT_EPS) or lp < math.log(SAT_EPS)


def main():
    viol, sat, ok = [], [], []
    for b1 in B_GRID:
        for b2 in B_GRID:
            for w in W_GRID:
                if saturated(b1, b2, w) or saturated(b1, b2, w + DELTA):
                    sat.append((b1, b2, w, log_dP_dW(b1, b2, w)))
                    continue
                gap = log_p_z1(b1, b2, w + DELTA) - log_p_z1(b1, b2, w)
                (viol if gap < 0.0 else ok).append((abs(b1) + abs(b2) + abs(w), b1, b2, w, gap))
    viol.sort()
    print(f"grid = {len(B_GRID)}x{len(B_GRID)}x{len(W_GRID)} 点, delta={DELTA}, sat_eps={SAT_EPS}")
    print("n_checked_supported =", len(ok))
    print("n_saturated (P 距 0/1 < 1e-16，数值上不可判定) =", len(sat))
    print("n_counterexample =", len(viol))
    print("saturated 的 |b| 取值 =", sorted({abs(x[0]) for x in sat} | {abs(x[1]) for x in sat}))
    if sat:
        pos = sum(1 for x in sat if x[3] > -700)
        print(f"saturated 点中闭式 log dP/dW > -700 的比例 = {pos}/{len(sat)}")
    if viol:
        print("最小反例（按 |b1|+|b2|+|W| 排序）:", viol[0])
    else:
        print("最小反例: 不存在（可判定区内 0 违反）")


if __name__ == "__main__":
    main()
