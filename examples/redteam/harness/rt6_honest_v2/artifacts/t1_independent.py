#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 对 T1 的独立复核（独立于 A 的 t1_stationary.py：不同路线、不同代码）。

路线：Markov chain tree theorem —— pi_j ∝ det(Q 去掉第 j 行、第 j 列)，
      在 Fraction 上精确计算 2x2 余子式后归一化；不调用任何线性方程求解。
用途：给 Q1 的 c1 一个真正的独立读数，用于 reject v1 / accept v2。
输出同时给出 |pi Q|_1（应恒为 0）与 float 残差对照。
用法：python3 artifacts/t1_independent.py [--k K]
"""
import sys
from fractions import Fraction as F

BASE = {(0, 1): F(1), (0, 2): F(1, 4), (1, 0): F(1, 2),
        (1, 2): F(2), (2, 0): F(3, 4), (2, 1): F(1, 4)}


def generator(k=0):
    rates = dict(BASE)
    if k:
        rates[(0, 1)] *= F(10) ** k
        rates[(1, 0)] /= F(10) ** k
    n = 3
    Q = [[F(0)] * n for _ in range(n)]
    for (i, j), r in rates.items():
        Q[i][j] += r
        Q[i][i] -= r
    return Q


def det(M):
    """递归行列式（仅 n<=3 时使用），Fraction 精确。"""
    n = len(M)
    if n == 1:
        return M[0][0]
    if n == 2:
        return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    return sum((-1) ** c * M[0][c] * det([row[:c] + row[c + 1:] for row in M[1:]])
               for c in range(n))


def tree_theorem(Q):
    """pi_j ∝ det(minor_jj)，用余子式（矩阵树定理的 CTMC 形式）。"""
    n = len(Q)
    w = []
    for j in range(n):
        minor = [[Q[r][c] for c in range(n) if c != j] for r in range(n) if r != j]
        w.append(det(minor))
    s = sum(w)
    return [x / s for x in w]


def main(argv):
    k = int(argv[argv.index("--k") + 1]) if "--k" in argv else 0
    Q = generator(k)
    n = len(Q)
    pi = tree_theorem(Q)
    res = sum(abs(sum(pi[i] * Q[i][j] for i in range(n))) for j in range(n))
    print(f"k = {k}")
    print("tree-theorem pi =", [str(x) for x in pi])
    print("tree-theorem |pi Q|_1 =", str(res))
    print("all entries positive =", all(x > 0 for x in pi))


if __name__ == "__main__":
    main(sys.argv[1:])
