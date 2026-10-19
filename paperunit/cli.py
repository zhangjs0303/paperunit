"""Command-line interface for paperunit.

Subcommands
-----------
run       execute an audit and write audit_report.json + report.md
verify    re-run an audit and compare against a stored report
validate  check an audit file's structure without running it
registry  build the static audit registry
init      scaffold a new audit file
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import engine
from .schema import AuditSpecError, load_audit

VERIFY_EXIT = {
    "REPRODUCIBLE": 0,
    "TAMPERED": 1,
    "DRIFT": 1,
    "INCONCLUSIVE": 2,
}


def _emit(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False))


def _summarise_claims(report: dict[str, Any]) -> None:
    for claim in report.get("claims", []):
        reason = str(claim.get("reason", ""))
        if len(reason) > 110:
            reason = reason[:109] + "…"
        print(f"  {claim.get('id', '?'):<10} {claim.get('verdict', '?'):<14} {reason}")
    counts = report.get("verdict_counts", {})
    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    print(f"summary: {summary}")


def cmd_run(args: argparse.Namespace) -> int:
    report, paths = engine.run_audit(args.audit, args.out)
    if args.json:
        _emit({"report": report, "paths": {k: str(v) for k, v in paths.items()}})
        return 0
    print(f"paperunit run: {len(report.get('claims', []))} claim(s)")
    _summarise_claims(report)
    print(f"report: {paths['json']}")
    print(f"markdown: {paths['markdown']}")
    print(f"report_sha256: {report.get('report_sha256')}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        status, details = engine.verify_audit(args.audit, args.report)
    except (FileNotFoundError, ValueError) as exc:
        print(f"paperunit verify: {exc}", file=sys.stderr)
        return 2
    if args.json:
        _emit({"status": status, "details": details})
    else:
        print(f"Verification: {status}")
        print(
            "stored={stored} recomputed={recomputed} tampered={tampered}".format(
                stored=str(details.get("stored_report_sha256"))[:16],
                recomputed=str(details.get("recomputed_stored_sha256"))[:16],
                tampered=details.get("tampered"),
            )
        )
        differences = details.get("differences") or []
        if differences:
            print("differences:")
            for item in differences:
                print(f"  {item}")
        else:
            print("No differences: verdicts and evidence are identical.")
        if details.get("stored_inconclusive"):
            print(f"INCONCLUSIVE claims: {details['stored_inconclusive']}")
    return VERIFY_EXIT.get(status, 2)


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        audit = load_audit(args.audit)
    except AuditSpecError as exc:
        if args.json:
            _emit({"ok": False, "error": str(exc)})
        else:
            print(f"paperunit validate: {exc}", file=sys.stderr)
        return 2
    result = {
        "ok": True,
        "schema": audit.get("schema"),
        "claims": len(audit.get("claims", [])),
        "kinds": sorted({c.get("kind") for c in audit.get("claims", [])}),
    }
    if args.json:
        _emit(result)
    else:
        print(
            f"OK: schema={result['schema']} claims={result['claims']} "
            f"kinds={','.join(str(k) for k in result['kinds'])}"
        )
    return 0


def cmd_registry_build(args: argparse.Namespace) -> int:
    try:
        from .registry import build_registry
    except ImportError as exc:
        print(f"paperunit registry: registry module unavailable: {exc}", file=sys.stderr)
        return 2
    index = build_registry(Path(args.audits_dir), Path(args.out))
    if args.json:
        _emit(index)
    else:
        print(
            f"registry: {len(index.get('audits', []))} audit(s) -> "
            f"{Path(args.out) / 'index.html'}"
        )
    return 0


TEMPLATE_AUDIT = {
    "schema": "paperunit/v1",
    "target": {
        "title": "REPLACE ME: paper title",
        "paper": "https://arxiv.org/abs/REPLACE",
        "repo_commit": "REPLACE ME: commit hash or released artifact version",
        "audited_by": "REPLACE ME: your name or team",
        "date": "YYYY-MM-DD",
    },
    "scope": {
        "tested": ["REPLACE ME: which claims / figures / tables this audit covers"],
        "not_tested": [
            "REPLACE ME: what this audit explicitly does NOT cover",
            "any claim or code path not listed above",
        ],
    },
    "claims": [
        {
            "id": "C1",
            "text": "REPLACE ME: quote or paraphrase one checkable claim",
            "kind": "numeric",
            "check": {
                "cmd": "python3 REPLACE_ME.py",
                "timeout_s": 120,
                "expect": {
                    "numeric_within": {
                        "number_regex": "metric=(?P<value>[0-9.]+)",
                        "target": 0.0,
                        "tolerance": 0.0,
                    }
                },
            },
            "preregistered": True,
        }
    ],
}


def cmd_init(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    directory.mkdir(parents=True, exist_ok=True)
    audit_path = directory / "audit.json"
    if audit_path.exists() and not args.force:
        print(f"paperunit init: {audit_path} already exists (use --force)", file=sys.stderr)
        return 2
    template = json.loads(json.dumps(TEMPLATE_AUDIT))
    if args.title:
        template["target"]["title"] = args.title
    audit_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {audit_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperunit",
        description=(
            "Executable paper audits: bind paper claims to checks a third party "
            "can re-run. No scores, no rankings."
        ),
    )
    parser.add_argument("--version", action="version", version=f"paperunit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="execute an audit and write reports")
    run.add_argument("--audit", required=True, help="path to audit.json")
    run.add_argument("--out", required=True, help="output directory")
    run.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    run.set_defaults(func=cmd_run)

    verify = sub.add_parser("verify", help="re-run an audit and compare with a report")
    verify.add_argument("--audit", required=True, help="path to audit.json")
    verify.add_argument("--report", required=True, help="path to audit_report.json")
    verify.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    verify.set_defaults(func=cmd_verify)

    validate = sub.add_parser("validate", help="validate an audit file")
    validate.add_argument("--audit", required=True, help="path to audit.json")
    validate.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    validate.set_defaults(func=cmd_validate)

    registry = sub.add_parser("registry", help="static registry operations")
    registry_sub = registry.add_subparsers(dest="registry_command", required=True)
    build = registry_sub.add_parser("build", help="build index.json + index.html")
    build.add_argument("--audits-dir", default="registry/audits", help="directory of audit_report.json files")
    build.add_argument("--out", default="registry/site", help="output directory")
    build.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    build.set_defaults(func=cmd_registry_build)

    init = sub.add_parser("init", help="scaffold a new audit.json")
    init.add_argument("--dir", required=True, help="directory for the new audit")
    init.add_argument("--title", default=None, help="optional paper title")
    init.add_argument("--force", action="store_true", help="overwrite an existing audit.json")
    init.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
