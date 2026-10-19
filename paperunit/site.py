"""Static site generation for the paperunit audit registry.

The site is a small, dependency-free "evidence ledger": a landing page, an
auditable registry and one dossier page per audit report.  Everything is
generated from ``audit_report.json`` files with the standard library; the only
assets are a stylesheet, a small progressive-enhancement script and a few
the Liquid Glass stylesheet and tiny enhancement script.

Design constraints:

* no JavaScript framework, no CDN, no network requests at runtime;
* every value coming from a report is HTML-escaped;
* deterministic output (no timestamps in rendered HTML);
* the generated site still works without JavaScript (search/filter is an
  enhancement, not a requirement).
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from . import __version__

SITE_ASSETS = Path(__file__).resolve().parent / "site_assets"
GITHUB_URL = "https://github.com/zhangjs0303/paperunit"

VERDICTS: tuple[str, ...] = ("SUPPORTED", "REFUTED", "INCONCLUSIVE", "NOT_RUN")
# The UI keeps the raw verdict tokens: they are the machine-readable contract,
# and the meaning is always adjacent (legend / tally caption).
VERDICT_LABEL = {verdict: verdict for verdict in VERDICTS}
VERDICT_MEANING = {
    "SUPPORTED": "every preregistered expectation passed",
    "REFUTED": "a preregistered expectation failed",
    "INCONCLUSIVE": "could not decide (toolchain, timeout, underpowered, ...)",
    "NOT_RUN": "no executable check (human review only)",
}

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' fill='%23191510'/%3E"
    "%3Crect x='4' y='4' width='24' height='24' fill='%23b9371b'/%3E"
    "%3Ctext x='16' y='23' font-family='monospace' font-size='17' "
    "text-anchor='middle' fill='%23f4efe3'%3EP%3C/text%3E%3C/svg%3E"
)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _e(value: Any) -> str:
    """Escape text for HTML content and attributes."""
    return html.escape("" if value is None else str(value), quote=True)


def _num(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return _e(value)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _short(value: Any, length: int = 16) -> str:
    text = "" if value is None else str(value)
    return text[:length] + ("..." if len(text) > length else "")


def _truncate(value: Any, length: int = 240) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    return text if len(text) <= length else text[: length - 1] + "…"


def _tally(counts: dict[str, int], compact: bool = False) -> str:
    chips = []
    for verdict in VERDICTS:
        count = int(counts.get(verdict, 0))
        if count == 0 and compact:
            continue
        chips.append(
            f'<span class="chip chip--{verdict}">{VERDICT_LABEL[verdict]} · {count}</span>'
        )
    if not chips:
        chips.append('<span class="chip chip--plain">no claims</span>')
    return "".join(chips)


def _counts(entry: dict[str, Any]) -> dict[str, int]:
    raw = entry.get("verdict_counts") or {}
    return {verdict: int(raw.get(verdict, 0) or 0) for verdict in VERDICTS}


def _total_claims(entry: dict[str, Any]) -> int:
    counts = _counts(entry)
    return sum(counts.values())


def _page(
    *,
    title: str,
    description: str,
    root: str,
    active: str,
    body: str,
    body_class: str = "",
) -> str:
    """Assemble one full HTML page."""
    nav_items = [
        ("registry", root + "audits/index.html", "Registry"),
        ("how", root + "index.html#how", "How it works"),
        ("principle", root + "index.html#principles", "Principles"),
    ]
    nav_html = ""
    for key, href, label in nav_items:
        current = ' aria-current="page"' if key == active else ""
        nav_html += f'<a href="{href}"{current}>{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<meta name="description" content="{_e(description)}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="{root}assets/style.css">
<script>
try {{
  var t = localStorage.getItem("paperunit-theme");
  if (t === "dark" || (t === null && matchMedia("(prefers-color-scheme: dark)").matches)) {{
    document.documentElement.setAttribute("data-theme", "dark");
  }}
}} catch (err) {{}}
</script>
</head>
<body class="{_e(body_class)}">
<a class="skip-link" href="#main">Skip to content</a>
<div class="ambient" aria-hidden="true">
  <span class="orb orb--1"></span>
  <span class="orb orb--2"></span>
  <span class="orb orb--3"></span>
</div>
<header class="topbar">
  <div class="shell topbar__inner">
    <a class="brand" href="{root}index.html">
      <span class="brand__mark" aria-hidden="true">P</span>
      <span class="brand__word"><b>paperunit</b><span>executable paper audits</span></span>
    </a>
    <nav class="nav" aria-label="Primary">
      {nav_html}
      <a href="{GITHUB_URL}" rel="noopener">GitHub ↗</a>
      <button class="theme-toggle" type="button" data-theme-toggle hidden
              aria-pressed="false">
        <span class="sr-only">Switch theme:</span> <span data-theme-label>Dark</span>
      </button>
    </nav>
  </div>
</header>
<main id="main" class="skip-anchor">
{body}
</main>
<footer class="footer">
  <div class="shell">
    <div class="footer__grid">
      <div class="footer__brand">
        <b>paperunit</b>
        <p>Bind a paper's claims to checks a stranger can execute. Verdicts are
        evidence-local; no scores, no rankings. 可执行论文审计 —— 有证据，不排名。</p>
      </div>
      <div>
        <h2>Site</h2>
        <ul>
          <li><a href="{root}audits/index.html">Audit registry</a></li>
          <li><a href="{root}index.html#how">How it works</a></li>
          <li><a href="{root}index.html#principles">Principles</a></li>
        </ul>
      </div>
      <div>
        <h2>Project</h2>
        <ul>
          <li><a href="{GITHUB_URL}" rel="noopener">Source &amp; issues ↗</a></li>
          <li><a href="{GITHUB_URL}/blob/main/OPS.md" rel="noopener">Operations manual ↗</a></li>
          <li><a href="{GITHUB_URL}/blob/main/docs/protocol.md" rel="noopener">Audit protocol ↗</a></li>
          <li><a href="{GITHUB_URL}/blob/main/docs/ethics.md" rel="noopener">Ethics &amp; red lines ↗</a></li>
        </ul>
      </div>
      <div>
        <h2>Fine print</h2>
        <ul>
          <li><a href="{GITHUB_URL}/blob/main/LICENSE" rel="noopener">Apache-2.0 licence ↗</a></li>
          <li>Reports: CC-BY-4.0</li>
          <li>Index data: CC0</li>
          <li>No tracker, no cookies.</li>
        </ul>
      </div>
    </div>
    <div class="footer__meta">
      <span>Generated statically from audit_report.json · paperunit {__version__}</span>
      <span>An audit is evidence, not a verdict on a paper's worth.</span>
    </div>
  </div>
</footer>
<script src="{root}assets/app.js" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# assets and raw reports
# ---------------------------------------------------------------------------


def _copy_assets(out_dir: Path) -> None:
    destination = out_dir / "assets"
    if SITE_ASSETS.is_dir():
        for source in sorted(SITE_ASSETS.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            target = destination / source.relative_to(SITE_ASSETS)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def _copy_raw_artifacts(
    out_dir: Path, slug: str, report_file: Path
) -> dict[str, str]:
    """Copy the raw JSON/report.md/author response next to the dossier page."""
    target_dir = out_dir / "audits" / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    links: dict[str, str] = {}
    if report_file.is_file():
        raw = target_dir / "report.json"
        shutil.copyfile(report_file, raw)
        links["json"] = f"{slug}/report.json"
    companion = report_file.with_name("report.md")
    if companion.is_file():
        target = target_dir / "report.md"
        shutil.copyfile(companion, target)
        links["markdown"] = f"{slug}/report.md"
    response = report_file.with_name("author_response.md")
    if response.is_file():
        target = target_dir / "author_response.md"
        shutil.copyfile(response, target)
        links["author_response"] = f"{slug}/author_response.md"
    return links


# ---------------------------------------------------------------------------
# landing page
# ---------------------------------------------------------------------------


def _aggregate(loaded: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = {verdict: 0 for verdict in VERDICTS}
    claims = 0
    for item in loaded:
        counts = _counts(item["entry"])
        for verdict in VERDICTS:
            verdicts[verdict] += counts[verdict]
        claims += counts_sum(counts)
    latest = loaded[0]["entry"].get("date", "") if loaded else ""
    return {
        "audits": len(loaded),
        "claims": claims,
        "verdicts": verdicts,
        "latest": latest,
    }


def counts_sum(counts: dict[str, int]) -> int:
    return sum(int(counts.get(verdict, 0)) for verdict in VERDICTS)


def _verdict_bars(counts: dict[str, int]) -> str:
    total = counts_sum(counts)
    if total <= 0:
        return '<div class="verdict-bars"><span class="b-none" style="width:100%"></span></div>'
    spans = []
    classes = {
        "SUPPORTED": "b-ok",
        "REFUTED": "b-bad",
        "INCONCLUSIVE": "b-warn",
        "NOT_RUN": "b-none",
    }
    for verdict in VERDICTS:
        count = counts.get(verdict, 0)
        if count <= 0:
            continue
        width = 100.0 * count / total
        spans.append(
            f'<span class="{classes[verdict]}" style="width:{width:.2f}%"></span>'
        )
    return f'<div class="verdict-bars" aria-hidden="true">{"".join(spans)}</div>'


def _case_card(item: dict[str, Any], index: int) -> str:
    entry = item["entry"]
    slug = entry["slug"]
    date = entry.get("date") or "undated"
    title = entry.get("title") or "untitled audit"
    by = entry.get("audited_by") or "unknown"
    return f"""
