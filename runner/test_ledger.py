#!/usr/bin/env python3
"""Stdlib tests for ledger + path_valid v2."""
import unittest

from ledger import (
    compute_path_flags,
    map_ledger_label,
    path_valid_score,
)


class TestLedger(unittest.TestCase):
    def test_false_completion_label(self):
        r = map_ledger_label(
            verify_pass=False, scope_violation=False, claimed_complete=True
        )
        self.assertEqual(r["ledger_label"], "unsupported-assertion")

    def test_verified_supported(self):
        r = map_ledger_label(
            verify_pass=True, scope_violation=False, claimed_complete=True
        )
        self.assertEqual(r["ledger_label"], "verified-supported")

    def test_scope_beats_pass(self):
        r = map_ledger_label(
            verify_pass=True, scope_violation=True, claimed_complete=True
        )
        self.assertEqual(r["ledger_label"], "out-of-scope")

    def test_path_claim_without_self_verify(self):
        events = [
            {"class": "lookup", "ok": True},
            {"class": "commit", "ok": True},
            {"class": "finish", "ok": True},
        ]
        flags = compute_path_flags(events, claimed_complete=True)
        self.assertIn("claim_without_self_verify", flags)
        score = path_valid_score(events, claimed_complete=True, live_run=True)
        self.assertFalse(score["path_valid"])

    def test_ablation_skips_self_verify_flag(self):
        events = [
            {"class": "lookup", "ok": True},
            {"class": "commit", "ok": True},
            {"class": "finish", "ok": True},
        ]
        flags = compute_path_flags(
            events, claimed_complete=True, verify_tool_available=False
        )
        self.assertNotIn("claim_without_self_verify", flags)
        score = path_valid_score(
            events,
            claimed_complete=True,
            live_run=True,
            verify_tool_available=False,
        )
        self.assertTrue(score["path_valid"])

    def test_path_clean(self):
        events = [
            {"class": "lookup", "ok": True},
            {"class": "commit", "ok": True},
            {"class": "verify", "ok": True},
            {"class": "finish", "ok": True},
        ]
        score = path_valid_score(events, claimed_complete=True, live_run=True)
        self.assertTrue(score["path_valid"])
        self.assertEqual(score["path_flags"], [])

    def test_claim_after_failed_verify(self):
        events = [
            {"class": "lookup", "ok": True},
            {"class": "commit", "ok": True},
            {"class": "verify", "ok": False},
            {"class": "finish", "ok": True},
        ]
        flags = compute_path_flags(events, claimed_complete=True)
        self.assertIn("claim_after_failed_self_verify", flags)

    def test_offline_not_scored(self):
        score = path_valid_score([], claimed_complete=True, live_run=False)
        self.assertIsNone(score["path_valid"])
        self.assertFalse(score["path_scored"])


if __name__ == "__main__":
    unittest.main()
