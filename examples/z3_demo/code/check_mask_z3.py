#!/usr/bin/env python3
"""Symbolic check of a causal-mask construction with z3 (optional dependency).

The mask construction is encoded as a predicate ``allows(i, j)`` over positions.
Positions are 5-bit unsigned bit-vectors, so the quantified property ranges over
all pairs ``0 <= i, j < 32``, i.e. all sequence lengths ``T <= 32``:

    for every i < j: attention from position i to position j is blocked.

The checker asks z3 for a *counterexample* to that property (a future edge that
is admitted).  For the correct causal mask the search is unsatisfiable; for the
deliberately broken mask it is satisfiable, which yields a concrete
counterexample as REFUTED evidence.  This is refutation by counterexample
finding, not by build failure.

z3 is an optional extra (``pip install 'paperunit[z3]'``).  When it is not
installed the script prints an INCONCLUSIVE payload and exits 0, so a missing
solver is never mistaken for a refutation.  The command always exits 0: the
verdict is the JSON payload on the last stdout line, not the exit status.

The prefix-invariance motivation comes from "The Mask Is Not the Model"
(arXiv:2608.22876); the companion test-based fixture is ``examples/causal_mask``.

Usage::

    python3 code/check_mask_z3.py --variant correct
    python3 code/check_mask_z3.py --variant broken
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

REFERENCE = "The Mask Is Not the Model (arXiv:2608.22876)"
PROPERTY = (
    "for every 0 <= i < j < 32: attention from position i to position j is "
    "blocked (no token may attend to a future position)"
)
AUDIT_TYPE = "symbolic SMT check of the encoded mask construction; counterexample-based"

#: Positions are 5-bit unsigned bit-vectors: 0..31, covering all T <= 32.
POSITION_BITS = 5
MAX_POSITION = 2**POSITION_BITS  # 32


def payload_without_z3(variant: str) -> dict[str, Any]:
    return {
        "verdict": "INCONCLUSIVE",
        "reason": (
            "z3-solver is not installed, so the symbolic mask check was "
            "skipped. Install the optional extra with: pip install "
            "'paperunit[z3]'. A missing solver is not evidence about the "
            "claim."
        ),
        "uncertainty": None,
        "evidence": {
            "variant": variant,
            "z3_available": False,
            "property": PROPERTY,
            "position_encoding": (
                f"{POSITION_BITS}-bit unsigned bit-vectors, positions "
                f"0..{MAX_POSITION - 1} (covers T <= {MAX_POSITION})"
            ),
            "reference": REFERENCE,
            "audit_type": AUDIT_TYPE,
        },
    }


def build_allows_predicate(variant: str, position_i: Any, position_j: Any) -> Any:
    """Encode the mask construction as a z3 boolean predicate.

    ``correct``: position i may attend to j iff j <= i (standard causal mask).
    ``broken``:  every position may attend to every other position (no mask).
    """
    import z3

    if variant == "correct":
        return z3.ULE(position_j, position_i)
    if variant == "broken":
        return z3.BoolVal(True)
    raise ValueError(f"unknown variant: {variant!r}")


def verify_with_z3(variant: str) -> dict[str, Any]:
    """Search for a future attention edge that the mask incorrectly admits."""
    import z3

    position_i = z3.BitVec("i", POSITION_BITS)
    position_j = z3.BitVec("j", POSITION_BITS)

    solver = z3.Solver()
    # Counterexample shape: i < j (unsigned) and the mask allows i -> j.
    solver.add(z3.ULT(position_i, position_j))
    solver.add(build_allows_predicate(variant, position_i, position_j))

    evidence: dict[str, Any] = {
        "variant": variant,
        "property": PROPERTY,
        "position_encoding": (
            f"{POSITION_BITS}-bit unsigned bit-vectors, positions "
            f"0..{MAX_POSITION - 1} (covers T <= {MAX_POSITION})"
        ),
        "solver": "z3",
        "z3_version": z3.get_version_string(),
        "reference": REFERENCE,
        "audit_type": AUDIT_TYPE,
    }
    result = solver.check()
    evidence["solver_result"] = str(result)

    if result == z3.unsat:
        return {
            "verdict": "SUPPORTED",
            "reason": (
                "z3 proved the property (unsat): for every pair of positions "
                f"0 <= i < j < {MAX_POSITION} the causal mask blocks attention "
                f"from i to j, covering all sequence lengths T <= {MAX_POSITION}."
            ),
            "uncertainty": None,
            "evidence": evidence,
        }

    if result == z3.sat:
        model = solver.model()
        counterexample_i = model.eval(position_i, model_completion=True).as_long()
        counterexample_j = model.eval(position_j, model_completion=True).as_long()
        evidence["counterexample"] = {
            "i": counterexample_i,
            "j": counterexample_j,
            "description": (
                f"position {counterexample_i} is allowed to attend to future "
                f"position {counterexample_j}"
            ),
        }
        return {
            "verdict": "REFUTED",
            "reason": (
                "z3 found a counterexample (sat): the mask allows position "
                f"{counterexample_i} to attend to future position "
                f"{counterexample_j}, so the construction is not causal."
            ),
            "uncertainty": None,
            "evidence": evidence,
        }

    return {
        "verdict": "INCONCLUSIVE",
        "reason": f"z3 returned unknown ({result}); the mask property was not decided.",
        "uncertainty": {"solver_result": str(result)},
        "evidence": evidence,
    }


def check_variant(variant: str) -> dict[str, Any]:
    try:
        import z3  # noqa: F401 - availability probe only
    except ImportError:
        return payload_without_z3(variant)
    return verify_with_z3(variant)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=("correct", "broken"),
        default="correct",
        help="mask construction to check (default: correct)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = check_variant(args.variant)
    except Exception as exc:  # noqa: BLE001 - the protocol needs a JSON line either way
        payload = {
            "verdict": "INCONCLUSIVE",
            "reason": f"z3 check crashed with {type(exc).__name__}: {exc}",
            "uncertainty": None,
            "evidence": {
                "variant": args.variant,
                "z3_available": True,
                "reference": REFERENCE,
                "audit_type": AUDIT_TYPE,
            },
        }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
