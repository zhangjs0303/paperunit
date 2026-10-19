"""External checker: delegate one claim to an arbitrary command.

This is the generic extension protocol of paperunit.  Any tool that can decide
something about a claim (an SMT solver, a property-based tester, a simulation
harness, ...) can be plugged in without writing Python-checker code.

Protocol
--------
The command runs inside :meth:`CheckContext.check_dir` (the claim may set
``check.cwd``) and must print its verdict as a single JSON object on the last
non-empty stdout line::

    {"verdict": "SUPPORTED" | "REFUTED" | "INCONCLUSIVE",
     "reason": "short human-readable explanation",
     "uncertainty": {...} | null,
     "evidence": {...}}

Anything printed before that line is treated as logging and ignored.

Trust rules
-----------
* A timeout or a non-zero exit status is INCONCLUSIVE.  A crashed external
  tool cannot adjudicate a claim, and a tool failure is never evidence against
  the paper.
* A missing or malformed verdict line is INCONCLUSIVE, never REFUTED.
* REFUTED is only accepted when the tool itself declares it (typically after
  finding a concrete counterexample); the checker does not infer refutations
  from error output.

This module is the integration point used by the z3 and causal-mask demos.
"""

from __future__ import annotations

import json
from typing import Any

from .base import CheckContext, Outcome, truncate

#: Verdicts an external command is allowed to declare.  NOT_RUN is a paperunit
#: bookkeeping state (no executable check), not something a tool can report.
EXTERNAL_VERDICTS: tuple[str, ...] = ("SUPPORTED", "REFUTED", "INCONCLUSIVE")


def _last_nonempty_line(text: str) -> str:
    """Return the last line containing non-whitespace characters, or ''."""
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _parse_payload(stdout: str) -> tuple[dict[str, Any] | None, str]:
    """Parse the external verdict payload from stdout.

    Returns ``(payload, "")`` on success and ``(None, error_message)`` on
    failure.  Only the last non-empty line is considered; that line has to be
    a JSON object.
    """
    line = _last_nonempty_line(stdout)
    if not line:
        return None, "external check printed no stdout"
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        return None, f"last non-empty stdout line is not valid JSON ({exc.msg})"
    if not isinstance(payload, dict):
        return None, (
            "external payload must be a JSON object, got "
            f"{type(payload).__name__}"
        )
    return payload, ""


def _timeout_from_spec(spec: dict[str, Any], default: float) -> float:
    """Resolve a positive timeout value, falling back to ``default``."""
    raw = spec.get("timeout_s", default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(default)
    return value if value > 0 else float(default)


class ExternalChecker:
    """Run a claim's external command and read the declared verdict.

    Claim shape::

        {"id": "P1", "kind": "external",
         "text": "...",
         "check": {"cmd": "python3 code/check.py",
                   "cwd": "optional/subdir",
                   "timeout_s": 60}}
    """

    kind = "external"

    def check(self, ctx: CheckContext) -> Outcome:
        claim = ctx.claim
        spec = claim.get("check")
        spec = spec if isinstance(spec, dict) else {}

        cmd = spec.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    "external check is missing 'check.cmd'; there is no "
                    "command to run for this claim."
                ),
                evidence={"claim_id": claim.get("id")},
            )

        cmd = cmd.strip()
        timeout_s = _timeout_from_spec(spec, ctx.timeout_s)
        cwd = ctx.check_dir()
        run = ctx.runner(cmd, cwd, timeout_s)
        evidence: dict[str, Any] = {"run": run.summary()}

        if run.timed_out:
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    f"external check timed out after {timeout_s:g}s; a "
                    "timed-out run cannot adjudicate the claim."
                ),
                evidence=evidence,
            )

        if run.exit_code != 0:
            evidence["stderr_excerpt"] = truncate(run.stderr, 2000)
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    f"external check exited with code {run.exit_code}; a "
                    "crashed or failed tool is not evidence for or against "
                    "the claim."
                ),
                evidence=evidence,
            )

        payload, parse_error = _parse_payload(run.stdout)
        if payload is None:
            evidence["parse_error"] = parse_error
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=f"external check produced no readable verdict: {parse_error}",
                evidence=evidence,
            )

        evidence["parsed"] = payload
        verdict = payload.get("verdict")
        if not isinstance(verdict, str) or verdict not in EXTERNAL_VERDICTS:
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    f"external check returned an invalid verdict {verdict!r}; "
                    f"expected one of {list(EXTERNAL_VERDICTS)}."
                ),
                evidence=evidence,
            )

        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    "external check returned no non-empty 'reason' string; "
                    "an unexplained verdict is treated as inconclusive."
                ),
                evidence=evidence,
            )

        uncertainty: dict[str, Any] | None = None
        raw_uncertainty = payload.get("uncertainty")
        if isinstance(raw_uncertainty, dict):
            uncertainty = raw_uncertainty
        elif raw_uncertainty is not None:
            evidence["invalid_uncertainty"] = raw_uncertainty

        return Outcome(
            verdict=verdict,
            reason=reason.strip(),
            evidence=evidence,
            uncertainty=uncertainty,
        )


#: Convenience instance for registry code that expects a checker object.
CHECKER = ExternalChecker()
