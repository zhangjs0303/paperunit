"""Tests for paperunit.checkers.statistics.

Most tests use a fake runner that returns constructed ``RunResult`` objects, so
the checker logic is tested without spawning subprocesses.  One end-to-end test
runs the real ``examples/stats_claim`` audit through ``run_command``.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from paperunit.checkers.base import CheckContext, RunResult, run_command
from paperunit.checkers.statistics import StatisticsChecker

FIXTURE_VALUES = (0.916, 0.920, 0.914, 0.922, 0.914, 0.922)
# Two demo claims S1 (REFUTED) and S2 (SUPPORTED) live in this fixture audit.
EXAMPLE_AUDIT = (
    Path(__file__).resolve().parents[1] / "examples" / "stats_claim" / "audit.json"
)


def make_run(
    stdout: str = "",
    *,
    exit_code: int | None = 0,
    timed_out: bool = False,
    stderr: str = "",
    cmd: str = "cmd",
    cwd: str = ".",
    timeout_s: float = 10.0,
) -> RunResult:
    return RunResult(
        cmd=cmd,
        cwd=cwd,
        timeout_s=timeout_s,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_s=0.01,
        stdout=stdout,
        stderr=stderr,
    )


def make_spec(
    *,
    claimed: float = 0.923,
    margin: float = 0.002,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4, 5),
    **overrides: object,
) -> dict:
    spec: dict = {
        "runs_cmd": "python3 code/train.py --seed {seed}",
        "seeds": list(seeds),
        "metric_regex": r"accuracy=(?P<value>[0-9.]+)",
        "claim": {"type": "mean", "value": claimed, "equivalence_margin": margin},
        "confidence": 0.95,
        "method": "bootstrap",
        "resamples": 500,
        "rng_seed": 0,
        "timeout_s": 30,
    }
    spec.update(overrides)
    return spec


def make_claim(spec: dict | None, *, preregistered: bool = True) -> dict:
    return {
        "id": "S1",
        "text": "test statistics claim",
        "kind": "statistics",
        "preregistered": preregistered,
        "check": spec,
    }


def make_ctx(
    spec: dict | None,
    runner,
    *,
    audit_dir: Path | str = ".",
    preregistered: bool = True,
    policy: dict | None = None,
) -> CheckContext:
    claim = make_claim(spec, preregistered=preregistered)
    audit = {"schema": "paperunit/v1", "target": {}, "claims": [claim]}
    return CheckContext(
        claim=claim,
        audit=audit,
        audit_dir=Path(audit_dir),
        runner=runner,
        policy=dict(policy or {}),
    )


def fixture_runner(
    values: tuple[float, ...] = FIXTURE_VALUES,
    *,
    calls: list[dict] | None = None,
    overrides: dict | None = None,
):
    """Fake runner: emits ``accuracy=<value>`` for the seed found in the command."""

    def runner(cmd: str, cwd: Path, timeout_s: float) -> RunResult:
        if calls is not None:
            calls.append({"cmd": cmd, "cwd": cwd, "timeout_s": timeout_s})
        seed = int(re.search(r"--seed (\d+)", cmd).group(1))
        if overrides is not None and seed in overrides:
            factory = overrides[seed]
            return factory(cmd, cwd, timeout_s)
        value = values[seed % len(values)]
        return make_run(
            f"accuracy={value:.4f}\n",
            cmd=cmd,
            cwd=str(cwd),
            timeout_s=timeout_s,
        )

    return runner


def collect_keys(obj, prefix: str = ""):
    """Yield every dict key in a nested evidence payload."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from collect_keys(value, f"{prefix}/{key}")
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from collect_keys(item, prefix)


class SuccessPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checker = StatisticsChecker()

    def test_supported_when_observed_mean_is_inside_margin(self):
        spec = make_spec(claimed=0.918, margin=0.01)
        outcome = self.checker.check(make_ctx(spec, fixture_runner()))
        self.assertEqual(outcome.verdict, "SUPPORTED", outcome.reason)
        self.assertEqual(outcome.evidence["values"], [
            {"seed": seed, "value": value}
            for seed, value in enumerate(FIXTURE_VALUES)
        ])
        self.assertEqual(outcome.uncertainty["n"], 6)
        self.assertAlmostEqual(outcome.uncertainty["mean"], 0.918, places=12)
        self.assertAlmostEqual(outcome.uncertainty["effect"], 0.0, places=12)

    def test_refuted_when_gap_exceeds_margin_and_interval_excludes_claim(self):
        outcome = self.checker.check(make_ctx(make_spec(), fixture_runner()))
        self.assertEqual(outcome.verdict, "REFUTED", outcome.reason)
        self.assertIn("0.923", outcome.reason)
        self.assertIn("MDE", outcome.reason)
        uncertainty = outcome.uncertainty
        self.assertLess(uncertainty["ci_high"], 0.923)
        self.assertAlmostEqual(uncertainty["effect"], -0.005, places=12)
        resolution = outcome.evidence["resolution"]
        self.assertTrue(resolution["ci_excludes_claimed"])
        self.assertAlmostEqual(resolution["observed_gap"], 0.005, places=12)
        self.assertTrue(resolution["mde_exceeds_margin"])
        self.assertTrue(resolution["observed_gap_exceeds_mde"])
        self.assertAlmostEqual(
            resolution["min_detectable_effect"], uncertainty["min_detectable_effect"]
        )

    def test_evidence_records_every_run_with_a_hash(self):
        outcome = self.checker.check(make_ctx(make_spec(), fixture_runner()))
        runs = outcome.evidence["runs"]
        self.assertEqual(len(runs), 6)
        self.assertEqual([run["seed"] for run in runs], [0, 1, 2, 3, 4, 5])
        for run in runs:
            self.assertEqual(run["exit_code"], 0)
            self.assertFalse(run["timed_out"])
            self.assertRegex(run["evidence_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(run["stdout_sha256"], r"^[0-9a-f]{64}$")
        # Outcome already canonicalises evidence through JSON; this also proves
        # the payload can be stored in an audit report.
        json.dumps(outcome.evidence)

    def test_uncertainty_contract(self):
        outcome = self.checker.check(make_ctx(make_spec(), fixture_runner()))
        uncertainty = outcome.uncertainty
        for key in (
            "n",
            "mean",
            "sd",
            "se",
            "ci_low",
            "ci_high",
            "ci_half_width",
            "method",
            "confidence",
            "resamples",
            "seed",
            "values_sha256",
            "min_detectable_effect",
            "effect",
        ):
            self.assertIn(key, uncertainty)
        self.assertEqual(uncertainty["n"], 6)
        self.assertEqual(uncertainty["method"], "bootstrap")
        self.assertEqual(uncertainty["confidence"], 0.95)
        self.assertIsNotNone(uncertainty["min_detectable_effect"])
        self.assertEqual(len(uncertainty["values_sha256"]), 64)
        # effect is the signed gap mean - claimed, not a score.
        self.assertAlmostEqual(
            uncertainty["effect"],
            uncertainty["mean"] - uncertainty["claimed_value"],
            places=15,
        )

    def test_no_score_or_ranking_keys(self):
        forbidden = {"score", "scores", "rank", "ranking", "leaderboard"}
        outcome = self.checker.check(make_ctx(make_spec(), fixture_runner()))
        keys = {key.lower() for key in collect_keys(outcome.evidence)}
        keys |= {key.lower() for key in collect_keys(outcome.uncertainty)}
        self.assertEqual(forbidden & keys, set())

    def test_checker_is_deterministic(self):
        first = self.checker.check(make_ctx(make_spec(), fixture_runner()))
        second = self.checker.check(make_ctx(make_spec(), fixture_runner()))
        self.assertEqual(first, second)

    def test_t_method_interval(self):
        spec = make_spec(method="t")
        outcome = self.checker.check(make_ctx(spec, fixture_runner()))
        self.assertEqual(outcome.verdict, "REFUTED", outcome.reason)
        uncertainty = outcome.uncertainty
        self.assertEqual(uncertainty["ci_method"], "t_interval_table")
        self.assertIsNone(uncertainty["resamples"])
        self.assertIsNone(uncertainty["seed"])
        self.assertLess(uncertainty["ci_high"], 0.923)

    def test_single_seed_is_tolerance_match_only(self):
        spec = make_spec(claimed=0.918, margin=0.01, seeds=(7,))
        outcome = self.checker.check(make_ctx(spec, fixture_runner()))
        self.assertEqual(outcome.verdict, "SUPPORTED", outcome.reason)
        self.assertEqual(outcome.evidence["values"], [{"seed": 7, "value": 0.920}])
        self.assertEqual(outcome.uncertainty["n"], 1)
        self.assertIsNone(outcome.uncertainty["ci_low"])
        self.assertIsNone(outcome.uncertainty["min_detectable_effect"])
        self.assertIsNone(outcome.evidence["resolution"]["min_detectable_effect"])

    def test_single_seed_outside_margin_is_inconclusive(self):
        spec = make_spec(claimed=0.918, margin=0.002, seeds=(7,))
        outcome = self.checker.check(make_ctx(spec, fixture_runner()))
        self.assertEqual(outcome.verdict, "INCONCLUSIVE", outcome.reason)
        self.assertIn("more seeds", outcome.reason)

    def test_preregistered_flag_is_echoed(self):
        spec = make_spec()
        outcome = self.checker.check(
            make_ctx(spec, fixture_runner(), preregistered=False)
        )
        self.assertFalse(outcome.evidence["preregistered"])

    def test_runs_use_seed_substitution_cwd_and_timeout(self):
        calls: list[dict] = []
        spec = make_spec(timeout_s=17)
        outcome = self.checker.check(
            make_ctx(spec, fixture_runner(calls=calls), audit_dir="/tmp/audit-dir")
        )
        self.assertEqual(outcome.verdict, "REFUTED", outcome.reason)
        self.assertEqual(
            [call["cmd"] for call in calls],
            [
                f"python3 code/train.py --seed {seed}"
                for seed in range(6)
            ],
        )
        self.assertTrue(all(call["cwd"] == Path("/tmp/audit-dir") for call in calls))
        self.assertTrue(all(call["timeout_s"] == 17.0 for call in calls))
        self.assertEqual(outcome.evidence["runs"][0]["cwd"], "/tmp/audit-dir")

    def test_policy_timeout_is_used_when_check_does_not_specify_one(self):
        calls: list[dict] = []
        spec = make_spec()
        del spec["timeout_s"]
        self.checker.check(
            make_ctx(
                spec,
                fixture_runner(calls=calls),
                policy={"timeout_s": 12.5},
            )
        )
        self.assertTrue(all(call["timeout_s"] == 12.5 for call in calls))

    def test_custom_metric_regex_capture_group_is_used(self):
        calls: list[dict] = []
        spec = make_spec(metric_regex=r"final_acc:(?P<value>[0-9.]+)%")

        def runner(cmd: str, cwd: Path, timeout_s: float) -> RunResult:
            calls.append({"cmd": cmd, "cwd": cwd, "timeout_s": timeout_s})
            seed = int(re.search(r"--seed (\d+)", cmd).group(1))
            return make_run(f"final_acc:{FIXTURE_VALUES[seed] * 100:.1f}%\n")

        outcome = self.checker.check(make_ctx(spec, runner))
        # Values are now percentages, so they land far outside the claim: the
        # claim is still judged on the parsed metric, whatever its scale.
        self.assertEqual(len(outcome.evidence["runs"]), 6)
        self.assertEqual(outcome.uncertainty["n"], 6)
        self.assertIsNotNone(outcome.verdict)


class FailurePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checker = StatisticsChecker()

    def test_timeout_is_inconclusive_and_records_runs_so_far(self):
        def timeout_factory(cmd, cwd, timeout_s):
            return make_run(
                "", cmd=cmd, cwd=str(cwd), timeout_s=timeout_s,
                exit_code=None, timed_out=True,
            )

        outcome = self.checker.check(
            make_ctx(make_spec(), fixture_runner(overrides={2: timeout_factory}))
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("timed out", outcome.reason)
        self.assertIsNone(outcome.uncertainty)
        evidence = outcome.evidence
        self.assertEqual(evidence["failed_seed"], 2)
        self.assertEqual(evidence["failure"]["kind"], "timeout")
        self.assertEqual(len(evidence["runs"]), 3)
        self.assertTrue(evidence["runs"][2]["timed_out"])
        self.assertEqual(len(evidence["runs"][2]["evidence_sha256"]), 64)
        self.assertEqual(evidence["seeds_not_run"], [3, 4, 5])

    def test_nonzero_exit_is_inconclusive(self):
        def failed_factory(cmd, cwd, timeout_s):
            return make_run(
                "", cmd=cmd, cwd=str(cwd), timeout_s=timeout_s,
                exit_code=5, stderr="Traceback: boom",
            )

        outcome = self.checker.check(
            make_ctx(make_spec(), fixture_runner(overrides={1: failed_factory}))
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("exited with code 5", outcome.reason)
        self.assertEqual(outcome.evidence["failure"]["kind"], "nonzero_exit")
        self.assertIn("boom", outcome.evidence["failure"]["stderr_excerpt"])

    def test_missing_metric_is_inconclusive(self):
        def unparsed_factory(cmd, cwd, timeout_s):
            return make_run("loss=0.123\n", cmd=cmd, cwd=str(cwd), timeout_s=timeout_s)

        outcome = self.checker.check(
            make_ctx(make_spec(), fixture_runner(overrides={0: unparsed_factory}))
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertEqual(outcome.evidence["failure"]["kind"], "metric_parse_error")
        self.assertIn("did not match stdout", outcome.reason)
        self.assertEqual(outcome.evidence["runs"][0]["stdout_excerpt"], "loss=0.123\n")

    def test_non_numeric_metric_is_inconclusive(self):
        spec = make_spec(metric_regex=r"accuracy=(?P<value>\w+)")

        def word_factory(cmd, cwd, timeout_s):
            return make_run("accuracy=high\n", cmd=cmd, cwd=str(cwd), timeout_s=timeout_s)

        outcome = self.checker.check(
            make_ctx(spec, fixture_runner(overrides={0: word_factory}))
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertEqual(outcome.evidence["failure"]["kind"], "metric_parse_error")
        self.assertIn("not a number", outcome.reason)

    def test_runner_exception_is_inconclusive(self):
        def raising_runner(cmd, cwd, timeout_s):
            raise RuntimeError("toolchain disappeared")

        outcome = self.checker.check(make_ctx(make_spec(), raising_runner))
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("RuntimeError", outcome.reason)
        self.assertEqual(outcome.evidence["failure"]["kind"], "runner_error")
        self.assertEqual(outcome.evidence["seeds_not_run"], [1, 2, 3, 4, 5])

    def test_runner_returning_wrong_type_is_inconclusive(self):
        outcome = self.checker.check(
            make_ctx(make_spec(), lambda cmd, cwd, timeout_s: "not a RunResult")
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertEqual(outcome.evidence["failure"]["kind"], "runner_error")
        self.assertIn("RunResult", outcome.reason)

    def test_exception_paths_never_raise(self):
        def raising_runner(cmd, cwd, timeout_s):
            raise ValueError("bad")

        for spec in (
            make_spec(),
            make_spec(seeds=(0,)),
        ):
            with self.subTest(seeds=spec["seeds"]):
                outcome = self.checker.check(make_ctx(spec, raising_runner))
                self.assertEqual(outcome.verdict, "INCONCLUSIVE")


class MalformedSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.checker = StatisticsChecker()

    def _assert_malformed(self, spec: dict | None, *, reason_fragment: str = ""):
        calls: list[dict] = []
        outcome = self.checker.check(
            make_ctx(spec, fixture_runner(calls=calls))
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("spec_error", outcome.evidence)
        self.assertEqual(calls, [], "malformed specs must not run commands")
        if reason_fragment:
            self.assertIn(reason_fragment, outcome.reason)
        return outcome

    def test_missing_check_object(self):
        outcome = self._assert_malformed(None)
        self.assertIn("check", outcome.reason)

    def test_missing_or_empty_runs_cmd(self):
        spec = make_spec()
        del spec["runs_cmd"]
        self._assert_malformed(spec)
        self._assert_malformed(make_spec(runs_cmd=""))

    def test_bad_seeds(self):
        self._assert_malformed(make_spec(seeds=()))
        spec = make_spec()
        spec["seeds"] = 6
        self._assert_malformed(spec)
        spec = make_spec()
        spec["seeds"] = [0, 1.5]
        self._assert_malformed(spec)

    def test_bad_metric_regex(self):
        self._assert_malformed(make_spec(metric_regex="("))
        self._assert_malformed(make_spec(metric_regex=r"accuracy=[0-9.]+"))

    def test_bad_claim_object(self):
        spec = make_spec()
        spec["claim"] = None
        self._assert_malformed(spec)
        spec = make_spec()
        spec["claim"] = {"type": "median", "value": 0.9, "equivalence_margin": 0.01}
        self._assert_malformed(spec, reason_fragment="median")
        spec = make_spec()
        spec["claim"] = {"type": "mean", "equivalence_margin": 0.01}
        self._assert_malformed(spec, reason_fragment="value")
        self._assert_malformed(make_spec(margin=-0.01))
        spec = make_spec()
        spec["claim"]["value"] = "not a number"
        self._assert_malformed(spec)

    def test_bad_statistics_options(self):
        self._assert_malformed(make_spec(confidence=1.5))
        self._assert_malformed(make_spec(confidence="high"))
        self._assert_malformed(make_spec(method="bayes"))
        self._assert_malformed(make_spec(resamples=0))
        self._assert_malformed(make_spec(rng_seed="seed"))
        self._assert_malformed(make_spec(timeout_s=0))

    def test_bad_policy_timeout_is_failure_not_crash(self):
        spec = make_spec()
        del spec["timeout_s"]
        outcome = self.checker.check(
            make_ctx(spec, fixture_runner(), policy={"timeout_s": "not-a-number"})
        )
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("spec_error", outcome.evidence)


@unittest.skipUnless(EXAMPLE_AUDIT.exists(), "examples/stats_claim/audit.json missing")
class ExampleAuditEndToEndTests(unittest.TestCase):
    """Runs the real fixture audit through real subprocesses (a few tenths of a second)."""

    def setUp(self) -> None:
        self.checker = StatisticsChecker()
        self.audit_path = EXAMPLE_AUDIT
        self.audit = json.loads(self.audit_path.read_text(encoding="utf-8"))
        self.audit_dir = self.audit_path.parent
        self.claims = {claim["id"]: claim for claim in self.audit["claims"]}

    def _check(self, claim_id: str):
        claim = self.claims[claim_id]
        ctx = CheckContext(
            claim=claim,
            audit=self.audit,
            audit_dir=self.audit_dir,
            runner=run_command,
            policy={"timeout_s": 60.0},
        )
        return self.checker.check(ctx)

    def test_s1_is_refuted_and_s2_is_supported(self):
        s1 = self._check("S1")
        s2 = self._check("S2")
        self.assertEqual(s1.verdict, "REFUTED", s1.reason)
        self.assertEqual(s2.verdict, "SUPPORTED", s2.reason)
        self.assertIn("0.923", s1.reason)
        self.assertIn("0.918", s2.reason)

    def test_fixture_accuracy_is_deterministic_with_expected_resolution(self):
        s1 = self._check("S1")
        values = [row["value"] for row in s1.evidence["values"]]
        self.assertEqual(len(values), 6)
        mean = sum(values) / len(values)
        sd = (sum((value - mean) ** 2 for value in values) / (len(values) - 1)) ** 0.5
        self.assertAlmostEqual(mean, 0.918, places=9)
        self.assertGreater(sd, 0.002)
        self.assertLess(sd, 0.006)
        # The fixture's resolution is coarser than S1's margin, yet the
        # observed gap is above the noise floor.  That is the demo's point.
        resolution = s1.evidence["resolution"]
        self.assertTrue(resolution["mde_exceeds_margin"])
        self.assertTrue(resolution["observed_gap_exceeds_mde"])
        self.assertIsNotNone(s1.uncertainty)
        self.assertAlmostEqual(s1.uncertainty["mean"], 0.918, places=9)

    def test_fixture_runs_execute_from_audit_directory(self):
        s1 = self._check("S1")
        runs = s1.evidence["runs"]
        self.assertEqual(len(runs), 6)
        for run in runs:
            self.assertEqual(run["exit_code"], 0)
            self.assertFalse(run["timed_out"])
            self.assertEqual(len(run["evidence_sha256"]), 64)
            self.assertEqual(Path(run["cwd"]), self.audit_dir)


if __name__ == "__main__":
    unittest.main()
