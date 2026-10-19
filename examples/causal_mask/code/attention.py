"""A tiny deterministic single-head attention implementation in pure Python.

Two mask variants are exposed, with identical weights:

* :func:`causal_ok`     - the standard causal mask: position ``i`` may attend
  only to positions ``j <= i``.
* :func:`causal_broken` - no causal mask at all: every position attends to
  every token, so future tokens leak into prefix representations.

The prefix-invariance audit in ``audit_mask.py`` follows the idea described in
"The Mask Is Not the Model" (arXiv:2608.22876): for a model with a correct
causal mask, replacing the tokens after position ``k`` must leave the hidden
states at positions ``0..k`` unchanged.  This is a *test-based* audit of one
fixed fixture input, not a proof; Z3-based symbolic checking lives in the
sibling ``z3_demo`` example.

Everything here is deterministic: no wall-clock time, no global RNG state, and
a fixed seed for the weight matrix.
"""

from __future__ import annotations

import math
import random
from typing import Any

D_MODEL = 4
N_TOKENS = 6

Matrix = list[list[float]]
Weights = dict[str, Matrix]


def make_weights(seed: int = 0, d_model: int = D_MODEL) -> Weights:
    """Deterministic pseudo-random projection matrices (seeded RNG)."""
    rng = random.Random(seed)

    def matrix() -> Matrix:
        return [[rng.uniform(-1.0, 1.0) for _ in range(d_model)] for _ in range(d_model)]

    return {
        "wq": matrix(),
        "wk": matrix(),
        "wv": matrix(),
        "wo": matrix(),
    }


def make_input(seed: int = 0, n_tokens: int = N_TOKENS, d_model: int = D_MODEL) -> Matrix:
    """Deterministic fixture input: small integer-derived floats in [-1, 1]."""
    return [
        [
            ((t * 7 + d * 13 + seed * 3) % 19 - 9) / 9.0
            for d in range(d_model)
        ]
        for t in range(n_tokens)
    ]


def _matvec(vector: list[float], matrix: Matrix) -> list[float]:
    return [
        sum(vector[row] * matrix[row][col] for row in range(len(vector)))
        for col in range(len(matrix[0]))
    ]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _softmax(scores: list[float]) -> list[float]:
    peak = max(scores)
    exponents = [math.exp(score - peak) for score in scores]
    total = sum(exponents)
    return [value / total for value in exponents]


def forward(
    tokens: Matrix,
    weights: Weights,
    *,
    causal: bool = True,
    d_model: int = D_MODEL,
) -> Matrix:
    """Single-head attention forward pass.

    With ``causal=True`` the attention scores for ``j > i`` are set to the
    sentinel ``-1e30`` before the softmax, which yields exactly 0.0 probability
    for future positions.  With ``causal=False`` the full bidirectional
    attention matrix is used.
    """
    queries = [_matvec(row, weights["wq"]) for row in tokens]
    keys = [_matvec(row, weights["wk"]) for row in tokens]
    values = [_matvec(row, weights["wv"]) for row in tokens]
    scale = math.sqrt(d_model)
    n_tokens = len(tokens)

    outputs: Matrix = []
    for position in range(n_tokens):
        scores: list[float] = []
        for other in range(n_tokens):
            if causal and other > position:
                scores.append(-1e30)
            else:
                scores.append(_dot(queries[position], keys[other]) / scale)
        probabilities = _softmax(scores)
        context = [
            sum(probabilities[other] * values[other][dim] for other in range(n_tokens))
            for dim in range(d_model)
        ]
        outputs.append(_matvec(context, weights["wo"]))
    return outputs


def causal_ok(tokens: Matrix, weights: Weights) -> Matrix:
    """Correct causal mask: position i attends only to positions j <= i."""
    return forward(tokens, weights, causal=True)


def causal_broken(tokens: Matrix, weights: Weights) -> Matrix:
    """Broken variant: the causal mask is missing entirely."""
    return forward(tokens, weights, causal=False)


VARIANTS: dict[str, Any] = {
    "causal_ok": causal_ok,
    "causal_broken": causal_broken,
}