<article class="case reveal" style="--i:{index % 6}">
  <div class="case__no"><span>No. {index + 1:03d}</span><span>{_e(date)}</span></div>
  <h3><a href="audits/{_e(slug)}.html">{_e(title)}</a></h3>
  <p class="case__by">audited by {_e(by)}</p>
  <div class="case__tally">{_tally(_counts(entry), compact=True)}</div>
  <span class="case__path">{_e(entry.get("report_path"))}</span>
</article>
"""


def _empty_state() -> str:
    return """
<div class="empty-state">
  <p>No audits yet · 尚无审计报告</p>
  <p class="mono">Add a directory containing <code>audit_report.json</code> to
  <code>registry/audits/</code> and rebuild.</p>
</div>
"""


def render_landing(loaded: list[dict[str, Any]]) -> str:
    stats = _aggregate(loaded)
    counts = stats["verdicts"]
    latest_cases = "".join(
        _case_card(item, index) for index, item in enumerate(loaded[:3])
    )
    if not latest_cases:
        latest_cases = _empty_state()

    verdict_legend = "".join(
        f"""
      <div class="legend__cell reveal" style="--i:{index}">
        <span class="chip chip--{verdict}">{VERDICT_LABEL[verdict]}</span>
        <p>{VERDICT_MEANING[verdict]}</p>
      </div>"""
        for index, verdict in enumerate(VERDICTS)
    )

    steps = [
        ("01", "Preregister", "An audit.json fixes the target, scope, tolerances and seeds before anything runs."),
        ("02", "Execute", "One checker runs one command per claim. Deterministic where possible, toolchains declared."),
        ("03", "Judge", "Each claim gets one evidence-local verdict: supported, refuted, inconclusive or not run."),
        ("04", "Publish", "report.json + report.md carry commands, hashes, uncertainty and explicit limits."),
        ("05", "Re-run", "verify recomputes the digest and re-executes every check; it detects drift and tampering."),
    ]
    steps_html = "".join(
        f"""
      <div class="step reveal" style="--i:{index}">
        <span class="step__no">{number}</span>
        <h3>{title}</h3>
        <p>{copy}</p>
      </div>"""
        for index, (number, title, copy) in enumerate(steps)
    )

    principles = [
        ("01", "No scores.", "Counts are not quality. An audit never produces a ranking, a reproducibility percentage or a leaderboard."),
        ("02", "Evidence-local.", "Every verdict belongs to one claim, one commit and one declared environment. Nothing aggregates into a judgement of a paper."),
        ("03", "Re-runnable.", "A stranger can re-execute the report. verify distinguishes a changed result (DRIFT) from a modified report (TAMPERED)."),
        ("04", "Right of reply.", "Reports carry an author-response slot and a 14–30 day window. The project audits artefacts, not people."),
    ]
    principles_html = "".join(
        f"""
      <div class="principle reveal" style="--i:{index}">
        <span class="principle__no">{number}</span>
        <div>
          <h3>{title}</h3>
          <p>{copy}</p>
        </div>
      </div>"""
        for index, (number, title, copy) in enumerate(principles)
    )

    run_commands = (
        "cd paperunit\n"
        "python3 -m paperunit run    --audit examples/lean_paper_ncc/audit.json --out out/lean\n"
        "python3 -m paperunit verify --audit examples/lean_paper_ncc/audit.json "
        "--report out/lean/audit_report.json\n"
        "# Verification: REPRODUCIBLE"
    )

    return f"""
