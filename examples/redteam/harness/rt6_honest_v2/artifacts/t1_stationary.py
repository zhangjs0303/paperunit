#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1 / c1 的第二个 artifact（版本 2）。

模型：3 状态非可逆循环 CTMC，生成元 Q 的非对角元（转移速率）
    q(0,1)=1, q(0,2)=1/4, q(1,0)=1/2, q(1,2)=2, q(2,0)=3/4, q(2,1)=1/4

方法：
  (1) 解 (Q^T) pi = 0 且 sum pi = 1：用 Q 的**列**组装线性系统，
      最后一个方程换成归一化行，Fraction 精确 Gauss-Jordan → 无浮点误差。
  (2) float64 沿同一路径再解一次，报告 max|pi_float - pi_exact|_inf
      与 |pi_float Q|_1。这两个数就是 Q1/c2 预注册预测的检验对象。

可选 --k K：把 q(0,1) 与 q(1,0) 分别乘 10^K 与 10^-K，得到 T3 用的 stiff 参数族。
用法：python3 artifacts/t1_stationary.py [--k K]
"""
import sys
from fractions import Fraction as F

BASE = {(0, 1): F(1), (0, 2): F(1, 4), (1, 0): F(1, 2),
        (1, 2): F(2), (2, 0): F(3, 4), (2, 1): F(1, 4)}
N = 3


def generator(k=0, n=N):
    """rate 族 k：q(0,1) *= 10^k, q(1,0) *= 10^-k（k=0 时即 BASE）。"""
    rates = dict(BASE)
    if k:
        rates[(0, 1)] = rates[(0, 1)] * F(10) ** k
        rates[(1, 0)] = rates[(1, 0)] / F(10) ** k
    Q = [[F(0)] * n for _ in range(n)]
    for (i, j), r in rates.items():
        Q[i][j] += r
        Q[i][i] -= r
    return Q


def system(Q):
    """返回 (A, b)：A pi = b 即 pi Q = 0（前 n-1 个方程）+ sum pi = 1。"""
    n = len(Q)
    A = [[Q[i][j] for i in range(n)] for j in range(n)]  # A[j][i] = Q[i][j] → (Q^T) pi = 0
    A = A[:-1] + [[F(1)] * n]
    b = [F(0)] * (n - 1) + [F(1)]
    return A, b


def gauss(A, b):
    """Fraction / float 通用 Gauss-Jordan（部分主元用绝对值最大者）。"""
    n = len(A)
    M = [list(row) + [b[r]] for r, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]
        M[c] = [x / pv for x in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def main(argv):
    k = 0
    if "--k" in argv:
        k = int(argv[argv.index("--k") + 1])
    Q = generator(k)
    n = len(Q)

    A_ex, b_ex = system(Q)
    pi_ex = gauss(A_ex, b_ex)                                          # Fraction 精确
    pi_fl = gauss([[float(x) for x in row] for row in A_ex],
                  [float(x) for x in b_ex])                            # float64 同路线
    res_ex = sum(abs(sum(pi_ex[i] * Q[i][j] for i in range(n))) for j in range(n))
    Qf = [[float(x) for x in row] for row in Q]
    res_fl = sum(abs(sum(pi_fl[i] * Qf[i][j] for i in range(n))) for j in range(n))
    dev = max(abs(a - b) for a, b in zip(pi_fl, [float(x) for x in pi_ex]))
    kappa = max(float(x) for x in pi_ex) / min(float(x) for x in pi_ex)

    # 循环亲和势（非可逆性证据）：0→1→2→0 与反向的速率乘机之比
    fwd = BASE[(0, 1)] * BASE[(1, 2)] * BASE[(2, 0)]
    bwd = BASE[(0, 2)] * BASE[(2, 1)] * BASE[(1, 0)]
    print(f"k = {k}")
    print("exact pi =", [str(x) for x in pi_ex])
    print("exact |pi Q|_1 =", float(res_ex))
    print("float pi =", [f"{x:.17g}" for x in pi_fl])
    print("max|dpi|_inf =", f"{dev:.6e}")
    print("float |pi Q|_1 =", f"{res_fl:.6e}")
    print("kappa_pi (max/min) =", f"{kappa:.6e}")
    print("cycle_ratio (prod_fwd/prod_bwd) =", float(fwd / bwd), " (ln =", f"{float(__import__('math').log(fwd / bwd)):.6f})")


if __name__ == "__main__":
    main(sys.argv[1:])
