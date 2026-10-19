"""Tests for paperunit.uncertainty (stdlib-only, deterministic statistics)."""

from __future__ import annotations

import json
import math
import unittest

from paperunit.uncertainty import (
    holm_adjust,
    min_detectable_effect,
    summarize_mean,
    verdict_from_interval,
)

# The six-seed sweep of examples/stats_claim: mean 0.918, sample SD ~0.0038.
VALUES = [0.916, 0.920, 0.914, 0.922, 0.914, 0.922]
VALUES_MEAN = 0.918
VALUES_SD = math.sqrt(14.4e-6)  # sum of squared deviations / (n-1)
VALUES_SE = VALUES_SD / math.sqrt(6)
# Two-sided t critical value for 95% confidence, df = 5.
T_975_DF5 = 2.570582
# z_{0.975} + z_{0.8}; the standard MDE multiplier for alpha=0.05, power=0.8.
MDE_MULTIPLIER = 2.801585218112968


class SummarizeMeanTests(unittest.TestCase):
    def test_known_statistics(self):
        summary = summarize_mean(VALUES, method="t")
        self.assertEqual(summary["n"], 6)
        self.assertAlmostEqual(summary["mean"], VALUES_MEAN, places=12)
        self.assertAlmostEqual(summary["sd"], VALUES_SD, places=12)
        self.assertAlmostEqual(summary["se"], VALUES_SE, places=12)
        self.assertAlmostEqual(
            summary["ci_low"], VALUES_MEAN - T_975_DF5 * VALUES_SE, places=4
        )
        self.assertAlmostEqual(
            summary["ci_high"], VALUES_MEAN + T_975_DF5 * VALUES_SE, places=4
        )
        self.assertAlmostEqual(
            summary["ci_half_width"], T_975_DF5 * VALUES_SE, places=4
        )
        self.assertEqual(summary["method"], "t")
        self.assertEqual(summary["confidence"], 0.95)
        self.assertIsNone(summary["resamples"])
        self.assertIsNone(summary["seed"])
        self.assertEqual(len(summary["values_sha256"]), 64)

    def test_bootstrap_is_deterministic_for_same_seed(self):
        first = summarize_mean(VALUES, resamples=500, rng_seed=7)
        second = summarize_mean(VALUES, resamples=500, rng_seed=7)
        self.assertEqual(first, second)
        self.assertIsNotNone(first["ci_low"])
        self.assertIsNotNone(first["ci_high"])
        self.assertEqual(first["method"], "bootstrap")
        self.assertEqual(first["resamples"], 500)
        self.assertEqual(first["seed"], 7)
        self.assertEqual(first["ci_method"], "bootstrap_percentile_linear")

    def test_bootstrap_interval_is_ordered_and_centred(self):
        summary = summarize_mean(VALUES, resamples=1000, rng_seed=3)
        self.assertLessEqual(summary["ci_low"], summary["ci_high"])
        self.assertAlmostEqual(
            summary["ci_half_width"],
            (summary["ci_high"] - summary["ci_low"]) / 2.0,
            places=15,
        )
        # Resampling the observed mean cannot move far on this tiny sample.
        self.assertLess(summary["ci_low"], summary["mean"])
        self.assertGreater(summary["ci_high"], summary["mean"])
        self.assertAlmostEqual(
            summary["ci_low"], summary["mean"] - summary["ci_half_width"], places=15
        )

    def test_confidence_level_changes_interval_width(self):
        narrow = summarize_mean(VALUES, method="t", confidence=0.90)
        wide = summarize_mean(VALUES, method="t", confidence=0.99)
        self.assertLess(narrow["ci_half_width"], wide["ci_half_width"])
        self.assertEqual(narrow["confidence"], 0.90)
        self.assertEqual(wide["confidence"], 0.99)

    def test_two_point_t_interval_uses_df_one(self):
        summary = summarize_mean([0.9, 1.0], method="t")
        self.assertAlmostEqual(summary["sd"], 0.07071067811865475, places=12)
        self.assertAlmostEqual(summary["se"], 0.05, places=12)
        # t(0.975, df=1) = 12.706205 from the lookup table.
        self.assertAlmostEqual(summary["ci_half_width"], 12.706205 * 0.05, places=9)

    def test_t_method_cornish_fisher_for_large_df(self):
        values = [0.90 + 0.001 * index for index in range(41)]
        summary = summarize_mean(values, method="t")
        self.assertEqual(summary["ci_method"], "t_interval_cornish_fisher")
        # For df=40 the critical value is very close to the normal 1.959964.
        self.assertAlmostEqual(summary["ci_half_width"], 1.959964 * summary["se"], places=3)

    def test_values_sha256_is_stable_and_order_sensitive(self):
        first = summarize_mean(VALUES, method="t")
        second = summarize_mean(VALUES, method="t")
        reordered = summarize_mean(list(reversed(VALUES)), method="t")
        self.assertEqual(first["values_sha256"], second["values_sha256"])
        self.assertNotEqual(first["values_sha256"], reordered["values_sha256"])
        self.assertEqual(len(first["values_sha256"]), 64)

    def test_empty_values_raise(self):
        with self.assertRaises(ValueError):
            summarize_mean([])

    def test_bad_values_raise(self):
        with self.assertRaises(ValueError):
            summarize_mean([float("nan")])
        with self.assertRaises(ValueError):
            summarize_mean([float("inf")])
        with self.assertRaises(ValueError):
            summarize_mean(["not a number"])

    def test_single_value_has_no_interval(self):
        summary = summarize_mean([0.5])
        self.assertEqual(summary["n"], 1)
        self.assertEqual(summary["mean"], 0.5)
        self.assertEqual(summary["sd"], 0.0)
        self.assertIsNone(summary["se"])
        self.assertIsNone(summary["ci_low"])
        self.assertIsNone(summary["ci_high"])
        self.assertIsNone(summary["ci_half_width"])
        self.assertEqual(summary["ci_method"], "none")
        self.assertIsInstance(summary["note"], str)
        self.assertIn("n=1", summary["note"])

    def test_invalid_method_and_confidence_raise(self):
        with self.assertRaises(ValueError):
            summarize_mean(VALUES, method="bayes")
        for confidence in (0.0, 1.0, -0.1, 1.5):
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValueError):
                    summarize_mean(VALUES, confidence=confidence)

    def test_invalid_bootstrap_options_raise(self):
        with self.assertRaises(ValueError):
            summarize_mean(VALUES, resamples=0)
        with self.assertRaises(ValueError):
            summarize_mean(VALUES, resamples=1.5)
        with self.assertRaises(ValueError):
            summarize_mean(VALUES, rng_seed=None)

    def test_t_method_rejects_untabulated_small_sample_confidence(self):
        with self.assertRaises(ValueError) as caught:
            summarize_mean(VALUES, method="t", confidence=0.80)
        self.assertIn("0.95", str(caught.exception))

    def test_summary_is_json_serialisable(self):
        for method in ("bootstrap", "t"):
            with self.subTest(method=method):
                summary = summarize_mean(VALUES, method=method, resamples=100)
                self.assertEqual(json.loads(json.dumps(summary)), summary)