<section class="hero shell">
  <div class="reveal">
    <p class="eyebrow">Executable paper audits · 可执行论文审计</p>
    <h1>Every claim gets a <em>re-run.</em></h1>
    <p class="hero__lede">
      paperunit binds a paper's claim to a command a stranger can execute. It
      publishes the evidence, the uncertainty and the limits — never a score.
      A verdict is about one claim on one artefact, not about a paper's worth.
    </p>
    <div class="hero__actions">
      <a class="btn btn--primary" href="audits/index.html">Browse the registry →</a>
      <a class="btn" href="#how">How it works</a>
      <a class="btn btn--ghost" href="{GITHUB_URL}" rel="noopener">Source on GitHub ↗</a>
    </div>
    <p class="hero__footnote">NO SCORES · NO RANKINGS · EVIDENCE-LOCAL VERDICTS</p>
  </div>
  <aside class="ledger reveal" style="--i:1" aria-label="Audit ledger summary">
    <div class="ledger__label"><span>Audit ledger</span><b>live</b></div>
    <div class="stats">
      <div class="stat"><b>{stats['audits']}</b><span>audits indexed</span></div>
      <div class="stat"><b>{stats['claims']}</b><span>claims executed</span></div>
      <div class="stat"><b>{counts['SUPPORTED']}</b><span>supported</span></div>
      <div class="stat"><b>{counts['REFUTED']}</b><span>refuted</span></div>
    </div>
    {_verdict_bars(counts)}
    <p class="ledger__note">
      Latest report date: <span class="mono">{_e(stats['latest'] or '—')}</span>.
      The counts are a ledger, not a score: read the individual reports.
    </p>
    <span class="stamp">Evidence, not vibes</span>
  </aside>
