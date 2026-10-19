#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1 / c1 的第一个 artifact（版本 1，保留作为失败证据，未删除）。

模型：3 状态非可逆循环 CTMC，生成元 Q 的非对角元（转移速率）
    q(0,1)=1, q(0,2)=1/4, q(1,0)=1/2, q(1,2)=2, q(2,0)=3/4, q(2,1)=1/4

版本说明：本版把 (Q 去掉最后一行 + 归一化行) 当作线性系统直接解，
求到的是 Q x = 0 的右零向量，而不是 pi Q = 0（左零向量）的稳态分布。
真实运行输出见 artifacts/out/t1_v1_transpose.out.txt，|pi Q|_1 明显不为 0，
由 B 在 v1（reject）中指出。
"""
from fractions import Fraction as F

RATES = {(0, 1): F(1), (0, 2): F(1, 4), (1, 0): F(1, 2),
         (1, 2): F(2), (2, 0): F(3, 4), (2, 1): F(1, 4)}
N = 3


def generator(rates, n=N):
    """由 off-diagonal 速率构造生成元（对角元 = -行和）。"""
    Q = [[F(0)] * n for _ in range(n)]
    for (i, j), r in rates.items():
        Q[i][j] += r
        Q[i][i] -= r
    return Q


def gauss_fraction(A, b):
    """Fraction 精确 Gauss-Jordan，返回解；不做数值稳定性处理（精确算术不需要）。"""
    n = len(A)
    M = [list(row) + [b[r]] for r, row in enumerate(A)]
    for c in range(n):
        p = next(r for r in range(c, n) if M[r][c] != 0)
        M[c], M[p] = M[p], M[c]
        pv = M[c][c]
        M[c] = [x / pv for x in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def residual_l1(pi, Q):
    """|pi Q|_1（精确分数，转 float 打印）。"""
    return sum(abs(sum(pi[i] * Q[i][j] for i in range(len(Q)))) for j in range(len(Q)))


def main():
    Q = generator(RATES)
    # BUG（v1）：这里用的是 Q 的行，求到的是右零向量
    A = [row[:] for row in Q[:-1]] + [[F(1)] * N]
    b = [F(0)] * (N - 1) + [F(1)]
    pi = gauss_fraction(A, b)
    print("v1 pi =", [str(x) for x in pi])
    print("v1 sum pi =", str(sum(pi)))
    print("v1 |pi Q|_1 =", float(residual_l1(pi, Q)))


if __name__ == "__main__":
    main()