class MinDetectableEffectTests(unittest.TestCase):
    def test_standard_formula(self):
        expected = MDE_MULTIPLIER * 0.004 / math.sqrt(6)
        self.assertAlmostEqual(min_detectable_effect(0.004, 6), expected, places=12)

    def test_familiar_2_8_rule_of_thumb(self):
        mde = min_detectable_effect(0.004, 6)
        self.assertAlmostEqual(mde, 2.8 * 0.004 / math.sqrt(6), places=3)
        self.assertLessEqual(
            abs(mde - 2.8 * 0.004 / math.sqrt(6)), 0.01 * mde
        )

    def test_zero_sd_gives_zero(self):
        self.assertEqual(min_detectable_effect(0.0, 6), 0.0)

    def test_mde_decreases_with_more_seeds(self):
        small = min_detectable_effect(0.01, 5)
        medium = min_detectable_effect(0.01, 20)
        large = min_detectable_effect(0.01, 100)
        self.assertGreater(small, medium)
        self.assertGreater(medium, large)

    def test_mde_scales_with_sd(self):
        base = min_detectable_effect(0.01, 10)
        self.assertAlmostEqual(min_detectable_effect(0.02, 10), 2.0 * base, places=12)

    def test_stricter_alpha_or_higher_power_larger_mde(self):
        default = min_detectable_effect(0.01, 10)
        self.assertGreater(min_detectable_effect(0.01, 10, alpha=0.01), default)
        self.assertGreater(min_detectable_effect(0.01, 10, power=0.9), default)

    def test_invalid_arguments_raise(self):
        with self.assertRaises(ValueError):
            min_detectable_effect(-0.01, 6)
        with self.assertRaises(ValueError):
            min_detectable_effect(0.01, 0)
        with self.assertRaises(ValueError):
            min_detectable_effect(0.01, 6, alpha=0.0)
        with self.assertRaises(ValueError):
            min_detectable_effect(0.01, 6, power=1.0)
        with self.assertRaises(ValueError):
            min_detectable_effect(float("nan"), 6)


