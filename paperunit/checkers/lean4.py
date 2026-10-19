"""Lean 4 proof checker: a real ``lake build`` plus graceful toolchain absence.

Trust model
-----------
A failed Lean build means *the audit's formalisation did not go through*.  It is
not evidence that the paper's claim is wrong and it is not evidence of
misconduct: formalising a paper's theorem is hard, and a broken build usually
says more about the audit's Lean development than about the paper.  Therefore:

* toolchain missing          -> INCONCLUSIVE ("Lean toolchain not found")
* build failed or timed out  -> INCONCLUSIVE (with stderr excerpt)
* build succeeded, but the development uses ``sorry`` while ``allow_sorry`` is
  false                      -> INCONCLUSIVE ("proof contains sorry")
* build succeeded, no ``sorry`` placeholders -> SUPPORTED

This checker never returns REFUTED.  Refutations of formal claims have to come
from counterexample-finding, e.g. an SMT solver behind the ``external`` checker.

Claim shape::

    {"id": "L1", "kind": "lean4",
     "text": "...",
     "check": {"project_dir": "lean_project",
               "build_cmd": "lake build",
               "allow_sorry": false,
               "theorem": "PaperunitDemo.add_comm_demo",
               "timeout_s": 180}}

``theorem`` is optional and informational only: the checker records whether the
named declaration was found, but does not require it (the build is the check).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .base import CheckContext, Outcome, truncate

#: Version probes tried in order; the first one that exits 0 marks the
#: toolchain as available.
LEAN_PROBES: tuple[str, ...] = ("lean --version", "lake --version")

DEFAULT_BUILD_CMD = "lake build"

#: A version probe is cheap; do not let a broken wrapper hang the audit.
PROBE_TIMEOUT_S = 30.0

_SORRY_RE = re.compile(r"\bsorry\b")
_DECL_TEMPLATE = r"\b(?:theorem|lemma)\s+{name}\b"

TRUST_MODEL_NOTE = (
    "A failed Lean build means the audit's formalisation did not go through; "
    "it is not evidence against the paper's claim and not evidence of "
    "misconduct. Only a successful proof check can support the claim."
)


def _as_timeout(raw: Any, default: float) -> float:
    """Resolve a positive timeout value, falling back to ``default``."""
    try:
        value = float(raw if raw is not None else default)
    except (TypeError, ValueError):
        return float(default)
    return value if value > 0 else float(default)


def _mask_lean_comments(source: str) -> str:
    """Blank out Lean comments while preserving line structure.

    Handles nested ``/- ... -/`` block comments (including ``/-!`` doc comments)
    and ``--`` line comments.  It is a deliberate approximation: it does not
    parse string literals, so a ``--`` inside a string can hide the rest of that
    line.  For the purpose of finding standalone ``sorry`` placeholders this is
    safe in practice and errs towards not reporting comments as proofs.
    """
    out = list(source)
    depth = 0
    i = 0
    n = len(source)
    while i < n:
        pair = source[i : i + 2]
        if depth == 0 and pair == "/-":
            depth = 1
            out[i] = " "
            if i + 1 < n:
                out[i + 1] = " "
            i += 2
            continue
        if depth > 0:
            if pair == "/-":
                depth += 1
                out[i] = " "
                if i + 1 < n:
                    out[i + 1] = " "
                i += 2
                continue
            if pair == "-/":
                depth -= 1
                out[i] = " "
                if i + 1 < n:
                    out[i + 1] = " "
                i += 2
                continue
            if source[i] != "\n":
                out[i] = " "
            i += 1
            continue
        if pair == "--":
            end = source.find("\n", i)
            if end == -1:
                end = n
            for k in range(i, end):
                out[k] = " "
            i = end
            continue
        i += 1
    return "".join(out)


def _lean_files(project_dir: Path) -> list[Path]:
    """All ``*.lean`` files under ``project_dir``, sorted for determinism."""
    if not project_dir.is_dir():
        return []
    return sorted(
        (path for path in project_dir.rglob("*.lean") if path.is_file()),
        key=lambda path: path.as_posix(),
    )


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:  # pragma: no cover - rglob output is always below root
        return path.as_posix()


def find_sorry(project_dir: Path) -> list[dict[str, Any]]:
    """Locate standalone ``sorry`` tokens in the project's Lean sources.

    Returns a list of ``{"file": <relative path>, "line": <1-based line>}``.
    Commented-out occurrences are ignored.
    """
    locations: list[dict[str, Any]] = []
    for path in _lean_files(project_dir):
        source = path.read_text(encoding="utf-8", errors="replace")
        masked = _mask_lean_comments(source)
        for line_number, line in enumerate(masked.splitlines(), start=1):
            if _SORRY_RE.search(line):
                locations.append(
                    {"file": _relative(path, project_dir), "line": line_number}
                )
    return locations


def _theorem_patterns(theorem: str) -> list[re.Pattern[str]]:
    """Regexes that recognise a declaration of ``theorem``.

    Declaration lookup is informational only; it never changes the verdict.
    For a fully qualified name such as ``PaperunitDemo.add_comm_demo`` we also
    accept a declaration of the last component (``add_comm_demo``), because the
    declaration is usually written inside a ``namespace`` block.
    """
    names = [theorem]
    if "." in theorem:
        names.append(theorem.rsplit(".", 1)[-1])
    return [
        re.compile(_DECL_TEMPLATE.format(name=re.escape(name))) for name in names
    ]


def find_theorem(project_dir: Path, theorem: str) -> list[str]:
    """Return files that declare ``theorem``/``lemma`` with the given name."""
    patterns = _theorem_patterns(theorem)
    matches: list[str] = []
    for path in _lean_files(project_dir):
        source = path.read_text(encoding="utf-8", errors="replace")
        masked = _mask_lean_comments(source)
        if any(pattern.search(masked) for pattern in patterns):
            matches.append(_relative(path, project_dir))
    return matches


class Lean4Checker:
    """Build a Lean 4 project and check that the proof is ``sorry``-free."""

    kind = "lean4"

    def check(self, ctx: CheckContext) -> Outcome:
        claim = ctx.claim
        spec = claim.get("check")
        spec = spec if isinstance(spec, dict) else {}

        project_dir = (ctx.check_dir() / str(spec.get("project_dir", "."))).resolve()
        timeout_s = _as_timeout(spec.get("timeout_s"), ctx.timeout_s)

        # 1. Probe the toolchain before pretending to check anything.
        probe_cwd = project_dir if project_dir.is_dir() else ctx.check_dir()
        probes: list[dict[str, Any]] = []
        available_cmd: str | None = None
        for probe in LEAN_PROBES:
            run = ctx.runner(probe, probe_cwd, PROBE_TIMEOUT_S)
            probes.append({"cmd": probe, "run": run.summary()})
            if run.exit_code == 0 and not run.timed_out:
                available_cmd = probe
                break

        base_evidence: dict[str, Any] = {
            "project_dir": str(project_dir),
            "toolchain": {"available_cmd": available_cmd, "probes": probes},
        }

        if available_cmd is None:
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    "Lean toolchain not found: neither `lean --version` nor "
                    "`lake --version` succeeded, so the Lean project was not "
                    "built and the formal claim was not checked."
                ),
                evidence=base_evidence,
            )

        # 2. The project has to exist before we can build it.
        if not project_dir.is_dir():
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    f"Lean project directory not found: {project_dir}; no "
                    "formal build was attempted, so the claim is unchecked."
                ),
                evidence=base_evidence,
            )

        raw_build_cmd = spec.get("build_cmd", DEFAULT_BUILD_CMD)
        build_cmd = raw_build_cmd if isinstance(raw_build_cmd, str) else ""
        if not build_cmd.strip():
            build_cmd = DEFAULT_BUILD_CMD

        # 3. Real build in the project directory.
        run = ctx.runner(build_cmd, project_dir, timeout_s)
        evidence = {
            **base_evidence,
            "build_cmd": build_cmd,
            "run": run.summary(),
            "trust_model": TRUST_MODEL_NOTE,
        }

        if run.timed_out:
            evidence["stderr_excerpt"] = truncate(run.stderr, 2000)
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    f"Lean build timed out after {timeout_s:g}s; the audit's "
                    "formalisation did not go through. This is not evidence "
                    "against the paper's claim."
                ),
                evidence=evidence,
            )

        if run.exit_code != 0:
            evidence["stderr_excerpt"] = truncate(run.stderr, 2000)
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    f"Lean build failed with exit code {run.exit_code}; the "
                    "audit's formalisation did not go through. This is not "
                    "evidence against the paper's claim."
                ),
                evidence=evidence,
            )

        # 4. A passing build is only meaningful if it does not admit the goal.
        allow_sorry = bool(spec.get("allow_sorry", False))
        lean_files = [_relative(path, project_dir) for path in _lean_files(project_dir)]
        sorry_locations = find_sorry(project_dir)
        evidence.update(
            {
                "allow_sorry": allow_sorry,
                "lean_files": lean_files,
                "sorry_locations": sorry_locations,
            }
        )
        if sorry_locations and not allow_sorry:
            return Outcome(
                verdict="INCONCLUSIVE",
                reason=(
                    "proof contains sorry: the Lean build succeeds, but the "
                    f"development uses {len(sorry_locations)} `sorry` "
                    "placeholder(s) while allow_sorry is false, so the goal is "
                    "admitted rather than proved."
                ),
                evidence=evidence,
            )

        # 5. Optional, informational declaration lookup.
        theorem_note = ""
        requested = spec.get("theorem")
        if isinstance(requested, str) and requested.strip():
            requested = requested.strip()
            theorem_files = find_theorem(project_dir, requested)
            evidence["theorem_check"] = {
                "requested": requested,
                "found": bool(theorem_files),
                "files": theorem_files,
            }
            if not theorem_files:
                theorem_note = (
                    f"; requested theorem {requested!r} was not found "
                    "(recorded only, not enforced)"
                )

        if allow_sorry:
            proof_note = (
                "`sorry` placeholders are allowed by the check spec and were "
                "therefore not enforced"
            )
        else:
            proof_note = "no `sorry` placeholders were found"

        return Outcome(
            verdict="SUPPORTED",
            reason=(
                f"Lean build succeeded ({build_cmd!r}, exit 0) and "
                f"{proof_note}{theorem_note}."
            ),
            evidence={**evidence, "verdict_basis": "successful build + sorry scan"},
        )


#: Convenience instance for registry code that expects a checker object.
CHECKER = Lean4Checker()
