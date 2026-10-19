"""Tests for the audit engine: verdicts, digests, tamper and drift detection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paperunit.checkers.base import RunResult
from paperunit.engine import (
    claim_fingerprint,
    run_audit,
    verify_audit,
)

ROOT = Path(__file__).resolve().parents[1]


def _fake_runner(value: float, exit_code: int = 0):
    def runner(cmd: str, cwd: Path, timeout_s: float) -> RunResult:
        return RunResult(
            cmd=cmd,
            cwd=str(cwd),
            timeout_s=timeout_s,
            exit_code=exit_code,
            timed_out=False,
            duration_s=0.01,
            stdout=f"metric={value}\n",
            stderr="",
        )

    return runner


def _audit_file(tmp: Path, claims=None) -> Path:
    audit = {
        "schema": "paperunit/v1",
        "target": {"title": "unit", "audited_by": "tests", "date": "2026-10-19"},
        "scope": {"tested": ["metric"], "not_tested": ["everything else"]},
        "claims": claims
        or [
            {
                "id": "C1",
                "text": "metric is 0.5",
                "kind": "numeric",
                "check": {
                    "cmd": "true",
                    "expect": {
                        "numeric_within": {
                            "number_regex": r"metric=(?P<value>[0-9.]+)",
                            "target": 0.5,
                            "tolerance": 0.01,
                        }
                    },
                },
                "preregistered": True,
            }
        ],
    }
    path = tmp / "audit.json"
    path.write_text(json.dumps(audit), encoding="utf-8")
    return path


class EngineTests(unittest.TestCase):
    def test_toy_example_verdict_mix_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            report, paths = run_audit(ROOT / "examples" / "toy_paper" / "audit.json", out)
            self.assertEqual(report["schema"], "paperunit/report/v1")
            self.assertEqual(
                report["verdict_counts"],
                {"SUPPORTED": 2, "REFUTED": 2, "INCONCLUSIVE": 0, "NOT_RUN": 0},
            )
            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["markdown"].exists())
            self.assertNotIn(
                "score",
                json.dumps(report.get("verdict_counts", {})).lower(),
            )
            status, details = verify_audit(
                ROOT / "examples" / "toy_paper" / "audit.json", paths["json"]
            )
            self.assertEqual(status, "REPRODUCIBLE")
            self.assertEqual(details["differences"], [])
            self.assertFalse(details["tampered"])

    def test_report_digest_is_stable_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = _audit_file(Path(tmp))
            report_a, _ = run_audit(audit, Path(tmp) / "a", runner=_fake_runner(0.5))
            report_b, _ = run_audit(audit, Path(tmp) / "b", runner=_fake_runner(0.5))
            self.assertEqual(report_a["report_sha256"], report_b["report_sha256"])
            self.assertEqual(
                claim_fingerprint(report_a["claims"][0]),
                claim_fingerprint(report_b["claims"][0]),
            )

    def test_changed_verdict_is_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audit = _audit_file(tmp_path)
            report, paths = run_audit(audit, tmp_path / "out", runner=_fake_runner(0.5))
            self.assertEqual(report["claims"][0]["verdict"], "SUPPORTED")
            status, details = verify_audit(
                audit, paths["json"], runner=_fake_runner(0.9)
            )
            self.assertEqual(status, "DRIFT")
            self.assertEqual(details["differences"][0]["change"], "verdict_changed")

    def test_modified_report_is_tampered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audit = _audit_file(tmp_path)
            _, paths = run_audit(audit, tmp_path / "out", runner=_fake_runner(0.5))
            stored = json.loads(paths["json"].read_text(encoding="utf-8"))
            stored["claims"][0]["verdict"] = "REFUTED"
            paths["json"].write_text(json.dumps(stored), encoding="utf-8")
            status, details = verify_audit(audit, paths["json"])
            self.assertEqual(status, "TAMPERED")
            self.assertTrue(details["tampered"])

    def test_human_claim_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audit = _audit_file(
                tmp_path,
                claims=[{"id": "H1", "text": "human", "kind": "human"}],
            )
            report, _ = run_audit(audit, tmp_path / "out")
            self.assertEqual(report["claims"][0]["verdict"], "NOT_RUN")
            self.assertEqual(report["verdict_counts"]["NOT_RUN"], 1)

    def test_unknown_kind_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audit = _audit_file(
                tmp_path,
                claims=[
                    {
                        "id": "X1",
                        "text": "unknown",
                        "kind": "does-not-exist",
                        "check": {},
                    }
                ],
            )
            report, _ = run_audit(audit, tmp_path / "out")
            self.assertEqual(report["claims"][0]["verdict"], "INCONCLUSIVE")
            self.assertIn("no checker registered", report["claims"][0]["reason"])

    def test_timeout_is_inconclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            audit = _audit_file(
                tmp_path,
                claims=[
                    {
                        "id": "T1",
                        "text": "timeout",
                        "kind": "numeric",
                        "check": {
                            "cmd": "true",
                            "timeout_s": 1,
                            "expect": {"exit_code": 0},
                        },
                    }
                ],
            )

            def timed_out(cmd: str, cwd: Path, timeout_s: float) -> RunResult:
                return RunResult(cmd, str(cwd), timeout_s, None, True, 1.0, "", "")

            report, _ = run_audit(audit, tmp_path / "out", runner=timed_out)
            self.assertEqual(report["claims"][0]["verdict"], "INCONCLUSIVE")

    def test_report_contains_no_aggregate_score_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report, _ = run_audit(
                ROOT / "examples" / "toy_paper" / "audit.json", Path(tmp) / "out"
            )
            self.assertNotIn("score", report)
            self.assertNotIn("rank", report)
            self.assertIn("limits", report)


if __name__ == "__main__":
    unittest.main()
