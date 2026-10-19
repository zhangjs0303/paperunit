"""Statistics checker: re-run a metric over a preregistered seed sweep.

One ``kind: "statistics"`` claim binds a *mean* claim (for example "the mean
test accuracy over six seeds is 92.3%") to a command that prints the metric
once per seed.  The checker:

1. runs ``runs_cmd`` once per seed, substituting ``{seed}``;
2. extracts the metric with ``metric_regex`` (first capture group);
3. summarises the per-seed values: mean, sample SD, standard error, an
   interval estimate, and the minimum detectable effect (MDE) of this sweep;
4. compares the claimed value with the observed mean and interval, using the
   claim's pre-declared equivalence margin.

The verdict is evidence-local: ``SUPPORTED`` means the observed mean is within
the claim's tolerance window, ``REFUTED`` means the gap exceeds the margin
*and* the interval actually excludes the claimed value, and ``INCONCLUSIVE``
means the sweep cannot decide (timeout, unparseable metric, too few seeds, or
an interval that still contains the claimed value).  A statistical
``INCONCLUSIVE`` is a statement about the audit's resolution, not about the
authors, and this checker never produces scores, rankings, or "probability the
paper is wrong".

Audit JSON shape::

    {
      "id": "S1", "text": "...", "kind": "statistics", "preregistered": true,
      "check": {
        "runs_cmd": "python3 code/train.py --seed {seed}",
        "seeds": [0, 1, 2, 3, 4, 5],
        "metric_regex": "accuracy=(?P<value>[0-9.]+)",
        "claim": {"type": "mean", "value": 0.923, "equivalence_margin": 0.002},
        "confidence": 0.95,
        "method": "bootstrap",
        "resamples": 2000,
        "rng_seed": 0,
        "timeout_s": 30
      }
    }

Only ``claim.type == "mean"`` is implemented.  The checker fails closed: any
malformed or unsupported spec yields ``INCONCLUSIVE`` with a ``spec_error`` in
the evidence rather than raising.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from ..margin import MarginError, resolve_margin
from ..uncertainty import (
    min_detectable_effect,
    summarize_mean,
    verdict_from_interval,
)
from .base import CheckContext, Outcome, RunResult

# Defaults for the MDE calculation, recorded in the evidence for re-runs.
MDE_ALPHA = 0.05
MDE_POWER = 0.8

_SUPPORTED_METHODS = ("bootstrap", "t")


class _SpecError(ValueError):
    """A malformed or unsupported claim check specification."""


def _format_number(value: float) -> str:
    return f"{value:.6g}"


def _json_safe(value: Any) -> Any:
    """Return ``value`` if JSON-serialisable, else its repr (never raise)."""
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)
    return value


def _finite_number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise _SpecError(f"{name} must be a number, got {value!r}") from exc
    if not math.isfinite(result):
        raise _SpecError(f"{name} must be finite, got {value!r}")
    return result


def _parse_spec(ctx: CheckContext) -> dict[str, Any]:
    """Validate and normalise the claim's check specification."""
    spec = ctx.claim.get("check")
    if not isinstance(spec, dict):
        raise _SpecError(
            "claim has no 'check' object; a statistics claim needs runs_cmd, "
            "seeds, metric_regex and a mean claim"
        )

    runs_cmd = spec.get("runs_cmd")
    if not isinstance(runs_cmd, str) or not runs_cmd.strip():
        raise _SpecError("check.runs_cmd must be a non-empty command string")

    raw_seeds = spec.get("seeds")
    if not isinstance(raw_seeds, list) or not raw_seeds:
        raise _SpecError("check.seeds must be a non-empty list of integers")
    seeds: list[int] = []
    for index, raw_seed in enumerate(raw_seeds):
        if isinstance(raw_seed, bool) or not isinstance(raw_seed, int):
            raise _SpecError(
                f"check.seeds[{index}] must be an integer, got {raw_seed!r}"
            )
        seeds.append(raw_seed)

    metric_regex = spec.get("metric_regex")
    if not isinstance(metric_regex, str) or not metric_regex:
        raise _SpecError("check.metric_regex must be a non-empty regular expression")
    try:
        pattern = re.compile(metric_regex)
    except re.error as exc:
        raise _SpecError(f"check.metric_regex is not a valid regex: {exc}") from exc
    if pattern.groups == 0:
        raise _SpecError(
            "check.metric_regex must contain a capture group for the metric value"
        )

    claim_spec = spec.get("claim")
    if not isinstance(claim_spec, dict):
        raise _SpecError(
            "check.claim must be an object like "
            '{"type": "mean", "value": 0.92, "equivalence_margin": 0.01}'
        )
    claim_type = claim_spec.get("type", "mean")
    if claim_type != "mean":
        raise _SpecError(
            f"unsupported check.claim.type {claim_type!r}; only 'mean' is implemented"
        )
    if "value" not in claim_spec:
        raise _SpecError("check.claim.value is required for a mean claim")
    claimed_value = _finite_number(claim_spec["value"], "check.claim.value")
    try:
        margin_info = resolve_margin(spec, ctx.audit, base_dir=ctx.audit_dir)
    except MarginError as exc:
        raise _SpecError(f"margin policy: {exc}") from exc
    equivalence_margin = float(margin_info["margin"])
    if equivalence_margin < 0.0:
        raise _SpecError("resolved equivalence margin must be non-negative")

    confidence = _finite_number(spec.get("confidence", 0.95), "check.confidence")
    if not 0.0 < confidence < 1.0:
        raise _SpecError("check.confidence must be in (0, 1)")

    method = spec.get("method", "bootstrap")
    if method not in _SUPPORTED_METHODS:
        raise _SpecError(
            f"check.method must be one of {_SUPPORTED_METHODS}, got {method!r}"
        )

    resamples = spec.get("resamples", 2000)
    if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 1:
        raise _SpecError("check.resamples must be a positive integer")
    rng_seed = spec.get("rng_seed", 0)
    if isinstance(rng_seed, bool) or not isinstance(rng_seed, int):
        raise _SpecError("check.rng_seed must be an integer")

    raw_timeout = spec.get("timeout_s")
    if raw_timeout is None:
        try:
            raw_timeout = ctx.timeout_s
        except (TypeError, ValueError) as exc:
            raise _SpecError(f"policy.timeout_s is invalid: {exc}") from exc
    timeout_s = _finite_number(raw_timeout, "check.timeout_s")
    if timeout_s <= 0.0:
        raise _SpecError("check.timeout_s must be positive")

    return {
        "runs_cmd": runs_cmd,
        "seeds": seeds,
        "pattern": pattern,
        "metric_regex": metric_regex,
        "claim": claim_spec,
        "claimed_value": claimed_value,
        "equivalence_margin": equivalence_margin,
        "margin_info": margin_info,
        "confidence": confidence,
        "method": method,
        "resamples": resamples,
        "rng_seed": rng_seed,
        "timeout_s": timeout_s,
    }


