# Executable paper audit: Formal audit: NCC energy identity from arXiv:2607.08897 (3-neuron integer instance)

| Field | Value |
|---|---|
| paper | examples/lean_paper_ncc/paper.md |
| repo_commit | leanprover/lean4:v4.35.0; formalisation authored by paperunit (auditor), not by the paper authors |
| audited_by | 无常 |
| date | 2026-10-19 |
| tool | paperunit 0.2.1 |
| generated_at | 2026-10-19T13:15:25Z |
| audit_file | `examples/lean_paper_ncc/audit.json` |
| report_sha256 | `79715deb0d30ea65fdd832b699d954e7e2ca81f0f6d033296f122855d9f2304a` |

> An audit is evidence-local. It is not a verdict on the paper's scientific value, and it carries no aggregate score or ranking.

## Scope

**Tested**

- energy drop equals 2*u_i for all three neurons (symmetric weights, zero self-coupling)
- u_i is independent of x_i
- beta=3 temperature scaling of the log-odds (algebraic level)

**Not tested / explicit limits**

- real-valued weights/biases (this formalisation uses integers)
- networks larger than 3 neurons
- the exp/log step from p proportional to exp(-E) to conditional log-odds
- any empirical or CSP-solving claim of the paper
- correctness of the auditor's LaTeX-to-Lean translation
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

**Claim:** Lean 4 checks the NCC energy identity (ncc0/ncc1/ncc2), independence lemmas and beta=3 scaling in PaperNCC.lean, with no sorry.

- **Verdict:** `SUPPORTED`
- **Reason:** Lean build succeeded ('lake build', exit 0) and no `sorry` placeholders were found.
- **Preregistered:** True

## How to re-run

```bash
python3 -m paperunit verify --audit examples/lean_paper_ncc/audit.json --report audit_report.json
```

`verify` recomputes the report digest, re-runs every check, and compares verdicts and evidence. A change is reported as DRIFT; a modified stored report is reported as TAMPERED.
