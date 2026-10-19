"""Static site generation for the paperunit audit registry.

The site is a small, dependency-free product site: a landing page, an audit
registry and one dossier page per report.  Everything is generated from
``audit_report.json`` files with the standard library; the only assets are a
stylesheet and a small progressive-enhancement script.

Design reference: apple.com — a slim translucent global nav, very large SF-style
display type, generous whitespace, alternating white / #f5f5f7 / black bands,
gallery tiles with product-like visuals, pill buttons and blue text links.

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
    "%3Crect width='32' height='32' rx='7' fill='%231d1d1f'/%3E"
    "%3Ctext x='16' y='23' font-family='-apple-system,Helvetica,Arial' "
    "font-size='17' font-weight='600' text-anchor='middle' "
    "fill='%23ffffff'%3EP%3C/text%3E%3C/svg%3E"
)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _e(value: Any) -> str:
    """Escape text for HTML content and attributes."""
    return html.escape("" if value is None else str(value), quote=True)


def _num(value: Any) -> str:
    """Format a numeric value compactly; never raise."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        try:
            return f"{value:.6g}"
        except (TypeError, ValueError, OverflowError):  # pragma: no cover
            return _e(value)
    return _e(value)


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return repr(value)


def _short(value: Any, length: int = 16) -> str:
    text = "" if value is None else str(value)
    return text[:length] + "…" if len(text) > length else text


def _truncate(value: Any, length: int = 240) -> str:
    text = " ".join(("" if value is None else str(value)).split())
    return text[: length - 1] + "…" if len(text) > length else text


def _tally(counts: dict[str, int], compact: bool = False) -> str:
    total = sum(int(counts.get(verdict, 0)) for verdict in VERDICTS)
    if total <= 0:
        return '<span class="chip chip--NOT_RUN">no claims</span>'
    parts = []
    for verdict in VERDICTS:
        count = int(counts.get(verdict, 0))
        if count <= 0:
            continue
        if compact:
            parts.append(f'<span class="chip chip--{verdict}">{verdict} {count}</span>')
        else:
            parts.append(f'<span class="chip chip--{verdict}">{VERDICT_LABEL[verdict]}</span>')
    return "".join(parts)


def _counts(entry: dict[str, Any]) -> dict[str, int]:
    counts = entry.get("verdict_counts") or {}
    return {
        verdict: int(counts.get(verdict, 0)) if isinstance(counts, dict) else 0
        for verdict in VERDICTS
    }


def _total_claims(entry: dict[str, Any]) -> int:
    return sum(_counts(entry).values())


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
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{_e(title)}</title>
<meta name="description" content="{_e(description)}">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="{root}assets/style.css">
</head>
<body class="{_e(body_class)}">
<a class="skip-link" href="#main">Skip to content</a>
<header class="global-nav">
  <div class="global-nav__inner">
    <a class="brand" href="{root}index.html">
      <span class="brand__mark" aria-hidden="true">P</span>
      <span class="brand__name">paperunit</span>
    </a>
    <nav class="global-nav__links" aria-label="Primary">
      {nav_html}
    </nav>
    <div class="global-nav__actions">
      <a class="global-nav__link" href="{GITHUB_URL}" rel="noopener">GitHub ↗</a>
    </div>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="footer">
  <div class="footer__inner">
    <div class="footer__columns">
      <div class="footer__about">
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
    <p class="footer__legal">
      An audit tests only the listed claims on the stated artefact in the stated
      environment. It does not judge scientific value, author conduct or research
      integrity. An audit is evidence, not a verdict on a paper's worth.
    </p>
    <div class="footer__bottom">
      <span>Copyright © 2026 无常 / paperunit contributors. Generated statically
      from <code>audit_report.json</code> · paperunit {__version__}.</span>
      <span>No tracker, no cookies, no external requests.</span>
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
# shared fragments
# ---------------------------------------------------------------------------


