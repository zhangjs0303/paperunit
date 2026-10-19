"""Tests for the formal / semi-formal checkers and their example audits.

Covered here:

* ``paperunit.checkers.external`` - protocol parsing and the trust rules
  (non-zero exit and timeouts are INCONCLUSIVE, missing tool is not a refutation).
* ``paperunit.checkers.lean4`` - toolchain probing, build outcomes, ``sorry``
  scanning, and informational theorem recording.
* shipped examples - causal-mask prefix invariance (SUPPORTED / REFUTED), the
  Lean demo's toolchain-missing INCONCLUSIVE path, and the z3 demo's
  INCONCLUSIVE-without-z3 path plus real symbolic verdicts when z3 is installed.

Checker tests use an injected fake runner and never touch subprocesses.  The
example tests execute the demo scripts for real (stdlib only, fast, deterministic).

Run from the ``paperunit/`` directory::

    python3 -m unittest discover -s tests -p "test_formal.py" -v
"""

from __future__ import annotations

import importlib.util
import json
import shlex
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from paperunit.checkers.base import CheckContext, RunResult, run_command  # noqa: E402
from paperunit.checkers.external import ExternalChecker  # noqa: E402
from paperunit.checkers.lean4 import (  # noqa: E402
    Lean4Checker,
    find_sorry,
    find_theorem,
)

EXAMPLES_DIR = PROJECT_ROOT / "examples"
FORMAL_EXAMPLES = ("causal_mask", "lean_demo", "z3_demo")
HAVE_Z3 = importlib.util.find_spec("z3") is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_result(
    cmd: str,
    cwd: Path | str,
    *,
    exit_code: int | None = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    timeout_s: float = 60.0,
    duration_s: float = 0.01,
) -> RunResult:
    """Build a RunResult without spawning a process."""
    return RunResult(
        cmd=cmd,
        cwd=str(cwd),
        timeout_s=timeout_s,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_s=duration_s,
        stdout=stdout,
        stderr=stderr,
    )


