#!/usr/bin/env python3
"""Prefix-invariance audit for a single-head attention mask.

The audit runs two forward passes with identical weights:

1. on the original fixture input;
2. on a copy whose suffix tokens (positions ``>= prefix_len``) were replaced.

A correct causal mask must leave the prefix outputs (positions ``0..prefix_len-1``)
unchanged: a token cannot attend to the future, so the future cannot influence
it.  This is the prefix-invariance idea discussed in "The Mask Is Not the
Model" (arXiv:2608.22876).

The command prints one JSON object on its last stdout line and always exits 0;
the verdict is the payload, not the exit status (see the paperunit external
checker protocol).  This is a *test-based* audit of one fixed fixture input -
evidence about this input, not a proof over all inputs.  The Z3-based symbolic
version is in ``examples/z3_demo``.

Usage::

    python3 code/audit_mask.py --variant causal_ok
    python3 code/audit_mask.py --variant causal_broken
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from attention import VARIANTS, make_input, make_weights

REFERENCE = "The Mask Is Not the Model (arXiv:2608.22876)"
AUDIT_TYPE = (
    "test-based audit of one fixed fixture input via two-forward prefix "
    "invariance; not a formal proof"
)


def change_suffix(tokens: list[list[float]], prefix_len: int) -> list[list[float]]:
    """Return a copy where every token at position >= prefix_len is replaced."""
    changed: list[list[float]] = []
    for position, row in enumerate(tokens):
        if position < prefix_len:
            changed.append(list(row))
        else:
            # A fixed affine remap guarantees a different suffix; the fixture
            # values are multiples of 1/9, so no value maps to itself here.
            changed.append([round(-2.0 * value + 0.25, 12) for value in row])
    return changed


def prefix_max_abs_diffs(
    before: list[list[float]], after: list[list[float]], prefix_len: int
) -> list[float]:
    """Per-prefix-position max abs difference between two forward passes."""
    diffs: list[float] = []
    for position in range(prefix_len):
        row_diff = max(
            abs(a - b) for a, b in zip(before[position], after[position])
        )
        diffs.append(row_diff)
    return diffs


def build_payload(
    variant: str,
    prefix_len: int,
    tolerance: float,
    seed: int,
) -> dict[str, Any]:
    """Run the two-forward prefix-invariance test and return the JSON payload."""
    forward = VARIANTS[variant]
    weights = make_weights(seed)
    tokens = make_input(seed)
    if not 0 < prefix_len < len(tokens):
        raise ValueError(
            f"prefix_len must be in 1..{len(tokens) - 1}, got {prefix_len}"
        )
    changed_suffix = list(range(prefix_len, len(tokens)))

    before = forward(tokens, weights)
    modified_tokens = change_suffix(tokens, prefix_len)
    after = forward(modified_tokens, weights)

    # Guard against a degenerate fixture where nothing was actually changed.
    if modified_tokens == tokens:
        raise ValueError("suffix replacement did not change any token")

    diffs = prefix_max_abs_diffs(before, after, prefix_len)
    first_violation = next(
        (position for position, diff in enumerate(diffs) if diff > tolerance),
        None,
    )
    max_diff = max(diffs)

    evidence: dict[str, Any] = {
        "variant": variant,
        "seed": seed,
        "n_tokens": len(tokens),
        "prefix_len": prefix_len,
        "changed_suffix_positions": changed_suffix,
        "tolerance": tolerance,
        "prefix_max_abs_diffs": [round(diff, 12) for diff in diffs],
        "max_abs_diff": round(max_diff, 12),
        "method": (
            "two forward passes with identical weights; replace suffix tokens; "
            "compare prefix hidden states"
        ),
        "reference": REFERENCE,
        "audit_type": AUDIT_TYPE,
    }

    if first_violation is None:
        return {
            "verdict": "SUPPORTED",
            "reason": (
                f"prefix invariance held: replacing tokens at positions "
                f"{changed_suffix[0]}..{changed_suffix[-1]} left positions "
                f"0..{prefix_len - 1} unchanged (max abs diff {max_diff:.3g} "
                f"<= tolerance {tolerance:g})."
            ),
            "uncertainty": None,
            "evidence": evidence,
        }

    counterexample = {
        "position": first_violation,
        "abs_diff": round(diffs[first_violation], 12),
        "prefix_output_before": [round(value, 12) for value in before[first_violation]],
        "prefix_output_after": [round(value, 12) for value in after[first_violation]],
        "changed_suffix_positions": changed_suffix,
        "description": (
            f"changing tokens at positions {changed_suffix[0]}.."
            f"{changed_suffix[-1]} changed the output at position "
            f"{first_violation}, so future information leaks into the prefix"
        ),
    }
    evidence["counterexample"] = counterexample
    evidence["first_violation_position"] = first_violation
    return {
        "verdict": "REFUTED",
        "reason": (
            f"prefix invariance violated at position {first_violation}: "
            f"changing suffix tokens changed the prefix output by "
            f"{diffs[first_violation]:.6g} (> tolerance {tolerance:g}); the "
            "mask does not block attention to future positions."
        ),
        "uncertainty": None,
        "evidence": evidence,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=sorted(VARIANTS),
        default="causal_ok",
        help="mask variant to audit (default: causal_ok)",
    )
    parser.add_argument(
        "--prefix-len",
        type=int,
        default=3,
        help="number of prefix positions compared (default: 3)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-9,
        help="absolute tolerance for prefix differences (default: 1e-9)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="fixture seed for weights and input (default: 0)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = build_payload(
            variant=args.variant,
            prefix_len=args.prefix_len,
            tolerance=args.tolerance,
            seed=args.seed,
        )
    except ValueError as exc:
        payload = {
            "verdict": "INCONCLUSIVE",
            "reason": f"audit could not run: {exc}",
            "uncertainty": None,
            "evidence": {"variant": args.variant, "audit_type": AUDIT_TYPE},
        }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
