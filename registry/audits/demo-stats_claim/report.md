# Executable paper audit: A Synthetic Seed-Sweep Paper: Claimed Accuracy versus Seed Noise

| Field | Value |
|---|---|
| paper | examples/stats_claim/paper.md |
| repo_commit | synthetic-fixture-v1 (not a git checkout) |
| audited_by | paperunit statistics demo (v0.2) |
| date | 2026-10-19 |
| tool | paperunit 0.2.1 |
| generated_at | 2026-10-19T12:53:29Z |
| audit_file | `examples/stats_claim/audit.json` |
| report_sha256 | `2cdf296b76194e9fded7fd2a0cffd260d8da360dfba3748d205fd04b2f1ba1e4` |

> An audit is evidence-local. It is not a verdict on the paper's scientific value, and it carries no aggregate score or ranking.

## Scope

**Tested**

- S1: mean accuracy claim 0.923 checked at the paper's own reported precision (default paper_precision margin)
- S2: mean accuracy claim 0.918 with an explicitly preregistered margin of 0.01
- S3: mean accuracy claim 0.918 checked against the versioned margin policy (policy_ref)
- seed-to-seed variability of the reported accuracy across seeds 0-5
- the resolution of the six-seed sweep: 95% interval and minimum detectable effect

**Not tested / explicit limits**

- any real dataset, model, paper, or author
- seeds outside 0-5
- statistical significance against a baseline or competing method
- wall-clock training performance (the fixture is deterministic and timed only by the runner)
- multiple-comparison correction across claims (holm_adjust exists but is not applied per-claim)
- An audit tests only the listed claims on the stated commit in the stated environment; it is not a verdict on the paper's scientific value, and it carries no aggregate score.

## Verdict summary

| Verdict | Count | Meaning |
|---|---:|---|
| SUPPORTED | 2 | every preregistered expectation passed |
| REFUTED | 1 | a preregistered expectation failed |
| INCONCLUSIVE | 0 | could not decide (toolchain, timeout, underpowered, ...) |
| NOT_RUN | 0 | no executable check (human review only) |

## Claims

| ID | Kind | Verdict | Reason |
|---|---|---|---|
| S1 | statistics | REFUTED | observed mean 0.918 differs from the claimed value 0.923 by a gap of 0.005, which exceeds the equivalence margin 0.001, and the interval [0.915333, 0.920667] excludes the claimed value; the minimum d… |
| S2 | statistics | SUPPORTED | observed mean 0.918 is within the equivalence margin 0.01 of the claimed value 0.918 (gap 0); the interval [0.915333, 0.920667] is reported for resolution; the minimum detectable effect (MDE) of this… |
| S3 | statistics | SUPPORTED | observed mean 0.918 is within the equivalence margin 0.0005 of the claimed value 0.918 (gap 0); the interval [0.915333, 0.920667] is reported for resolution; the minimum detectable effect (MDE) of th… |

### S1 - REFUTED

