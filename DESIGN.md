# paperunit design

This document records the architecture and the trust model. The operating
model (roles, cadence, governance, funding, risks) is in [OPS.md](OPS.md).

## 1. Problem

A published paper is a bundle of claims; almost none of them are bound to
anything a reader can execute. Reproduction is organised at the *paper* level
(MLRC, ReScience, CODECHECK) or automated as *research benchmarks*
(PaperBench, CORE-Bench, VERITAS), but there is no public, per-paper-ID record
of *who ran what, in which environment, which number differed, and what the
authors said*. Papers with Code, which came closest to a paper→code→number
ledger, shut down in 2025.

paperunit is the missing connective layer: a claim-level, re-runnable audit
report format, a small CLI, and a static registry. It does not publish papers,
review papers, or rank researchers.

## 2. Design principles

1. **Claim-local evidence.** Every verdict belongs to one claim and one
   preregistered check. No aggregate score is produced, because a score invites
   optimisation against the score.
2. **No scores, no rankings.** This is a direct consequence of the project's own
   red-team evidence: a reward function that is measurable can be gamed, and a
   score measuring compliance is not a score measuring value.
3. **Executable evidence beats self-report.** A claim is supported by a command
   whose output is captured and hashed, not by prose or by a reviewer's rating.
4. **Re-runnable reports.** `verify` recomputes the report digest, re-runs every
   check, and distinguishes a modified stored report (`TAMPERED`) from a changed
   result (`DRIFT`).
5. **Audit artefacts, not people.** The report states what happened under stated
   conditions; it never attributes intent or misconduct. Authors get a
   documented right of reply before publication.
6. **Explicit resolution.** Statistical and formal verdicts state what they can
   and cannot establish: a confidence interval and minimum detectable effect for
   data; the shipped formalisation for proofs; INCONCLUSIVE when the toolchain
   is missing.
7. **Static, forkable infrastructure.** Reports live in git; the registry is a
   generated static site; there are no accounts, no backend, no tokens, no chain.

## 3. Architecture

```
audit.json (preregistered claims)
     │
     ▼
┌─────────────┐   one CheckContext per claim
│   engine    │────────────────────────────────┐
└─────────────┘                                │
     │ dispatch by claim.kind                  ▼
     │                              ┌───────────────────────┐
     │                              │ checker registry      │
     │                              │ numeric/stdout/exit   │
     │                              │ statistics   lean4    │
     │                              │ external     human    │
     │                              └───────────┬───────────┘
     │                                          │ Outcome(verdict, reason,
     │                                          │         evidence, uncertainty)
     ▼                                          ▼
report.json  (+ report.md)  ──►  static registry (index.json/html)
     │
     └── verify: digest check → re-run → compare (REPRODUCIBLE/DRIFT/TAMPERED)
```

Modules:

- `schema.py` — load/migrate/validate audit specs; schema versioning (`paperaudit/v0` → `paperunit/v1`).
- `engine.py` — dispatch, outcome collection, stable report digest, verify comparison.
- `report.py` — Markdown rendering (scope, verdicts, evidence, uncertainty, limits).
- `cli.py` — `run`, `verify`, `validate`, `registry build`, `init`.
- `checkers/` — `base.py` (frozen interface), `executables.py`, `human.py`, plus optional `statistics.py`, `lean4.py`, `external.py`.
- `registry.py` — scan `audit_report.json` files, emit static index.
- `docs/` — protocol, ethics, checker authoring.

## 4. Claim taxonomy and trust hierarchy

| class | example | checker | what is trusted |
|---|---|---|---|
| A numeric | "test accuracy 92.3%" | `numeric` / `statistics` | the re-run, under preregistered tolerance |
| B property | "no future-token leakage", "shape contract" | `external` (property test / Z3) | the property harness and its domain |
| C mathematical | "Theorem 3.1: rate O(1/T)" | `lean4` | the proof checker + the shipped formalisation |
| D empirical / compute-bound | "trained on 8×H100 for 3 days" | `human` / not supported | nothing mechanical; recorded as NOT_RUN |

The hierarchy in every report is: proof > counterexample > deterministic re-run >
interval estimate > human note. Higher layers can be stronger but narrower;
lower layers are cheaper but weaker. Mixing them into one number is exactly what
this project refuses to do.

### 4.1 Statistical verdicts

The statistics checker runs a command once per preregistered seed, parses one
metric, and reports `mean`, `sd`, `se`, a confidence interval (bootstrap
percentile by default, t-interval optional), the equivalence margin, the effect
size and the minimum detectable effect.

The margin is resolved by `paperunit/margin.py` and is part of the
preregistration: `paper_precision` (default; one unit in the paper's last
reported decimal place), `fixed` (explicit number), or `policy_ref` (read from
`policies/margin/vN.json`, recording the policy path and `decision_id`). The
policy file is the only object a future DAO/council may govern; verdicts and
evidence are reproducible artefacts, not votes. Policy changes apply to new
audits only.

- difference ≤ margin → `SUPPORTED`
- difference > margin and claimed value outside the interval → `REFUTED`
- otherwise → `INCONCLUSIVE` (underpowered; the report says so)

