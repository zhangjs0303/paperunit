"""Uncertainty summaries and evidence-local statistical verdicts.

This module exists so that a statistical audit can report *what its data can
resolve*, not how likely it is that a paper is wrong.  Every function here is
stdlib-only and deterministic: the same inputs (and RNG seed) produce exactly
the same numbers, because audit evidence must be re-runnable by a third party.

For one seed sweep the audit reports three things:

* ``mean`` / ``sd`` / ``se`` -- the observed metric and its seed-to-seed
  variability (sample SD, ``n - 1`` denominator);
* ``ci_low`` / ``ci_high`` -- an interval estimate for the mean at the
  requested confidence level;
* ``min_detectable_effect`` -- the smallest true shift the sweep could
  plausibly distinguish from seed noise at ``alpha`` and ``power``.

The verdict then compares the *claim's* effect size (the gap between the
claimed value and the observed mean, with the claim's pre-declared equivalence
margin) against the *audit's* resolution (interval and minimum detectable
effect).  When the interval still contains the claimed value, the honest
outcome is INCONCLUSIVE: the data are too coarse to decide, which is a
statement about the audit, not about the authors.

None of these numbers is a score, a ranking, or "the probability that the
paper is wrong".
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from statistics import NormalDist
from typing import Any, Iterable, Sequence

__all__ = [
    "holm_adjust",
    "min_detectable_effect",
    "summarize_mean",
    "verdict_from_interval",
]

# Two-sided Student-t critical values for the confidence levels we tabulate.
# Sources are standard t-tables (values rounded to six decimal places).  For
# ``df <= 30`` these are used directly; for ``df > 30`` a Cornish-Fisher
# expansion around the normal quantile is accurate to well under 1% and is
# used instead.  For ``df <= 30`` with a confidence level outside these three
# columns we raise ValueError instead of silently using a poor approximation.
_T_TABLE: dict[float, dict[int, float]] = {
    0.90: {
        1: 6.313752, 2: 2.919986, 3: 2.353363, 4: 2.131847, 5: 2.015048,
        6: 1.943180, 7: 1.894579, 8: 1.859548, 9: 1.833113, 10: 1.812461,
        11: 1.795885, 12: 1.782288, 13: 1.770933, 14: 1.761310, 15: 1.753050,
        16: 1.745884, 17: 1.739607, 18: 1.734064, 19: 1.729133, 20: 1.724718,
        21: 1.720743, 22: 1.717144, 23: 1.713872, 24: 1.710882, 25: 1.708141,
        26: 1.705618, 27: 1.703288, 28: 1.701131, 29: 1.699127, 30: 1.697261,
    },
    0.95: {
        1: 12.706205, 2: 4.302653, 3: 3.182446, 4: 2.776445, 5: 2.570582,
        6: 2.446912, 7: 2.364624, 8: 2.306004, 9: 2.262157, 10: 2.228139,
        11: 2.200985, 12: 2.178813, 13: 2.160369, 14: 2.144787, 15: 2.131450,
        16: 2.119905, 17: 2.109816, 18: 2.100922, 19: 2.093024, 20: 2.085963,
        21: 2.079614, 22: 2.073873, 23: 2.068658, 24: 2.063899, 25: 2.059539,
        26: 2.055529, 27: 2.051831, 28: 2.048407, 29: 2.045230, 30: 2.042272,
    },
    0.99: {
        1: 63.656741, 2: 9.924843, 3: 5.840909, 4: 4.604095, 5: 4.032143,
        6: 3.707428, 7: 3.499483, 8: 3.355387, 9: 3.249836, 10: 3.169273,
        11: 3.105807, 12: 3.054540, 13: 3.012276, 14: 2.976843, 15: 2.946713,
        16: 2.920782, 17: 2.898231, 18: 2.878440, 19: 2.860935, 20: 2.845340,
        21: 2.831360, 22: 2.818756, 23: 2.807336, 24: 2.796940, 25: 2.787436,
        26: 2.778715, 27: 2.770683, 28: 2.763262, 29: 2.756386, 30: 2.749996,
    },
}

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _format_number(value: float) -> str:
    """Compact, deterministic number formatting for human-readable reasons."""
    return f"{value:.6g}"


def _as_finite_float(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return result


def _clean_values(values: Iterable[Any]) -> list[float]:
    """Convert to a non-empty list of finite floats."""
    try:
        cleaned = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"values must be numbers: {exc}") from exc
    if not cleaned:
        raise ValueError("summarize_mean requires at least one value")
    for index, value in enumerate(cleaned):
        if not math.isfinite(value):
            raise ValueError(f"values[{index}] must be finite, got {value!r}")
    return cleaned


def _values_sha256(values: Sequence[float]) -> str:
    """Stable hash of the raw per-seed values, in the order supplied."""
    payload = json.dumps(
        list(values), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile (same convention as numpy's "linear").

    ``q`` is in [0, 1]; the sequence must already be sorted ascending.
    """
    if not sorted_values:
        raise ValueError("cannot take a percentile of an empty sequence")
    q = min(1.0, max(0.0, float(q)))
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = q * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    low_value = float(sorted_values[lower])
    high_value = float(sorted_values[upper])
    return low_value + fraction * (high_value - low_value)


