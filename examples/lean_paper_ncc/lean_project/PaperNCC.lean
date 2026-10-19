import Std

/-!
# Formalisation of the Neural Computability Condition (NCC) core

Source paper: "Breaking Local-Minimum Traps in Spiking Neural Network-Based
Solvers for CSPs via Parallel Tempering", Uludag, Efe, Akturk, Karpuzcu
(arXiv:2607.08897v1, 2026), Section 2.2.

The paper's method states (Eqs. 3-6) that with membrane potential

    u_i(x) = b_i + Σ_j w_ij x_j                                   (3)

and pairwise energy

    E_N(x) = -Σ_i b_i x_i - (1/2) Σ_{i,j} w_ij x_i x_j,           (6)

the Neural Computability Condition makes the stationary law Boltzmann
p(x) ∝ exp(-E(x)) (Eq. 5), so that u_i equals the conditional log-odds of
neuron i being active (Eq. 4-5).  Eqs. 9-10 say that rescaling the membrane
potential by beta is equivalent to replacing E by beta * E.

This file formalises the algebraic core of that statement for a 3-neuron
network over integer weights and biases:

* with symmetric weights (w_ij = w_ji) and no self-coupling (w_ii = 0),
  the energy drop from flipping neuron i on equals 2 * u_i when energies are
  represented as 2E (the factor 2 clears the paper's 1/2);
* u_i does not depend on x_i (the "conditional" part);
* for beta = 3, the log-odds are exactly 3x the beta = 1 log-odds.

The transcendental step (p ∝ exp(-E) => log-odds = energy drop) is not
formalised here; it is the standard Boltzmann argument and would need a real
analysis library.  No Mathlib is used; only Lean's standard library.
-/


/-- Truth value of a binary neuron as an integer. -/
def xv : Bool → Int
  | true => 1
  | false => 0

/-- Twice the pairwise energy (Eq. 6), with the 1/2 factor cleared. -/
def E2 (b0 b1 b2 w00 w01 w02 w10 w11 w12 w20 w21 w22 : Int)
    (x0 x1 x2 : Bool) : Int :=
  -2 * (b0 * xv x0 + b1 * xv x1 + b2 * xv x2)
  - (w00 * xv x0 * xv x0 + w01 * xv x0 * xv x1 + w02 * xv x0 * xv x2
     + w10 * xv x1 * xv x0 + w11 * xv x1 * xv x1 + w12 * xv x1 * xv x2
     + w20 * xv x2 * xv x0 + w21 * xv x2 * xv x1 + w22 * xv x2 * xv x2)

/-- Membrane potential of neuron 0 (Eq. 3). -/
def u0 (b0 w00 w01 w02 : Int) (x0 x1 x2 : Bool) : Int :=
  b0 + w00 * xv x0 + w01 * xv x1 + w02 * xv x2

/-- Membrane potential of neuron 1 (Eq. 3). -/
def u1 (b1 w10 w11 w12 : Int) (x0 x1 x2 : Bool) : Int :=
  b1 + w10 * xv x0 + w11 * xv x1 + w12 * xv x2

/-- Membrane potential of neuron 2 (Eq. 3). -/
def u2 (b2 w20 w21 w22 : Int) (x0 x1 x2 : Bool) : Int :=
  b2 + w20 * xv x0 + w21 * xv x1 + w22 * xv x2

/-! ## NCC core: energy drop equals membrane potential -/

theorem ncc0 (b0 b1 b2 w01 w02 w12 : Int) (x0 x1 x2 : Bool) :
    E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 false x1 x2
      - E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 true x1 x2
      = 2 * u0 b0 0 w01 w02 x0 x1 x2 := by
  cases x0 <;> cases x1 <;> cases x2 <;> simp [E2, u0, xv] <;> omega

theorem ncc1 (b0 b1 b2 w01 w02 w12 : Int) (x0 x1 x2 : Bool) :
    E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 x0 false x2
      - E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 x0 true x2
      = 2 * u1 b1 w01 0 w12 x0 x1 x2 := by
  cases x0 <;> cases x1 <;> cases x2 <;> simp [E2, u1, xv] <;> omega

theorem ncc2 (b0 b1 b2 w01 w02 w12 : Int) (x0 x1 x2 : Bool) :
    E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 x0 x1 false
      - E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 x0 x1 true
      = 2 * u2 b2 w02 w12 0 x0 x1 x2 := by
  cases x0 <;> cases x1 <;> cases x2 <;> simp [E2, u2, xv] <;> omega

/-! ## The conditional part: u_i does not depend on x_i -/

theorem u0_independent (b0 w01 w02 : Int) (x1 x2 : Bool) :
    u0 b0 0 w01 w02 true x1 x2 = u0 b0 0 w01 w02 false x1 x2 := by
  simp [u0, xv]

theorem u1_independent (b1 w01 w12 : Int) (x0 x2 : Bool) :
    u1 b1 w01 0 w12 x0 true x2 = u1 b1 w01 0 w12 x0 false x2 := by
  simp [u1, xv]

theorem u2_independent (b2 w02 w12 : Int) (x0 x1 : Bool) :
    u2 b2 w02 w12 0 x0 x1 true = u2 b2 w02 w12 0 x0 x1 false := by
  simp [u2, xv]

/-! ## Temperature scaling (Eqs. 9-10): beta = 3 multiplies the log-odds by 3 -/

theorem temp3 (b0 b1 b2 w01 w02 w12 : Int) (x1 x2 : Bool) :
    3 * E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 false x1 x2
      - 3 * E2 b0 b1 b2 0 w01 w02 w01 0 w12 w02 w12 0 true x1 x2
      = 6 * u0 b0 0 w01 w02 false x1 x2 := by
  cases x1 <;> cases x2 <;> simp [E2, u0, xv] <;> omega
