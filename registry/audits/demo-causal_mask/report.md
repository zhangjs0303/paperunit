# Executable paper audit: Causal Mask Prefix Invariance: A Test-Based Audit Fixture

| Field | Value |
|---|---|
| paper | examples/causal_mask/paper.md |
| repo_commit | synthetic-fixture-v1 (not a git checkout) |
| audited_by | paperunit formal-checker demo |
| date | 2026-10-19 |
| tool | paperunit 0.2.1 |
| generated_at | 2026-10-19T12:53:29Z |
| audit_file | `examples/causal_mask/audit.json` |
| report_sha256 | `50c6c65d2704591149000a0c7272b0bb8671dd5486899aaced0ea0c131536e80` |

> An audit is evidence-local. It is not a verdict on the paper's scientific value, and it carries no aggregate score or ranking.

## Scope

**Tested**

- prefix invariance of the correct causal mask (causal_ok)
- prefix invariance of the broken no-mask variant (causal_broken), expected to fail
- the presence of a concrete counterexample (position and output delta) for the broken variant

**Not tested / explicit limits**

- correctness of attention for inputs other than the fixed fixture input
- training dynamics, model quality, or any claim beyond prefix invariance
- a formal proof over all inputs (the z3_demo symbolic check is a separate fixture)
- anything outside the two claims listed below
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
| M1 | external | SUPPORTED | prefix invariance held: replacing tokens at positions 3..5 left positions 0..2 unchanged (max abs diff 0 <= tolerance 1e-09). |
| M2 | external | REFUTED | prefix invariance violated at position 0: changing suffix tokens changed the prefix output by 0.564952 (> tolerance 1e-09); the mask does not block attention to future positions. |

### M1 - SUPPORTED

**Claim:** With the correct causal mask, replacing the suffix tokens of the fixture input leaves the prefix hidden states unchanged (prefix invariance).

- **Verdict:** `SUPPORTED`
- **Reason:** prefix invariance held: replacing tokens at positions 3..5 left positions 0..2 unchanged (max abs diff 0 <= tolerance 1e-09).
- **Preregistered:** True

### M2 - REFUTED

**Claim:** DETECTOR SELF-TEST: the broken variant that drops the future mask still preserves prefix invariance and must be REFUTED by the audit with a concrete counterexample.

- **Verdict:** `REFUTED`
- **Reason:** prefix invariance violated at position 0: changing suffix tokens changed the prefix output by 0.564952 (> tolerance 1e-09); the mask does not block attention to future positions.
- **Preregistered:** False

## How to re-run

```bash
python3 -m paperunit verify --audit examples/causal_mask/audit.json --report audit_report.json
```

`verify` recomputes the report digest, re-runs every check, and compares verdicts and evidence. A change is reported as DRIFT; a modified stored report is reported as TAMPERED.