def _base_evidence(ctx: CheckContext) -> dict[str, Any]:
    spec = ctx.claim.get("check")
    spec = spec if isinstance(spec, dict) else {}
    claim_spec = spec.get("claim")
    return {
        "runs_cmd": _json_safe(spec.get("runs_cmd")),
        "seeds": _json_safe(spec.get("seeds")),
        "metric_regex": _json_safe(spec.get("metric_regex")),
        "claim": _json_safe(claim_spec if isinstance(claim_spec, dict) else {}),
        "preregistered": bool(ctx.claim.get("preregistered", False)),
    }


def _run_failure(result: Any, timeout_s: float) -> dict[str, Any] | None:
    """Describe why one run cannot be used, or return None."""
    if result.timed_out:
        return {
            "kind": "timeout",
            "detail": f"timed out after {timeout_s:g}s",
        }
    if result.exit_code is None:
        return {
            "kind": "runner_error",
            "detail": "the runner returned no exit code",
            "stderr_excerpt": result.stderr[-1000:],
        }
    if result.exit_code != 0:
        return {
            "kind": "nonzero_exit",
            "detail": f"exited with code {result.exit_code}",
            "stderr_excerpt": result.stderr[-1000:],
        }
    return None


def _resolution_note(
    summary: dict[str, Any],
    claimed_value: float,
    equivalence_margin: float,
    mde: float | None,
) -> str:
    """Plain-English comparison of claim effect size and audit resolution."""
    n = summary["n"]
    mean = summary["mean"]
    gap = abs(mean - claimed_value)
    parts: list[str] = []

    if mde is None:
        parts.append(
            "Only one seed was run, so no interval or minimum detectable effect "
            "can be formed; only the tolerance match against the margin is "
            "checked."
        )
        return " ".join(parts)

    parts.append(
        f"Seed sweep n={n} with observed SD={_format_number(summary['sd'])} gives "
        f"a {_format_number(summary['confidence'])} interval half-width of "
        f"{_format_number(summary['ci_half_width'])} and a minimum detectable "
        f"effect (MDE) of {_format_number(mde)} at alpha={MDE_ALPHA:g}, "
        f"power={MDE_POWER:g} (one-sample, two-sided)."
    )
    if mde > equivalence_margin:
        parts.append(
            f"The MDE ({_format_number(mde)}) is larger than the claim's "
            f"equivalence margin ({_format_number(equivalence_margin)}): this "
            "sweep cannot resolve differences as small as the margin."
        )
    else:
        parts.append(
            f"The MDE ({_format_number(mde)}) is no larger than the claim's "
            f"equivalence margin ({_format_number(equivalence_margin)}): the "
            "sweep's resolution is at least as fine as the claimed tolerance."
        )
    if gap <= equivalence_margin:
        parts.append(
            f"The observed gap ({_format_number(gap)}) is inside the claim's "
            "equivalence margin, so the tolerance window is met; this is a "
            "tolerance match, not a significance claim."
        )
    elif gap > mde:
        parts.append(
            f"The observed gap ({_format_number(gap)}) is larger than the MDE, "
            "so the observed discrepancy is above this sweep's noise floor."
        )
    else:
        parts.append(
            f"The observed gap ({_format_number(gap)}) is not larger than the "
            "MDE, so this sweep cannot separate the observed mean from the "
            "claimed value at its own resolution."
        )
    if summary["method"] == "bootstrap" and n < 10:
        parts.append(
            "The percentile bootstrap interval over so few values is coarse and "
            "can understate its width; the MDE is reported so that the interval "
            "alone is not treated as decisive."
        )
    return " ".join(parts)


