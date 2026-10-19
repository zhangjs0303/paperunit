# paperunit

**Executable paper audits.** Bind each paper claim to a check that a third party
can re-run, and make the audit report itself re-runnable.

An audit produces evidence-local verdicts — `SUPPORTED`, `REFUTED`,
`INCONCLUSIVE`, `NOT_RUN` — and **no scores, no rankings, no leaderboards**.
It tests the artefact (code, data, formal statement) on a stated commit in a
stated environment; it is not a verdict on the paper's scientific value.

This repository is v0.3: runnable engine, seven checker kinds, statistical and
formal-verification support (including a published-paper Lean formalisation
demo), demo audits, a generated static **registry UI** (landing page, searchable
browser, per-audit dossier pages), and a long-term operations plan. It is not yet
a public registry with real papers; the next milestone is 5–10 real audits.

中文概览见 [README.zh-CN.md](README.zh-CN.md)；运营与治理见 [OPS.md](OPS.md)。

## Quickstart

Requires Python 3.11+; the core has no third-party dependencies.

```bash
cd paperunit

# validate an audit spec without running anything
python3 -m paperunit validate --audit examples/toy_paper/audit.json

# run it, then re-run it to verify the report
python3 -m paperunit run    --audit examples/toy_paper/audit.json --out out/toy
python3 -m paperunit verify --audit examples/toy_paper/audit.json --report out/toy/audit_report.json

# the demo that audits the project's own red-team report ("audit the audit")
python3 -m paperunit run --audit examples/redteam/audit.json --out out/redteam

# tests
python3 -m unittest discover -s tests -v

# static registry + site (scan for audit_report.json files, write the full UI)
python3 -m paperunit registry build --audits-dir registry/audits --out registry/site
```

`registry build` also generates a small static site: a landing page, a searchable
registry and one dossier page per audit (commands, evidence, uncertainty, limits,
author-response slot). The site is plain HTML/CSS plus a ~100-line progressive
enhancement script; fonts are self-hosted; there are no external requests and no
trackers. Open `registry/site/index.html` directly or let CI deploy it to GitHub
Pages.

`run` writes `audit_report.json` (machine-readable, digest-bearing) and
`report.md` (human-readable: scope, verdicts, evidence, uncertainty, limits).
`run` exits 0 when the report was written even if claims are `REFUTED`;
`verify` exits 0 for `REPRODUCIBLE`, 1 for `DRIFT`/`TAMPERED`, 2 for
`INCONCLUSIVE`/error.

### Optional toolchains (z3, Lean 4)

The core is standard-library-only. Two checker families need external tools:

- **z3** for symbolic `external` checks: `python3 -m venv .venv && .venv/bin/pip install z3-solver`
- **Lean 4** for `lean4` proof checks: install a toolchain so `lean --version`
  and `lake --version` work (e.g. elan); `examples/lean_demo` pins
  `leanprover/lean4:v4.35.0`.

This workspace installs both locally (gitignored): `.venv/` and `.toolchains/`.
Use the wrapper so the demo audits find them:

```bash
scripts/with-toolchains.sh python3 -m paperunit run --audit examples/lean_demo/audit.json --out out/lean
scripts/with-toolchains.sh python3 -m paperunit run --audit examples/z3_demo/audit.json --out out/z3
```

Without a toolchain the corresponding checker returns `INCONCLUSIVE` (by
design, never a false verdict), and `verify` reports `INCONCLUSIVE`/`DRIFT`
accordingly.

## Audit file (schema `paperunit/v1`)

```json
{
  "schema": "paperunit/v1",
  "target": {"title": "...", "paper": "...", "repo_commit": "...",
             "audited_by": "...", "date": "YYYY-MM-DD"},
  "scope": {"tested": ["..."], "not_tested": ["..."]},
  "claims": [
    {"id": "C1", "text": "the paper's claim", "kind": "numeric",
     "check": {"cmd": "python3 code/run.py", "timeout_s": 120,
               "expect": {"numeric_within": {"number_regex": "acc=(?P<value>[0-9.]+)",
                                              "target": 0.923, "tolerance": 0.002}}},
     "preregistered": true}
  ]
}
```

Rules enforced by the engine: unique non-empty claim ids, explicit `scope`,
one checker per claim, structural validation before any command runs, and a
stable `report_sha256` that covers claim verdicts and evidence but not clocks.

## Checker kinds

| kind | What it tests | Trust source | Notes |
|---|---|---|---|
| `numeric` | a claimed number vs a command's output | deterministic re-run + preregistered tolerance | core |
| `stdout` | claimed output/substring/regex | deterministic re-run | core |
| `exit` | a command succeeds/fails as claimed | deterministic re-run | core |
| `statistics` | a claimed value/effect vs repeated runs with different seeds | interval estimate + equivalence margin | stdlib bootstrap/t intervals; reports resolution and minimum detectable effect |
| `lean4` | a formal statement whose proof is checked by Lean 4 | proof checker | `SUPPORTED` only when the build checks with no `sorry`; missing toolchain or failed formalisation is `INCONCLUSIVE`, never evidence against the paper |
| `external` | anything printable as one JSON line by a command | depends on the external tool (e.g. Z3, property tests, custom re-runs) | extension point; the external script must print `{"verdict": "...", "reason": "...", ...}` on its last stdout line |
| `human` | judgement that is not mechanically decidable | human | recorded as `NOT_RUN`, not scored |

