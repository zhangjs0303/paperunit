#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q3 / c1 的 artifact（版本 2）。

问题：把 Q1 的 q(0,1) 乘 10^k、q(1,0) 除 10^k 之后，
      Q1/c2 注册的绝对阈值 max|dpi|_inf < 1e-13 是否还成立？
      float 解的误差能否用精确稳态分布的动态范围 kappa_pi = max/min pi 预测？

与 v1 的差别：判定改成 criterion 字面要求的**绝对**误差 max_i |pi_fl - pi_ex|；
同时报告相对误差、kappa_pi、以及预注册的比值 max|dpi| / (u * kappa_pi)，u=2.22e-16。
预注册见 artifacts/prereg_q3_predictions.txt（写在跑本脚本之前）。

用法：python3 artifacts/t3_stiff.py
"""
import sys
from fractions import Fraction as F

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from t1_stationary import generator, gauss, system

U = 2.22e-16
ABS_THRESH = 1e-13
KS = list(range(8))


def one(k):
    Q = generator(k)
    n = len(Q)
    A_ex, b_ex = system(Q)
    pi_ex = gauss(A_ex, b_ex)
    pi_fl = gauss([[float(x) for x in row] for row in A_ex], [float(x) for x in b_ex])
    ex = [float(x) for x in pi_ex]
    dev = max(abs(a - b) for a, b in zip(pi_fl, ex))
    rel = max(abs(a - b) / max(abs(b), 1e-300) for a, b in zip(pi_fl, ex))
    kappa = max(ex) / min(ex)
    Qf = [[float(x) for x in row] for row in Q]
    res = sum(abs(sum(pi_fl[i] * Qf[i][j] for i in range(n))) for j in range(n))
    scale = max(sum(abs(float(x)) for x in row) for row in Q)
    return k, dev, rel, kappa, dev / (U * kappa), res, res / scale


def main():
    rows = [one(k) for k in KS]
    print(f"{'k':>2} {'max|dpi|_abs':>14} {'max rel':>11} {'kappa_pi':>12} "
          f"{'ratio=abs/(u*kappa)':>21} {'|pi_fl Q|_1':>13} {'res/||Q||':>11}")
    for k, dev, rel, kappa, ratio, res, resn in rows:
        print(f"{k:>2} {dev:>14.6e} {rel:>11.3e} {kappa:>12.4e} {ratio:>21.4e} "
              f"{res:>13.6e} {resn:>11.3e}")
    breaks = [k for (k, dev, *_rest) in rows if dev > ABS_THRESH]
    k_star = breaks[0] if breaks else None
    max_ratio = max(r[4] for r in rows)
    kappa_mono = all(rows[i][3] < rows[i + 1][3] for i in range(len(rows) - 1))
    print()
    print(f"criterion(max|dpi|_abs < {ABS_THRESH:g}) 的首次突破点 k* = {k_star}")
    print(f"P1 预测 k* = 3  -> {'成立' if k_star == 3 else '不成立'}")
    print(f"P2 max ratio = {max_ratio:.4e}  < 100  -> {'成立' if max_ratio < 100 else '不成立'}")
    print(f"P3 kappa_pi 单调增大 -> {'成立' if kappa_mono else '不成立'}")
    n_meet = sum(1 for (k, dev, *_r) in rows if dev <= ABS_THRESH)
    print(f"落在绝对阈值内的 k 个数 = {n_meet}/{len(KS)}")
    res_break = [r[0] for r in rows if r[5] > 1e-15]
    print(f"Q1/c2 的第二个子句 |pi_float Q|_1 < 1e-15 的首次突破点 = "
          f"{res_break[0] if res_break else None}   (突破点个数 {len(res_break)}/{len(KS)})")
    print(f"归一化残差 res/||Q||_1 的最大值 = {max(r[6] for r in rows):.3e}")
    print(f"|pi_fl Q|_1 的最大值 = {max(r[5] for r in rows):.3e}")


if __name__ == "__main__":
    main()
