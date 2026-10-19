"""Engine: run an audit, produce a report, and re-run it to verify the report.

Design rules enforced here:

* every claim is dispatched to exactly one checker and gets one verdict;
* the report carries no aggregate score or ranking;
* ``report_sha256`` covers a *stable view* of the claim results, so wall-clock
  durations do not make two honest runs differ;
* a checker crash becomes ``INCONCLUSIVE`` for that claim instead of failing
  the whole audit.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import VERDICTS, __version__
from .checkers import get_checker
from .checkers.base import (
    CheckContext,
    Outcome,
    Runner,
    canonical_json,
    run_command,
    sha256_text,
)
from .schema import load_audit

REPORT_SCHEMA = "paperunit/report/v1"
DEFAULT_POLICY: dict[str, Any] = {
    "timeout_s": 120.0,
    "confidence": 0.95,
}

STANDARD_DISCLAIMER = (
    "An audit tests only the listed claims on the stated commit in the stated "
    "environment; it is not a verdict on the paper's scientific value, and it "
    "carries no aggregate score."
)

# Keys whose values legitimately vary between honest runs.
_UNSTABLE_KEYS = {
    "duration_s",
    "generated_at",
    "started_at",
    "finished_at",
    "timestamp",
    "started_utc",
    "finished_utc",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_view(obj: Any) -> Any:
    """Strip volatile keys recursively so digests describe evidence, not clocks."""
    if isinstance(obj, dict):
        return {k: stable_view(v) for k, v in obj.items() if k not in _UNSTABLE_KEYS}
    if isinstance(obj, list):
        return [stable_view(v) for v in obj]
    return obj


# Run-level fields that are not decisive evidence when a checker only judges the
# exit status: unittest timings and harmless stdout differences would otherwise
# make honest re-runs look like DRIFT.
_VOLATILE_RUN_FIELDS = {
    "stdout_sha256",
    "stderr_sha256",
    "evidence_sha256",
    "stdout_excerpt",
    "stderr_excerpt",
    "duration_s",
}


def claim_record(claim: dict[str, Any], outcome: Outcome) -> dict[str, Any]:
    record = {
        "id": claim["id"],
        "kind": claim["kind"],
        "text": claim.get("text", ""),
        "preregistered": bool(claim.get("preregistered", True)),
        "verdict": outcome.verdict,
        "reason": outcome.reason,
        "evidence": outcome.evidence,
        "uncertainty": outcome.uncertainty,
    }
    if claim.get("evidence_comparison"):
        record["evidence_comparison"] = claim["evidence_comparison"]
    return record


def _strip_volatile_evidence(record: dict[str, Any]) -> dict[str, Any]:
    """Drop non-decisive run output when a claim is compared by verdict only."""
    evidence = record.get("evidence") or {}
    mode = record.get("evidence_comparison") or evidence.get("comparison_mode")
    if mode != "verdict_only":
        return record
    cleaned_evidence = dict(evidence)
    runs = cleaned_evidence.get("runs")
    if isinstance(runs, list):
        cleaned_evidence["runs"] = [
            {k: v for k, v in run.items() if k not in _VOLATILE_RUN_FIELDS}
            if isinstance(run, dict)
            else run
            for run in runs
        ]
    cleaned_evidence.pop("stdout_excerpt", None)
    cleaned_evidence.pop("stdout", None)
    cleaned = dict(record)
    cleaned["evidence"] = cleaned_evidence
    return cleaned


def claim_fingerprint(record: dict[str, Any]) -> str:
    return sha256_text(canonical_json(stable_view(_strip_volatile_evidence(record))))


def report_digest(records: list[dict[str, Any]]) -> str:
    return sha256_text(
        canonical_json(
            [{"id": r["id"], "fingerprint": claim_fingerprint(r)} for r in records]
        )
    )


def effective_policy(audit: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = dict(DEFAULT_POLICY)
    configured = audit.get("policy")
    if isinstance(configured, dict):
        policy.update(configured)
    if overrides:
        policy.update(overrides)
    return policy


def run_claims(
    audit: dict[str, Any],
    audit_dir: Path,
    runner: Runner | None = None,
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run every claim once and return claim records."""
    run = runner or run_command
    effective = policy or effective_policy(audit)
    records: list[dict[str, Any]] = []
    for claim in audit["claims"]:
        kind = str(claim.get("kind"))
        checker = get_checker(kind)
        if checker is None:
            records.append(
                claim_record(
                    claim,
                    Outcome(
                        "INCONCLUSIVE",
                        f"no checker registered for kind {kind!r}",
                        evidence={"kind": kind},
                    ),
                )
            )
            continue
        ctx = CheckContext(
            claim=claim,
            audit=audit,
            audit_dir=audit_dir,
            runner=run,
            policy=effective,
        )
        try:
            outcome = checker.check(ctx)
        except Exception as exc:  # noqa: BLE001 - one bad checker must not kill the audit
            outcome = Outcome(
                "INCONCLUSIVE",
                f"checker for kind {kind!r} raised {type(exc).__name__}: {exc}",
                evidence={"kind": kind, "error_type": type(exc).__name__},
            )
        records.append(claim_record(claim, outcome))
    return records


