#!/usr/bin/env python3
"""Tests for pass^k, efficiency metrics, failure-mode classification, mutation."""
import unittest

from failure_modes import (
    E_TOOL_1,
    E_TOOL_2,
    E_TOOL_3,
    E_TOOL_4,
    classify_trajectory,
    merge_scope_violation,
)
from metrics import (
    consistency_claim_supported,
    pass_cost_k,
    pass_hat_k,
    step_ratio,
    summarize_usage,
)
from mutate import apply_renames, build_rename_map, collect_renamable, detect_contamination


class TestPassHatK(unittest.TestCase):
    def test_all_trials_succeeded(self):
        self.assertEqual(pass_hat_k(n=10, c=10, k=8), 1.0)

    def test_no_trial_succeeded(self):
        self.assertEqual(pass_hat_k(n=10, c=0, k=1), 0.0)

    def test_fewer_successes_than_k_is_zero(self):
        self.assertEqual(pass_hat_k(n=10, c=3, k=8), 0.0)

    def test_k_above_n_is_unmeasured_not_zero(self):
        # Reporting 0.0 here would read as "it always fails" rather than
        # "we never ran that many trials".
        self.assertIsNone(pass_hat_k(n=2, c=2, k=8))

    def test_k_one_is_the_per_trial_rate(self):
        self.assertAlmostEqual(pass_hat_k(n=10, c=3, k=1), 0.3)

    def test_consistency_falls_off_faster_than_the_rate(self):
        # Why a single-trial score misleads. A model passing 7 of 10 reads as
        # respectable, and the odds that eight straight trials all pass are
        # exactly zero. This is the whole argument for reporting pass^k.
        self.assertAlmostEqual(pass_hat_k(n=10, c=7, k=1), 0.70)
        self.assertAlmostEqual(pass_hat_k(n=10, c=7, k=2), 21 / 45)
        self.assertAlmostEqual(pass_hat_k(n=10, c=7, k=4), 35 / 210)
        self.assertEqual(pass_hat_k(n=10, c=7, k=8), 0.0)

    def test_small_n_cannot_support_a_consistency_claim(self):
        self.assertFalse(consistency_claim_supported(2))
        self.assertFalse(consistency_claim_supported(7))
        self.assertTrue(consistency_claim_supported(8))


class TestEfficiency(unittest.TestCase):
    def test_step_ratio_is_one_when_optimal(self):
        self.assertEqual(step_ratio(4, 4), 1.0)

    def test_step_ratio_penalizes_a_loop(self):
        self.assertLess(step_ratio(4, 13), 0.35)

    def test_step_ratio_none_without_an_authored_optimum(self):
        self.assertIsNone(step_ratio(None, 10))

    def test_pass_cost_k_discounts_the_expensive_model(self):
        cheap = pass_cost_k(1.0, total_tokens=1000, baseline_tokens=1000)
        dear = pass_cost_k(1.0, total_tokens=10000, baseline_tokens=1000)
        self.assertAlmostEqual(cheap, 1.0)
        self.assertAlmostEqual(dear, 0.5)

    def test_pass_cost_k_none_when_pass_k_unmeasured(self):
        self.assertIsNone(pass_cost_k(None, 1000, 1000))

    def test_usage_flags_partial_coverage(self):
        rows = [{"usage": {"input_tokens": 10, "output_tokens": 5}}, {}]
        s = summarize_usage(rows)
        self.assertEqual(s["total_tokens"], 15)
        self.assertFalse(s["complete"])
        self.assertEqual(s["rows_with_usage"], 1)