</section>

<section class="section shell" id="how">
  <div class="section__head">
    <div>
      <p class="kicker">01 / Method</p>
      <h2>From a sentence in a paper to a verdict you can re-run.</h2>
    </div>
    <p>No review committee, no reputation points. The unit of work is a claim
    bound to an executable check and shipped with its evidence.</p>
  </div>
  <div class="steps">{steps_html}</div>
  <div style="margin-top:26px" class="legend">{verdict_legend}</div>
</section>

<section class="section shell" id="audits">
  <div class="section__head">
    <div>
      <p class="kicker">02 / Registry</p>
      <h2>Recent case files.</h2>
    </div>
    <a class="btn btn--ghost" href="audits/index.html">All audits →</a>
  </div>
  <div class="cases">{latest_cases}</div>
</section>

<section class="section shell" id="run">
  <div class="split">
    <div>
      <p class="kicker">03 / Run it</p>
      <h2>Clone, run, verify.</h2>
      <p>The core is standard-library-only. Optional toolchains (z3, Lean 4)
      are detected; when they are absent a claim is <span class="mono">INCONCLUSIVE</span>,
      never a false verdict. Every report can be checked by someone who does
      not trust its author.</p>
      <div class="hero__actions">
        <a class="btn" href="{GITHUB_URL}#quickstart" rel="noopener">Quickstart ↗</a>
        <a class="btn btn--ghost" href="{root_registry()}">Open the registry</a>
      </div>
    </div>
    <div class="terminal reveal" style="--i:1">
      <div class="terminal__bar"><i></i><i></i><i></i><span>paperunit — zsh</span></div>
      <pre tabindex="0"><span class="cmt"># claim → check → verdict → report → verify</span>
<span class="cmd">cd paperunit</span>
<span class="cmd">python3 -m paperunit run</span>    <span class="prm">--audit</span> examples/lean_paper_ncc/audit.json <span class="prm">--out</span> out/lean
<span class="cmd">python3 -m paperunit verify</span> <span class="prm">--audit</span> examples/lean_paper_ncc/audit.json <span class="prm">--report</span> out/lean/audit_report.json
<span class="cmt">Verification: REPRODUCIBLE</span>
<span class="cmt">report_sha256: 79715deb0d30ea65…</span></pre>
      <div class="terminal__foot">
        <span>4 commands · stdlib only</span>
        <button class="copy-btn" type="button" data-copy="{_e(run_commands)}">Copy</button>
      </div>
    </div>
  </div>
</section>

<section class="section shell" id="principles">
  <div class="section__head">
    <div>
      <p class="kicker">04 / Principles</p>
      <h2>What this project refuses to be.</h2>
    </div>
    <p>These are constraints, not aspirations. The operating manual and the
    protocol spell out the red lines; the registry applies them.</p>
  </div>
  <div class="principles">{principles_html}</div>
</section>
"""


def root_registry() -> str:
    return "audits/index.html"


# ---------------------------------------------------------------------------
# registry page
# ---------------------------------------------------------------------------


def render_registry(loaded: list[dict[str, Any]]) -> str:
    rows = []
    for item in loaded:
        entry = item["entry"]
        slug = entry["slug"]
        counts = _counts(entry)
        verdicts_present = " ".join(
            verdict for verdict in VERDICTS if counts.get(verdict, 0) > 0
        )
        claims = item["report"].get("claims") or []
        claim_text = " ".join(
            str(claim.get("text", "")) + " " + str(claim.get("id", ""))
            for claim in claims
            if isinstance(claim, dict)
        )
        haystack = " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("audited_by", "")),
                str(entry.get("date", "")),
                str(entry.get("report_path", "")),
                verdicts_present,
                claim_text,
            ]
        )
        rows.append(
            f"""
<article class="audit-row" data-audit
         data-verdicts="{_e(verdicts_present)}"
         data-search="{_e(haystack)}">
  <div class="audit-row__date">{_e(entry.get('date') or 'undated')}</div>
  <div>
    <h2 class="audit-row__title"><a href="{_e(slug)}.html">{_e(entry.get('title') or 'untitled audit')}</a></h2>
    <p class="audit-row__path">{_e(entry.get('report_path'))}</p>
  </div>
  <div class="audit-row__by">audited by<br>{_e(entry.get('audited_by') or 'unknown')}</div>
  <div class="audit-row__tally">{_tally(counts, compact=True)}</div>
  <div class="audit-row__sha">sha256<br>{_e(_short(entry.get('report_sha256'), 14))}</div>
