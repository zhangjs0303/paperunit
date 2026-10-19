"""Equivalence-margin policy resolution.

The equivalence margin is the part of an audit's preregistration that answers:
*how close must the audit's estimate be to the paper's claimed value before the
claim counts as SUPPORTED?*  It is a policy choice, not a statistical fact, so
it is resolved by an explicit, versioned rule instead of being typed ad hoc into
every audit.

Supported modes
---------------
``paper_precision`` (default)
    The margin is one unit in the last decimal place the paper itself reports:
    ``10 ** -d`` where ``d`` is the number of decimal places in the claimed
    value (``0.923`` -> ``0.001``).  An optional ``margin_factor`` scales it.
    This is the "only check whether the paper reaches its own reported
    precision" rule.

``fixed`` (a number, or ``{"mode": "fixed", "value": ...}``)
    An explicitly preregistered numeric margin.  Kept for backwards
    compatibility with earlier audits.

``policy_ref`` (``{"mode": "policy_ref", "path": ..., "decision_id": ...}``)
    Read the margin from a versioned policy file (``policies/margin/v1.json``).
    This is the hook for future governance: a DAO or council may own the policy
    file, but never the verdict of a particular audit.  The report records the
    policy path and ``decision_id`` so a reader can reproduce the decision.

The resolver never mutates the audit and never decides a verdict; it only
returns the margin plus provenance metadata that the report must display.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

DEFAULT_MODE = "paper_precision"
POLICY_SCHEMA = "paperunit/margin-policy/v1"
DEFAULT_POLICY_PATH = "policies/margin/v1.json"


class MarginError(ValueError):
    """A malformed margin specification or an unreadable margin policy."""


def decimal_places(value: Any) -> int:
    """Number of decimal places in the value as written (0 for integers)."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MarginError(f"claimed value {value!r} is not a finite decimal") from exc
    if not number.is_finite():
        raise MarginError(f"claimed value {value!r} is not finite")
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and exponent < 0:
        return -exponent
    return 0


