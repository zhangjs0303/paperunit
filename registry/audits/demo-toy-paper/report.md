# Executable paper audit: A Synthetic Toy Paper: Two-Feature Threshold Classification

| Field | Value |
|---|---|
| paper | examples/toy_paper/paper.md |
| repo_commit | synthetic-fixture-v1 (not a git checkout) |
| audited_by | paperunit demo (v0.2) |
| date | 2026-10-19 |
| tool | paperunit 0.2.1 |
| generated_at | 2026-10-19T12:53:27Z |
| audit_file | `examples/toy_paper/audit.json` |
| report_sha256 | `bb1fe04dfd2d421be5826affff6040e63d0cfe6d241f71f7345352d2e620d798` |

> An audit is evidence-local. It is not a verdict on the paper's scientific value, and it carries no aggregate score or ranking.

## Scope

**Tested**

- reported test accuracy
- reported synthetic training time
- reported sample count in stdout
- the fabricated 1,000 held-out example claim

**Not tested / explicit limits**

- generalization to any other dataset
- statistical significance or uncertainty
- wall-clock training performance (the fixture emits a fixed synthetic time)
- any claim or code path not listed above
- An audit tests only the listed claims on the stated commit in the stated environment; it is not a verdict on the paper's scientific value, and it carries no aggregate score.

## Verdict summary

| Verdict | Count | Meaning |
|---|---:|---|
| SUPPORTED | 2 | every preregistered expectation passed |
| REFUTED | 2 | a preregistered expectation failed |
| INCONCLUSIVE | 0 | could not decide (toolchain, timeout, underpowered, ...) |
| NOT_RUN | 0 | no executable check (human review only) |

## Claims

| ID | Kind | Verdict | Reason |
|---|---|---|---|
| C1 | numeric | REFUTED | expectation failed: numeric_within: value 0.918 vs 0.923 +/- 0.002 |
| C2 | numeric | SUPPORTED | all 1 expectation(s) passed |
| C3 | stdout | SUPPORTED | all 1 expectation(s) passed |
| C4 | stdout | REFUTED | expectation failed: stdout_regex: samples=1000\b |

### C1 - REFUTED

**Claim:** On 1,000 held-out examples the classifier reaches 92.3% accuracy.

- **Verdict:** `REFUTED`
- **Reason:** expectation failed: numeric_within: value 0.918 vs 0.923 +/- 0.002
- **Preregistered:** True

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 code/train.py` | 0 | 0.0327s | `8022c979b65171d3` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `numeric_within` | no | value 0.918 vs 0.923 +/- 0.002 |


### C2 - SUPPORTED

**Claim:** Training takes 4.2 seconds on a laptop CPU (synthetic fixture value).

- **Verdict:** `SUPPORTED`
- **Reason:** all 1 expectation(s) passed
- **Preregistered:** True

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 code/train.py` | 0 | 0.0315s | `8022c979b65171d3` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `numeric_within` | yes | value 4.2 vs 4.2 +/- 2.0 |


### C3 - SUPPORTED

**Claim:** The released implementation reports the size of its synthetic dataset.

- **Verdict:** `SUPPORTED`
- **Reason:** all 1 expectation(s) passed
- **Preregistered:** True

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 code/train.py` | 0 | 0.0308s | `8022c979b65171d3` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `stdout_contains` | yes | 'samples=500' |


### C4 - REFUTED

**Claim:** The evaluation uses 1,000 held-out examples.

- **Verdict:** `REFUTED`
- **Reason:** expectation failed: stdout_regex: samples=1000\b
- **Preregistered:** True

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 code/train.py` | 0 | 0.03s | `8022c979b65171d3` |

**Expectations**

| rule | passed | detail |
|---|---|---|
| `stdout_regex` | no | samples=1000\b |


## How to re-run

```bash
python3 -m paperunit verify --audit examples/toy_paper/audit.json --report audit_report.json
```

`verify` recomputes the report digest, re-runs every check, and compares verdicts and evidence. A change is reported as DRIFT; a modified stored report is reported as TAMPERED.