</article>"""
        )

    list_html = "".join(rows)
    empty = _empty_state() if not rows else ""
    count = len(rows)
    return f"""
<div class="shell">
  <header class="page-head">
    <p class="eyebrow">Audit registry · 审计登记处</p>
    <h1>Case files, not a leaderboard.</h1>
    <p>Every entry is a generated <span class="mono">audit_report.json</span>:
    commands, verdicts, evidence hashes, uncertainty and limits. Entries are
    ordered by date. Read the report before drawing conclusions; counts are not
    a score.</p>
  </header>

  <div class="controls" role="search" aria-label="Filter audits">
    <label class="search">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           aria-hidden="true"><circle cx="11" cy="11" r="6.5"></circle><path d="M16 16l4 4"></path></svg>
      <span class="sr-only">Search audits</span>
      <input type="search" placeholder="Search title, author, claim, sha…" data-audit-search autocomplete="off">
    </label>
    <div class="filters" role="group" aria-label="Filter by verdict">
      <button class="filter" type="button" data-audit-filter="ALL" aria-pressed="true">All</button>
      {''.join(
        f'<button class="filter" type="button" data-audit-filter="{verdict}" aria-pressed="false">{VERDICT_LABEL[verdict]}</button>'
        for verdict in VERDICTS
      )}
    </div>
    <span class="result-count" data-result-count aria-live="polite">{count} audits</span>
  </div>

  <section class="audit-list" data-audit-list aria-label="Audit reports">
    {list_html}
  </section>
  <div data-empty-state class="{'is-hidden' if rows else ''}">{empty}</div>

  <div class="note" style="margin-top:26px">
    <strong>Demo entries.</strong> Reports under <code>registry/audits/demo-*</code>
    are self-tests of the pipeline, not published audits. Lean and z3 demos need
    the optional toolchains; on a machine without them a re-run reports
    <span class="mono">INCONCLUSIVE</span>/<span class="mono">DRIFT</span>, never a
    false verdict.
  </div>

  <div class="prevnext" style="margin-top:34px">
    <a href="../index.html">← Home</a>
    <span>{count} reports in this registry</span>
    <a href="{GITHUB_URL}/blob/main/registry/README.md" rel="noopener">How to add an audit ↗</a>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# dossier page
# ---------------------------------------------------------------------------


def _verdict_summary(counts: dict[str, int]) -> tuple[str, str]:
    if counts.get("REFUTED", 0) > 0:
        return ("CONTAINS REFUTED CLAIMS", "stamp")
    if counts.get("INCONCLUSIVE", 0) > 0:
        return ("RESOLUTION: PARTIAL", "stamp")
    if counts.get("SUPPORTED", 0) > 0:
        return ("CHECKED CLAIMS SUPPORTED", "stamp ok")
    return ("NO EXECUTABLE CLAIMS", "stamp")


def _render_dl(mapping: dict[str, Any]) -> str:
    if not mapping:
        return ""
    rows = []
    for key in sorted(mapping):
        value = mapping[key]
        if isinstance(value, (dict, list)):
            value_html = f"<code>{_e(_json(value))}</code>"
        elif isinstance(value, float):
            value_html = f"<code>{value:.6g}</code>"
        else:
            rendered = _e(value)
            if len(rendered) > 1200:
                rendered = rendered[:1199] + "…"
            value_html = f"<code>{rendered}</code>"
        rows.append(f"<dt>{_e(key)}</dt><dd>{value_html}</dd>")
    return '<dl class="dl">' + "".join(rows) + "</dl>"


def _render_runs(runs: Any) -> str:
    if not isinstance(runs, list) or not runs:
        return ""
    rows = []
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            continue
        rows.append(
            "<tr>"
            f'<td class="num">{index}</td>'
            f"<td><code>{_e(run.get('cmd', ''))}</code><br>"
            f"<span class=\"mono muted\">cwd {_e(run.get('cwd', ''))}</span></td>"
            f'<td class="num">{_e(run.get("exit_code"))}</td>'
            f'<td class="num">{_e(run.get("duration_s"))}s</td>'
            f'<td><code>{_e(_short(run.get("evidence_sha256"), 18))}</code></td>'
            "</tr>"
        )
    return f"""
<h3>Runs</h3>
<div class="table-wrap"><table class="evidence">
<thead><tr><th class="num">#</th><th>command</th><th class="num">exit</th><th class="num">time</th><th>evidence sha256</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>
"""


