# Formal audit: the NCC energy identity from arXiv:2607.08897

**Source paper.** R. B. Uludag, A. Efe, I. Akturk, U. R. Karpuzcu,
"Breaking Local-Minimum Traps in Spiking Neural Network-Based Solvers for CSPs
via Parallel Tempering", arXiv:2607.08897v1, July 2026 (Section 2.2, Eqs. 3-10).
Local copy: `26 summer/KB/Breaking Local-Minimum Traps ... Parallel Tempering .pdf`.

**What the method says.** For binary neurons with membrane potential
`u_i(x) = b_i + Σ_j w_ij x_j` (Eq. 3) and pairwise energy
`E_N(x) = -Σ_i b_i x_i - (1/2) Σ_{i,j} w_ij x_i x_j` (Eq. 6), the Neural
Computability Condition makes the stationary distribution Boltzmann,
`p(x) ∝ exp(-E(x))` (Eq. 5), so `u_i` is the conditional log-odds of neuron
`i` being active (Eq. 4). Eqs. 9-10 state that scaling the membrane potential
by `beta` is equivalent to replacing `E` by `beta E`.

**What is formalised here.** The algebraic core, for a 3-neuron network over
integer weights and biases:

1. with symmetric weights (`w_ij = w_ji`) and no self-coupling (`w_ii = 0`),
   the energy drop from flipping neuron `i` on equals `2 * u_i`, where the
   energy is represented as `2E` to clear the paper's `1/2` factor;
2. `u_i` does not depend on `x_i` (the "conditional" part);
3. for `beta = 3`, the log-odds are exactly `3x` the `beta = 1` log-odds
   (Eq. 10 at the algebraic level).

All three neurons are covered (`ncc0`, `ncc1`, `ncc2`). The Lean file is
`lean_project/PaperNCC.lean`, builds with `lake build`, contains no `sorry`,
and uses only Lean's standard library (no Mathlib).

## Formalisation map

| Paper (LaTeX) | Lean (`PaperNCC.lean`) |
|---|---|
| `x_i ∈ {0,1}` | `xv : Bool → Int` |
| `E_N(x)`, Eq. 6 | `E2` (twice the energy; factor 1/2 cleared) |
| `u_i(x)`, Eq. 3 | `u0`, `u1`, `u2` |
| `w_ij = w_ji`, `w_ii = 0` | instantiated hypotheses in the theorems |
| energy drop | `E2 (x_i := false) - E2 (x_i := true)` |
| `beta = 3` scaling, Eq. 10 | `temp3` |

## Trust boundary (read this before citing)

`SUPPORTED` means: **Lean checks this formalisation**. It does not mean the
paper's full real-valued theorem is proved. Specifically, not formalised:

- real-valued weights/biases (the paper states `w_ij ∈ R`; this audit uses `Z`);
- networks larger than 3 neurons;
- the transcendental step `p ∝ exp(-E) ⇒ log-odds = energy drop` (it needs a
  real-analysis library; here it is documented, not proved);
- any empirical/CSP-solving claim of the paper.

The formalisation was written by the auditor, not by the authors; a mis-translation
would be the auditor's error, not evidence about the paper. This is the trust model
described in `DESIGN.md` §4.2: a proof failure is `INCONCLUSIVE`, and only a
counterexample would be a `REFUTED` for formal claims.

## Reproduce

```bash
# with a Lean 4.35.0 toolchain on PATH (this workspace: scripts/with-toolchains.sh)
cd examples/lean_paper_ncc/lean_project && lake build
cd ../../..   # paperunit/
python3 -m paperunit run    --audit examples/lean_paper_ncc/audit.json --out out/lean_paper_ncc
python3 -m paperunit verify --audit examples/lean_paper_ncc/audit.json --report out/lean_paper_ncc/audit_report.json
```
