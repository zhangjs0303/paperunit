# policies/

Versioned policy files that governance may own. In v0.2 this directory contains
one policy: the equivalence margin (`margin/v1.json`).

## Why the margin is a policy

The equivalence margin decides how close an audit's estimate must be to the
paper's claimed value before the claim counts as `SUPPORTED`. It is a **policy
choice**, not a statistical fact, so it should be explicit, versioned, and
reviewable — not retyped into every audit file.

Modes (resolved by `paperunit/margin.py`):

| mode | how the margin is set |
|---|---|
| `paper_precision` (default) | one unit in the last decimal place the paper reports (`0.923` → `0.001`); optional `margin_factor` |
| `fixed` | an explicit number preregistered in the audit file (backwards compatible) |
| `policy_ref` | read from a versioned policy file in this directory; the report records the policy path and `decision_id` |

## What a future DAO may and may not govern

OPS.md §4.7 describes the experiment. The intended separation:

- **may** govern: which margin policy version applies to future audits;
- **may not** govern: the evidence, verdict, or correction history of a
  particular audit. Those are reproducible artefacts, not votes.

v0.2 has no DAO and no token. The policy file is maintained by the maintainer
(pseudonym 无常) as an interim rule. A non-token mixed council (auditors,
authors, readers) is the planned first governance experiment; any token-based
mechanism would require a legal review and an OPS amendment first.

## Changing a policy

1. Open a PR adding `policies/margin/v2.json` (do not edit v1 in place).
2. State: decision id, claim type, margin, rationale, who decided, date.
3. The change applies to **new audits only**; published reports keep the policy
   they used (`decision_id` is recorded in each report).
4. CI revalidates every audit in `registry/audits/` with its recorded policy.