class TestFailureModes(unittest.TestCase):
    def _traj(self, events):
        return {"tool_events": events}

    def test_unknown_tool_is_hallucination(self):
        c = classify_trajectory(self._traj([
            {"tool": "delete_everything", "args": {}, "ok": False, "detail": "unknown tool"},
        ]))
        self.assertEqual(c["counts"][E_TOOL_4], 1)

    def test_bad_path_is_a_parameter_violation(self):
        c = classify_trajectory(self._traj([
            {"tool": "read_file", "args": {"path": "../etc"}, "ok": False, "detail": "bad path"},
        ]))
        self.assertEqual(c["counts"][E_TOOL_1], 1)

    def test_blocked_write_is_a_policy_breach(self):
        c = classify_trajectory(self._traj([
            {"tool": "write_file", "args": {"path": "legacy.py"}, "ok": False,
             "detail": "out of scope write blocked by adapter"},
        ]))
        self.assertEqual(c["counts"][E_TOOL_2], 1)

    def test_repeated_identical_calls_are_intent_drift(self):
        # The observed loop: the same write issued over and over.
        events = [{"tool": "write_file", "args": {"path": "cart.py"}, "ok": True}] * 11
        c = classify_trajectory(self._traj(events))
        self.assertEqual(c["counts"][E_TOOL_3], 1)
        self.assertEqual(c["redundant_calls"], 10)

    def test_a_little_repetition_is_not_drift(self):
        # Re-reading a file after editing it is ordinary behaviour.
        events = [
            {"tool": "read_file", "args": {"path": "a.py"}, "ok": True},
            {"tool": "write_file", "args": {"path": "a.py"}, "ok": True},
            {"tool": "read_file", "args": {"path": "a.py"}, "ok": True},
        ]
        c = classify_trajectory(self._traj(events))
        self.assertEqual(c["counts"][E_TOOL_3], 0)

    def test_graded_scope_violation_fires_policy_breach(self):
        # The adapter can miss a violation; the workspace diff is the authority.
        c = merge_scope_violation(classify_trajectory(self._traj([])), True)
        self.assertEqual(c["counts"][E_TOOL_2], 1)

    def test_empty_trajectory_is_clean(self):
        c = classify_trajectory(None)
        self.assertEqual(c["classes_fired"], [])


class TestMutation(unittest.TestCase):
    SRC = "import math\n\n\ndef total(items):\n    # keep this comment\n    return sum(items)\n"

    def test_collects_definitions_but_not_imports(self):
        names = collect_renamable(self.SRC)
        self.assertIn("total", names)
        self.assertIn("items", names)
        self.assertNotIn("math", names)

    def test_rename_is_deterministic_for_a_seed(self):
        names = collect_renamable(self.SRC)
        a = build_rename_map(names, "t", 42)
        b = build_rename_map(names, "t", 42)
        self.assertEqual(a, b)
        self.assertNotEqual(a, build_rename_map(names, "t", 43))

    def test_protected_names_keep_their_spelling(self):
        names = collect_renamable(self.SRC)
        m = build_rename_map(names, "t", 42, protected={"total"})
        self.assertNotIn("total", m)

    def test_rename_preserves_comments_and_layout(self):
        m = build_rename_map(collect_renamable(self.SRC), "t", 42)
        out = apply_renames(self.SRC, m)
        self.assertIn("# keep this comment", out)
        self.assertIn("import math", out)
        self.assertNotIn("def total(", out)

    def test_rename_does_not_touch_string_contents(self):
        src = 'def total(x):\n    return "total is fixed text"\n'
        m = build_rename_map(collect_renamable(src), "t", 42)
        out = apply_renames(src, m)
        self.assertIn('"total is fixed text"', out)

    def test_contamination_tripwire_ignores_the_mutated_form(self):
        # total_abc123 contains "total"; that must not count as a hit.
        hits = detect_contamination("def total_abc123(x):", ["total"], ["total_abc123"])
        self.assertEqual(hits, [])

    def test_contamination_tripwire_catches_the_original_spelling(self):
        hits = detect_contamination("def total(x):", ["total"], ["total_abc123"])
        self.assertEqual(hits, ["total"])


if __name__ == "__main__":
    unittest.main()
