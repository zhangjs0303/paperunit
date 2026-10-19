# Contributing to paperunit

Thanks for considering a contribution. paperunit is a small, long-lived project:
we prefer one completed audit over ten half-finished features.

## Ways to contribute

1. **Publish an audit** — pick a paper with an open artefact and one decidable
   claim (a number, a property, a short theorem), preregister a check, run it,
   and open a PR adding `registry/audits/<slug>/`. Read
   [registry/README.md](registry/README.md) and
   [docs/protocol.md](docs/protocol.md) first.
2. **Add a checker** — implement `kind` + `check(ctx) -> Outcome` against
   [paperunit/checkers/base.py](paperunit/checkers/base.py), add tests with fake
   runners, and follow [docs/checker-authoring.md](docs/checker-authoring.md).
3. **Improve the tool or docs** — bug fixes, tests, protocol clarifications.

Good first issues are listed in [OPS.md §10](OPS.md#10-上手路径新贡献者).

## Ground rules

- **No scores, rankings, or leaderboards.** A PR that adds an aggregate score,
  a "reproducibility percentage", or a ranking is rejected. Verdicts are
  evidence-local.
- **Audit artefacts, not people.** Never add a claim about intent or misconduct;
  see [docs/ethics.md](docs/ethics.md).
- **Every checker must have a check that actually runs.** A PR that only adds a
  field or an opinion is not reviewable.
- **Sign off your commits** (`git commit -s`, Developer Certificate of Origin).
- **Tests:** `python3 -m unittest discover -s tests -v` must pass, and new code
  needs tests. Keep the core standard-library-only; optional dependencies go
  behind extras (see `pyproject.toml`).
- **One PR, one purpose.** Small PRs are reviewed faster.
- **Be a decent human.** See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Review and release

- Every audit report is published only after a second maintainer signs off
  (OPS §4.2) and the corresponding author has had a 14–30 day response window.
- Corrections are versioned; never edit a published report in place. Open a new
  report version and record the supersession.
- Releases follow semver. The audit schema (`paperunit/v1`) and the report
  schema are documented in [DESIGN.md](DESIGN.md) and `paperunit/schema.py`.

## Questions

Open an issue with the `question` label. Do not open a public issue containing
an author's personal data, private correspondence, or an unverified accusation.