def _t_critical(df: int, confidence: float) -> float:
    """Two-sided Student-t critical value (table for df<=30, expansion after)."""
    if df <= 0:
        raise ValueError("degrees of freedom must be positive")
    if df <= 30:
        table_confidence = None
        for candidate in _T_TABLE:
            if abs(confidence - candidate) <= 1e-9:
                table_confidence = candidate
                break
        if table_confidence is not None:
            return float(_T_TABLE[table_confidence][df])
        raise ValueError(
            "t-method confidence levels supported for n <= 31 are 0.90, 0.95 "
            f"and 0.99 (got {confidence!r}); use method='bootstrap' or a larger n"
        )
    # Cornish-Fisher expansion around the normal quantile; accurate for df > 30.
    z = NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    correction = (z**3 + z) / (4.0 * df)
    correction += (5.0 * z**5 + 16.0 * z**3 + 3.0 * z) / (96.0 * df**2)
    return z + correction


def _bootstrap_ci(
    values: Sequence[float],
    confidence: float,
    resamples: int,
    rng_seed: int,
) -> tuple[float, float]:
    """Percentile bootstrap interval for the mean of ``values``."""
    n = len(values)
    rng = random.Random(rng_seed)
    resampled_means: list[float] = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += values[rng.randrange(n)]
        resampled_means.append(total / n)
    resampled_means.sort()
    alpha = 1.0 - confidence
    ci_low = _percentile(resampled_means, alpha / 2.0)
    ci_high = _percentile(resampled_means, 1.0 - alpha / 2.0)
    return ci_low, ci_high


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def summarize_mean(
    values: Sequence[float],
    confidence: float = 0.95,
    method: str = "bootstrap",
    resamples: int = 2000,
    rng_seed: int = 0,
) -> dict[str, Any]:
    """Summarise a metric measured once per seed.

    Parameters
    ----------
    values:
        One observation per seed, in seed order.  Must be non-empty and finite.
    confidence:
        Confidence level of the interval, in (0, 1).
    method:
        ``"bootstrap"`` (percentile bootstrap of the mean, ``random.Random``
        seeded by ``rng_seed``) or ``"t"`` (Student-t interval with a lookup
        table for df <= 30 and a Cornish-Fisher approximation beyond).
    resamples:
        Bootstrap resample count; ignored (returned as ``None``) for ``"t"``.
    rng_seed:
        Seed for the bootstrap RNG; ignored (returned as ``None``) for ``"t"``.

    Returns
    -------
    dict
        ``n, mean, sd, se, ci_low, ci_high, ci_half_width, method, confidence,
        resamples, seed, values_sha256, ci_method, note``.

        With ``n == 1`` the sample SD is undefined but is reported as ``0.0``
        per the audit format, ``se``/``ci_*`` are ``None``, and ``note``
        explains that a single value supports no interval.  The returned dict
        is JSON-serialisable.
    """
    raw_values = _clean_values(values)
    n = len(raw_values)
    mean = math.fsum(raw_values) / n
    confidence = _as_finite_float(confidence, "confidence")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence!r}")
    if method not in ("bootstrap", "t"):
        raise ValueError(
            f"method must be 'bootstrap' or 't', got {method!r}"
        )

    if method == "bootstrap":
        if not isinstance(resamples, int) or isinstance(resamples, bool) or resamples < 1:
            raise ValueError(f"resamples must be a positive integer, got {resamples!r}")
        if not isinstance(rng_seed, int) or isinstance(rng_seed, bool):
            raise ValueError(
                f"rng_seed must be an integer for deterministic bootstrap, got {rng_seed!r}"
            )

    note: str | None = None
    if n == 1:
        sd = 0.0
        se: float | None = None
        ci_low: float | None = None
        ci_high: float | None = None
        ci_half_width: float | None = None
        ci_method = "none"
        note = (
            "n=1: the sample standard deviation is undefined (reported as 0.0) "
            "and a single seed cannot support an interval estimate; only the "
            "tolerance match against the equivalence margin can be checked."
        )
    else:
        sd = math.sqrt(math.fsum((value - mean) ** 2 for value in raw_values) / (n - 1))
        se = sd / math.sqrt(n)
        if method == "bootstrap":
            ci_low, ci_high = _bootstrap_ci(raw_values, confidence, resamples, rng_seed)
            ci_method = "bootstrap_percentile_linear"
            if n < 10:
                note = (
                    f"percentile bootstrap with n={n} is a coarse resolution "
                    "check; read it together with the minimum detectable effect, "
                    "not as a calibrated posterior statement."
                )
        else:  # method == "t"
            df = n - 1
            critical = _t_critical(df, confidence)
            ci_low = mean - critical * se
            ci_high = mean + critical * se
            ci_method = (
                "t_interval_table" if df <= 30 else "t_interval_cornish_fisher"
            )
        ci_half_width = (ci_high - ci_low) / 2.0

    return {
        "n": n,
        "mean": mean,
        "sd": sd,
        "se": se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "ci_half_width": ci_half_width,
        "method": method,
        "confidence": confidence,
        "resamples": resamples if method == "bootstrap" else None,
        "seed": rng_seed if method == "bootstrap" else None,
        "values_sha256": _values_sha256(raw_values),
        "ci_method": ci_method,
        "note": note,
    }