def _render_expectations(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return ""
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        passed = item.get("passed") is True
        status = "pass" if passed else "fail"
        rows.append(
            f"<tr><td><code>{_e(item.get('rule'))}</code></td>"
            f"<td>{status}</td>"
            f"<td>{_e(item.get('detail'))}</td></tr>"
        )
    return f"""
<h3>Expectations</h3>
<div class="table-wrap"><table class="evidence">
<thead><tr><th>rule</th><th>result</th><th>detail</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>
"""


def _render_values(value: Any) -> str:
    if isinstance(value, list) and value and all(
        isinstance(item, (int, float)) for item in value
    ):
        return "<h3>Values</h3><p class=\"mono\">" + ", ".join(
            _num(item) for item in value
        ) + "</p>"
    return ""


def _render_evidence(claim: dict[str, Any]) -> str:
    evidence = claim.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    uncertainty = claim.get("uncertainty")
    parts: list[str] = []

    runs = _render_runs(evidence.get("runs"))
    if runs:
        parts.append(runs)
    expectations = _render_expectations(evidence.get("expectations"))
    if expectations:
        parts.append(expectations)

    resolution = evidence.get("resolution")
    if isinstance(resolution, dict) and resolution:
        parts.append("<h3>Resolution</h3>" + _render_dl(resolution))

    margin = evidence.get("margin_policy")
    if isinstance(margin, dict) and margin:
        parts.append("<h3>Margin policy</h3>" + _render_dl(margin))

    if isinstance(uncertainty, dict) and uncertainty:
        parts.append("<h3>Uncertainty</h3>" + _render_dl(uncertainty))

    values = _render_values(evidence.get("values"))
    if values:
        parts.append(values)

    stdout = evidence.get("stdout_excerpt") or evidence.get("stdout")
    if not stdout and isinstance(evidence.get("runs"), list):
        for run in evidence["runs"]:
            if isinstance(run, dict) and run.get("stdout_excerpt"):
                stdout = run["stdout_excerpt"]
                break
    if isinstance(stdout, str) and stdout.strip():
        parts.append(f"<h3>stdout excerpt</h3><pre class=\"term\" tabindex=\"0\">{_e(stdout)}</pre>")

    rendered = {"runs", "expectations", "resolution", "margin_policy", "values"}
    leftovers = {
        key: value
        for key, value in evidence.items()
        if key not in rendered and value not in (None, "", [], {})
    }
    if leftovers:
        parts.append("<h3>Other evidence</h3>" + _render_dl(leftovers))

    if not parts:
        return '<p class="muted">No evidence recorded for this claim.</p>'
    return (
        "<details class=\"evidence\"><summary>Evidence &amp; uncertainty</summary>"
        '<div class="evidence-body">'
        + "".join(parts)
        + "</div></details>"
    )


def _render_claim(claim: dict[str, Any], index: int) -> str:
    verdict = str(claim.get("verdict") or "NOT_RUN")
    if verdict not in VERDICTS:
        verdict = "NOT_RUN"
    claim_id = claim.get("id") or f"C{index + 1}"
    kind = claim.get("kind") or "unknown"
    preregistered = claim.get("preregistered")
    pre_tag = (
        '<span class="claim__kind">preregistered</span>'
        if preregistered
        else ""
    )
    text = claim.get("text") or ""
    reason = claim.get("reason") or ""
    return f"""
<article class="claim claim--{verdict}">
  <header class="claim__head">
    <span class="claim__id">{_e(claim_id)}</span>
    <span class="claim__kind">kind · {_e(kind)}</span>
    {pre_tag}
    <span class="claim__verdict"><span class="chip chip--{verdict}">{VERDICT_LABEL[verdict]}</span></span>
  </header>
  <div class="claim__body">
    <p class="claim__text">{_e(text)}</p>
    <p class="claim__reason"><b>Reason</b>{_e(reason)}</p>
    {_render_evidence(claim)}
  </div>
</article>"""


def _render_author_response(text: str | None) -> str:
    if text:
        return f'<pre class="term" tabindex="0" style="max-height:420px">{_e(text.strip())}</pre>'
    return (
        '<p class="muted">No author response is recorded in this registry entry. '
        "Per the audit protocol the corresponding author receives a 14–30 day "
        "window before publication, and any response is published verbatim.</p>"
    )


def render_audit(
    item: dict[str, Any],
    previous: dict[str, Any] | None,
    following: dict[str, Any] | None,
    author_response: str | None,
    raw_links: dict[str, str],
    position: int = 1,
) -> str:
    entry = item["entry"]
    report = item["report"]
    slug = entry["slug"]
    target = report.get("target") or {}
    scope = report.get("scope") or {}
    claims = report.get("claims") or []
    limits = report.get("limits") or []
    counts = _counts(entry)
    stamp_text, stamp_class = _verdict_summary(counts)
    tested = scope.get("tested") or []
    not_tested = scope.get("not_tested") or []
    tool = report.get("tool") or {}
    env = report.get("environment") or {}

    tested_html = (
        "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in tested) + "</ul>"
        if tested
        else '<p class="muted">Not declared.</p>'
    )
    not_tested_html = (
        "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in not_tested) + "</ul>"
        if not_tested
        else '<p class="muted">Not declared.</p>'
    )
    limits_html = (
        "<ul class=\"limits\">" + "".join(f"<li>{_e(item)}</li>" for item in limits) + "</ul>"
        if limits
        else '<p class="muted">No explicit limits were recorded.</p>'
    )
    claims_html = "".join(_render_claim(claim, index) for index, claim in enumerate(claims))
    if not claims_html:
        claims_html = '<div class="empty-state"><p>This report contains no claims.</p></div>'

    tally_html = "".join(
        f'<div class="tally-cell"><b>{counts[verdict]}</b>'
        f'<span>{VERDICT_LABEL[verdict]}</span></div>'
        for verdict in VERDICTS
    )

    paper = target.get("paper")
    paper_html = (
        f'<a href="{_e(paper)}" rel="noopener"><code>{_e(paper)}</code></a>'
        if isinstance(paper, str) and paper.startswith(("http://", "https://"))
        else f"<code>{_e(paper or '—')}</code>"
    )
    raw_json = raw_links.get("json", "")
    raw_md = raw_links.get("markdown", "")
    raw_links_html = ""
    if raw_json:
        raw_links_html += f'<li><a href="{_e(raw_json)}">Raw report JSON</a></li>'
    if raw_md:
        raw_links_html += f'<li><a href="{_e(raw_md)}">Markdown report</a></li>'

    prev_link = (
        f'<a href="{_e(previous["entry"]["slug"])}.html">← '
        f'{_e(_truncate(previous["entry"].get("title"), 48))}</a>'
        if previous
        else "<span></span>"
    )
    next_link = (
        f'<a href="{_e(following["entry"]["slug"])}.html">'
        f'{_e(_truncate(following["entry"].get("title"), 48))} →</a>'
        if following
        else "<span></span>"
    )

    report_sha = report.get("report_sha256") or entry.get("report_sha256") or ""
    audit_file = env.get("audit_file") or ""
    verify_command = (
        f"python3 -m paperunit verify --audit {audit_file} "
        f"--report registry/site/audits/{slug}/report.json" if audit_file else ""
    )
    verify_html = (
        f'<div class="hash-row"><code>{_e(verify_command)}</code>'
        f'<button class="copy-btn" type="button" data-copy="{_e(verify_command)}">Copy</button></div>'
        if verify_command
        else ""
    )

    body = f"""
<div class="shell">
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <a href="../index.html">Home</a><span>/</span>
    <a href="../audits/index.html">Registry</a><span>/</span>
    <span aria-current="page">No. {position:03d}</span>
  </nav>

  <div class="dossier">

    <article>
      <header class="dossier__head">
        <p class="eyebrow">Audit dossier · No. {position:03d} · {_e(entry.get('date') or 'undated')}</p>
        <h1>{_e(entry.get('title') or 'untitled audit')}</h1>
        <p class="dossier__byline">
          <span>audited by {_e(entry.get('audited_by') or 'unknown')}</span>
          <span>{len(claims)} claim{'' if len(claims) == 1 else 's'}</span>
          <span>{_e(slug)}</span>
        </p>
        <div class="tally-block">{tally_html}</div>
      </header>

      <section class="block">
        <h2>Scope</h2>
        <div class="scope-grid">
          <div class="scope-col"><h3>Tested</h3>{tested_html}</div>
          <div class="scope-col"><h3>Not tested</h3>{not_tested_html}</div>
        </div>
      </section>

      <section class="block">
        <h2>Claims &amp; evidence</h2>
        {claims_html}
      </section>

      <section class="block">
        <h2>Limits</h2>
        {limits_html}
        <div class="note" style="margin-top:14px">
          <strong>Not a verdict on the paper.</strong> An audit tests only the
          listed claims on the stated artefact in the stated environment. It does
          not judge scientific value, author conduct or research integrity.
        </div>
      </section>

      <section class="block">
        <h2>Author response</h2>
        {_render_author_response(author_response)}
      </section>

      <section class="block">
        <h2>Provenance &amp; reproduction</h2>
        <div class="hash-row">
          <span class="muted">report_sha256</span>
          <code>{_e(report_sha)}</code>
          <button class="copy-btn" type="button" data-copy="{_e(report_sha)}">Copy</button>
        </div>
        <p class="muted" style="margin:10px 0 0">The digest covers a stable view
        of the claim results (volatile timings excluded). Re-run the audit and
        compare: a changed number is DRIFT; a modified stored report is TAMPERED.</p>
        {verify_html}
        <ul class="mono muted" style="margin:14px 0 0;font-size:.74rem">{raw_links_html}</ul>
      </section>

      <nav class="prevnext" aria-label="Neighbouring audits">
        {prev_link}
        <span>← / →</span>
        {next_link}
      </nav>
    </article>
    <aside class="rail">
      <div class="meta-card">
        <h2>Provenance</h2>
        <dl>
          <div><dt>Audited by</dt><dd>{_e(entry.get('audited_by') or 'unknown')}</dd></div>
          <div><dt>Date</dt><dd>{_e(entry.get('date') or 'undated')}</dd></div>
          <div><dt>Tool</dt><dd><code>{_e(tool.get('name', 'paperunit'))} {_e(tool.get('version', ''))}</code></dd></div>
          <div><dt>Generated</dt><dd><code>{_e(report.get('generated_at') or '—')}</code></dd></div>
          <div><dt>Report sha256</dt><dd><code>{_e(report_sha)}</code></dd></div>
          <div><dt>Report path</dt><dd><code>{_e(entry.get('report_path'))}</code></dd></div>
        </dl>
      </div>
      <div class="meta-card">
        <h2>Target</h2>
        <dl>
          <div><dt>Paper / artefact</dt><dd>{paper_html}</dd></div>
          <div><dt>Commit</dt><dd><code>{_e(target.get('repo_commit') or '—')}</code></dd></div>
          <div><dt>Environment</dt><dd><code>{_e(env.get('python', ''))} {_e(env.get('platform', ''))}</code></dd></div>
        </dl>
      </div>
      <span class="{stamp_class}">{stamp_text}</span>
    </aside>
  </div>
</div>
"""
    return _page(
        title=f"{entry.get('title') or 'Audit'} · paperunit",
        description=_truncate(
            f"Executable paper audit: {entry.get('title', '')}. "
            "Verdicts are evidence-local; no scores, no rankings.",
            220,
        ),
        root="../",
        active="registry",
        body=body,
        body_class="page-audit",
    )


# ---------------------------------------------------------------------------
# public entry point
# ---------------------------------------------------------------------------


def build_site(
    index: dict[str, Any],
    loaded: list[tuple[str, dict[str, Any], dict[str, Any]]],
    out_dir: str | Path,
    audits_dir: str | Path,
) -> None:
    """Write the full static site from the registry index and loaded reports.

    ``loaded`` is a list of ``(report_relative_path, report_dict, index_entry)``;
    each index entry must carry its ``slug``.  ``audits_dir`` is the source tree
    the relative paths refer to (needed to copy raw reports and responses).
    """
    out = Path(out_dir)
    source_root = Path(audits_dir)
    out.mkdir(parents=True, exist_ok=True)
    # The site tree is generated; remove the previous generation so deleted
    # audits do not leave stale pages behind.
    shutil.rmtree(out / "assets", ignore_errors=True)
    if (out / "audits").resolve() != source_root.resolve():
        shutil.rmtree(out / "audits", ignore_errors=True)
    (out / "audits").mkdir(parents=True, exist_ok=True)
    _copy_assets(out)

    items: list[dict[str, Any]] = []
    for relative, report, entry in loaded:
        slug = entry["slug"]
        source = source_root / relative
        raw_links = _copy_raw_artifacts(out, slug, source)
        response_text = None
        response_path = source.with_name("author_response.md")
        if response_path.is_file():
            response_text = response_path.read_text(encoding="utf-8")
        items.append(
            {
                "entry": entry,
                "report": report,
                "slug": slug,
                "raw_links": raw_links,
                "author_response": response_text,
            }
        )

    landing = _page(
        title="paperunit · executable paper audits",
        description=(
            "Bind a paper's claims to checks a stranger can execute. Evidence-local "
            "verdicts, re-runnable reports, no scores, no rankings."
        ),
        root="",
        active="",
        body=render_landing(items),
    )
    (out / "index.html").write_text(landing, encoding="utf-8")

    registry_page = _page(
        title="Audit registry · paperunit",
        description=(
            "The paperunit audit registry: case files with executable evidence, "
            "uncertainty and limits. Counts are not a score."
        ),
        root="../",
        active="registry",
        body=render_registry(items),
        body_class="page-registry",
    )
    (out / "audits" / "index.html").write_text(registry_page, encoding="utf-8")

    for position, item in enumerate(items):
        previous = items[position - 1] if position > 0 else None
        following = items[position + 1] if position + 1 < len(items) else None
        page = render_audit(
            item,
            previous,
            following,
            item.get("author_response"),
            item.get("raw_links") or {},
            position + 1,
        )
        (out / "audits" / f"{item['slug']}.html").write_text(page, encoding="utf-8")
