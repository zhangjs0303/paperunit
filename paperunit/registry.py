"""Static registry builder for paperunit audit reports.

Scans an ``audits/`` tree for ``audit_report.json`` files (the artefact written
by the audit engine), writes ``index.json`` (machine-readable index) and then
delegates the HTML site to :mod:`paperunit.site` (landing page, registry browser
and one dossier page per audit).

Design constraints:

* Standard library only; no network access, ever.
* Deterministic: the same input tree always yields byte-identical output, so
  the registry can be rebuilt in CI and diffed.  No wall-clock timestamps are
  stored in the index.
* Tolerant: a report with missing or malformed fields is still indexed with
  defaults; a file that is not valid JSON is skipped and listed under
  ``warnings`` so a build never crashes because of one bad report.

The registry is an index of *artefacts*, not a ranking.  It carries no score,
no ordering by quality, and no aggregate judgement of papers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from .site import build_site

REGISTRY_SCHEMA = "paperunit/registry/v1"
REPORT_FILENAME = "audit_report.json"

# Keep in sync with paperunit.VERDICTS.  Duplicated on purpose so the registry
# builder has no import-time dependency on the rest of the package.
VERDICTS: tuple[str, ...] = ("SUPPORTED", "REFUTED", "INCONCLUSIVE", "NOT_RUN")

UNTITLED = "(untitled audit)"
UNKNOWN_AUTHOR = "unknown"


# ---------------------------------------------------------------------------
# Tolerant field readers
# ---------------------------------------------------------------------------


def _as_dict(value: Any) -> dict[str, Any]:
    """Return ``value`` if it is a dict, else an empty dict."""
    return value if isinstance(value, dict) else {}


def _as_str(value: Any, default: str = "") -> str:
    """Return a stripped string, or ``default`` for missing/blank values."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return default


def _as_count(value: Any) -> int:
    """Coerce a verdict count to a non-negative int."""
    if isinstance(value, bool):  # bool is an int subclass; refuse it explicitly
        return 0
    if isinstance(value, (int, float, str)):
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            return 0
        return parsed if parsed >= 0 else 0
    return 0


def _count_verdicts(report: dict[str, Any]) -> dict[str, int]:
    """Read ``verdict_counts``, falling back to counting claim verdicts."""
    counts = {verdict: 0 for verdict in VERDICTS}
    raw_counts = report.get("verdict_counts")
    if isinstance(raw_counts, dict):
        for verdict in VERDICTS:
            counts[verdict] = _as_count(raw_counts.get(verdict))
        return counts

    claims = report.get("claims")
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            verdict = claim.get("verdict")
            if isinstance(verdict, str) and verdict in counts:
                counts[verdict] += 1
    return counts


def _slug_for(relative: str, used: set[str]) -> str:
    """Deterministic URL slug for one report path."""
    parent = relative.rsplit("/", 1)[0] if "/" in relative else ""
    base = parent.strip("/") or "audit"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-._").lower() or "audit"
    candidate = slug
    suffix = 2
    while candidate in used:
        candidate = f"{slug}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _entry_from_report(
    report: dict[str, Any],
    report_path: str,
    file_sha256: str,
    slug: str,
) -> dict[str, Any]:
    """Build one index entry from a parsed report.

    All fields are optional: missing ones fall back to documented defaults.
    """
    target = _as_dict(report.get("target"))
    report_sha256 = _as_str(report.get("report_sha256"), default="")
    if not report_sha256:
        # be honest about the fallback: no content hash was provided by the
        # report, so use the hash of the report file itself.
        report_sha256 = file_sha256
    return {
        "title": _as_str(target.get("title"), default=UNTITLED),
        "audited_by": _as_str(target.get("audited_by"), default=UNKNOWN_AUTHOR),
        "date": _as_str(target.get("date"), default=""),
        "verdict_counts": _count_verdicts(report),
        "report_sha256": report_sha256,
        "report_path": report_path,
        "slug": slug,
    }


# ---------------------------------------------------------------------------
# Collection and ordering
# ---------------------------------------------------------------------------


def _find_report_files(audits_dir: Path, out_dir: Path) -> list[Path]:
    """Recursively find report files, sorted; skip the registry output tree."""
    try:
        out_resolved = out_dir.resolve()
        audits_resolved = audits_dir.resolve()
    except OSError:  # pragma: no cover - unreadable parent directories
        out_resolved = out_dir
        audits_resolved = audits_dir
    # Only skip the output tree when it is a *separate* directory; if the caller
    # passes the same directory for both, every report would otherwise vanish.
    skip_out_tree = out_resolved != audits_resolved
    found: list[Path] = []
    for path in audits_dir.rglob(REPORT_FILENAME):
        if not path.is_file():
            continue
        if skip_out_tree:
            try:
                if path.resolve().is_relative_to(out_resolved):
                    continue
            except (OSError, ValueError):  # pragma: no cover - defensive
                pass
        found.append(path)
    found.sort(key=lambda item: item.relative_to(audits_dir).as_posix())
    return found


