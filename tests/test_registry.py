"""Tests for the static registry builder.

Run from ``paperunit/``::

    python3 -m unittest discover -s tests -p "test_registry.py" -v

The tests use only ``tempfile`` trees; they never touch the network and never
depend on the other test modules in this repository.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from paperunit.registry import (  # noqa: E402
    REGISTRY_SCHEMA,
    UNKNOWN_AUTHOR,
    UNTITLED,
    build_registry,
    main,
)


def _write_report(root: Path, relative: str, payload: object) -> Path:
    """Write one report file (as UTF-8 JSON) and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(raw, encoding="utf-8")
    return path


def _full_report() -> dict:
    """A report shaped like the engine's ``paperunit/report/v1`` output."""
    return {
        "schema": "paperunit/report/v1",
        "tool": {"name": "paperunit", "version": "0.2.0"},
        "target": {
            "title": "合成示例：两特征阈值分类",
            "paper": "examples/toy_paper/paper.md",
            "repo_commit": "synthetic-fixture-v1",
            "audited_by": "paperunit demo",
            "date": "2026-10-20",
        },
        "scope": {"tested": ["accuracy"], "not_tested": ["generalisation"]},
        "environment": {"python": "3.11.9"},
        "generated_at": "2026-10-20T00:00:00Z",
        "claims": [
            {
                "id": "C1",
                "kind": "numeric",
                "text": "test accuracy 0.923",
                "verdict": "REFUTED",
                "reason": "observed 0.918",
                "evidence": {},
                "uncertainty": None,
            }
        ],
        "verdict_counts": {
            "SUPPORTED": 1,
            "REFUTED": 2,
            "INCONCLUSIVE": 3,
            "NOT_RUN": 4,
        },
        "report_sha256": "a" * 64,
        "limits": ["one commit, one environment"],
    }