def min_detectable_effect(
    sd: float,
    n: int,
    alpha: float = 0.05,
    power: float = 0.8,
) -> float:
    """Minimum detectable effect for a one-sample, two-sided mean test.

    Standard normal-approximation formula::

        MDE = (z_{1 - alpha/2} + z_{power}) * sd / sqrt(n)

    At ``alpha=0.05`` and ``power=0.8`` the multiplier is 2.8016, i.e. the
    familiar ``~2.8 * sd / sqrt(n)``.  ``sd`` is the observed seed-to-seed
    standard deviation and ``n`` the number of seeds.  The result is the
    smallest true shift that this sweep would detect most of the time; gaps
    smaller than it cannot be separated from seed noise by this audit.

    This is a resolution statement about the audit, not a property of the
    paper.  For a two-sample comparison the required n is roughly four times
    larger, so this formula gives a lower bound on the resolution needed.
    """
    sd = _as_finite_float(sd, "sd")
    if sd < 0.0:
        raise ValueError(f"sd must be non-negative, got {sd!r}")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError(f"n must be a positive integer, got {n!r}")
    alpha = _as_finite_float(alpha, "alpha")
    power = _as_finite_float(power, "power")
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha!r}")
    if not 0.0 < power < 1.0:
        raise ValueError(f"power must be in (0, 1), got {power!r}")
    if sd == 0.0:
        return 0.0
    z_alpha = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    z_power = NormalDist().inv_cdf(power)
    return (z_alpha + z_power) * sd / math.sqrt(n)