**Claim:** The seed-averaged test accuracy over six seeds is 92.3% (checked at the paper's own reported precision).

- **Verdict:** `REFUTED`
- **Reason:** observed mean 0.918 differs from the claimed value 0.923 by a gap of 0.005, which exceeds the equivalence margin 0.001, and the interval [0.915333, 0.920667] excludes the claimed value; the minimum detectable effect (MDE) of this sweep is 0.0043402.
- **Preregistered:** True

**Uncertainty / resolution**

- `n`: 6
- `mean`: 0.918
- `sd`: 0.00379473
- `se`: 0.00154919
- `ci_low`: 0.915333
- `ci_high`: 0.920667
- `ci_half_width`: 0.00266667
- `method`: bootstrap
- `confidence`: 0.95
- `resamples`: 2000
- `seed`: 0
- `min_detectable_effect`: 0.0043402
- `equivalence_margin`: 0.001
- `effect`: -0.005
- `ci_method`: bootstrap_percentile_linear
- `claimed_value`: 0.923
- `margin_decision_id`: 
- `margin_mode`: paper_precision
- `margin_policy_version`: 
- `margin_source`: paper_precision
- `note`: percentile bootstrap with n=6 is a coarse resolution check; read it together with the minimum detectable effect, not as a calibrated posterior statement.
- `values_sha256`: fe04cd5b51a479a0fb67d5b8edb610af7726802766f18a912d03825b3b850892

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 code/train.py --seed 0` | 0 | 0.0461s | `ab05bffa145501f2` |
| 2 | `python3 code/train.py --seed 1` | 0 | 0.0462s | `8ccbece0e6bf04ce` |
| 3 | `python3 code/train.py --seed 2` | 0 | 0.046s | `eafd48726d93421b` |
| 4 | `python3 code/train.py --seed 3` | 0 | 0.0451s | `de6e12aca96738d8` |
| 5 | `python3 code/train.py --seed 4` | 0 | 0.0479s | `4fb8966ff5940e4a` |
| 6 | `python3 code/train.py --seed 5` | 0 | 0.0482s | `3523e9debdec9f6e` |

**Resolution (how much doubt this data can bear)**

- `ci_excludes_claimed`: True
- `ci_half_width`: 0.00266667
- `equivalence_margin`: 0.001
- `margin_mode`: paper_precision
- `margin_note`: margin derived from the paper's own reported precision: 3 decimal place(s) -> 0.001
- `margin_source`: paper_precision
- `mde_alpha`: 0.05
- `mde_exceeds_margin`: True
- `mde_over_margin`: 4.3402
- `mde_power`: 0.8
- `min_detectable_effect`: 0.0043402
- `n`: 6
- `observed_gap`: 0.005
- `observed_gap_exceeds_mde`: True

> Seed sweep n=6 with observed SD=0.00379473 gives a 0.95 interval half-width of 0.00266667 and a minimum detectable effect (MDE) of 0.0043402 at alpha=0.05, power=0.8 (one-sample, two-sided). The MDE (0.0043402) is larger than the claim's equivalence margin (0.001): this sweep cannot resolve differences as small as the margin. The observed gap (0.005) is larger than the MDE, so the observed discrepancy is above this sweep's noise floor. The percentile bootstrap interval over so few values is coarse and can understate its width; the MDE is reported so that the interval alone is not treated as decisive.


### S2 - SUPPORTED

**Claim:** The seed-averaged test accuracy over six seeds is 91.8% (equivalence margin 1 percentage point).

- **Verdict:** `SUPPORTED`
- **Reason:** observed mean 0.918 is within the equivalence margin 0.01 of the claimed value 0.918 (gap 0); the interval [0.915333, 0.920667] is reported for resolution; the minimum detectable effect (MDE) of this sweep is 0.0043402.
- **Preregistered:** True

**Uncertainty / resolution**

- `n`: 6
- `mean`: 0.918
- `sd`: 0.00379473
- `se`: 0.00154919
- `ci_low`: 0.915333
- `ci_high`: 0.920667
- `ci_half_width`: 0.00266667
- `method`: bootstrap
- `confidence`: 0.95
- `resamples`: 2000
- `seed`: 0
- `min_detectable_effect`: 0.0043402
- `equivalence_margin`: 0.01
- `effect`: 0
- `ci_method`: bootstrap_percentile_linear
- `claimed_value`: 0.918
- `margin_decision_id`: 
- `margin_mode`: fixed
- `margin_policy_version`: 
- `margin_source`: explicit numeric equivalence_margin
- `note`: percentile bootstrap with n=6 is a coarse resolution check; read it together with the minimum detectable effect, not as a calibrated posterior statement.
- `values_sha256`: fe04cd5b51a479a0fb67d5b8edb610af7726802766f18a912d03825b3b850892

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 code/train.py --seed 0` | 0 | 0.0473s | `ab05bffa145501f2` |
| 2 | `python3 code/train.py --seed 1` | 0 | 0.0477s | `8ccbece0e6bf04ce` |
| 3 | `python3 code/train.py --seed 2` | 0 | 0.0473s | `eafd48726d93421b` |
| 4 | `python3 code/train.py --seed 3` | 0 | 0.0484s | `de6e12aca96738d8` |
| 5 | `python3 code/train.py --seed 4` | 0 | 0.048s | `4fb8966ff5940e4a` |
| 6 | `python3 code/train.py --seed 5` | 0 | 0.0482s | `3523e9debdec9f6e` |

**Resolution (how much doubt this data can bear)**

- `ci_excludes_claimed`: False
- `ci_half_width`: 0.00266667
- `equivalence_margin`: 0.01
- `margin_mode`: fixed
- `margin_note`: explicit margin 0.01 declared in the audit file
- `margin_source`: explicit numeric equivalence_margin
- `mde_alpha`: 0.05
- `mde_exceeds_margin`: False
- `mde_over_margin`: 0.43402
- `mde_power`: 0.8
- `min_detectable_effect`: 0.0043402
- `n`: 6
- `observed_gap`: 0
- `observed_gap_exceeds_mde`: False

> Seed sweep n=6 with observed SD=0.00379473 gives a 0.95 interval half-width of 0.00266667 and a minimum detectable effect (MDE) of 0.0043402 at alpha=0.05, power=0.8 (one-sample, two-sided). The MDE (0.0043402) is no larger than the claim's equivalence margin (0.01): the sweep's resolution is at least as fine as the claimed tolerance. The observed gap (0) is inside the claim's equivalence margin, so the tolerance window is met; this is a tolerance match, not a significance claim. The percentile bootstrap interval over so few values is coarse and can understate its width; the MDE is reported so that the interval alone is not treated as decisive.


### S3 - SUPPORTED

**Claim:** The seed-averaged test accuracy over six seeds is 91.8%, checked against the versioned margin policy.

- **Verdict:** `SUPPORTED`
- **Reason:** observed mean 0.918 is within the equivalence margin 0.0005 of the claimed value 0.918 (gap 0); the interval [0.915333, 0.920667] is reported for resolution; the minimum detectable effect (MDE) of this sweep is 0.0043402.
- **Preregistered:** True

**Uncertainty / resolution**

- `n`: 6
- `mean`: 0.918
- `sd`: 0.00379473
- `se`: 0.00154919
- `ci_low`: 0.915333
- `ci_high`: 0.920667
- `ci_half_width`: 0.00266667
- `method`: bootstrap
- `confidence`: 0.95
- `resamples`: 2000
- `seed`: 0
- `min_detectable_effect`: 0.0043402
- `equivalence_margin`: 0.0005
- `effect`: 0
- `ci_method`: bootstrap_percentile_linear
- `claimed_value`: 0.918
- `margin_decision_id`: MARGIN-2026-10-19-01
- `margin_mode`: policy_ref
- `margin_policy_version`: v1
- `margin_source`: policies/margin/v1.json
- `note`: percentile bootstrap with n=6 is a coarse resolution check; read it together with the minimum detectable effect, not as a calibrated posterior statement.
- `values_sha256`: fe04cd5b51a479a0fb67d5b8edb610af7726802766f18a912d03825b3b850892

**Runs**

| # | command | exit | duration | evidence sha256 |
|---|---|---:|---:|---|
| 1 | `python3 code/train.py --seed 0` | 0 | 0.0465s | `ab05bffa145501f2` |
| 2 | `python3 code/train.py --seed 1` | 0 | 0.0462s | `8ccbece0e6bf04ce` |
| 3 | `python3 code/train.py --seed 2` | 0 | 0.0465s | `eafd48726d93421b` |
| 4 | `python3 code/train.py --seed 3` | 0 | 0.0463s | `de6e12aca96738d8` |
| 5 | `python3 code/train.py --seed 4` | 0 | 0.046s | `4fb8966ff5940e4a` |
| 6 | `python3 code/train.py --seed 5` | 0 | 0.0493s | `3523e9debdec9f6e` |

**Resolution (how much doubt this data can bear)**

- `ci_excludes_claimed`: False
- `ci_half_width`: 0.00266667
- `equivalence_margin`: 0.0005
- `margin_decision_id`: MARGIN-2026-10-19-01
- `margin_mode`: policy_ref
- `margin_note`: margin 0.0005 read from policy policies/margin/v1.json (decision MARGIN-2026-10-19-01): Demo policy: half of the paper's last reported digit. Example of the fu…
- `margin_policy_version`: v1
- `margin_source`: policies/margin/v1.json
- `mde_alpha`: 0.05
- `mde_exceeds_margin`: True
- `mde_over_margin`: 8.68039
- `mde_power`: 0.8
- `min_detectable_effect`: 0.0043402
- `n`: 6
- `observed_gap`: 0
- `observed_gap_exceeds_mde`: False

> Seed sweep n=6 with observed SD=0.00379473 gives a 0.95 interval half-width of 0.00266667 and a minimum detectable effect (MDE) of 0.0043402 at alpha=0.05, power=0.8 (one-sample, two-sided). The MDE (0.0043402) is larger than the claim's equivalence margin (0.0005): this sweep cannot resolve differences as small as the margin. The observed gap (0) is inside the claim's equivalence margin, so the tolerance window is met; this is a tolerance match, not a significance claim. The percentile bootstrap interval over so few values is coarse and can understate its width; the MDE is reported so that the interval alone is not treated as decisive.


## How to re-run

```bash
python3 -m paperunit verify --audit examples/stats_claim/audit.json --report audit_report.json
```

`verify` recomputes the report digest, re-runs every check, and compares verdicts and evidence. A change is reported as DRIFT; a modified stored report is reported as TAMPERED.
