"""Markdown rendering for audit reports.

The Markdown report is the human-readable half of the audit artifact. It must
travel with the JSON report: it states scope, environment, verdicts, evidence,
uncertainty and limits, and never presents an aggregate score.
"""

from __future__ import annotations

from typing import Any


def _cell(value: Any, limit: int = 160) -> str:
    text = "" if value is None else str(value)
    text = text.replace("|", "\\|").replace("\n", " ")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def _fmt_number(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_uncertainty(uncertainty: dict[str, Any] | None) -> list[str]:
    if not uncertainty:
        return []
    lines = ["**Uncertainty / resolution**", ""]
    priority = [
        "n",
        "mean",
        "sd",
        "se",
        "ci_low",
        "ci_high",
        "ci_half_width",
        "method",
        "confidence",
        "resamples",
        "seed",
        "min_detectable_effect",
        "equivalence_margin",
        "effect",
        "claim_value",
    ]
    seen: set[str] = set()
    for key in priority:
        if key in uncertainty:
            lines.append(f"- `{key}`: {_fmt_number(uncertainty[key])}")
            seen.add(key)
    for key in sorted(uncertainty):
        if key not in seen:
            lines.append(f"- `{key}`: {_cell(uncertainty[key])}")
    lines.append("")
    return lines


def _evidence_lines(evidence: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    runs = evidence.get("runs")
    if isinstance(runs, list) and runs:
        lines.append("**Runs**")
        lines.append("")
        lines.append("| # | command | exit | duration | evidence sha256 |")
        lines.append("|---|---|---:|---:|---|")
        for index, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                continue
            sha = str(run.get("evidence_sha256", ""))[:16]
            lines.append(
                "| {i} | `{cmd}` | {exit} | {duration}s | `{sha}` |".format(
                    i=index,
                    cmd=_cell(run.get("cmd", ""), 120),
                    exit=_cell(run.get("exit_code")),
                    duration=_cell(run.get("duration_s")),
                    sha=sha,
                )
            )
        lines.append("")
    expectations = evidence.get("expectations")
    if isinstance(expectations, list) and expectations:
        lines.append("**Expectations**")
        lines.append("")
        lines.append("| rule | passed | detail |")
        lines.append("|---|---|---|")
        for item in expectations:
            if not isinstance(item, dict):
                continue
            passed = "yes" if item.get("passed") else "no"
            lines.append(
                f"| `{_cell(item.get('rule'))}` | {passed} | {_cell(item.get('detail'))} |"
            )
        lines.append("")
    resolution = evidence.get("resolution")
    if isinstance(resolution, dict) and resolution:
        lines.append("**Resolution (how much doubt this data can bear)**")
        lines.append("")
        skip = {"note"}
        for key in sorted(resolution):
            if key in skip:
                continue
            value = resolution[key]
            if value is None:
                continue
            if isinstance(value, float):
                lines.append(f"- `{key}`: {value:.6g}")
            else:
                lines.append(f"- `{key}`: {_cell(value)}")
        if resolution.get("note"):
            lines.append("")
            lines.append(f"> {_cell(resolution['note'], 800)}")
        lines.append("")
    for key in ("detail", "error", "note"):
        if evidence.get(key):
            lines.append(f"- `{key}`: {_cell(evidence[key], 400)}")
    if lines:
        lines.append("")
    excerpt = evidence.get("stdout_excerpt") or evidence.get("stdout")
    if isinstance(excerpt, str) and excerpt.strip():
        lines.append("**stdout excerpt**")
        lines.append("")
        lines.append("```text")
        lines.append(excerpt.rstrip())
        lines.append("```")
        lines.append("")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    target = report.get("target") or {}
    lines: list[str] = []
    lines.append(f"# Executable paper audit: {target.get('title', 'untitled')}")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    for key in ("paper", "repo_commit", "audited_by", "date"):
        if target.get(key):
            lines.append(f"| {key} | {_cell(target[key])} |")
    lines.append(f"| tool | paperunit {report.get('tool', {}).get('version', '?')} |")
    lines.append(f"| generated_at | {report.get('generated_at', '')} |")
    lines.append(f"| audit_file | `{_cell(report.get('environment', {}).get('audit_file', ''))}` |")
    lines.append(f"| report_sha256 | `{report.get('report_sha256', '')}` |")
    lines.append("")
    lines.append(
        "> An audit is evidence-local. It is not a verdict on the paper's scientific "
        "value, and it carries no aggregate score or ranking."
    )
    lines.append("")

    scope = report.get("scope") or {}
    lines.append("## Scope")
    lines.append("")
    lines.append("**Tested**")
    lines.append("")
    tested = scope.get("tested") or []
    if tested:
        lines.extend(f"- {item}" for item in tested)
    else:
        lines.append("- (not declared)")
    lines.append("")
    lines.append("**Not tested / explicit limits**")
    lines.append("")
    limits = report.get("limits") or []
    if limits:
        lines.extend(f"- {item}" for item in limits)
    else:
        lines.append("- (none declared)")
    lines.append("")

    counts = report.get("verdict_counts") or {}
    lines.append("## Verdict summary")
    lines.append("")
    lines.append("| Verdict | Count | Meaning |")
    lines.append("|---|---:|---|")
    meanings = {
        "SUPPORTED": "every preregistered expectation passed",
        "REFUTED": "a preregistered expectation failed",
        "INCONCLUSIVE": "could not decide (toolchain, timeout, underpowered, ...)",
        "NOT_RUN": "no executable check (human review only)",
    }
    for verdict in ("SUPPORTED", "REFUTED", "INCONCLUSIVE", "NOT_RUN"):
        lines.append(f"| {verdict} | {counts.get(verdict, 0)} | {meanings[verdict]} |")
    lines.append("")

    lines.append("## Claims")
    lines.append("")
    lines.append("| ID | Kind | Verdict | Reason |")
    lines.append("|---|---|---|---|")
    for claim in report.get("claims") or []:
        lines.append(
            "| {id} | {kind} | {verdict} | {reason} |".format(
                id=_cell(claim.get("id"), 40),
                kind=_cell(claim.get("kind"), 40),
                verdict=_cell(claim.get("verdict"), 40),
                reason=_cell(claim.get("reason"), 200),
            )
        )
    lines.append("")

    for claim in report.get("claims") or []:
        lines.append(f"### {claim.get('id')} - {claim.get('verdict')}")
        lines.append("")
        if claim.get("text"):
            lines.append(f"**Claim:** {claim['text']}")
            lines.append("")
        lines.append(f"- **Verdict:** `{claim.get('verdict')}`")
        lines.append(f"- **Reason:** {_cell(claim.get('reason'), 600)}")
        lines.append(f"- **Preregistered:** {claim.get('preregistered')}")
        lines.append("")
        lines.extend(render_uncertainty(claim.get("uncertainty")))
        lines.extend(_evidence_lines(claim.get("evidence") or {}))

    lines.append("## How to re-run")
    lines.append("")
    lines.append("```bash")
    lines.append(
        "python3 -m paperunit verify --audit "
        f"{report.get('environment', {}).get('audit_file', '<audit.json>')} "
        "--report audit_report.json"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        "`verify` recomputes the report digest, re-runs every check, and compares "
        "verdicts and evidence. A change is reported as DRIFT; a modified stored "
        "report is reported as TAMPERED."
    )
    lines.append("")
    return "\n".join(lines)
