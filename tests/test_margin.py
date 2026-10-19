"""Tests for the equivalence-margin policy resolver and its use by statistics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paperunit.margin import (
    MarginError,
    decimal_places,
    paper_precision_margin,
    resolve_margin,
)
from paperunit.checkers.base import CheckContext, RunResult
from paperunit.checkers.statistics import StatisticsChecker

ROOT = Path(__file__).resolve().parents[1]


class DecimalPlacesTests(unittest.TestCase):
    def test_decimal_places(self) -> None:
        self.assertEqual(decimal_places(0.923), 3)
        self.assertEqual(decimal_places(0.918), 3)
        self.assertEqual(decimal_places(0.1), 1)
        self.assertEqual(decimal_places(92.3), 1)
        self.assertEqual(decimal_places(92), 0)
        self.assertEqual(decimal_places(0.0005), 4)

    def test_paper_precision_margin(self) -> None:
        self.assertAlmostEqual(paper_precision_margin(0.923), 0.001)
        self.assertAlmostEqual(paper_precision_margin(0.918), 0.001)
        self.assertAlmostEqual(paper_precision_margin(0.923, factor=2.0), 0.002)
        self.assertAlmostEqual(paper_precision_margin(92), 1.0)

    def test_non_finite_rejected(self) -> None:
        with self.assertRaises(MarginError):
            decimal_places(float("nan"))


class ResolveMarginTests(unittest.TestCase):
    def _check(self, value=0.923, **extra):
        check = {"claim": {"type": "mean", "value": value}}
        check.update(extra)
        return check

    def test_default_is_paper_precision(self) -> None:
        info = resolve_margin(self._check())
        self.assertEqual(info["mode"], "paper_precision")
        self.assertAlmostEqual(info["margin"], 0.001)
        self.assertIn("3 decimal place", info["note"])

    def test_paper_precision_string(self) -> None:
        info = resolve_margin(self._check(equivalence_margin="paper_precision"))
        self.assertAlmostEqual(info["margin"], 0.001)

    def test_margin_factor(self) -> None:
        info = resolve_margin(self._check(margin_factor=2.0))
        self.assertAlmostEqual(info["margin"], 0.002)

    def test_integer_claim_warns_about_coarse_resolution(self) -> None:
        info = resolve_margin(self._check(value=92))
        self.assertAlmostEqual(info["margin"], 1.0)
        self.assertIn("coarse", info["note"])

    def test_explicit_numeric_margin(self) -> None:
        info = resolve_margin(self._check(equivalence_margin=0.002))
        self.assertEqual(info["mode"], "fixed")
        self.assertAlmostEqual(info["margin"], 0.002)

    def test_fixed_object_margin(self) -> None:
        info = resolve_margin(
            self._check(equivalence_margin={"mode": "fixed", "value": 0.003})
        )
        self.assertAlmostEqual(info["margin"], 0.003)

    def test_policy_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "policies" / "margin").mkdir(parents=True)
            policy = {
                "schema": "paperunit/margin-policy/v1",
                "decisions": [
                    {
                        "decision_id": "D-1",
                        "claim_type": "mean",
                        "margin": 0.0007,
                        "rationale": "unit test policy",
                    }
                ],
            }
            (root / "policies" / "margin" / "v1.json").write_text(
                json.dumps(policy), encoding="utf-8"
            )
            info = resolve_margin(
                self._check(
                    equivalence_margin={
                        "mode": "policy_ref",
                        "path": "policies/margin/v1.json",
                        "decision_id": "D-1",
                    }
                ),
                base_dir=root,
            )
            self.assertEqual(info["mode"], "policy_ref")
            self.assertAlmostEqual(info["margin"], 0.0007)
            self.assertEqual(info["decision_id"], "D-1")
            self.assertEqual(info["source"], "policies/margin/v1.json")
            self.assertIn("unit test policy", info["note"])

    def test_missing_policy_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(MarginError):
                resolve_margin(
                    self._check(
                        equivalence_margin={"mode": "policy_ref", "path": "nope.json"}
                    ),
                    base_dir=Path(tmp),
                )

    def test_unknown_mode_raises(self) -> None:
        with self.assertRaises(MarginError):
            resolve_margin(self._check(equivalence_margin={"mode": "magic"}))

    def test_default_without_value_raises(self) -> None:
        with self.assertRaises(MarginError):
            resolve_margin({"claim": {"type": "mean"}})


class StatisticsMarginIntegrationTests(unittest.TestCase):
    def _audit(self) -> dict:
        return {"schema": "paperunit/v1", "target": {"title": "t", "audited_by": "a", "date": "2026-10-19"}}

    def _context(self, check: dict) -> CheckContext:
        return CheckContext(
            claim={"id": "S1", "kind": "statistics", "check": check},
            audit=self._audit(),
            audit_dir=ROOT,
            runner=self._runner,
            policy={},
        )

    def _runner(self, cmd: str, cwd: Path, timeout_s: float) -> RunResult:
        return RunResult(cmd, str(cwd), timeout_s, 0, False, 0.01, "accuracy=0.918\n", "")

    def _check(self, **claim_extra) -> dict:
        return {
            "runs_cmd": "run {seed}",
            "seeds": [0, 1, 2, 3, 4, 5],
            "metric_regex": r"accuracy=(?P<value>[0-9.]+)",
            "claim": {"type": "mean", "value": 0.918, **claim_extra},
            "confidence": 0.95,
            "method": "bootstrap",
            "resamples": 300,
            "rng_seed": 0,
        }

    def test_default_paper_precision_in_evidence(self) -> None:
        outcome = StatisticsChecker().check(self._context(self._check()))
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(outcome.evidence["resolution"]["margin_mode"], "paper_precision")
        self.assertAlmostEqual(outcome.uncertainty["equivalence_margin"], 0.001)

    def test_policy_ref_in_evidence(self) -> None:
        check = self._check(
            equivalence_margin={
                "mode": "policy_ref",
                "path": "policies/margin/v1.json",
                "decision_id": "MARGIN-2026-10-19-01",
            }
        )
        outcome = StatisticsChecker().check(self._context(check))
        self.assertEqual(outcome.verdict, "SUPPORTED")
        self.assertEqual(outcome.evidence["resolution"]["margin_mode"], "policy_ref")
        self.assertEqual(
            outcome.evidence["resolution"]["margin_decision_id"],
            "MARGIN-2026-10-19-01",
        )
        self.assertEqual(
            outcome.evidence["resolution"]["margin_policy_version"], "v1"
        )

    def test_bad_margin_spec_is_inconclusive(self) -> None:
        check = self._check(equivalence_margin={"mode": "policy_ref", "path": "missing.json"})
        outcome = StatisticsChecker().check(self._context(check))
        self.assertEqual(outcome.verdict, "INCONCLUSIVE")
        self.assertIn("margin policy", outcome.reason)


class ExampleAuditTests(unittest.TestCase):
    def test_stats_example_has_three_margin_modes(self) -> None:
        audit = json.loads(
            (ROOT / "examples" / "stats_claim" / "audit.json").read_text(encoding="utf-8")
        )
        modes = []
        for claim in audit["claims"]:
            raw = claim["check"]["claim"].get("equivalence_margin")
            if raw is None or raw == "paper_precision":
                modes.append("paper_precision")
            elif isinstance(raw, dict):
                modes.append("policy_ref")
            else:
                modes.append("fixed")
        self.assertEqual(modes, ["paper_precision", "fixed", "policy_ref"])


if __name__ == "__main__":
    unittest.main()
