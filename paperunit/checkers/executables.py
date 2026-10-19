"""Executable checkers: numeric re-computation, stdout/substring and exit status.

These are the v0.1 check kinds, kept deliberately small and boring.  Their job
is to make "the claimed number" and "the number this command prints" comparable
under a preregistered tolerance.
"""

from __future__ import annotations

import re
from typing import Any

from .base import CheckContext, Outcome, RunResult


def _execute(ctx: CheckContext, check: dict[str, Any]) -> RunResult:
    cmd = check.get("cmd")
    if not isinstance(cmd, str) or not cmd.strip():
        raise ValueError("check.cmd must be a non-empty string")
    timeout_s = float(check.get("timeout_s", ctx.timeout_s))
    return ctx.runner(cmd, ctx.check_dir(), timeout_s)


def _parse_number(pattern: str, stdout: str) -> float | None:
    match = re.search(pattern, stdout, re.MULTILINE)
    if match is None:
        return None
    if "value" in (match.groupdict() or {}):
        raw = match.group("value")
    elif match.groups():
        raw = match.group(1)
    else:
        raw = match.group(0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _evaluate(
    expect: dict[str, Any], run: RunResult
) -> tuple[list[dict[str, Any]], str | None]:
    """Evaluate expectation rules. Returns (results, hard_error)."""
    results: list[dict[str, Any]] = []
    hard_error: str | None = None

    numeric = expect.get("numeric_within")
    if isinstance(numeric, dict):
        pattern = numeric.get("number_regex")
        target = numeric.get("target")
        tolerance = numeric.get("tolerance", 0.0)
        if not isinstance(pattern, str) or not isinstance(target, (int, float)):
            hard_error = "invalid numeric_within spec"
        else:
            value = _parse_number(pattern, run.stdout)
            if value is None:
                hard_error = f"number not found in stdout with pattern {pattern!r}"
            else:
                passed = abs(value - float(target)) <= float(tolerance)
                results.append(
                    {
                        "rule": "numeric_within",
                        "passed": passed,
                        "detail": f"value {value} vs {target} +/- {tolerance}",
                    }
                )

    contains = expect.get("stdout_contains")
    if isinstance(contains, str):
        passed = contains in run.stdout
        results.append(
            {"rule": "stdout_contains", "passed": passed, "detail": repr(contains)}
        )

    pattern = expect.get("stdout_regex")
    if isinstance(pattern, str):
        passed = re.search(pattern, run.stdout, re.MULTILINE) is not None
        results.append(
            {"rule": "stdout_regex", "passed": passed, "detail": pattern}
        )

    exit_code = expect.get("exit_code")
    if exit_code is not None:
        passed = run.exit_code == int(exit_code)
        results.append(
            {
                "rule": "exit_code",
                "passed": passed,
                "detail": f"exit {run.exit_code} vs {exit_code}",
            }
        )

    if not results and hard_error is None:
        hard_error = "no supported expectation rules in check.expect"
    return results, hard_error


def _finish(
    run: RunResult,
    results: list[dict[str, Any]],
    hard_error: str | None,
    expect: dict[str, Any],
    comparison_mode: str = "stdout",
) -> Outcome:
    evidence: dict[str, Any] = {
        "runs": [run.summary()],
        "expectations": results,
        "comparison_mode": comparison_mode,
    }
    if run.timed_out:
        return Outcome(
            "INCONCLUSIVE",
            f"command timed out after {run.timeout_s}s",
            evidence=evidence,
        )
    if hard_error:
        return Outcome("INCONCLUSIVE", hard_error, evidence=evidence)
    if run.exit_code not in (0, None) and "exit_code" not in expect:
        return Outcome(
            "INCONCLUSIVE",
            f"command exited {run.exit_code} and no exit_code expectation was declared",
            evidence=evidence,
        )
    failed = [r for r in results if not r["passed"]]
    if failed:
        first = failed[0]
        return Outcome(
            "REFUTED",
            f"expectation failed: {first['rule']}: {first['detail']}",
            evidence=evidence,
        )
    return Outcome(
        "SUPPORTED",
        f"all {len(results)} expectation(s) passed",
        evidence=evidence,
    )


class NumericChecker:
    kind = "numeric"

    def check(self, ctx: CheckContext) -> Outcome:
        check = ctx.claim.get("check") or {}
        run = _execute(ctx, check)
        expect = check.get("expect") or {}
        results, hard_error = _evaluate(expect, run)
        return _finish(run, results, hard_error, expect)


class StdoutChecker:
    kind = "stdout"

    def check(self, ctx: CheckContext) -> Outcome:
        check = ctx.claim.get("check") or {}
        run = _execute(ctx, check)
        expect = check.get("expect") or {}
        results, hard_error = _evaluate(expect, run)
        return _finish(run, results, hard_error, expect)


class ExitChecker:
    kind = "exit"

    def check(self, ctx: CheckContext) -> Outcome:
        check = ctx.claim.get("check") or {}
        run = _execute(ctx, check)
        expect = check.get("expect") or {}
        results, hard_error = _evaluate(expect, run)
        # Only the exit status is judged; unittest timings and other stdout
        # differences must not make an honest re-run look like DRIFT.
        return _finish(run, results, hard_error, expect, comparison_mode="verdict_only")