The semantic claim is: *"at the preregistered resolution, the audit's estimate is
or is not distinguishable from the claimed value."* It is not "the paper is
wrong with probability p". Multiple-comparison correction (Holm) is implemented
as a helper and will be wired to multi-claim audits in a later version; until
then reports must state that comparisons are unadjusted.

### 4.2 Formal verification trust model

- `lean4` `SUPPORTED` means: the Lean project builds with the declared command,
  contains no `sorry`, and the formal statement is the one shipped in the audit.
- Build failure, missing toolchain, or `sorry` → `INCONCLUSIVE`. A failed
  formalisation is an audit-side failure until a counterexample exists.
- `external` + Z3/property tests may return `REFUTED` with a witness; this is
  the only way a formal-style check can claim a refutation, and the witness is
  included in the report.
- Autoformalisation (LLM-drafted Lean) is allowed only as a labelled hypothesis.
  A human must review the formalisation before it can appear as a check.
- Scope: AI papers rarely have fully formalisable claims. The value of the
  formal layer is to make the boundary explicit — this claim is proved, this one
  is estimated, this one is untestable as stated.

## 5. Evidence, digests and verification

Each check records the exact command, working directory, timeout, exit status,
wall-clock duration, stdout/stderr hashes and an evidence hash. The report digest
is computed over a **stable view** of the claim records: volatile fields
(`duration_s`, timestamps) are removed before hashing, so two honest runs match.

`verify`:

1. recompute the stored report's digest → mismatch ⇒ `TAMPERED`;
2. re-run every claim with the same audit spec;
3. compare verdicts and stable evidence ⇒ differences ⇒ `DRIFT`;
4. otherwise `REPRODUCIBLE` (or `INCONCLUSIVE` if any re-run is inconclusive).

This makes "the report is re-runnable" a property of the artefact, not a promise.

### 5.1 Evidence stability

Not every byte of stdout is decisive. A ``kind: exit`` claim judges the exit
status; unittest timings and incidental output differ between honest runs and
must not produce DRIFT. Such checkers mark their evidence with
``comparison_mode: "verdict_only"``, and the fingerprint drops the volatile run
fields (stdout/stderr hashes, excerpts, durations) while keeping exit status and
timeout. Numeric and stdout checkers stay strict: a changed number is a real
``evidence_changed`` difference. An audit file may override the mode per claim
with ``evidence_comparison``.

## 6. Schema and evolution

- `paperunit/v1` is the current audit schema; `paperaudit/v0` is migrated
  automatically. Report schema is `paperunit/report/v1`.
- Schema changes follow semver. Breaking changes require a migration function
  and a major version bump; the registry keeps old reports readable.
- Checkers are versioned by their `kind` contract; adding a new kind is
  additive. Removing a kind requires a deprecation cycle (see OPS.md).

## 7. Roadmap

- **v0.2.1** — margin policy (`paper_precision` default; `policy_ref` hook);
  pseudonymous maintainer identity and independent repository.
- **v0.3** — real audits (5–10 papers); multiple-comparison correction across
  claims; dataset-leakage checker (train/test overlap, normalization leakage);
  package the causal-mask two-forward audit as a first-class checker.
- **v0.4** — Lean CI job with a pinned toolchain; optional Z3 extra in CI;
  registry membership workflow (PR + CI verify); audit correction/retraction
  fields; Zenodo archival and DOI for registry releases. The first
  published-paper formalisation demo (NCC energy identity, arXiv:2607.08897)
  landed as `examples/lean_paper_ncc/` in v0.2.1.
- **v1.0** — schema stability, published two or three real audit batches,
  external re-runner(s) other than the authors, and one reproducibility-venue
  submission (TMLR / MLRC "methods and tools" or "meta-reproducibility").
- **12 months / ≥20 audits** — evaluate the first non-token margin-policy
  council (auditors + authors + readers); only then consider whether a DAO
  should own `policies/margin/` (OPS §4.7).

## 8. Open questions

- How many real audits are needed before the registry is useful to anyone but
  its authors? (Plan: 5–10 per semester, one external re-runner as the bar.)
- Should statistical verdicts use equivalence testing explicitly (TOST) rather
  than the current margin rule? (Probably yes; needs a clearer preregistration
  interface.)
- How much of the causal-mask/leakage property suite can be packaged without
  pulling in ML frameworks as dependencies? (Current answer: run external
  scripts in the auditor's environment; keep the core stdlib-only.)
- What is the minimal legal review that makes a public audit defensible in
  mainland China? (See docs/ethics.md; default to paper + DOI, no author naming,
  right of reply first.)

## 9. References

- The Mask Is Not the Model: prefix invariance and two-forward causal audit (arXiv 2608.22876, 2026).
- MLRC 2026 / NeurIPS 2026 reproducibility track (TMLR-first).
- CODECHECK certificates of reproducible computation; Gundersen et al. 2018 (8% of top-tier AI papers shared code).
- PubPeer commenting guidelines (facts only, no misconduct allegations, right of reply).
- This workspace's red-team report on scoring rules, for the "no aggregate score" decision.
