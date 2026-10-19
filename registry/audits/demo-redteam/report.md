# Executable paper audit: Dogfood audit of the DeSci red-team scoring harness

| Field | Value |
|---|---|
| paper | vendored copy of the DeSci red-team harness (read-only; see harness/README.md) |
| repo_commit | unversioned local tree: score.py sha256 7d0ba01971be..., verify_all.py sha256 b0faa2d49cf4... |
| audited_by | paperunit demo (v0.2) |
| date | 2026-10-19 |
| tool | paperunit 0.2.1 |
| generated_at | 2026-10-19T12:53:28Z |
| audit_file | `examples/redteam/audit.json` |
| report_sha256 | `dcd81abda3b10ef26ddad4a358630e289e23c0e260587dc5985fa4e8b726fccc` |

> An audit is evidence-local. It is not a verdict on the paper's scientific value, and it carries no aggregate score or ranking.

## Scope

**Tested**

- baseline total R printed by score.py
- rt1_volume total R printed by score.py
- exit status of verify_all.py
- one deliberately false expectation used as a detector self-test

**Not tested / explicit limits**

- scientific validity or incentive properties of the red-team scoring rules
- behavior on modified, additional, or regenerated logs
- floating-point internals of score.py or score_v2.py
- anything outside the four claims listed here
- An audit tests only the listed claims on the stated commit in the stated environment; it is not a verdict on the paper's scientific value, and it carries no aggregate score.

## Verdict summary

| Verdict | Count | Meaning |
|---|---:|---|
| SUPPORTED | 3 | every preregistered expectation passed |
| REFUTED | 1 | a preregistered expectation failed |
| INCONCLUSIVE | 0 | could not decide (toolchain, timeout, underpowered, ...) |
| NOT_RUN | 0 | no executable check (human review only) |

## Claims

| ID | Kind | Verdict | Reason |
|---|---|---|---|
| R1 | stdout | SUPPORTED | all 1 expectation(s) passed |
| R2 | stdout | SUPPORTED | all 1 expectation(s) passed |
| R3 | exit | SUPPORTED | all 1 expectation(s) passed |
| R4 | stdout | REFUTED | expectation failed: stdout_contains: '总 R = 999.999' |

### R1 - SUPPORTED

**Claim:** The frozen v0 scorer reproduces the baseline total R = 9.450.

- **Verdict:** `SUPPORTED`
- **Reason:** all 1 expectation(s) passed
- **Preregistered:** True

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 score.py baseline.jsonl` | 0 | 0.0306s | `98046b4830d183a3` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `stdout_contains` | yes | '总 R = 9.450' |


### R2 - SUPPORTED

**Claim:** The frozen v0 scorer reproduces the rt1_volume total R = 92.997.

- **Verdict:** `SUPPORTED`
- **Reason:** all 1 expectation(s) passed
- **Preregistered:** True

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 score.py rt1_volume/events.jsonl` | 0 | 0.0311s | `56ed4b36501f2cd2` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `stdout_contains` | yes | '总 R = 92.997' |


### R3 - SUPPORTED

**Claim:** The red-team's verify_all.py self-check exits 0.

- **Verdict:** `SUPPORTED`
- **Reason:** all 1 expectation(s) passed
- **Preregistered:** True

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 verify_all.py` | 0 | 1.1668s | `4ab68e051bc1d06b` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `exit_code` | yes | exit 0 vs 0 |


### R4 - REFUTED

**Claim:** SELF-TEST: the deliberately wrong expectation 总 R = 999.999 must be REFUTED; this demonstrates that the audit catches a false claim.

- **Verdict:** `REFUTED`
- **Reason:** expectation failed: stdout_contains: '总 R = 999.999'
- **Preregistered:** False

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 score.py baseline.jsonl` | 0 | 0.042s | `98046b4830d183a3` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `stdout_contains` | no | '总 R = 999.999' |


## How to re-run

```bash
python3 -m paperunit verify --audit examples/redteam/audit.json --report audit_report.json
```

`verify` recomputes the report digest, re-runs every check, and compares verdicts and evidence. A change is reported as DRIFT; a modified stored report is reported as TAMPERED.
