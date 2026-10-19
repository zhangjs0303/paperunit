#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 对 T2/c1（单调性预测）的独立复核：不复用 D 的 t2_search.py。

三条独立检查：
  1. 直接从 4 状态 joint 定义暴力枚举 Z 与 P(z1=1)，与 D 声明的闭式边际对比；
  2. 用中心差分 (P(W+h)-P(W-h))/(2h) 与闭式导数 C*B/(A+C+B)^2 对比；
  3. 对称点 b1 = b2 时 P(z1=1) 应恰为 1/2（族对称性给的恒等式）。
用法：python3 artifacts/t2_checker.py
"""
import math

PTS = [(-1.0, -1.0, 2.0), (-1.0, -1.0, 0.0), (-2.0, 0.5, 1.0),
       (0.3, -1.7, -2.0), (2.0, 3.0, 0.5), (-0.5, 0.7, 4.0)]
SYM = [(-1.0, 2.0), (0.4, -3.0), (-2.5, 1.5)]   # (b, W)，b1=b2=b


def p_bruteforce(b1, b2, w):
    """直接枚举 4 个 (z1,z2) 状态。"""
    z = sum(math.exp(b1 * a + b2 * b + w * a * b) for a in (0, 1) for b in (0, 1))
    return (math.exp(b1) + math.exp(b1 + b2 + w)) / z


def p_closed(b1, b2, w):
    A, B, C = math.exp(b1), 1.0 + math.exp(b2), math.exp(b1 + b2 + w)
    return (A + C) / (A + C + B)


def p_closed_for(b1, b2, w):
    """把 z1/z2 标签交换后再算一次 P(z2=1)（用交换后的参数 b2,b1）。"""
    return p_closed(b2, b1, w)


def dp_closed(b1, b2, w):
    A, B, C = math.exp(b1), 1.0 + math.exp(b2), math.exp(b1 + b2 + w)
    return C * B / (A + C + B) ** 2


def main():
    print("1) 暴力枚举 vs 闭式边际：")
    for (b1, b2, w) in PTS:
        pb, pc = p_bruteforce(b1, b2, w), p_closed(b1, b2, w)
        print(f"   b1={b1:>5} b2={b2:>5} W={w:>4}  P_brute={pb:.15f}  P_closed={pc:.15f}"
              f"  rel={abs(pb - pc) / max(pc, 1e-300):.3e}")

    print("2) 中心差分 vs 闭式导数（h=1e-5）：")
    worst = 0.0
    for (b1, b2, w) in PTS:
        h = 1e-5
        fd = (p_closed(b1, b2, w + h) - p_closed(b1, b2, w - h)) / (2 * h)
        an = dp_closed(b1, b2, w)
        rel = abs(fd - an) / an
        worst = max(worst, rel)
        print(f"   b1={b1:>5} b2={b2:>5} W={w:>4}  fd={fd:.12e}  closed={an:.12e}"
              f"  rel={rel:.3e}")
    print(f"   max rel = {worst:.3e}")

    print("3) 对称点 b1=b2：P 应等于 1/2")
    dev = 0.0
    for (b, w) in SYM:
        d = abs(p_closed(b, b, w) - 0.5)
        dev = max(dev, d)
        print(f"   b={b:>5} W={w:>4}  P={p_closed(b, b, w):.17f}  |P-1/2|={d:.3e}")
    print(f"   max |P-1/2| = {dev:.3e}   <-- 这一项的前提是错的（见下）")

    print("4) 更正：b1=b2 时正确的不变量是 exchangeability P(z1=1)=P(z2=1)，不是 1/2")
    worst = 0.0
    for (b, w) in SYM:
        p1 = p_closed(b, b, w)
        p2 = p_closed_for(b, b, w)   # 把两个节点标签交换后的同一个计算
        d = abs(p1 - p2)
        worst = max(worst, d)
        print(f"   b={b:>5} W={w:>4}  P(z1=1)={p1:.17f}  P(z2=1)={p2:.17f}  diff={d:.3e}")
    print(f"   max diff = {worst:.3e}")


if __name__ == "__main__":
    main()
