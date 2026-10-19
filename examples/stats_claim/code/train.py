#!/usr/bin/env python3
"""Deterministic synthetic seed sweep for the paperunit statistics demo.

This is a fixture, not a real experiment and not a benchmark.  A two-feature
threshold classifier is fitted on a hardcoded synthetic dataset; the only
source of seed-to-seed variation is a fixed number of label flips applied at
the extremes of each class.  There is no numpy, no wall clock and no entropy:
a given seed always prints byte-identical output.

The six documented seeds are tuned so the sweep gives approximately

    mean accuracy = 0.918, sample SD = 0.0038

which is the resolution the example audit compares against two different
claims (one assertable, one too coarse to test at this sample size).
"""
from __future__ import annotations

import argparse

N = 500

# Number of labels flipped away from the deterministic sign rule.  The flips
# are placed at the extremes of each class, so a threshold shift that would
# "fix" a flipped point has to misclassify a whole block of clean points:
# the fitted threshold therefore keeps the expected error count.
_FLIPS_BY_SEED = (42, 40, 43, 39, 43, 39)


def flip_count(seed: int) -> int:
    """Number of label flips for ``seed`` (fixed for the six documented seeds)."""
    if 0 <= seed < len(_FLIPS_BY_SEED):
        return _FLIPS_BY_SEED[seed]
    # Deterministic fallback so arbitrary seeds still run; only the documented
    # seeds 0-5 are part of the demo.
    return 39 + (seed * 7) % 5


def make_dataset(seed: int) -> list[list[float | int]]:
    """Build the synthetic rows: [x1, x2, score, label]."""
    rows: list[list[float | int]] = []
    for index in range(N):
        x1 = ((index * 37 + seed) % 101 - 50) / 50.0
        x2 = ((index * 61 + seed * 3) % 97 - 48) / 48.0
        score = x1 + x2
        label = 1 if score > 0.0 else 0
        rows.append([x1, x2, score, label])

    flips = flip_count(seed)
    negative_indices = [i for i, row in enumerate(rows) if row[3] == 0]
    positive_indices = [i for i, row in enumerate(rows) if row[3] == 1]
    # Negative rows with the lowest scores and positive rows with the highest:
    # flipping labels there creates irreducible classification error.
    negative_indices.sort(key=lambda i: float(rows[i][2]))
    positive_indices.sort(key=lambda i: float(rows[i][2]))
    n_negative_flips = flips // 2
    n_positive_flips = flips - n_negative_flips
    for index in negative_indices[:n_negative_flips]:
        rows[index][3] = 1 - int(rows[index][3])
    for index in positive_indices[-n_positive_flips:]:
        rows[index][3] = 1 - int(rows[index][3])
    return rows


def fit_threshold(rows: list[list[float | int]]) -> tuple[float, int]:
    """Grid-search the threshold ``score >= t`` that maximises training accuracy."""
    thresholds = sorted({float(row[2]) for row in rows})
    best_threshold = thresholds[0]
    best_correct = -1
    for threshold in thresholds:
        correct = 0
        for row in rows:
            predicted = 1 if float(row[2]) >= threshold else 0
            if predicted == int(row[3]):
                correct += 1
        if correct > best_correct:
            best_threshold = threshold
            best_correct = correct
    return best_threshold, best_correct


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Synthetic deterministic seed-sweep fixture (not a real experiment)."
    )
    parser.add_argument("--seed", type=int, default=0, help="seed for the synthetic dataset")
    args = parser.parse_args(argv)

    rows = make_dataset(args.seed)
    threshold, correct = fit_threshold(rows)
    accuracy = correct / len(rows)
    print(f"samples={len(rows)}")
    print(f"accuracy={accuracy:.4f}")
    print(f"seed={args.seed}")
    print(f"flips={flip_count(args.seed)}")
    print(f"threshold={threshold:.6f}")


if __name__ == "__main__":
    main()
