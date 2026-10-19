# Executable paper audit: Symbolic Causal-Mask Check with z3: A Counterexample-Finding Demo

| Field | Value |
|---|---|
| paper | examples/z3_demo/paper.md |
| repo_commit | synthetic-fixture-v1 (not a git checkout) |
| audited_by | paperunit formal-checker demo |
| date | 2026-10-19 |
| tool | paperunit 0.2.1 |
| generated_at | 2026-10-19T12:53:30Z |
| audit_file | `examples/z3_demo/audit.json` |
| report_sha256 | `36660109ad9fe27bc68e97097fd25fdd18c461b768d4dfdd9796afb1b9b59fb5` |

> An audit is evidence-local. It is not a verdict on the paper's scientific value, and it carries no aggregate score or ranking.

## Scope

**Tested**

- for every 0 <= i < j < 32, the correct causal mask construction blocks attention from i to j
- the deliberately broken construction, expected to admit a future attention edge (REFUTED)
- the exact counterexample positions reported by the SMT solver for the broken construction

**Not tested / explicit limits**

- any concrete Python implementation's floating-point behavior (see examples/causal_mask)
- sequence lengths above 32
- mask constructions other than the two encoded predicates
- anything outside the two claims listed below; without z3-solver both claims are INCONCLUSIVE by design
- An audit tests only the listed claims on the stated commit in the stated environment; it is not a verdict on the paper's scientific value, and it carries no aggregate score.

## Verdict summary

| Verdict | Count | Meaning |
|---|---:|---|
| SUPPORTED | 1 | every preregistered expectation passed |
| REFUTED | 1 | a preregistered expectation failed |
| INCONCLUSIVE | 0 | could not decide (toolchain, timeout, underpowered, ...) |
| NOT_RUN | 0 | no executable check (human review only) |

## Claims

| ID | Kind | Verdict | Reason |
|---|---|---|---|
| Z1 | external | SUPPORTED | z3 proved the property (unsat): for every pair of positions 0 <= i < j < 32 the causal mask blocks attention from i to j, covering all sequence lengths T <= 32. |
| Z2 | external | REFUTED | z3 found a counterexample (sat): the mask allows position 0 to attend to future position 1, so the construction is not causal. |

### Z1 - SUPPORTED

**Claim:** The correct causal-mask construction blocks every attention edge to a future position for all sequence lengths T <= 32.

- **Verdict:** `SUPPORTED`
- **Reason:** z3 proved the property (unsat): for every pair of positions 0 <= i < j < 32 the causal mask blocks attention from i to j, covering all sequence lengths T <= 32.
- **Preregistered:** True

### Z2 - REFUTED

**Claim:** DETECTOR SELF-TEST: the deliberately broken mask construction (no future mask) must be REFUTED with a concrete counterexample.

- **Verdict:** `REFUTED`
- **Reason:** z3 found a counterexample (sat): the mask allows position 0 to attend to future position 1, so the construction is not causal.
- **Preregistered:** False

## How to re-run

```bash
python3 -m paperunit verify --audit examples/z3_demo/audit.json --report audit_report.json
```

`verify` recomputes the report digest, re-runs every check, and compares verdicts and evidence. A change is reported as DRIFT; a modified stored report is reported as TAMPERED.