class FakeRunner:
    """Runner stub that records calls and dispatches on the command string."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[tuple[str, Path, float]] = []

    def __call__(self, cmd: str, cwd: Path, timeout_s: float) -> RunResult:
        cwd = Path(cwd)
        self.calls.append((cmd, cwd, timeout_s))
        return self.handler(cmd, cwd, timeout_s)

    @property
    def commands(self) -> list[str]:
        return [cmd for cmd, _cwd, _timeout in self.calls]


def make_context(
    claim: dict,
    runner,
    audit_dir: Path | str,
    policy: dict | None = None,
) -> CheckContext:
    audit_dir = Path(audit_dir)
    audit = {"schema": "paperunit/v1", "claims": [claim]}
    return CheckContext(
        claim=claim,
        audit=audit,
        audit_dir=audit_dir,
        runner=runner,
        policy=policy or {},
    )


def external_claim(cmd: str = "python3 code/check.py", **check_extra) -> dict:
    check: dict = {"cmd": cmd}
    check.update(check_extra)
    return {"id": "P1", "text": "external claim", "kind": "external", "check": check}


def json_stdout(payload: dict) -> str:
    """Log lines first, verdict JSON as the last non-empty stdout line."""
    return "starting external check\n" + json.dumps(payload, sort_keys=True) + "\n\n"


def last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""


def load_audit(example: str) -> dict:
    path = EXAMPLES_DIR / example / "audit.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# external checker
# ---------------------------------------------------------------------------


class ExternalCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audit_dir = Path(self.tmp.name)
        self.checker = ExternalChecker()

    def _check(self, stdout: str = "", **kwargs) -> tuple:
        claim = kwargs.pop("claim", None) or external_claim()
        exit_code = kwargs.pop("exit_code", 0)
        timed_out = kwargs.pop("timed_out", False)
        policy = kwargs.pop("policy", None)
        self.assertFalse(kwargs, f"unused kwargs: {kwargs}")
        runner = FakeRunner(
            lambda cmd, cwd, timeout_s: make_result(
                cmd,
                cwd,
                exit_code=exit_code,
                stdout=stdout,
                timed_out=timed_out,
            )
        )
        outcome = self.checker.check(
            make_context(claim, runner, self.audit_dir, policy=policy)
        )
        return outcome, runner

    def test_kind_attribute(self) -> None:
        self.assertEqual(self.checker.kind, "external")

    def test_supported_verdict_passed_through(self) -> None:
        payload = {
            "verdict": "SUPPORTED",
            "reason": "property holds for the encoded cases",
            "uncertainty": None,
            "evidence": {"cases": 12},
        }
        outcome, _ = self._check(json_stdout(payload))
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(outcome.reason, "property holds for the encoded cases")
        self.assertEqual(outcome.evidence["parsed"]["evidence"]["cases"], 12)
        self.assertIn("run", outcome.evidence)
        self.assertEqual(outcome.evidence["run"]["exit_code"], 0)
        self.assertIsNone(outcome.uncertainty)

    def test_refuted_verdict_keeps_counterexample_evidence(self) -> None:
        payload = {
            "verdict": "REFUTED",
            "reason": "z3 found a counterexample",
            "uncertainty": {"assurance": "symbolic"},
            "evidence": {"counterexample": {"i": 0, "j": 1}},
        }
        outcome, _ = self._check(json_stdout(payload))
        self.assertEqual(outcome.verdict, "REFUTED")
        self.assertEqual(
            outcome.evidence["parsed"]["evidence"]["counterexample"],
            {"i": 0, "j": 1},
        )
        self.assertEqual(outcome.uncertainty, {"assurance": "symbolic"})

    def test_uses_last_nonempty_stdout_line(self) -> None:
        payload = {"verdict": "SUPPORTED", "reason": "ok", "evidence": {}}
        stdout = "log line 1\nlog line 2\n" + json.dumps(payload) + "\n\n   \n"
        outcome, _ = self._check(stdout)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(outcome.reason, "ok")

    def test_invalid_json_is_inconclusive(self) -> None:
        outcome, _ = self._check("this is not json\n")
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("JSON", outcome.evidence["parse_error"])
        self.assertIn("no readable verdict", outcome.reason)

    def test_empty_stdout_is_inconclusive(self) -> None:
        outcome, _ = self._check("")
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("parse_error", outcome.evidence)

    def test_non_object_json_is_inconclusive(self) -> None:
        outcome, _ = self._check("[1, 2, 3]\n")
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("JSON object", outcome.evidence["parse_error"])

    def test_invalid_verdict_is_inconclusive(self) -> None:
        payload = {"verdict": "MAYBE", "reason": "unsure", "evidence": {}}
        outcome, _ = self._check(json_stdout(payload))
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("invalid verdict", outcome.reason)

    def test_not_run_verdict_is_rejected(self) -> None:
        payload = {"verdict": "NOT_RUN", "reason": "not executable", "evidence": {}}
        outcome, _ = self._check(json_stdout(payload))
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("invalid verdict", outcome.reason)

    def test_missing_reason_is_inconclusive(self) -> None:
        payload = {"verdict": "SUPPORTED", "evidence": {}}
        outcome, _ = self._check(json_stdout(payload))
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("reason", outcome.reason)

    def test_nonzero_exit_is_inconclusive_even_with_valid_json(self) -> None:
        payload = {"verdict": "SUPPORTED", "reason": "ok", "evidence": {}}
        outcome, _ = self._check(json_stdout(payload), exit_code=1)
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("exited with code 1", outcome.reason)
        self.assertIn("stderr_excerpt", outcome.evidence)

    def test_timeout_is_inconclusive(self) -> None:
        outcome, _ = self._check("", timed_out=True)
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("timed out", outcome.reason)
        self.assertTrue(outcome.evidence["run"]["timed_out"])

    def test_missing_cmd_is_inconclusive_without_runner_call(self) -> None:
        claim = {"id": "P1", "kind": "external", "text": "no command", "check": {}}
        runner = FakeRunner(
            lambda cmd, cwd, timeout_s: self.fail("runner must not be called")
        )
        outcome = self.checker.check(
            make_context(claim, runner, self.audit_dir)
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("check.cmd", outcome.reason)
        self.assertEqual(runner.calls, [])

    def test_claim_timeout_is_forwarded(self) -> None:
        payload = {"verdict": "SUPPORTED", "reason": "ok", "evidence": {}}
        claim = external_claim(timeout_s=3.5)
        outcome, runner = self._check(json_stdout(payload), claim=claim)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(runner.calls[0][2], 3.5)

    def test_policy_timeout_is_used_as_default(self) -> None:
        payload = {"verdict": "SUPPORTED", "reason": "ok", "evidence": {}}
        outcome, runner = self._check(
            json_stdout(payload), policy={"timeout_s": 17}
        )
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(runner.calls[0][2], 17.0)

    def test_check_cwd_is_respected(self) -> None:
        payload = {"verdict": "SUPPORTED", "reason": "ok", "evidence": {}}
        claim = external_claim(cwd="sub/check")
        outcome, runner = self._check(json_stdout(payload), claim=claim)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(runner.calls[0][1], (self.audit_dir / "sub/check").resolve())


# ---------------------------------------------------------------------------
# lean4 checker
# ---------------------------------------------------------------------------


class Lean4CheckerTests(unittest.TestCase):
    CLEAN_LEAN = (
        "theorem good : 1 + 1 = 2 := rfl\n"
        "theorem add_comm_demo (a b : Nat) : a + b = b + a := Nat.add_comm a b\n"
    )

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audit_dir = Path(self.tmp.name)
        self.project = self.audit_dir / "lean_project"
        self.project.mkdir()
        self.checker = Lean4Checker()

    # -- helpers ----------------------------------------------------------

    def _write(self, rel: str, text: str) -> Path:
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _claim(self, **check) -> dict:
        spec: dict = {"project_dir": "lean_project"}
        spec.update(check)
        return {"id": "L1", "text": "lean claim", "kind": "lean4", "check": spec}

    def _runner(
        self,
        *,
        lean_present: bool = True,
        fallback_lake: bool = False,
        probe_timed_out: bool = False,
        build: dict | None = None,
    ) -> FakeRunner:
        """Fake runner with configurable toolchain probe and build result."""
        build = dict(build or {})
        build.setdefault("exit_code", 0)
        build.setdefault("stdout", "Build completed successfully.\n")
        build.setdefault("stderr", "")
        build.setdefault("timed_out", False)

        def handler(cmd: str, cwd: Path, timeout_s: float) -> RunResult:
            if cmd.startswith("lean --version"):
                ok = lean_present and not fallback_lake
                code = 0 if ok else (None if probe_timed_out else 127)
                return make_result(
                    cmd,
                    cwd,
                    exit_code=code,
                    stdout="Lean (version 4.9.0)\n" if ok else "",
                    stderr="" if ok else "/bin/sh: lean: command not found\n",
                    timed_out=probe_timed_out,
                )
            if cmd.startswith("lake --version"):
                ok = lean_present
                code = 0 if ok else (None if probe_timed_out else 127)
                return make_result(
                    cmd,
                    cwd,
                    exit_code=code,
                    stdout="Lake version 4.9.0\n" if ok else "",
                    stderr="" if ok else "/bin/sh: lake: command not found\n",
                    timed_out=probe_timed_out,
                )
            return make_result(
                cmd,
                cwd,
                exit_code=build["exit_code"],
                stdout=build["stdout"],
                stderr=build["stderr"],
                timed_out=build["timed_out"],
            )

        return FakeRunner(handler)

    def _check(self, claim: dict | None = None, runner: FakeRunner | None = None, **kwargs) -> tuple:
        claim = claim or self._claim()
        runner = runner or self._runner(**kwargs)
        outcome = self.checker.check(make_context(claim, runner, self.audit_dir))
        return outcome, runner

    # -- toolchain probing ------------------------------------------------

    def test_kind_attribute(self) -> None:
        self.assertEqual(self.checker.kind, "lean4")

    def test_missing_toolchain_is_inconclusive(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        outcome, runner = self._check(lean_present=False)
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("Lean toolchain not found", outcome.reason)
        self.assertEqual(
            runner.commands, ["lean --version", "lake --version"]
        )
        self.assertEqual(len(outcome.evidence["toolchain"]["probes"]), 2)
        self.assertIsNone(outcome.evidence["toolchain"]["available_cmd"])
        self.assertNotIn("run", outcome.evidence)

    def test_probe_timeout_is_treated_as_missing(self) -> None:
        outcome, runner = self._check(lean_present=False, probe_timed_out=True)
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("Lean toolchain not found", outcome.reason)
        self.assertTrue(
            outcome.evidence["toolchain"]["probes"][0]["run"]["timed_out"]
        )
        self.assertEqual(runner.commands, ["lean --version", "lake --version"])

    def test_lake_fallback_probe(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        outcome, runner = self._check(lean_present=True, fallback_lake=True)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(
            runner.commands, ["lean --version", "lake --version", "lake build"]
        )
        self.assertEqual(
            outcome.evidence["toolchain"]["available_cmd"], "lake --version"
        )

    def test_probes_run_in_project_dir(self) -> None:
        outcome, runner = self._check(lean_present=False)
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertEqual(runner.calls[0][1], self.project.resolve())

    def test_missing_project_dir_is_inconclusive(self) -> None:
        claim = self._claim(project_dir="does_not_exist")
        outcome, runner = self._check(claim=claim)
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("project directory not found", outcome.reason)
        self.assertNotIn("lake build", runner.commands)

    # -- build outcomes ---------------------------------------------------

    def test_build_success_is_supported(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        outcome, runner = self._check()
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertIn("no `sorry` placeholders", outcome.reason)
        self.assertEqual(outcome.evidence["run"]["exit_code"], 0)
        self.assertEqual(outcome.evidence["build_cmd"], "lake build")
        self.assertEqual(outcome.evidence["lean_files"], ["PaperunitDemo.lean"])
        self.assertEqual(outcome.evidence["sorry_locations"], [])
        self.assertFalse(outcome.evidence["allow_sorry"])
        self.assertEqual(runner.commands[-1], "lake build")

    def test_build_failure_is_inconclusive_not_refuted(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        outcome, _ = self._check(
            build={
                "exit_code": 1,
                "stderr": "PaperunitDemo.lean:3:0: error: unknown identifier 'foo'\n",
            }
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertNotEqual(outcome.verdict, "REFUTED")
        self.assertIn("formalisation did not go through", outcome.reason)
        self.assertIn("not evidence against", outcome.reason)
        self.assertIn("unknown identifier", outcome.evidence["stderr_excerpt"])
        self.assertEqual(outcome.evidence["run"]["exit_code"], 1)

    def test_build_timeout_is_inconclusive(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        outcome, _ = self._check(build={"timed_out": True, "exit_code": None})
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("timed out", outcome.reason)
        self.assertIn("not evidence against", outcome.reason)

    def test_build_cmd_defaults_to_lake_build(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        outcome, runner = self._check()
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(runner.commands[-1], "lake build")

    def test_custom_build_cmd_is_used(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        claim = self._claim(build_cmd="lake build PaperunitDemo")
        outcome, runner = self._check(claim=claim)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(runner.commands[-1], "lake build PaperunitDemo")
        self.assertEqual(outcome.evidence["build_cmd"], "lake build PaperunitDemo")

    def test_claim_timeout_is_forwarded_to_build(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        claim = self._claim(build_cmd="lake build", timeout_s=7.5)
        outcome, runner = self._check(claim=claim)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(runner.calls[-1][2], 7.5)

    def test_policy_timeout_is_used_for_build(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        claim = self._claim()
        runner = self._runner()
        outcome = self.checker.check(
            make_context(claim, runner, self.audit_dir, policy={"timeout_s": 90})
        )
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(runner.calls[-1][2], 90.0)

    # -- sorry scanning ---------------------------------------------------

    def test_sorry_is_inconclusive(self) -> None:
        self._write(
            "PaperunitDemo.lean",
            "theorem good : 1 + 1 = 2 := rfl\n"
            "theorem bad : False := by\n"
            "  sorry\n",
        )
        outcome, _ = self._check()
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("proof contains sorry", outcome.reason)
        self.assertEqual(
            outcome.evidence["sorry_locations"],
            [{"file": "PaperunitDemo.lean", "line": 3}],
        )

    def test_sorry_scan_is_recursive(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        self._write("Sub/Extra.lean", "theorem bad : False := by sorry\n")
        outcome, _ = self._check()
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("proof contains sorry", outcome.reason)
        self.assertEqual(
            outcome.evidence["sorry_locations"],
            [{"file": "Sub/Extra.lean", "line": 1}],
        )

    def test_sorry_in_line_comment_is_ignored(self) -> None:
        self._write(
            "PaperunitDemo.lean",
            "-- this is not a proof: sorry\n" + self.CLEAN_LEAN,
        )
        outcome, _ = self._check()
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(outcome.evidence["sorry_locations"], [])

    def test_sorry_in_block_comment_is_ignored(self) -> None:
        self._write(
            "PaperunitDemo.lean",
            "/-\n  theorem fake : False := by sorry\n-/\n" + self.CLEAN_LEAN,
        )
        outcome, _ = self._check()
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(outcome.evidence["sorry_locations"], [])

    def test_sorry_substring_in_names_is_not_matched(self) -> None:
        self._write(
            "PaperunitDemo.lean",
            "def sorry_free : Nat := 0\ndef sorryAx_ish : Nat := 1\n"
            + self.CLEAN_LEAN,
        )
        outcome, _ = self._check()
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(outcome.evidence["sorry_locations"], [])

    def test_allow_sorry_true_is_supported_but_recorded(self) -> None:
        self._write("PaperunitDemo.lean", "theorem bad : False := by sorry\n")
        claim = self._claim(allow_sorry=True)
        outcome, _ = self._check(claim=claim)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertTrue(outcome.evidence["allow_sorry"])
        self.assertTrue(outcome.evidence["sorry_locations"])
        self.assertIn("allowed", outcome.reason)

    # -- optional theorem recording ---------------------------------------

    def test_theorem_found_is_recorded(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        claim = self._claim(theorem="PaperunitDemo.add_comm_demo")
        outcome, _ = self._check(claim=claim)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        check = outcome.evidence["theorem_check"]
        self.assertTrue(check["found"])
        self.assertEqual(check["requested"], "PaperunitDemo.add_comm_demo")
        self.assertEqual(check["files"], ["PaperunitDemo.lean"])

    def test_missing_theorem_is_informational_only(self) -> None:
        self._write("PaperunitDemo.lean", self.CLEAN_LEAN)
        claim = self._claim(theorem="PaperunitDemo.not_there")
        outcome, _ = self._check(claim=claim)
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertFalse(outcome.evidence["theorem_check"]["found"])
        self.assertIn("not found", outcome.reason)

    # -- direct scanner functions -----------------------------------------

    def test_find_sorry_reports_comment_free_locations(self) -> None:
        self._write("A.lean", "theorem a : True := trivial\n")
        self._write("B.lean", "-- sorry\ntheorem b : True := by\n  sorry\n")
        locations = find_sorry(self.project)
        self.assertEqual(locations, [{"file": "B.lean", "line": 3}])

    def test_find_theorem_matches_theorem_and_lemma(self) -> None:
        self._write("A.lean", "theorem my_thm : True := trivial\n")
        self._write("B.lean", "lemma my_other : True := trivial\n")
        self.assertEqual(find_theorem(self.project, "my_thm"), ["A.lean"])
        self.assertEqual(find_theorem(self.project, "my_other"), ["B.lean"])
        self.assertEqual(find_theorem(self.project, "absent"), [])


# ---------------------------------------------------------------------------
# Example audits: fixture integrity
# ---------------------------------------------------------------------------


class AuditFixtureTests(unittest.TestCase):
    def test_all_formal_audits_follow_schema(self) -> None:
        for example in FORMAL_EXAMPLES:
            with self.subTest(example=example):
                audit = load_audit(example)
                self.assertEqual(audit["schema"], "paperunit/v1")
                target = audit["target"]
                for key in ("title", "paper", "audited_by", "date"):
                    self.assertIn(key, target)
                self.assertIn("tested", audit["scope"])
                self.assertIn("not_tested", audit["scope"])
                claims = audit["claims"]
                self.assertTrue(claims)
                ids = [claim["id"] for claim in claims]
                self.assertEqual(len(ids), len(set(ids)))
                for claim in claims:
                    self.assertIn(claim["kind"], {"external", "lean4"})
                    self.assertIsInstance(claim["check"], dict)

    def test_referenced_scripts_and_projects_exist(self) -> None:
        for example in FORMAL_EXAMPLES:
            audit_dir = EXAMPLES_DIR / example
            for claim in load_audit(example)["claims"]:
                with self.subTest(example=example, claim=claim["id"]):
                    if claim["kind"] == "external":
                        parts = shlex.split(claim["check"]["cmd"])
                        self.assertGreaterEqual(len(parts), 2)
                        script = audit_dir / parts[1]
                        self.assertTrue(script.is_file(), f"missing {script}")
                    else:
                        project = audit_dir / claim["check"]["project_dir"]
                        self.assertTrue(project.is_dir(), f"missing {project}")
                        self.assertTrue((project / "lakefile.toml").is_file())

    def test_causal_mask_paper_cites_reference_and_audit_type(self) -> None:
        text = (EXAMPLES_DIR / "causal_mask" / "paper.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("2608.22876", text)
        self.assertIn("测试型审计", text)


# ---------------------------------------------------------------------------
# Example audit: causal mask (test-based, always available)
# ---------------------------------------------------------------------------


class CausalMaskExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit_dir = EXAMPLES_DIR / "causal_mask"
        cls.audit = load_audit("causal_mask")

    def _claim(self, claim_id: str) -> dict:
        return next(claim for claim in self.audit["claims"] if claim["id"] == claim_id)

    def _check(self, claim_id: str):
        ctx = CheckContext(
            claim=self._claim(claim_id),
            audit=self.audit,
            audit_dir=self.audit_dir,
            runner=run_command,
        )
        return ExternalChecker().check(ctx)

    def test_m1_correct_mask_is_supported(self) -> None:
        outcome = self._check("M1")
        self.assertEqual(outcome.verdict, "SUPPORTED")
        parsed = outcome.evidence["parsed"]["evidence"]
        self.assertEqual(parsed["variant"], "causal_ok")
        self.assertEqual(parsed["max_abs_diff"], 0.0)
        self.assertIn("prefix invariance", outcome.reason)
        self.assertIn("2608.22876", parsed["reference"])

    def test_m2_broken_mask_is_refuted_with_counterexample(self) -> None:
        outcome = self._check("M2")
        self.assertEqual(outcome.verdict, "REFUTED")
        parsed = outcome.evidence["parsed"]["evidence"]
        self.assertEqual(parsed["variant"], "causal_broken")
        counterexample = parsed["counterexample"]
        self.assertEqual(counterexample["position"], 0)
        self.assertGreater(counterexample["abs_diff"], 1e-6)
        self.assertEqual(parsed["changed_suffix_positions"], [3, 4, 5])
        self.assertIn("violated", outcome.reason)

    def test_audit_scripts_exit_zero_and_print_json(self) -> None:
        for variant, expected in (
            ("causal_ok", "SUPPORTED"),
            ("causal_broken", "REFUTED"),
        ):
            with self.subTest(variant=variant):
                run = run_command(
                    f"python3 code/audit_mask.py --variant {variant}",
                    self.audit_dir,
                    30.0,
                )
                self.assertEqual(run.exit_code, 0)
                line = last_nonempty_line(run.stdout)
                payload = json.loads(line)
                self.assertEqual(payload["verdict"], expected)
                self.assertIn("audit_type", payload["evidence"])

    def test_audit_script_is_deterministic(self) -> None:
        cmd = "python3 code/audit_mask.py --variant causal_broken"
        first = run_command(cmd, self.audit_dir, 30.0)
        second = run_command(cmd, self.audit_dir, 30.0)
        self.assertEqual(first.exit_code, 0)
        self.assertEqual(first.stdout, second.stdout)


# ---------------------------------------------------------------------------
# Example audit: z3 demo (optional dependency)
# ---------------------------------------------------------------------------


class Z3DemoExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit_dir = EXAMPLES_DIR / "z3_demo"
        cls.audit = load_audit("z3_demo")

    def _claim(self, claim_id: str) -> dict:
        return next(claim for claim in self.audit["claims"] if claim["id"] == claim_id)

    def _check(self, claim_id: str):
        ctx = CheckContext(
            claim=self._claim(claim_id),
            audit=self.audit,
            audit_dir=self.audit_dir,
            runner=run_command,
        )
        return ExternalChecker().check(ctx)

    def test_script_prints_json_and_exits_zero(self) -> None:
        for variant in ("correct", "broken"):
            with self.subTest(variant=variant):
                run = run_command(
                    f"python3 code/check_mask_z3.py --variant {variant}",
                    self.audit_dir,
                    60.0,
                )
                self.assertEqual(run.exit_code, 0)
                payload = json.loads(last_nonempty_line(run.stdout))
                self.assertIn(
                    payload["verdict"],
                    {"SUPPORTED", "REFUTED", "INCONCLUSIVE"},
                )
                self.assertEqual(payload["evidence"]["variant"], variant)

    @unittest.skipIf(HAVE_Z3, "z3-solver is installed; the missing-solver path is not testable")
    def test_without_z3_both_claims_are_inconclusive(self) -> None:
        for claim_id in ("Z1", "Z2"):
            with self.subTest(claim_id=claim_id):
                outcome = self._check(claim_id)
                self.assertEqual(outcome.verdict, "INCONCLUSIVE")
                self.assertIn("z3", outcome.reason)
                parsed = outcome.evidence["parsed"]
                self.assertFalse(parsed["evidence"]["z3_available"])

    @unittest.skipUnless(HAVE_Z3, "z3-solver is not installed; install 'paperunit[z3]' to run")
    def test_with_z3_symbolic_verdicts(self) -> None:
        correct = self._check("Z1")
        self.assertEqual(correct.verdict, "SUPPORTED")
        self.assertEqual(
            correct.evidence["parsed"]["evidence"]["solver_result"], "unsat"
        )
        broken = self._check("Z2")
        self.assertEqual(broken.verdict, "REFUTED")
        evidence = broken.evidence["parsed"]["evidence"]
        self.assertEqual(evidence["solver_result"], "sat")
        counterexample = evidence["counterexample"]
        self.assertLess(counterexample["i"], counterexample["j"])


# ---------------------------------------------------------------------------
# Example audit: Lean demo (toolchain missing in this environment)
# ---------------------------------------------------------------------------


class LeanDemoExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit_dir = EXAMPLES_DIR / "lean_demo"
        cls.audit = load_audit("lean_demo")

    def test_fixture_lake_project_is_present(self) -> None:
        project = self.audit_dir / "lean_project"
        self.assertTrue((project / "lakefile.toml").is_file())
        source = (project / "PaperunitDemo.lean").read_text(encoding="utf-8")
        self.assertIn("theorem add_comm_demo", source)
        self.assertIn("Nat.add_comm", source)
        # The doc comment mentions `sorry` in prose; the scanner must still see
        # no placeholder in the development itself.
        self.assertEqual(find_sorry(project), [])

    def test_claim_requests_no_sorry_and_records_theorem(self) -> None:
        claim = self.audit["claims"][0]
        self.assertEqual(claim["kind"], "lean4")
        self.assertFalse(claim["check"]["allow_sorry"])
        self.assertEqual(
            claim["check"]["theorem"], "PaperunitDemo.add_comm_demo"
        )

    @unittest.skipIf(
        shutil.which("lean") or shutil.which("lake"),
        "a Lean toolchain is installed; the missing-toolchain path is not testable",
    )
    def test_missing_toolchain_path_is_inconclusive(self) -> None:
        claim = self.audit["claims"][0]
        ctx = CheckContext(
            claim=claim,
            audit=self.audit,
            audit_dir=self.audit_dir,
            runner=run_command,
        )
        outcome = Lean4Checker().check(ctx)
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("Lean toolchain not found", outcome.reason)
        probes = outcome.evidence["toolchain"]["probes"]
        self.assertEqual(len(probes), 2)
        self.assertNotIn("run", outcome.evidence)


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class RegistryIntegrationTests(unittest.TestCase):
    def test_formal_checkers_are_registered(self) -> None:
        from paperunit.checkers import get_checker

        self.assertIsInstance(get_checker("lean4"), Lean4Checker)
        self.assertIsInstance(get_checker("external"), ExternalChecker)


if __name__ == "__main__":
    unittest.main()
