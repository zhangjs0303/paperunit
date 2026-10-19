# registry/audits

Public audit reports live here. One audit = one directory containing the
machine-readable report produced by `paperunit run`:

```
registry/audits/<slug>/
  audit_report.json    # written by `python3 -m paperunit run --out ...`
  report.md            # human-readable companion (optional in registry)
  audit.json           # the audit spec, copied verbatim (recommended)
  author_response.md   # the authors' reply, verbatim (when one exists)
```

`slug` convention: `<year>-<short-title>-<first-author-or-lab>`; keep it stable,
the registry links to it.

When an `audit.json` is copied here for provenance, its relative `cwd`
paths still refer to the audit's original location; the registry only indexes
`audit_report.json`.

Do not edit `audit_report.json` by hand: `verify` detects a modified report as
`TAMPERED`. Corrections go through a new report version with a note in the
audit protocol (`docs/protocol.md`).

Build the static site:

```bash
python3 -m paperunit registry build --audits-dir registry/audits --out registry/site
```

The builder is a pure function of the files in this directory (stdlib only,
deterministic). It writes `index.json` plus a full static site: `index.html`
(landing), `audits/index.html` (searchable registry), `audits/<slug>.html`
(dossier pages), raw report copies under `audits/<slug>/`, and self-hosted
assets. CI rebuilds it from `registry/audits/` and asserts the output exists;
the generated `registry/site/` is not committed (see `.gitignore`).

Publication checklist before adding a directory here:

1. the audit was run on a clean checkout and `verify` returns `REPRODUCIBLE`;
2. `scope.tested` / `scope.not_tested` are filled in;
3. the corresponding author received the draft at least 14 days ago
   (or the report states that no response has arrived);
4. the report contains no misconduct allegation, no motive attribution and no
   named individual author by default;
5. a second maintainer signed off.

The registry is not a ranking. It is an index of what was tested, on which
artefact, with what result and what response.

Demo audits under `registry/audits/demo-*` are self-tests, not published
audits. `demo-lean_demo` needs a Lean toolchain and `demo-*` z3-style reports
need the optional z3 extra; on a machine without them `verify` returns
`INCONCLUSIVE`/`DRIFT` for those reports (by design, never a false verdict).