class RegistryBuildTest(unittest.TestCase):
    """Behaviour of ``build_registry`` on temporary audit trees."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.audits = self.tmp / "audits"
        self.audits.mkdir()
        self.out = self.tmp / "site"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build(self) -> dict:
        return build_registry(self.audits, self.out)

    def _read_index_json(self) -> dict:
        return json.loads((self.out / "index.json").read_text(encoding="utf-8"))

    def _read_index_html(self) -> str:
        return (self.out / "index.html").read_text(encoding="utf-8")

    def test_empty_directory_writes_empty_registry(self) -> None:
        index = self._build()

        self.assertEqual(index["schema"], REGISTRY_SCHEMA)
        self.assertEqual(index["count"], 0)
        self.assertEqual(index["audits"], [])
        self.assertNotIn("warnings", index)

        self.assertTrue((self.out / "index.json").is_file())
        self.assertTrue((self.out / "index.html").is_file())
        self.assertTrue((self.out / "audits" / "index.html").is_file())
        self.assertTrue((self.out / "assets" / "style.css").is_file())
        self.assertEqual(self._read_index_json(), index)
        self.assertIn("尚无审计报告", self._read_index_html())

    def test_indexes_reports_and_tolerates_missing_fields(self) -> None:
        full = _full_report()
        _write_report(self.audits, "paper_a/audit_report.json", full)
        minimal_path = _write_report(
            self.audits,
            "paper_b/audit_report.json",
            {"schema": "paperunit/report/v1"},
        )

        index = self._build()

        self.assertEqual(index["schema"], REGISTRY_SCHEMA)
        self.assertEqual(index["count"], 2)
        self.assertEqual([entry["report_path"] for entry in index["audits"]], [
            "paper_a/audit_report.json",
            "paper_b/audit_report.json",
        ])

        dated, undated = index["audits"]
        self.assertEqual(dated["title"], full["target"]["title"])
        self.assertEqual(dated["audited_by"], "paperunit demo")
        self.assertEqual(dated["date"], "2026-10-20")
        self.assertEqual(dated["verdict_counts"], full["verdict_counts"])
        self.assertEqual(dated["report_sha256"], "a" * 64)

        # Missing fields fall back to documented defaults, never crash.
        minimal_sha256 = hashlib.sha256(minimal_path.read_bytes()).hexdigest()
        self.assertEqual(undated["title"], UNTITLED)
        self.assertEqual(undated["audited_by"], UNKNOWN_AUTHOR)
        self.assertEqual(undated["date"], "")
        self.assertEqual(
            undated["verdict_counts"],
            {"SUPPORTED": 0, "REFUTED": 0, "INCONCLUSIVE": 0, "NOT_RUN": 0},
        )
        self.assertEqual(undated["report_sha256"], minimal_sha256)

        # index.json on disk round-trips to exactly the returned index.
        self.assertEqual(self._read_index_json(), index)

        page = self._read_index_html()
        self.assertIn(full["target"]["title"], page)
        self.assertIn("paperunit demo", page)
        self.assertIn("SUPPORTED", page)
        self.assertIn("REFUTED", page)
        self.assertIn("INCONCLUSIVE", page)
        self.assertIn("NOT_RUN", page)
        self.assertIn("paper_b/audit_report.json", page)
        # Two audit cards on the landing page.
        self.assertEqual(page.count('<a class="promo'), 2)

        registry_page = (self.out / "audits" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(registry_page.count('class="audit-card"'), 2)
        self.assertIn(full["target"]["title"], registry_page)

        detail = (self.out / "audits" / "paper_a.html").read_text(encoding="utf-8")
        self.assertIn(full["target"]["title"], detail)
        self.assertIn("test accuracy 0.923", detail)
        self.assertIn("observed 0.918", detail)
        self.assertTrue((self.out / "audits" / "paper_a" / "report.json").is_file())

    def test_site_assets_are_copied(self) -> None:
        _write_report(
            self.audits,
            "one/audit_report.json",
            {"schema": "paperunit/report/v1", "target": {"title": "Asset test", "date": "2026-10-20"}},
        )
        self._build()
        assets = self.out / "assets"
        self.assertTrue((assets / "style.css").is_file())
        self.assertTrue((assets / "app.js").is_file())

    def test_html_does_not_embed_scripts(self) -> None:
        _write_report(
            self.audits,
            "sneaky/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {
                    "title": '<script>alert("x")</script>',
                    "audited_by": "a & b",
                    "date": "2026-10-20",
                },
                "verdict_counts": {"REFUTED": 1},
            },
        )

        self._build()
        page = self._read_index_html()

        # Report data is escaped; the only scripts are the site's own assets.
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("a &amp; b", page)
        self.assertIn('src="assets/app.js"', page)

    def test_date_sort_is_descending_and_undated_last(self) -> None:
        _write_report(
            self.audits,
            "jan/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "January audit", "date": "2026-01-05"},
            },
        )
        _write_report(
            self.audits,
            "oct/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "October audit", "date": "2026-10-20"},
            },
        )
        _write_report(
            self.audits,
            "nodate/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Undated audit"},
            },
        )

        index = self._build()
        titles = [entry["title"] for entry in index["audits"]]

        self.assertEqual(titles, ["October audit", "January audit", "Undated audit"])

    def test_verdict_counts_derived_from_claims(self) -> None:
        _write_report(
            self.audits,
            "derived/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Derived counts", "date": "2026-10-19"},
                "claims": [
                    {"id": "C1", "verdict": "SUPPORTED"},
                    {"id": "C2", "verdict": "REFUTED"},
                    {"id": "C3", "verdict": "REFUTED"},
                    {"id": "C4", "verdict": "SOMETHING_ELSE"},
                ],
            },
        )

        index = self._build()
        counts = index["audits"][0]["verdict_counts"]

        self.assertEqual(counts["SUPPORTED"], 1)
        self.assertEqual(counts["REFUTED"], 2)
        self.assertEqual(counts["INCONCLUSIVE"], 0)
        self.assertEqual(counts["NOT_RUN"], 0)

    def test_malformed_report_is_skipped_with_warning(self) -> None:
        good = _write_report(
            self.audits,
            "good/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Valid report", "date": "2026-10-20"},
            },
        )
        broken_path = self.audits / "broken" / "audit_report.json"
        broken_path.parent.mkdir(parents=True)
        broken_path.write_text("{not json", encoding="utf-8")
        # Valid JSON but not an object: also skipped.
        list_path = self.audits / "listy" / "audit_report.json"
        list_path.parent.mkdir(parents=True)
        list_path.write_text("[1, 2, 3]\n", encoding="utf-8")

        index = self._build()

        self.assertEqual(index["count"], 1)
        self.assertEqual(
            index["audits"][0]["title"],
            "Valid report",
        )
        warning_paths = [warning["report_path"] for warning in index["warnings"]]
        self.assertEqual(warning_paths, ["broken/audit_report.json", "listy/audit_report.json"])
        self.assertIn("not valid JSON", index["warnings"][0]["error"])
        self.assertIn("must be a JSON object", index["warnings"][1]["error"])
        # The valid report is still indexed and referenced by the page.
        self.assertIn(good.name, (self.out / "index.html").read_text(encoding="utf-8"))

    def test_output_is_deterministic(self) -> None:
        _write_report(
            self.audits,
            "one/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Deterministic audit", "date": "2026-10-20"},
            },
        )
        _write_report(
            self.audits,
            "two/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Another audit", "date": "2026-10-19"},
            },
        )

        first = self._build()
        json_first = (self.out / "index.json").read_bytes()
        html_first = (self.out / "index.html").read_bytes()
        registry_first = (self.out / "audits" / "index.html").read_bytes()
        detail_first = (self.out / "audits" / "one.html").read_bytes()

        second = self._build()

        self.assertEqual(first, second)
        self.assertEqual((self.out / "index.json").read_bytes(), json_first)
        self.assertEqual((self.out / "index.html").read_bytes(), html_first)
        self.assertEqual((self.out / "audits" / "index.html").read_bytes(), registry_first)
        self.assertEqual((self.out / "audits" / "one.html").read_bytes(), detail_first)

    def test_out_dir_inside_audits_dir_is_not_rescanned(self) -> None:
        _write_report(
            self.audits,
            "paper/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Nested output test", "date": "2026-10-20"},
            },
        )
        nested_out = self.audits / "site"

        build_registry(self.audits, nested_out)
        index = build_registry(self.audits, nested_out)

        self.assertEqual(index["count"], 1)

    def test_same_audits_and_out_dir_still_indexes_reports(self) -> None:
        _write_report(
            self.audits,
            "paper/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Same directory test", "date": "2026-10-20"},
            },
        )

        index = build_registry(self.audits, self.audits)

        self.assertEqual(index["count"], 1)
        self.assertEqual(index["audits"][0]["title"], "Same directory test")

    def test_verdict_counts_tolerate_bad_values(self) -> None:
        _write_report(
            self.audits,
            "weird/audit_report.json",
            {
                "schema": "paperunit/report/v1",
                "target": {"title": "Weird counts", "date": "2026-10-20"},
                "verdict_counts": {
                    "SUPPORTED": "2",       # numeric string
                    "REFUTED": -3,          # negative
                    "INCONCLUSIVE": True,   # bool must not count as 1
                    "NOT_RUN": None,        # missing/None
                    "EXTRA": 99,            # unknown verdict ignored
                },
            },
        )

        index = self._build()
        counts = index["audits"][0]["verdict_counts"]

        self.assertEqual(
            counts,
            {"SUPPORTED": 2, "REFUTED": 0, "INCONCLUSIVE": 0, "NOT_RUN": 0},
        )

    def test_main_returns_zero_and_writes_output(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["--audits-dir", str(self.audits), "--out", str(self.out)])

        self.assertEqual(code, 0)
        self.assertIn("indexed 0 audit report(s)", stdout.getvalue())
        self.assertTrue((self.out / "index.json").is_file())
        self.assertTrue((self.out / "index.html").is_file())

    def test_main_reports_missing_audits_dir(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main([
                "--audits-dir", str(self.tmp / "does-not-exist"),
                "--out", str(self.out),
            ])

        self.assertEqual(code, 2)
        self.assertIn("audits directory not found", stderr.getvalue())
        self.assertFalse((self.out / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
