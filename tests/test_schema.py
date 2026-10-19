"""Tests for audit spec loading, migration and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paperunit.schema import AuditSpecError, load_audit, migrate_audit, validate_audit

ROOT = Path(__file__).resolve().parents[1]


def _minimal(**overrides):
    audit = {
        "schema": "paperunit/v1",
        "target": {
            "title": "t",
            "audited_by": "a",
            "date": "2026-10-19",
        },
        "claims": [
            {
                "id": "C1",
                "text": "x",
                "kind": "numeric",
                "check": {"cmd": "true", "expect": {"exit_code": 0}},
            }
        ],
    }
    audit.update(overrides)
    return audit


class SchemaTests(unittest.TestCase):
    def test_toy_and_redteam_examples_load(self) -> None:
        for name in ("toy_paper", "redteam"):
            audit = load_audit(ROOT / "examples" / name / "audit.json")
            self.assertEqual(audit["schema"], "paperunit/v1")
            self.assertGreaterEqual(len(audit["claims"]), 1)

    def test_all_example_audits_load(self) -> None:
        for audit_path in sorted((ROOT / "examples").glob("*/audit.json")):
            audit = load_audit(audit_path)
            self.assertEqual(audit["schema"], "paperunit/v1", audit_path)
            self.assertGreaterEqual(len(audit["claims"]), 1, audit_path)

    def test_duplicate_claim_id_rejected(self) -> None:
        audit = _minimal()
        audit["claims"].append(dict(audit["claims"][0]))
        with self.assertRaises(AuditSpecError):
            validate_audit(audit)

    def test_missing_target_field_rejected(self) -> None:
        audit = _minimal()
        del audit["target"]["audited_by"]
        with self.assertRaises(AuditSpecError):
            validate_audit(audit)

    def test_unsupported_schema_rejected(self) -> None:
        with self.assertRaises(AuditSpecError):
            validate_audit(_minimal(schema="paperunit/v999"))

    def test_non_numeric_check_rejected(self) -> None:
        audit = _minimal()
        audit["claims"][0]["check"] = "not-an-object"
        with self.assertRaises(AuditSpecError):
            validate_audit(audit)

    def test_human_claim_needs_no_check(self) -> None:
        audit = _minimal()
        audit["claims"].append({"id": "H1", "text": "judgement", "kind": "human"})
        validate_audit(audit)

    def test_legacy_schema_is_migrated(self) -> None:
        legacy = _minimal()
        legacy["schema"] = "paperaudit/v0"
        migrated = migrate_audit(legacy, Path("legacy.json"))
        self.assertEqual(migrated["schema"], "paperunit/v1")
        self.assertEqual(migrated["target"]["migrated_from"], "paperaudit/v0")

    def test_load_reads_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.json"
            path.write_text(json.dumps(_minimal()), encoding="utf-8")
            audit = load_audit(path)
            self.assertEqual(len(audit["claims"]), 1)

    def test_invalid_json_reports_spec_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(AuditSpecError):
                load_audit(path)


if __name__ == "__main__":
    unittest.main()