class HolmAdjustTests(unittest.TestCase):
    def test_known_adjustment_and_original_order(self):
        # Sorted: 0.005 (x4), 0.01 (x3), 0.03 (x2), 0.04 (x1), monotone.
        self.assertEqual(
            holm_adjust([0.01, 0.04, 0.03, 0.005]),
            [0.03, 0.06, 0.06, 0.02],
        )

    def test_empty_and_single(self):
        self.assertEqual(holm_adjust([]), [])
        self.assertEqual(holm_adjust([0.03]), [0.03])

    def test_adjusted_values_are_capped_at_one(self):
        adjusted = holm_adjust([0.5, 0.9])
        self.assertEqual(adjusted, [1.0, 1.0])

    def test_invalid_pvalues_raise(self):
        with self.assertRaises(ValueError):
            holm_adjust([-0.01])
        with self.assertRaises(ValueError):
            holm_adjust([1.2])
        with self.assertRaises(ValueError):
            holm_adjust([float("nan")])
        with self.assertRaises(ValueError):
            holm_adjust(["x"])

    def test_adjusted_pvalues_dominate_raw_pvalues(self):
        raw = [0.001, 0.02, 0.2, 0.5]
        adjusted = holm_adjust(raw)
        for before, after in zip(raw, adjusted):
            self.assertGreaterEqual(after, before)


class VerdictFromIntervalTests(unittest.TestCase):
    def test_supported_when_inside_margin(self):
        verdict, reason = verdict_from_interval(0.918, 0.918, 0.915, 0.921, 0.01)
        self.assertEqual(verdict, "SUPPORTED")
        self.assertIn("within", reason)
        self.assertIn("0.01", reason)

    def test_refuted_when_gap_exceeds_margin_and_interval_excludes_claim(self):
        verdict, reason = verdict_from_interval(0.923, 0.918, 0.915, 0.921, 0.002)
        self.assertEqual(verdict, "REFUTED")
        self.assertIn("0.002", reason)
        self.assertIn("[0.915, 0.921]", reason)
        self.assertIn("0.923", reason)

    def test_inconclusive_when_interval_still_contains_claim(self):
        verdict, reason = verdict_from_interval(0.923, 0.918, 0.914, 0.924, 0.002)
        self.assertEqual(verdict, "INCONCLUSIVE")
        self.assertIn("0.923", reason)
        self.assertIn("resolution", reason.lower())

    def test_mde_is_quoted_in_reason_when_supplied(self):
        verdict, reason = verdict_from_interval(
            0.923, 0.918, 0.915, 0.921, 0.002, mde=0.00434
        )
        self.assertEqual(verdict, "REFUTED")
        self.assertIn("minimum detectable effect", reason.lower())
        self.assertIn("0.00434", reason)

    def test_margin_boundary_is_inclusive(self):
        # 3.5 - 3.0 == 0.5 exactly in binary floating point.
        verdict, _ = verdict_from_interval(3.0, 3.5, 3.0, 4.0, 0.5)
        self.assertEqual(verdict, "SUPPORTED")

    def test_no_interval_within_margin_is_tolerance_match(self):
        verdict, reason = verdict_from_interval(0.5, 0.5, None, None, 0.01)
        self.assertEqual(verdict, "SUPPORTED")
        self.assertIn("n=1", reason)

    def test_no_interval_outside_margin_is_inconclusive(self):
        verdict, reason = verdict_from_interval(0.6, 0.5, None, None, 0.01)
        self.assertEqual(verdict, "INCONCLUSIVE")
        self.assertIn("more seeds", reason)

    def test_invalid_arguments_raise(self):
        with self.assertRaises(ValueError):
            verdict_from_interval(0.5, 0.5, 0.6, 0.4, 0.01)  # low > high
        with self.assertRaises(ValueError):
            verdict_from_interval(0.5, 0.5, 0.4, None, 0.01)  # mismatched CI
        with self.assertRaises(ValueError):
            verdict_from_interval(0.5, 0.5, 0.4, 0.6, -0.01)  # negative margin
        with self.assertRaises(ValueError):
            verdict_from_interval(float("nan"), 0.5, 0.4, 0.6, 0.01)
        with self.assertRaises(ValueError):
            verdict_from_interval(0.5, 0.5, 0.4, 0.6, 0.01, mde=-0.1)


if __name__ == "__main__":
    unittest.main()