class StatisticsChecker:
    """Check a mean claim by re-running a preregistered seed sweep.

    The checker never raises for a malformed audit: problems become
    ``INCONCLUSIVE`` outcomes with the attempted runs in ``evidence`` so a
    reader can see what happened.
    """

    kind = "statistics"

    def check(self, ctx: CheckContext) -> Outcome:
        try:
            spec = _parse_spec(ctx)
        except _SpecError as exc:
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=f"malformed statistics check: {exc}",
                evidence={
                    **_base_evidence(ctx),
                    "spec_error": str(exc),
                },
            )

        seeds: list[int] = spec["seeds"]
        pattern: re.Pattern[str] = spec["pattern"]
        runs_cmd: str = spec["runs_cmd"]
        timeout_s: float = spec["timeout_s"]
        try:
            cwd = ctx.check_dir()
        except (TypeError, ValueError, OSError) as exc:
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=f"malformed statistics check: check.cwd is invalid ({exc})",
                evidence={
                    **_base_evidence(ctx),
                    "spec_error": f"check.cwd is invalid: {exc}",
                },
            )
        value_rows: list[dict[str, Any]] = []
        runs: list[dict[str, Any]] = []
        values: list[float] = []

        for index, seed in enumerate(seeds):
            cmd = runs_cmd.replace("{seed}", str(seed))
            try:
                result = ctx.runner(cmd, cwd, timeout_s)
            except Exception as exc:  # noqa: BLE001 - toolchain failures must not crash
                failure = {
                    "kind": "runner_error",
                    "detail": f"runner raised {type(exc).__name__}: {exc}",
                }
                return Outcome(
                    verdict="INCONCLUSIVE",
                    reason=(
                        f"seed {seed}: the command runner failed before producing "
                        f"evidence ({type(exc).__name__}: {exc})"
                    ),
                    evidence={
                        **_base_evidence(ctx),
                        "runs": runs,
                        "values": value_rows,
                        "failed_seed": seed,
                        "failure": failure,
                        "seeds_not_run": seeds[index + 1 :],
                    },
                )

            if not isinstance(result, RunResult):
                return Outcome(
                    verdict="INCONCLUSIVE",
                    reason=(
                        f"seed {seed}: the command runner returned "
                        f"{type(result).__name__}, not a RunResult; no usable "
                        "evidence was produced"
                    ),
                    evidence={
                        **_base_evidence(ctx),
                        "runs": runs,
                        "values": value_rows,
                        "failed_seed": seed,
                        "failure": {
                            "kind": "runner_error",
                            "detail": f"runner returned {type(result).__name__}",
                        },
                        "seeds_not_run": seeds[index + 1 :],
                    },
                )
            runs.append({"seed": seed, **result.summary()})
            failure = _run_failure(result, timeout_s)
            if failure is not None:
                return Outcome(
                    verdict="INCONCLUSIVE",
                    reason=(
                        f"seed {seed}: could not obtain a metric ({failure['detail']}); "
                        "the audit re-ran the preregistered command once per seed but "
                        "this run produced no usable evidence"
                    ),
                    evidence={
                        **_base_evidence(ctx),
                        "runs": runs,
                        "values": value_rows,
                        "failed_seed": seed,
                        "failure": failure,
                        "seeds_not_run": seeds[index + 1 :],
                    },
                )

            match = pattern.search(result.stdout)
            if match is None:
                return self._parse_failure(
                    ctx,
                    seeds,
                    index,
                    seed,
                    runs,
                    value_rows,
                    f"metric_regex {spec['metric_regex']!r} did not match stdout",
                )
            raw_value = match.group(1) if pattern.groups else match.group(0)
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return self._parse_failure(
                    ctx,
                    seeds,
                    index,
                    seed,
                    runs,
                    value_rows,
                    f"matched text {raw_value!r} is not a number",
                )
            if not math.isfinite(value):
                return self._parse_failure(
                    ctx,
                    seeds,
                    index,
                    seed,
                    runs,
                    value_rows,
                    f"metric value {value!r} is not finite",
                )
            values.append(value)
            value_rows.append({"seed": seed, "value": value})

        # Every seed produced a parsed value at this point; spec validation
        # guarantees seeds is non-empty.
        summary = summarize_mean(
            values,
            confidence=spec["confidence"],
            method=spec["method"],
            resamples=spec["resamples"],
            rng_seed=spec["rng_seed"],
        )
        mde = (
            min_detectable_effect(summary["sd"], summary["n"])
            if summary["n"] >= 2
            else None
        )
        verdict, reason = verdict_from_interval(
            spec["claimed_value"],
            summary["mean"],
            summary["ci_low"],
            summary["ci_high"],
            spec["equivalence_margin"],
            mde=mde,
        )

        claimed_value = spec["claimed_value"]
        equivalence_margin = spec["equivalence_margin"]
        gap = abs(summary["mean"] - claimed_value)
        ci_low = summary["ci_low"]
        ci_high = summary["ci_high"]
        ci_excludes_claimed = (
            ci_low is not None
            and ci_high is not None
            and (claimed_value < ci_low or claimed_value > ci_high)
        )
        resolution = {
            "n": summary["n"],
            "margin_mode": spec["margin_info"]["mode"],
            "margin_source": spec["margin_info"]["source"],
            "margin_decision_id": spec["margin_info"]["decision_id"],
            "margin_policy_version": spec["margin_info"].get("policy_version"),
            "margin_note": spec["margin_info"]["note"],
            "min_detectable_effect": mde,
            "mde_alpha": MDE_ALPHA,
            "mde_power": MDE_POWER,
            "equivalence_margin": equivalence_margin,
            "observed_gap": gap,
            "ci_half_width": summary["ci_half_width"],
            "ci_excludes_claimed": ci_excludes_claimed,
            "mde_exceeds_margin": mde is not None and mde > equivalence_margin,
            "mde_over_margin": (
                mde / equivalence_margin
                if mde is not None and equivalence_margin > 0.0
                else None
            ),
            "observed_gap_exceeds_mde": mde is not None and gap > mde,
            "note": _resolution_note(
                summary, claimed_value, equivalence_margin, mde
            ),
        }

        uncertainty = dict(summary)
        uncertainty["min_detectable_effect"] = mde
        uncertainty["effect"] = summary["mean"] - claimed_value
        uncertainty["claimed_value"] = claimed_value
        uncertainty["equivalence_margin"] = equivalence_margin
        uncertainty["margin_mode"] = spec["margin_info"]["mode"]
        uncertainty["margin_source"] = spec["margin_info"]["source"]
        uncertainty["margin_decision_id"] = spec["margin_info"]["decision_id"]
        uncertainty["margin_policy_version"] = spec["margin_info"].get("policy_version")

        evidence = {
            **_base_evidence(ctx),
            "runs": runs,
            "values": value_rows,
            "resolution": resolution,
            "margin_policy": spec["margin_info"],
        }
        return Outcome(
            verdict=verdict,
            reason=reason,
            evidence=evidence,
            uncertainty=uncertainty,
        )

    @staticmethod
    def _parse_failure(
        ctx: CheckContext,
        seeds: list[int],
        index: int,
        seed: int,
        runs: list[dict[str, Any]],
        value_rows: list[dict[str, Any]],
        detail: str,
    ) -> Outcome:
        return Outcome(
            verdict="INCONCLUSIVE",
            reason=(
                f"seed {seed}: could not parse the preregistered metric ({detail}); "
                "the check spec or the command output needs fixing before this "
                "claim can be judged"
            ),
            evidence={
                **_base_evidence(ctx),
                "runs": runs,
                "values": value_rows,
                "failed_seed": seed,
                "failure": {"kind": "metric_parse_error", "detail": detail},
                "seeds_not_run": seeds[index + 1 :],
            },
        )