def paper_precision_margin(claimed_value: Any, factor: float = 1.0) -> float:
    """Margin = one unit in the claim's last reported decimal place."""
    if factor <= 0.0:
        raise MarginError("margin_factor must be positive")
    return (10.0 ** -decimal_places(claimed_value)) * factor


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MarginError(f"margin policy file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MarginError(f"margin policy is not valid JSON: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise MarginError(f"margin policy must be a JSON object: {path}")
    decisions = raw.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise MarginError(f"margin policy has no non-empty 'decisions' list: {path}")
    return raw


def _find_policy_file(relative: str, base_dir: Path | None) -> Path:
    """Locate a repo-relative policy file from an audit location."""
    candidate = Path(relative)
    if candidate.is_absolute():
        return candidate
    search_roots: list[Path] = []
    if base_dir is not None:
        here = base_dir.resolve()
        search_roots.extend([here, *here.parents])
    search_roots.append(Path.cwd())
    for root in search_roots:
        possible = root / relative
        if possible.is_file():
            return possible
    raise MarginError(
        f"margin policy file {relative!r} not found from {base_dir or Path.cwd()}; "
        "expected a repo-relative policies/ directory"
    )


def _select_decision(
    policy: dict[str, Any],
    decision_id: Any,
    claim_type: str,
    policy_path: Path,
) -> dict[str, Any]:
    decisions = policy["decisions"]
    for item in decisions:
        if not isinstance(item, dict):
            continue
        if decision_id is not None and item.get("decision_id") == decision_id:
            return item
    if decision_id is not None:
        raise MarginError(
            f"decision_id {decision_id!r} not found in policy {policy_path}"
        )
    matching = [
        item
        for item in decisions
        if isinstance(item, dict) and item.get("claim_type", "mean") == claim_type
    ]
    if not matching:
        raise MarginError(
            f"policy {policy_path} has no decision for claim_type {claim_type!r}"
        )
    return matching[-1]


def resolve_margin(
    check: dict[str, Any],
    audit: dict[str, Any] | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Resolve ``check``'s margin rule.

    Returns ``{"margin", "mode", "source", "policy_version", "decision_id",
"note"}``.  Raises
    :class:`MarginError` when the rule is malformed or a policy cannot be read.
    """
    if not isinstance(check, dict):
        raise MarginError("check must be an object")
    claim_spec = check.get("claim")
    claim_spec = claim_spec if isinstance(claim_spec, dict) else {}
    claim_type = str(claim_spec.get("type", "mean"))

    raw = check.get("equivalence_margin", claim_spec.get("equivalence_margin", None))
    factor_raw = check.get("margin_factor", claim_spec.get("margin_factor", 1.0))
    try:
        factor = float(factor_raw)
    except (TypeError, ValueError) as exc:
        raise MarginError(f"margin_factor must be a number, got {factor_raw!r}") from exc
    claimed_value = claim_spec.get("value")

    if raw is None or raw == DEFAULT_MODE:
        if claimed_value is None:
            raise MarginError(
                "paper_precision needs check.claim.value to read the last decimal place"
            )
        places = decimal_places(claimed_value)
        margin = paper_precision_margin(claimed_value, factor)
        note = (
            f"margin derived from the paper's own reported precision: "
            f"{places} decimal place(s) -> {margin:g}"
            + (f" (factor {factor:g})" if factor != 1.0 else "")
        )
        if places == 0:
            note += (
                "; the claim is an integer, so the margin is one whole unit and "
                "the resolution is coarse; declare an explicit margin if that is "
                "not intended"
            )
        return {
            "margin": margin,
            "mode": DEFAULT_MODE,
            "source": "paper_precision",
            "policy_version": None,
            "decision_id": None,
            "note": note,
        }

    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        margin = float(raw)
        if margin < 0.0:
            raise MarginError("equivalence_margin must be non-negative")
        return {
            "margin": margin,
            "mode": "fixed",
            "source": "explicit numeric equivalence_margin",
            "policy_version": None,
            "decision_id": None,
            "note": f"explicit margin {margin:g} declared in the audit file",
        }

    if isinstance(raw, dict):
        mode = raw.get("mode")
        if mode == "fixed":
            try:
                margin = float(raw.get("value"))
            except (TypeError, ValueError) as exc:
                raise MarginError("fixed margin needs a numeric 'value'") from exc
            if margin < 0.0:
                raise MarginError("fixed margin must be non-negative")
            return {
                "margin": margin,
                "mode": "fixed",
                "source": "explicit fixed margin",
                "policy_version": None,
                "decision_id": None,
                "note": f"explicit fixed margin {margin:g} declared in the audit file",
            }
        if mode in ("policy_ref", "policy"):
            relative = raw.get("path") or DEFAULT_POLICY_PATH
            if not isinstance(relative, str):
                raise MarginError("policy_ref.path must be a string")
            decision_id = raw.get("decision_id")
            policy_path = _find_policy_file(relative, base_dir)
            policy = _load_policy(policy_path)
            decision = _select_decision(policy, decision_id, claim_type, policy_path)
            try:
                margin = float(decision.get("margin"))
            except (TypeError, ValueError) as exc:
                raise MarginError(
                    f"policy {policy_path} decision has no numeric 'margin'"
                ) from exc
            if margin < 0.0:
                raise MarginError(f"policy {policy_path} margin must be non-negative")
            resolved_id = decision.get("decision_id", decision_id)
            note = (
                f"margin {margin:g} read from policy {relative}"
                f" (decision {resolved_id})"
            )
            if decision.get("rationale"):
                note += f": {decision['rationale']}"
            return {
                "margin": margin,
                "mode": "policy_ref",
                "source": relative,
                "policy_version": policy.get("policy_version"),
                "decision_id": resolved_id,
                "note": note,
            }
        raise MarginError(f"unsupported margin mode {mode!r}")

    raise MarginError(f"unsupported equivalence_margin specification {raw!r}")