def holm_adjust(pvalues: Sequence[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values.

    Returns adjusted p-values in the *original* input order.  The adjustment is
    ``p_adj_(i) = max_{j <= i} min(1, (m - j + 1) * p_(j))`` over the ascending
    sorted p-values, which enforces monotonicity.  It is deterministic and
    available for future multi-claim audits; the statistics checker currently
    reports one claim per outcome and therefore does not apply it.
    """
    try:
        raw = [float(value) for value in pvalues]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"pvalues must be numbers: {exc}") from exc
    for index, value in enumerate(raw):
        if not math.isfinite(value):
            raise ValueError(f"pvalues[{index}] must be finite, got {value!r}")
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"pvalues[{index}] must be in [0, 1], got {value!r}")
    m = len(raw)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda index: (raw[index], index))
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (m - rank) * raw[index])
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted


def verdict_from_interval(
    claimed: float,
    mean: float,
    ci_low: float | None,
    ci_high: float | None,
    equivalence_margin: float,
    *,
    mde: float | None = None,
) -> tuple[str, str]:
    """Evidence-local verdict comparing a claim against observed resolution.

    Rules (all values are on the metric's own scale):

    * ``SUPPORTED``    -- ``abs(mean - claimed) <= equivalence_margin``.  The
      observed mean lands inside the pre-declared tolerance window.
    * ``REFUTED``      -- the gap exceeds the margin *and* the interval
      estimate excludes the claimed value.  The data can actually separate the
      claim from what was observed.
    * ``INCONCLUSIVE`` -- otherwise.  The typical case is a gap larger than
      the margin that the interval still contains: the audit cannot resolve
      the claim at this sample size.  That is a limit of the evidence, not
      proof that the claim is false.

    ``mde`` (minimum detectable effect) is optional but, when given, is quoted
    in the reason so a reader can compare the audit's resolution with the
    claim's effect size.  Without an interval (e.g. ``n == 1``) only the
    tolerance match can be checked, and any gap larger than the margin yields
    ``INCONCLUSIVE``.

    Returns ``(verdict, reason)`` where ``reason`` is a factual, human-readable
    sentence suitable for an audit report.
    """
    claimed = _as_finite_float(claimed, "claimed")
    mean = _as_finite_float(mean, "mean")
    equivalence_margin = _as_finite_float(equivalence_margin, "equivalence_margin")
    if equivalence_margin < 0.0:
        raise ValueError(
            f"equivalence_margin must be non-negative, got {equivalence_margin!r}"
        )
    if mde is not None:
        mde = _as_finite_float(mde, "mde")
        if mde < 0.0:
            raise ValueError(f"mde must be non-negative, got {mde!r}")
    if (ci_low is None) != (ci_high is None):
        raise ValueError("ci_low and ci_high must both be None or both be numbers")
    if ci_low is not None and ci_high is not None:
        ci_low = _as_finite_float(ci_low, "ci_low")
        ci_high = _as_finite_float(ci_high, "ci_high")
        if ci_low > ci_high:
            raise ValueError(
                f"ci_low ({ci_low!r}) must not exceed ci_high ({ci_high!r})"
            )

    gap = abs(mean - claimed)
    margin_text = (
        f"the equivalence margin {_format_number(equivalence_margin)}"
    )
    mde_text = ""
    if mde is not None:
        mde_text = (
            f"; the minimum detectable effect (MDE) of this sweep is "
            f"{_format_number(mde)}"
        )

    if ci_low is None or ci_high is None:
        if gap <= equivalence_margin:
            reason = (
                f"observed mean {_format_number(mean)} is within {margin_text} of "
                f"the claimed value {_format_number(claimed)} (gap "
                f"{_format_number(gap)}){mde_text}. No interval estimate is "
                "available (n=1), so this is a tolerance match, not a statistical "
                "test."
            )
            return "SUPPORTED", reason
        reason = (
            f"observed mean {_format_number(mean)} differs from the claimed value "
            f"{_format_number(claimed)} by a gap of {_format_number(gap)}, which "
            f"exceeds {margin_text}{mde_text}, but no interval estimate is "
            "available (n=1) to show that the claim is outside the observed "
            "range; more seeds are needed to decide."
        )
        return "INCONCLUSIVE", reason

    interval_text = (
        f"the interval [{_format_number(ci_low)}, {_format_number(ci_high)}]"
    )
    includes_claimed = ci_low <= claimed <= ci_high

    if gap <= equivalence_margin:
        reason = (
            f"observed mean {_format_number(mean)} is within {margin_text} of the "
            f"claimed value {_format_number(claimed)} (gap {_format_number(gap)}); "
            f"{interval_text} is reported for resolution{mde_text}."
        )
        return "SUPPORTED", reason

    if not includes_claimed:
        reason = (
            f"observed mean {_format_number(mean)} differs from the claimed value "
            f"{_format_number(claimed)} by a gap of {_format_number(gap)}, which "
            f"exceeds {margin_text}, and {interval_text} excludes the claimed "
            f"value{mde_text}."
        )
        return "REFUTED", reason

    reason = (
        f"observed mean {_format_number(mean)} differs from the claimed value "
        f"{_format_number(claimed)} by a gap of {_format_number(gap)}, which "
        f"exceeds {margin_text}, but {interval_text} still includes the claimed "
        f"value{mde_text}. The data cannot resolve a difference of this size at "
        "this sample size, so the result is INCONCLUSIVE about the claim -- a "
        "limitation of the audit's resolution, not evidence about the authors."
    )
    return "INCONCLUSIVE", reason