def _sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest first; entries without a date go last, ordered by path."""
    dated = [entry for entry in entries if entry["date"]]
    undated = [entry for entry in entries if not entry["date"]]
    # Two stable passes: path ascending, then date descending.
    dated.sort(key=lambda entry: entry["report_path"])
    dated.sort(key=lambda entry: entry["date"], reverse=True)
    undated.sort(key=lambda entry: entry["report_path"])
    return dated + undated


def _load_report(path: Path) -> tuple[dict[str, Any], str]:
    """Parse one report file. Returns ``(report, file_sha256)``.

    Raises ``ValueError`` for anything that is not a JSON object.
    """
    raw = path.read_bytes()
    file_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"report is not valid UTF-8: {exc}") from exc
    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError(f"report is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"report must be a JSON object, got {type(parsed).__name__}")
    return parsed, file_sha256


# ---------------------------------------------------------------------------
# Rendering (index.json only; HTML lives in paperunit.site)
# ---------------------------------------------------------------------------


def render_index_json(index: dict[str, Any]) -> str:
    """Serialise the index as deterministic, human-readable JSON."""
    return json.dumps(index, ensure_ascii=False, indent=2) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_registry(audits_dir: Path | str, out_dir: Path | str) -> dict[str, Any]:
    """Build the static registry for one audit tree.

    Parameters
    ----------
    audits_dir:
        Directory scanned recursively for ``audit_report.json`` files.
    out_dir:
        Directory that receives ``index.json``, the generated site and its
        assets (created if missing).  A tree inside ``audits_dir`` is skipped
        during the scan.

    Returns
    -------
    dict
        The JSON-compatible index that was written to ``index.json``::

            {"schema": "paperunit/registry/v1",
             "count": 2,
             "audits": [{"title": ..., "audited_by": ..., "date": ...,
                         "verdict_counts": {...}, "report_sha256": ...,
                         "report_path": "relative/path/audit_report.json",
                         "slug": "..."},
                        ...],
             "warnings": [{"report_path": ..., "error": ...}]  # optional
             }

    Deterministic: the same inputs and output directory produce byte-identical
    files on every run.
    """
    audits_path = Path(audits_dir)
    out_path = Path(out_dir)
    if not audits_path.is_dir():
        raise FileNotFoundError(f"audits directory not found: {audits_path}")

    entries: list[dict[str, Any]] = []
    loaded: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    warnings: list[dict[str, str]] = []
    used_slugs: set[str] = set()
    for report_file in _find_report_files(audits_path, out_path):
        relative = report_file.relative_to(audits_path).as_posix()
        try:
            report, file_sha256 = _load_report(report_file)
        except (OSError, ValueError) as exc:
            warnings.append({"report_path": relative, "error": str(exc)})
            continue
        slug = _slug_for(relative, used_slugs)
        entry = _entry_from_report(report, relative, file_sha256, slug)
        entries.append(entry)
        loaded.append((relative, report, entry))

    index: dict[str, Any] = {
        "schema": REGISTRY_SCHEMA,
        "count": len(entries),
        "audits": _sort_entries(entries),
    }
    if warnings:
        warnings.sort(key=lambda item: item["report_path"])
        index["warnings"] = warnings

    out_path.mkdir(parents=True, exist_ok=True)
    index_json = render_index_json(index)
    _write_text(out_path / "index.json", index_json)

    ordered = _sort_entries(entries)
    order_key = {entry["report_path"]: position for position, entry in enumerate(ordered)}
    loaded.sort(key=lambda item: order_key[item[2]["report_path"]])
    build_site(index, loaded, out_path, audits_path)
    return index


def _write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with ``\\n`` newlines on every platform."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: ``python -m paperunit.registry``."""
    parser = argparse.ArgumentParser(
        prog="python -m paperunit.registry",
        description="Build the static paperunit registry from audit reports.",
    )
    parser.add_argument(
        "--audits-dir",
        default="registry/audits",
        help="directory scanned recursively for audit_report.json (default: registry/audits)",
    )
    parser.add_argument(
        "--out",
        default="registry/site",
        help="output directory for index.json and the site (default: registry/site)",
    )
    args = parser.parse_args(argv)

    try:
        index = build_registry(Path(args.audits_dir), Path(args.out))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"registry: indexed {index['count']} audit report(s) into {args.out}")
    for warning in index.get("warnings", []):
        print(
            f"warning: skipped {warning['report_path']}: {warning['error']}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
