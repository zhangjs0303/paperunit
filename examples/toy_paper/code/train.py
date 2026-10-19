#!/usr/bin/env python3
"""Deterministic synthetic toy experiment for the paperaudit demo.

A 2-feature threshold classifier is trained on a hardcoded synthetic dataset.
No third-party packages, no randomness at run time, and no wall-clock benchmark:
the training time printed below is a fixed value so that the audit's stdout hash
is reproducible. This is a fixture, not a real experiment.
"""
from __future__ import annotations

N = 500
SEED = 0
# Deterministic label noise: 41 of 500 labels are flipped, so the best
# threshold reaches 459/500 = 0.918 rather than 1.0.
FLIP_INDICES = frozenset(range(8, N, 12))


def make_dataset() -> list[tuple[float, float, int, float]]:
    rows: list[tuple[float, float, int, float]] = []
    for i in range(N):
        x1 = ((i * 37 + SEED) % 101 - 50) / 50.0
        x2 = ((i * 61 + SEED * 3) % 97 - 48) / 48.0
        score = x1 + x2
        label = 1 if score > 0.0 else 0
        if i in FLIP_INDICES:
            label = 1 - label
        rows.append((x1, x2, label, score))
    return rows


def fit_threshold(rows: list[tuple[float, float, int, float]]) -> tuple[float, int]:
    best_threshold, best_correct = 0.0, -1
    for threshold in sorted({row[3] for row in rows}):
        correct = sum(1 for _, _, label, score in rows if (1 if score >= threshold else 0) == label)
        if correct > best_correct:
            best_threshold, best_correct = threshold, correct
    return best_threshold, best_correct


def main() -> None:
    rows = make_dataset()
    threshold, correct = fit_threshold(rows)
    accuracy = correct / len(rows)
    print(f"samples={len(rows)}")
    print(f"accuracy={accuracy:.3f}")
    # Fixed synthetic timing; measuring wall clock would break reproducibility.
    print("train_seconds=4.200")
    print(f"seed={SEED}")
    print(f"threshold={threshold:.6f}")


if __name__ == "__main__":
    main()