Adding a checker: implement `kind` + `check(ctx) -> Outcome` against
`paperunit/checkers/base.py`; see [docs/checker-authoring.md](docs/checker-authoring.md).

## Statistics: report resolution, not "probability the paper is wrong"

The statistical checker re-runs an experiment across preregistered seeds and
reports an interval estimate plus the audit's resolution:

- `SUPPORTED`: the claimed value is within the preregistered equivalence margin
  of the audit's estimate (difference ≤ margin). By default the margin is
  `paper_precision`: one unit in the last decimal place the paper reports
  (`0.923` → `0.001`) — "only check whether the paper reaches its own reported
  precision". `fixed` and `policy_ref` are explicit/policy-driven alternatives.
- `REFUTED`: the difference exceeds the margin **and** the claimed value lies
  outside the audit's confidence interval.
- `INCONCLUSIVE`: otherwise — typically the difference exceeds the margin but
  the interval still contains the claim, i.e. the audit is underpowered. The
  report states the CI, the minimum detectable effect and the effect size so a
  reader can see *how much doubt the data can bear*, instead of a verdict the
  data cannot support.

No p-hacking: seeds, margin and confidence are preregistered in the audit file.
The margin rule is resolved by `paperunit/margin.py`; `policy_ref` reads a
versioned file under `policies/margin/`, which is the governance hook for a
future DAO/council. A report records the margin, its mode and the policy
`decision_id`; changing a policy only affects new audits.

## Formal verification: what a proof does and does not buy

The trust hierarchy is explicit in every report:

1. **Proof checked** (`lean4` → `SUPPORTED`): the supplied formal statement and
   proof compile with no `sorry`. The audit ships the formalisation alongside the
   report; the claim is only as strong as that formalisation.
2. **Counterexample found** (`external` + Z3/property test → `REFUTED`): a
   bounded-domain property is violated; the report includes the witness.
3. **Deterministic re-run** (`numeric`/`stdout`/`exit`): outputs match or do not.
4. **Interval estimate** (`statistics`): an estimate with uncertainty.
5. **Human judgement** (`human` → `NOT_RUN`): recorded, never scored.

A Lean build failure is `INCONCLUSIVE`, because "the audit's formalisation did
not go through" is not evidence about the paper. Only a counterexample (or a
failed preregistered check) can `REFUTE`. Autoformalisation, if used, is labelled
as a hypothesis and must be reviewed by a human before being trusted.

A worked example: [`examples/lean_paper_ncc/`](examples/lean_paper_ncc/) takes the
Neural Computability Condition equations from a 2026 spiking-neural-network CSP
solver (arXiv:2607.08897, Section 2.2), translates the algebraic core to Lean 4
by hand, and checks it with `lake build`. Its `paper.md` states exactly what was
and was not formalised (integer weights, 3 neurons, no Mathlib, no exp/log step).

## Repository layout

```
paperunit/
  paperunit/            # package: cli, engine, schema, report, registry, site, checkers/
    site_assets/       # stylesheet, tiny JS enhancement, self-hosted fonts
  examples/            # toy/redteam/stats/causal/lean/z3 demos + a published-paper formalisation
  tests/               # stdlib unittest
  registry/            # audit reports + generated site (landing, browser, dossiers)
  docs/                # protocol.md, ethics.md, checker-authoring.md
  OPS.md               # long-term operations: roles, cadence, governance, funding, risks
  DESIGN.md            # architecture and trust model
```

## Long-term operation

This is designed to be run for years by a small team, not to be a launch:

- monthly audit batch (3–5 papers), quarterly schema/checker release, annual report;
- at least two maintainers (bus factor), named editor for every published audit,
  second-reviewer sign-off before publication;
- author right-of-reply (14–30 days) and a correction/retraction path;
- zero-cost baseline (GitHub Actions, GitHub Pages static registry), no tokens;
- metrics that cannot be gamed by attention: audits published, external
  re-runners, author response rate, checker coverage.

See [OPS.md](OPS.md) for roles, cadence, governance, legal incident playbook and
the 12-month roadmap; [docs/protocol.md](docs/protocol.md) and
[docs/ethics.md](docs/ethics.md) for the red lines.

## Who runs it

The project is maintained under the pseudonym **无常**. Audit reports and the
registry are signed with that name; the maintainer's real-name contact is held by
a second maintainer for legal/platform purposes (see [docs/ethics.md](docs/ethics.md)).
The project is an independent repository, not part of any lab's publication list.

## License

Code: Apache-2.0 (see [LICENSE](LICENSE)). Audit reports and docs: CC-BY-4.0
unless stated otherwise; third-party figures quoted in reports remain under
their original terms. The registry index data is CC0.

## Status and limitations

- v0.3; the registry currently contains demo audits, not public real-paper audits.
- Checkers execute shell commands; audit files are executable input — only run
  audits you trust (sandboxing is on the roadmap).
- The statistical checker assumes independent seeds and a single metric; it does
  not yet do multiple-comparison correction across claims (planned).
- The Lean checker is tested for the toolchain-missing path; CI with a real Lean
  toolchain is on the roadmap. Z3 support is an optional dependency.
- An audit can be wrong. Reports are versioned, correctable, and the audit itself
  can be re-run (`verify`); if you find a mistake in an audit, open an issue.
