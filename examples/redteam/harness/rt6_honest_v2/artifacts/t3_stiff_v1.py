#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q3 / c1 的 artifact（版本 1，保留为失败证据；由 A 在 v6 reject）。

问题：把 Q1 用的 q(0,1) 乘 10^k、q(1,0) 除 10^k 之后，
      Q1/c2 注册的绝对阈值 max|dpi|_inf < 1e-13 是否还成立？

版本说明：本版用 math.isclose(rel_tol=1e-13, abs_tol=0.0) 做判定。
对 k>=1，稳态分布里 pi_0 很小，rel_tol 给出的容差比 abs 阈值宽很多
（甚至宽到若干个数量级），于是每个 k 都打印 PASS。
真实输出见 artifacts/out/t3_stiff_v1.out.txt：全部 PASS——与 A 的独立读数矛盾。
A 的 reject 理由：criterion 注册的是**绝对**阈值，isclose(rel_tol) 不是同一判据。
"""
import math
import sys
from fractions import Fraction as F

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from t1_stationary import generator, gauss, system  # 复用 T1/v2 的模型与解算器


def one(k):
    Q = generator(k)
    n = len(Q)
    A_ex, b_ex = system(Q)
    pi_ex = gauss(A_ex, b_ex)
    pi_fl = gauss([[float(x) for x in row] for row in A_ex], [float(x) for x in b_ex])
    dev = max(abs(a - float(b)) for a, b in zip(pi_fl, pi_ex))
    ok = all(math.isclose(pi_fl[i], float(pi_ex[i]), rel_tol=1e-13, abs_tol=0.0)
             for i in range(n))
    return dev, ok


def main():
    n_break = 0
    for k in range(8):
        dev, ok = one(k)
        print(f"k = {k}  max|dpi|_inf = {dev:.6e}  isclose(rel_tol=1e-13) -> "
              f"{'PASS' if ok else 'FAIL'}")
        n_break += 0 if ok else 1
    print(f"isclose(rel_tol=1e-13) 判定下阈值的突破点个数 = {n_break}（0 表示全部 PASS）")


if __name__ == "__main__":
    main()
