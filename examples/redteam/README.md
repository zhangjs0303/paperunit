# examples/redteam

A self-contained "audit the audit" demo: paperunit re-runs claims made by this
workspace's earlier red-team simulation of a scoring rule for research
collaboration. The report being audited claimed specific scorer readings
(baseline `总 R = 9.450`, one attack route `总 R = 92.997`, and that
`verify_all.py` exits 0). This audit re-executes those commands and checks the
numbers.

`harness/` is a **vendored, read-only copy** of that red-team harness (the
scorer, its frozen rules, the event logs and its own verification script). It is
kept here so the example is reproducible outside the original workspace; the
files are unchanged and the same frozen scorers are used.

The last claim (`R4`) is a deliberately wrong expectation (`总 R = 999.999`): it
must be `REFUTED`, and serves as a self-test that the auditor actually detects a
false claim. This is the "audit the audit" pattern recommended for new
contributors: start by auditing your own previous report.

Provenance and context: see the workspace documents
`2026-10-18_奖励函数红队模拟_报告与v0.2修订.md` and
`2026-10-19_开源项目立项评估_可执行论文审计.md` (outside this repository when
it is exported standalone).

Run it:

```bash
python3 -m paperunit run    --audit examples/redteam/audit.json --out out/redteam
python3 -m paperunit verify --audit examples/redteam/audit.json --report out/redteam/audit_report.json
```
