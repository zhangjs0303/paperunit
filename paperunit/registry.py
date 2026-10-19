"""Static registry builder for paperunit audit reports.

Scans an ``audits/`` tree for ``audit_report.json`` files (the artefact written
by the audit engine) and writes two plain static files:

* ``index.json`` - machine-readable index of the reports;
* ``index.html`` - a single static HTML page, no JavaScript, no CDN, no backend.

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
import html
import json
import os
import sys
from pathlib import Path
from typing import Any

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


def _entry_from_report(
    report: dict[str, Any],
    report_path: str,
    file_sha256: str,
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
# Rendering
# ---------------------------------------------------------------------------

def render_index_json(index: dict[str, Any]) -> str:
    """Serialise the index as deterministic, human-readable JSON."""
    return json.dumps(index, ensure_ascii=False, indent=2) + "\n"


def _relative_href(audits_dir: Path, out_dir: Path, report_path: str) -> str:
    """Best-effort relative link from the generated page to the report file."""
    target = (audits_dir / report_path).resolve()
    try:
        base = out_dir.resolve()
        relative = os.path.relpath(target, base)
    except (OSError, ValueError):  # pragma: no cover - different drives etc.
        return report_path
    return Path(relative).as_posix()


def _short_sha256(value: str, length: int = 12) -> str:
    if not value:
        return ""
    return value[:length] + ("..." if len(value) > length else "")


def _render_table_row(entry: dict[str, Any], href: str) -> str:
    counts = entry["verdict_counts"]
    title = html.escape(entry["title"])
    audited_by = html.escape(entry["audited_by"])
    date = html.escape(entry["date"]) if entry["date"] else "未标注"
    sha256 = entry["report_sha256"]
    sha_title = html.escape(sha256)
    sha_short = html.escape(_short_sha256(sha256))
    href_attr = html.escape(href, quote=True)
    path_text = html.escape(entry["report_path"])
    return (
        "      <tr>\n"
        f"        <td class=\"date\">{date}</td>\n"
        f"        <td class=\"title\">{title}</td>\n"
        f"        <td>{audited_by}</td>\n"
        f"        <td class=\"num s\">{counts['SUPPORTED']}</td>\n"
        f"        <td class=\"num r\">{counts['REFUTED']}</td>\n"
        f"        <td class=\"num i\">{counts['INCONCLUSIVE']}</td>\n"
        f"        <td class=\"num n\">{counts['NOT_RUN']}</td>\n"
        "        <td class=\"report\">"
        f"<a href=\"{href_attr}\"><code>{path_text}</code></a>"
        f"<br><code class=\"sha\" title=\"{sha_title}\">{sha_short}</code></td>\n"
        "      </tr>\n"
    )


_HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>paperunit 审计登记处</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, "Segoe UI", "Noto Sans CJK SC", sans-serif;
           max-width: 1100px; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; }
    h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
    .lede { color: #666; margin-top: 0; }
    .notice { border-left: 4px solid #999; padding: 0.6rem 1rem; margin: 1.2rem 0;
              background: rgba(127,127,127,0.08); }
    .notice p { margin: 0.35rem 0; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border: 1px solid rgba(127,127,127,0.35); padding: 0.4rem 0.55rem;
             text-align: left; vertical-align: top; }
    th { background: rgba(127,127,127,0.12); font-weight: 600; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    td.s { color: #1a7f37; }
    td.r { color: #b42318; }
    td.i { color: #8a5a00; }
    td.n { color: #666; }
    td.date { white-space: nowrap; }
    code { font-size: 0.85em; }
    .sha { color: #666; }
    .legend dt { font-weight: 600; }
    .legend dd { margin: 0 0 0.35rem 1.2rem; }
    footer { margin-top: 2rem; color: #666; font-size: 0.85rem; }
  </style>
</head>
<body>
  <h1>paperunit 审计登记处</h1>
  <p class="lede">可执行论文审计报告的静态索引。没有分数，没有排名。</p>

  <div class="notice">
    <p><strong>声明：</strong>本页只登记针对论文中具体 claim 的可执行检查结果。
    每条 verdict 都绑定一个 commit、一组命令和一次运行环境；它不是对论文科学价值、
    作者能力或研究诚信的评价。</p>
    <p>REFUTED 表示在给定 commit 与环境下预注册的检查未通过，不表示作者存在学术不端；
    遇到分歧时以报告中的证据与作者回应为准。报告可被第三方重新运行。</p>
  </div>

  <h2>图例</h2>
  <dl class="legend">
    <dt>SUPPORTED</dt><dd>检查已运行，且全部预注册期望均满足。</dd>
    <dt>REFUTED</dt><dd>检查已运行，且至少一项预注册期望未满足。</dd>
    <dt>INCONCLUSIVE</dt><dd>检查无法判定（工具链缺失、超时、统计功效不足、形式化未通过等）。</dd>
    <dt>NOT_RUN</dt><dd>该 claim 没有可执行检查（例如仅有人审记录）。</dd>
  </dl>
"""

