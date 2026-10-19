"""Tests for the command-line interface."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paperunit.cli import main

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_validate_example(self) -> None:
        self.assertEqual(
            main(["validate", "--audit", str(ROOT / "examples" / "toy_paper" / "audit.json")]),
            0,
        )

    def test_validate_missing_file(self) -> None:
        self.assertEqual(main(["validate", "--audit", "/nonexistent/audit.json"]), 2)

    def test_run_and_verify_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            audit = str(ROOT / "examples" / "toy_paper" / "audit.json")
            self.assertEqual(main(["run", "--audit", audit, "--out", str(out)]), 0)
            report_path = out / "audit_report.json"
            self.assertTrue(report_path.exists())
            self.assertEqual(
                main(
                    [
                        "verify",
                        "--audit",
                        audit,
                        "--report",
                        str(report_path),
                    ]
                ),
                0,
            )

    def test_verify_missing_report(self) -> None:
        self.assertEqual(
            main(
                [
                    "verify",
                    "--audit",
                    str(ROOT / "examples" / "toy_paper" / "audit.json"),
                    "--report",
                    "/nonexistent/report.json",
                ]
            ),
            2,
        )

    def test_run_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            audit = str(ROOT / "examples" / "toy_paper" / "audit.json")
            self.assertEqual(
                main(["run", "--audit", audit, "--out", str(out), "--json"]), 0
            )
            stored = json.loads((out / "audit_report.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["schema"], "paperunit/report/v1")

    def test_init_scaffolds_valid_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new_audit"
            self.assertEqual(main(["init", "--dir", str(target)]), 0)
            self.assertTrue((target / "audit.json").exists())
            self.assertEqual(
                main(["validate", "--audit", str(target / "audit.json")]), 0
            )
            # Second init without --force refuses to overwrite.
            self.assertEqual(main(["init", "--dir", str(target)]), 2)
            self.assertEqual(main(["init", "--dir", str(target), "--force"]), 0)


if __name__ == "__main__":
    unittest.main()