def _aggregate(loaded: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = {verdict: 0 for verdict in VERDICTS}
    claims = 0
    for item in loaded:
        counts = _counts(item["entry"])
        for verdict in VERDICTS:
            verdicts[verdict] += counts[verdict]
        claims += sum(counts.values())
    latest = loaded[0]["entry"].get("date", "") if loaded else ""
    return {
        "audits": len(loaded),
        "claims": claims,
        "verdicts": verdicts,
        "latest": latest,
    }


def _verdict_bars(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    if total <= 0:
        return '<div class="verdict-bars"><span class="b-none" style="width:100%"></span></div>'
    classes = {
        "SUPPORTED": "b-ok",
        "REFUTED": "b-bad",
        "INCONCLUSIVE": "b-warn",
        "NOT_RUN": "b-none",
    }
    spans = []
    for verdict in VERDICTS:
        count = counts.get(verdict, 0)
        if count <= 0:
            continue
        width = 100.0 * count / total
        spans.append(f'<span class="{classes[verdict]}" style="width:{width:.2f}%"></span>')
    return '<div class="verdict-bars" aria-hidden="true">' + "".join(spans) + "</div>"


def _empty_state() -> str:
    return """
<div class="empty-state">
  <p>No audits yet · 尚无审计报告</p>
  <p>Add a directory containing <code>audit_report.json</code> to
  <code>registry/audits/</code> and rebuild.</p>
</div>
"""


def _claim_rows(report: dict[str, Any], limit: int = 3) -> str:
    claims = report.get("claims")
    if not isinstance(claims, list):
        return ""
    rows = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        text = _truncate(claim.get("text") or claim.get("id") or "claim", 120)
        verdict = claim.get("verdict")
        if verdict not in VERDICTS:
            verdict = "NOT_RUN"
        rows.append(
            f'<div class="mini__row"><span>{_e(text)}</span>'
            f'<span class="chip chip--{verdict}">{verdict}</span></div>'
        )
        if len(rows) >= limit:
            break
    return "".join(rows)


def _window(item: dict[str, Any] | None) -> str:
    """A product-shot window showing a real audit dossier."""
    if item is None:
        return """
<div class="window window--empty" aria-hidden="true">
  <div class="window__bar"><span class="window__bar-title">paperunit</span></div>
  <div class="window__body">
    <p class="window__eyebrow">Audit dossier</p>
    <h2 class="window__title">No audits indexed yet.</h2>
    <p class="window__by">Add an audit_report.json and rebuild the registry.</p>
  </div>
</div>
"""
    entry = item["entry"]
    report = item["report"]
    counts = _counts(entry)
    rows = _claim_rows(report, 3)
    if not rows:
        rows = '<div class="mini__row"><span>This report contains no claims.</span></div>'
    return f"""
<div class="window" aria-hidden="true">
  <div class="window__bar">
    <span class="window__bar-title">paperunit — audit dossier</span>
  </div>
  <div class="window__body">
    <p class="window__eyebrow">Audit dossier · No. 001 · {_e(entry.get('date') or 'undated')}</p>
    <h2 class="window__title">{_e(entry.get('title') or 'untitled audit')}</h2>
    <p class="window__by">audited by {_e(entry.get('audited_by') or 'unknown')} · {_total_claims(entry)} claims</p>
    <div class="window__chips">{_tally(counts, compact=True)}</div>
    <div class="window__list">{rows}</div>
    <div class="window__foot"><span>{_e(entry.get('report_path'))}</span><span>report_sha256 {_e(_short(entry.get('report_sha256'), 12))}</span></div>
  </div>
</div>
"""


def _promo_card(item: dict[str, Any], index: int) -> str:
    entry = item["entry"]
    report = item["report"]
    slug = entry["slug"]
    dark = index % 2 == 1
    rows = _claim_rows(report, 2)
    if not rows:
        rows = '<div class="mini__row"><span>No claims in this report.</span></div>'
    return f"""
<a class="promo{' promo--dark' if dark else ''} reveal" style="--i:{index}" href="audits/{_e(slug)}.html">
  <div class="promo__head">
    <p class="promo__kicker">No. {index + 1:03d} · {_e(entry.get('date') or 'undated')}</p>
    <h3>{_e(entry.get('title') or 'untitled audit')}</h3>
    <p class="promo__by">audited by {_e(entry.get('audited_by') or 'unknown')}</p>
  </div>
  <div class="promo__chips">{_tally(_counts(entry), compact=True)}</div>
  <div class="mini" aria-hidden="true">
    <div class="mini__bar"><span></span></div>
    <div class="mini__rows">{rows}</div>
  </div>
  <p class="promo__path">{_e(entry.get('report_path'))}</p>
  <span class="promo__more">Open dossier ›</span>
</a>
"""


# ---------------------------------------------------------------------------
# landing page
# ---------------------------------------------------------------------------


def render_landing(loaded: list[dict[str, Any]]) -> str:
    stats = _aggregate(loaded)
    counts = stats["verdicts"]
    latest = loaded[0] if loaded else None
    promos = "".join(_promo_card(item, index) for index, item in enumerate(loaded[:2]))
    if not promos:
        promos = _empty_state()

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
        <span class="principle__num">{number}</span>
        <h3>{title}</h3>
        <p>{copy}</p>
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

    meta = (
        f"{stats['audits']} audits · {stats['claims']} claims · "
        f"latest {_e(stats['latest'] or '—')}"
    )

    return f"""
<section class="hero">
  <div class="shell hero__copy reveal">
    <p class="eyebrow">Executable paper audits</p>
    <h1>Every claim<br>gets a <span class="hero__accent">re-run.</span></h1>
    <p class="hero__tagline">Evidence, not a score.</p>
    <p class="hero__note">paperunit binds a paper's claim to a command a stranger
    can execute — then publishes the evidence, the uncertainty and the limits.
    A verdict is about one claim on one artefact, not about a paper's worth.</p>
    <div class="cta">
      <a class="button" href="audits/index.html">Browse the registry</a>
      <a class="button button--secondary" href="#how">How it works</a>
    </div>
    <p class="hero__meta">{meta} · no scores · no rankings</p>
  </div>
  <div class="shell hero__shot reveal" style="--i:1">
    <div class="hero__glow" aria-hidden="true"></div>
    {_window(latest)}
  </div>
</section>

<section class="band band--dark" id="how">
  <div class="shell">
    <p class="eyebrow eyebrow--light">The method</p>
    <h2>From a sentence in a paper<br>to a verdict you can re-run.</h2>
    <p class="band__lede">No review committee, no reputation points. The unit of
    work is a claim bound to an executable check and shipped with its evidence.</p>
    <div class="steps">{steps_html}</div>
    <div class="legend">{verdict_legend}</div>
  </div>
</section>

<section class="band band--light" id="audits">
  <div class="shell shell--wide">
    <h2>Recent case files.</h2>
    <p class="band__lede">Every entry is a generated audit_report.json: commands,
    verdicts, evidence hashes, uncertainty and limits. Counts are not a score.</p>
    <div class="promo-grid">{promos}</div>
    <p class="more"><a class="link" href="audits/index.html">Browse all audits ›</a></p>
  </div>
</section>

<section class="band band--dark" id="run">
  <div class="shell shell--narrow">
    <h2>Clone, run, verify.</h2>
    <p class="band__lede">The core is standard-library-only. Optional toolchains
    (z3, Lean 4) are detected; when they are absent a claim is INCONCLUSIVE,
    never a false verdict. Every report can be checked by someone who does not
    trust its author.</p>
    <div class="terminal reveal">
      <div class="terminal__bar"><span>paperunit — zsh</span></div>
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
    <p class="more more--light">
      <a class="link link--light" href="{GITHUB_URL}#quickstart" rel="noopener">Quickstart ›</a>
      <a class="link link--light" href="audits/index.html">Open the registry ›</a>
    </p>
  </div>
</section>

<section class="band band--light" id="principles">
  <div class="shell">
    <h2>What this project refuses to be.</h2>
    <p class="band__lede">These are constraints, not aspirations. The operating
    manual and the protocol spell out the red lines; the registry applies them.</p>
    <div class="principle-grid">{principles_html}</div>
  </div>
</section>
"""


def root_registry() -> str:
    return "audits/index.html"


# ---------------------------------------------------------------------------
# registry page
# ---------------------------------------------------------------------------


def render_registry(loaded: list[dict[str, Any]]) -> str:
    cards = []
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
        cards.append(
            f"""
<article class="audit-card" data-audit
         data-verdicts="{_e(verdicts_present)}"
         data-search="{_e(haystack)}">
  <a class="audit-card__link" href="{_e(slug)}.html">
    <p class="audit-card__date">{_e(entry.get('date') or 'undated')}</p>
    <h2 class="audit-card__title">{_e(entry.get('title') or 'untitled audit')}</h2>
    <p class="audit-card__by">audited by {_e(entry.get('audited_by') or 'unknown')}</p>
    <div class="audit-card__chips">{_tally(counts, compact=True)}</div>
    <div class="audit-card__bar">{_verdict_bars(counts)}<span class="audit-card__claims">{_total_claims(entry)} claims</span></div>
    <p class="audit-card__path">{_e(entry.get('report_path'))}</p>
    <span class="audit-card__more">Open dossier ›</span>
  </a>
</article>"""
        )

    list_html = "".join(cards)
    empty = _empty_state() if not cards else ""
    count = len(cards)
    return f"""
<header class="page-head">
  <div class="shell">
    <h1>Registry</h1>
    <p class="page-head__tagline">Case files, not a leaderboard.</p>
    <p class="page-head__note">Every entry is a generated audit_report.json:
    commands, verdicts, evidence hashes, uncertainty and limits. Entries are
    ordered by date. Read the report before drawing conclusions; counts are not
    a score.</p>
  </div>
</header>

<div class="filterbar">
  <div class="shell filterbar__inner" role="search" aria-label="Filter audits">
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
</div>

<div class="shell">
  <section class="audit-grid" data-audit-list aria-label="Audit reports">
    {list_html}
  </section>
  <div data-empty-state class="{'is-hidden' if cards else ''}">{empty}</div>

  <p class="demo-note"><strong>Demo entries.</strong> Reports under
  <code>registry/audits/demo-*</code> are self-tests of the pipeline, not
  published audits. Lean and z3 demos need the optional toolchains; on a machine
  without them a re-run reports INCONCLUSIVE / DRIFT, never a false verdict.</p>

  <nav class="page-links" aria-label="Registry links">
    <a class="link" href="../index.html">‹ Home</a>
    <a class="link" href="{GITHUB_URL}/blob/main/registry/README.md" rel="noopener">How to add an audit ›</a>
  </nav>
</div>
"""


# ---------------------------------------------------------------------------
# dossier helpers
# ---------------------------------------------------------------------------


def _render_dl(mapping: dict[str, Any]) -> str:
    rows = []
    for key, value in mapping.items():
        rendered = _e(value)
        if len(rendered) > 1200:
            rendered = rendered[:1199] + "…"
        rows.append(f"<dt>{_e(key)}</dt><dd>{rendered}</dd>")
    return '<dl class="dl">' + "".join(rows) + "</dl>"


def _render_runs(runs: Any) -> str:
    if not isinstance(runs, list) or not runs:
        return ""
    rows = []
    for index, run in enumerate(runs, 1):
        if not isinstance(run, dict):
            continue
        rows.append(
            f"<tr><td class=\"num\">{index}</td>"
            f"<td><code>{_e(_truncate(run.get('command', ''), 160))}</code></td>"
            f"<td class=\"num\">{_e(run.get('exit_code'))}</td>"
            f"<td><code>{_e(_short(run.get('evidence_sha256'), 18))}</code></td></tr>"
        )
    return f"""
<h3>Runs</h3>
<div class="table-wrap"><table class="evidence">
<thead><tr><th class="num">#</th><th>command</th><th class="num">exit</th><th>evidence sha256</th></tr></thead>
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
        rows.append(
            f"<tr><td><code>{_e(item.get('rule'))}</code></td>"
            f"<td>{'pass' if passed else 'fail'}</td>"
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
        return '<h3>Values</h3><p class="mono">' + ", ".join(
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
        parts.append(f'<h3>stdout excerpt</h3><pre class="code-block" tabindex="0">{_e(stdout)}</pre>')

    rendered = {"runs", "expectations", "resolution", "margin_policy", "values"}
    leftovers = {
        key: value
        for key, value in evidence.items()
        if key not in rendered and value not in (None, "", [], {})
    }
    if leftovers:
        parts.append("<h3>Other evidence</h3>" + _render_dl(leftovers))

    if isinstance(uncertainty, dict) and uncertainty:
        parts.append("<h3>Uncertainty</h3>" + _render_dl(uncertainty))

    if not parts:
        return '<p class="muted">No evidence recorded for this claim.</p>'
    return (
        '<details class="evidence"><summary>Evidence &amp; uncertainty</summary>'
        '<div class="evidence-body">'
        + "".join(parts)
        + "</div></details>"
    )


def _render_claim(claim: dict[str, Any], index: int) -> str:
    if not isinstance(claim, dict):
        return ""
    verdict = claim.get("verdict")
    if verdict not in VERDICTS:
        verdict = "NOT_RUN"
    claim_id = claim.get("id") or f"claim-{index + 1}"
    kind = claim.get("kind") or ""
    preregistered = " · preregistered" if claim.get("preregistered") else ""
    text = claim.get("text") or "(no claim text recorded)"
    reason = claim.get("reason")
    reason_html = (
        f'<p class="claim__reason"><b>Reason</b>{_e(reason)}</p>' if reason else ""
    )
    return f"""
<article class="claim claim--{verdict}">
  <div class="claim__head">
    <span class="claim__id">{_e(claim_id)}</span>
    <span class="claim__kind">{_e(kind)}{preregistered}</span>
    <span class="chip chip--{verdict}">{VERDICT_LABEL[verdict]}</span>
  </div>
  <p class="claim__text">{_e(text)}</p>
  {reason_html}
  {_render_evidence(claim)}
</article>
"""


def _render_author_response(text: str | None) -> str:
    if text:
        return f'<pre class="code-block" tabindex="0">{_e(text.strip())}</pre>'
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
        '<ul class="limits">' + "".join(f"<li>{_e(item)}</li>" for item in limits) + "</ul>"
        if limits
        else '<p class="muted">No explicit limits were recorded.</p>'
    )
    claims_html = "".join(_render_claim(claim, index) for index, claim in enumerate(claims))
    if not claims_html:
        claims_html = '<div class="empty-state"><p>This report contains no claims.</p></div>'

    verdict_stats = "".join(
        f'<div class="verdict-stat"><b>{counts[verdict]}</b>'
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
        f'<a class="link" href="{_e(previous["entry"]["slug"])}.html">‹ '
        f'{_e(_truncate(previous["entry"].get("title"), 42))}</a>'
        if previous
        else "<span></span>"
    )
    next_link = (
        f'<a class="link" href="{_e(following["entry"]["slug"])}.html">'
        f'{_e(_truncate(following["entry"].get("title"), 42))} ›</a>'
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

    spec_items = [
        ("Audited by", _e(entry.get("audited_by") or "unknown")),
        ("Date", _e(entry.get("date") or "undated")),
        ("Tool", f'<code>{_e(tool.get("name", "paperunit"))} {_e(tool.get("version", ""))}</code>'),
        ("Environment", f'<code>{_e(env.get("python", ""))} {_e(env.get("platform", ""))}</code>'),
        ("Paper / artefact", paper_html),
        ("Commit", f'<code>{_e(target.get("repo_commit") or "—")}</code>'),
        ("Report path", f'<code>{_e(entry.get("report_path"))}</code>'),
        ("Report sha256", f'<code>{_e(report_sha)}</code>'),
    ]
    spec_html = "".join(
        f'<div class="spec"><dt>{label}</dt><dd>{value}</dd></div>'
        for label, value in spec_items
    )

    body = f"""
<header class="dossier-hero">
  <div class="shell">
    <nav class="breadcrumb breadcrumb--dark" aria-label="Breadcrumb">
      <a href="../index.html">Home</a><span>/</span>
      <a href="../audits/index.html">Registry</a><span>/</span>
      <span aria-current="page">No. {position:03d}</span>
    </nav>
    <p class="eyebrow eyebrow--light">Audit dossier · No. {position:03d} · {_e(entry.get('date') or 'undated')}</p>
    <h1>{_e(entry.get('title') or 'untitled audit')}</h1>
    <p class="dossier-hero__by">audited by {_e(entry.get('audited_by') or 'unknown')}
      · {len(claims)} claim{'' if len(claims) == 1 else 's'}
      · {_e(slug)}</p>
    <div class="verdict-row">{verdict_stats}</div>
  </div>
</header>

<div class="dossier-body">
  <div class="shell">
    <section class="content-section">
      <h2>Scope</h2>
      <div class="scope-grid">
        <div class="scope-col"><h3>Tested</h3>{tested_html}</div>
        <div class="scope-col"><h3>Not tested</h3>{not_tested_html}</div>
      </div>
    </section>

    <section class="content-section">
      <h2>Claims &amp; evidence</h2>
      {claims_html}
    </section>

    <section class="content-section">
      <h2>Limits</h2>
      {limits_html}
      <p class="note"><strong>Not a verdict on the paper.</strong> An audit tests
      only the listed claims on the stated artefact in the stated environment. It
      does not judge scientific value, author conduct or research integrity.</p>
    </section>

    <section class="content-section">
      <h2>Author response</h2>
      {_render_author_response(author_response)}
    </section>

    <section class="content-section">
      <h2>Provenance &amp; reproduction</h2>
      <dl class="spec-grid">{spec_html}</dl>
      <p class="muted">The digest covers a stable view of the claim results
      (volatile timings excluded). Re-run the audit and compare: a changed number
      is DRIFT; a modified stored report is TAMPERED.</p>
      <div class="hash-row">
        <span class="muted">report_sha256</span>
        <code>{_e(report_sha)}</code>
        <button class="copy-btn" type="button" data-copy="{_e(report_sha)}">Copy</button>
      </div>
      {verify_html}
      <ul class="raw-links">{raw_links_html}</ul>
    </section>

    <nav class="dossier-nav" aria-label="Neighbouring audits">
      {prev_link}
      <a class="link" href="../audits/index.html">All audits</a>
      {next_link}
    </nav>
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