_HTML_FOOT = """  <footer>
    <p>本页由 <code>paperunit.registry.build_registry</code> 从 <code>audit_report.json</code>
    静态生成；无 JavaScript、无后端、无外部依赖。</p>
  </footer>
</body>
</html>
"""


def render_index_html(
    index: dict[str, Any],
    audits_dir: Path,
    out_dir: Path,
) -> str:
    """Render the static HTML index (no JavaScript, no external resources)."""
    entries = index["audits"]
    parts = [_HTML_HEAD]
    if not entries:
        parts.append(
            "\n  <h2>审计报告</h2>\n"
            "  <p>尚无审计报告。把包含 <code>audit_report.json</code> 的目录放进 "
            "<code>audits/</code>，然后重建本页。</p>\n"
        )
    else:
        parts.append(
            f"\n  <h2>审计报告（{index['count']} 份）</h2>\n"
            "  <table>\n"
            "    <thead>\n"
            "      <tr>\n"
            "        <th>日期</th>\n"
            "        <th>论文 / 目标</th>\n"
            "        <th>审计者</th>\n"
            "        <th class=\"num\">SUPPORTED</th>\n"
            "        <th class=\"num\">REFUTED</th>\n"
            "        <th class=\"num\">INCONCLUSIVE</th>\n"
            "        <th class=\"num\">NOT_RUN</th>\n"
            "        <th>报告</th>\n"
            "      </tr>\n"
            "    </thead>\n"
            "    <tbody>\n"
        )
        for entry in entries:
            href = _relative_href(audits_dir, out_dir, entry["report_path"])
            parts.append(_render_table_row(entry, href))
        parts.append("    </tbody>\n  </table>\n")
        parts.append(
            "\n  <p class=\"lede\">按日期倒序排列；日期缺失的报告排在末尾。<br>"
            "sha256 前缀为报告文件的内容哈希；点开报告可复核完整证据。</p>\n"
        )
    parts.append(_HTML_FOOT)
    return "".join(parts)


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
        Directory that receives ``index.json`` and ``index.html`` (created if
        missing).  A tree inside ``audits_dir`` is skipped during the scan.

    Returns
    -------
    dict
        The JSON-compatible index that was written to ``index.json``::

            {"schema": "paperunit/registry/v1",
             "count": 2,
             "audits": [{"title": ..., "audited_by": ..., "date": ...,
                         "verdict_counts": {...}, "report_sha256": ...,
                         "report_path": "relative/path/audit_report.json"},
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
    warnings: list[dict[str, str]] = []
    for report_file in _find_report_files(audits_path, out_path):
        relative = report_file.relative_to(audits_path).as_posix()
        try:
            report, file_sha256 = _load_report(report_file)
        except (OSError, ValueError) as exc:
            warnings.append({"report_path": relative, "error": str(exc)})
            continue
        entries.append(_entry_from_report(report, relative, file_sha256))

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
    index_html = render_index_html(index, audits_path, out_path)
    _write_text(out_path / "index.json", index_json)
    _write_text(out_path / "index.html", index_html)
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
        help="output directory for index.json and index.html (default: registry/site)",
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
