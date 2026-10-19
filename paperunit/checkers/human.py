"""Human review check.

A ``human`` claim records that judgement is not mechanically decidable.  It is
explicitly NOT_RUN: the audit does not pretend a human note is evidence, and it
does not score the reviewer.
"""

from __future__ import annotations

from .base import CheckContext, Outcome


class HumanChecker:
    kind = "human"

    def check(self, ctx: CheckContext) -> Outcome:
        check = ctx.claim.get("check") or {}
        note = check.get("note") or ctx.claim.get("text") or ""
        return Outcome(
            "NOT_RUN",
            "human review only; no executable check, no score",
            evidence={"note": note, "is_executable": False},
        )