def build_report(
    audit: dict[str, Any],
    audit_path: Path,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    scope = audit.get("scope") or {}
    limits = list(scope.get("not_tested") or [])
    limits.append(STANDARD_DISCLAIMER)
    if not scope.get("tested"):
        limits.append("scope.tested was empty: the audit does not declare what it covers.")
    counts = {verdict: 0 for verdict in VERDICTS}
    for record in records:
        counts[record["verdict"]] = counts.get(record["verdict"], 0) + 1
    return {
        "schema": REPORT_SCHEMA,
        "tool": {"name": "paperunit", "version": __version__},
        "target": audit.get("target", {}),
        "scope": scope,
        "policy": effective_policy(audit),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "audit_file": str(audit_path),
        },
        "generated_at": utc_now(),
        "claims": records,
        "verdict_counts": counts,
        "limits": limits,
        "report_sha256": report_digest(records),
    }


def run_audit(
    audit_path: str | Path,
    out_dir: str | Path,
    runner: Runner | None = None,
) -> tuple[dict[str, Any], dict[str, Path]]:
    """Run an audit and write ``audit_report.json`` + ``report.md``."""
    from .report import render_markdown  # local import keeps engine cheap to import

    path = Path(audit_path)
    audit = load_audit(path)
    audit_dir = path.parent.resolve()
    records = run_claims(audit, audit_dir, runner=runner)
    report = build_report(audit, path, records)
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "audit_report.json"
    md_path = destination / "report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return report, {"json": json_path, "markdown": md_path}


def compare_reports(
    stored: dict[str, Any],
    fresh: dict[str, Any],
) -> list[dict[str, Any]]:
    """Per-claim differences between a stored and a freshly run report."""
    stored_by_id = {c["id"]: c for c in stored.get("claims", [])}
    fresh_by_id = {c["id"]: c for c in fresh.get("claims", [])}
    differences: list[dict[str, Any]] = []
    for cid in sorted(set(stored_by_id) | set(fresh_by_id)):
        old = stored_by_id.get(cid)
        new = fresh_by_id.get(cid)
        if old is None:
            differences.append({"claim": cid, "change": "missing_in_stored_report"})
            continue
        if new is None:
            differences.append({"claim": cid, "change": "missing_in_fresh_run"})
            continue
        if old.get("verdict") != new.get("verdict"):
            differences.append(
                {
                    "claim": cid,
                    "change": "verdict_changed",
                    "stored": old.get("verdict"),
                    "fresh": new.get("verdict"),
                }
            )
            continue
        if claim_fingerprint(old) != claim_fingerprint(new):
            differences.append({"claim": cid, "change": "evidence_changed"})
    return differences


def verify_audit(
    audit_path: str | Path,
    report_path: str | Path,
    runner: Runner | None = None,
) -> tuple[str, dict[str, Any]]:
    """Re-run an audit and compare it with a stored report.

    Status: ``REPRODUCIBLE``, ``INCONCLUSIVE``, ``DRIFT`` or ``TAMPERED``.
    """
    path = Path(audit_path)
    report_file = Path(report_path)
    audit = load_audit(path)
    try:
        stored = json.loads(report_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"report not found: {report_file}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"report is not valid JSON: {report_file}: {exc}") from exc

    details: dict[str, Any] = {
        "stored_report_sha256": stored.get("report_sha256"),
        "tampered": False,
        "semantic_tampered": False,
        "differences": [],
        "stored_inconclusive": [],
    }

    stored_records = stored.get("claims") or []
    stored_digest = stored.get("report_sha256")
    recomputed_stored = report_digest(stored_records) if stored_records else None
    details["recomputed_stored_sha256"] = recomputed_stored
    if stored_digest and recomputed_stored and stored_digest != recomputed_stored:
        details["tampered"] = True
        return "TAMPERED", details

    fresh_records = run_claims(
        audit, path.parent.resolve(), runner=runner, policy=effective_policy(audit)
    )
    differences = compare_reports({"claims": stored_records}, {"claims": fresh_records})
    details["differences"] = differences
    fresh = build_report(audit, path, fresh_records)
    details["fresh_report_sha256"] = fresh["report_sha256"]

    inconclusive = [r["id"] for r in fresh_records if r["verdict"] == "INCONCLUSIVE"]
    details["stored_inconclusive"] = inconclusive
    if differences:
        return "DRIFT", details
    if inconclusive:
        return "INCONCLUSIVE", details
    return "REPRODUCIBLE", details
