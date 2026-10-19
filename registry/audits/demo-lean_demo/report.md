# Executable paper audit: Lean 4 Proof Check Demo: sorry-free arithmetic lemmas

| Field | Value |
|---|---|
| paper | examples/lean_demo/paper.md |
| repo_commit | synthetic-fixture-v1 (not a git checkout) |
| audited_by | paperunit formal-checker demo |
| date | 2026-10-19 |
| tool | paperunit 0.2.1 |
| generated_at | 2026-10-19T12:53:30Z |
| audit_file | `examples/lean_demo/audit.json` |
| report_sha256 | `c4415e895465e6a751e66c1986faffcf9db27aac09d1f585c9d76d73f023f8b7` |

> An audit is evidence-local. It is not a verdict on the paper's scientific value, and it carries no aggregate score or ranking.

## Scope

**Tested**

- the Lean 4 project builds with `lake build` (when a toolchain is present)
- the development contains no standalone `sorry` placeholders
- optional existence of the named theorem PaperunitDemo.add_comm_demo

**Not tested / explicit limits**

- scientific validity of the demo statements (they are core arithmetic lemmas)
- whether the Lean development matches any real paper's definitions
- any Lean file or claim outside this fixture directory
- on a machine without a Lean toolchain, nothing is tested and the claim must be INCONCLUSIVE
- An audit tests only the listed claims on the stated commit in the stated environment; it is not a verdict on the paper's scientific value, and it carries no aggregate score.

## Verdict summary

| Verdict | Count | Meaning |
|---|---:|---|
| SUPPORTED | 1 | every preregistered expectation passed |
| REFUTED | 0 | a preregistered expectation failed |
| INCONCLUSIVE | 0 | could not decide (toolchain, timeout, underpowered, ...) |
| NOT_RUN | 0 | no executable check (human review only) |

## Claims

| ID | Kind | Verdict | Reason |
|---|---|---|---|
| L1 | lean4 | SUPPORTED | Lean build succeeded ('lake build', exit 0) and no `sorry` placeholders were found. |

### L1 - SUPPORTED

**Claim:** The Lean 4 formalisation in lean_project builds and its proofs contain no `sorry` placeholders.

- **Verdict:** `SUPPORTED`
- **Reason:** Lean build succeeded ('lake build', exit 0) and no `sorry` placeholders were found.
- **Preregistered:** True

## How to re-run

```bash
python3 -m paperunit verify --audit examples/lean_demo/audit.json --report audit_report.json
```

`verify` recomputes the report digest, re-runs every check, and compares verdicts and evidence. A change is reported as DRIFT; a modified stored report is reported as TAMPERED.
