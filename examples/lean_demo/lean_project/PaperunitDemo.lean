/-!
# PaperunitDemo

A tiny Lean 4 library used by the paperunit `lean4` checker demo.  Every
theorem below is closed by a core lemma or by definitional equality, so the
development contains no `sorry` placeholders.  The file is intentionally small:
the demo is about the audit protocol and the toolchain-absence path, not about
formalising a real paper.
-/

namespace PaperunitDemo

/-- Addition on `Nat` is commutative; proved by the core lemma `Nat.add_comm`. -/
theorem add_comm_demo (a b : Nat) : a + b = b + a :=
  Nat.add_comm a b

/-- A concrete computation, closed by definitional equality. -/
theorem one_add_one : 1 + 1 = 2 :=
  rfl

/-- Left identity of `Nat` addition; proved by the core lemma `Nat.zero_add`. -/
theorem zero_add_demo (n : Nat) : 0 + n = n :=
  Nat.zero_add n

end PaperunitDemo
