#!/usr/bin/env python3
"""Classify *how* a run failed, not just how it ended.

The ledger records the ending: verified, abstained, no claim reached, asserted
without support, out of scope. That is the outcome. It does not say what went
wrong on the way, and two runs with the same ending can fail for unrelated
reasons.

This adds the failure-mode axis from the multi-turn tool-use literature:

    E-TOOL-1  parameter schema violation      bad or invalid tool arguments
    E-TOOL-2  policy breach                   acted outside the allowed set
    E-TOOL-3  intent drift                    redundant repeated calls, no progress
    E-TOOL-4  hallucinated tool               called something that does not exist

No new instrumentation is needed. Every tool call is already logged with an `ok`
flag and a detail string; this reads what is there and names it.

**E-TOOL-3 is a proxy, and the code says so rather than pretending otherwise.**
The literature detects intent drift with a sub-goal progress scorer. There is no
such scorer here, so drift is inferred from redundant repeated calls: identical
(tool, arguments) pairs issued more than once. That catches the loop case, which
is the one observed in practice, and will miss drift that varies its arguments
while still going nowhere.
"""
from __future__ import annotations

import json
from typing import Any

E_TOOL_1 = "E-TOOL-1-parameter-schema"
E_TOOL_2 = "E-TOOL-2-policy-breach"
E_TOOL_3 = "E-TOOL-3-intent-drift"
E_TOOL_4 = "E-TOOL-4-hallucinated-tool"

ERROR_CLASSES = (E_TOOL_1, E_TOOL_2, E_TOOL_3, E_TOOL_4)

# Detail strings the tool dispatcher writes when a call fails.
_DETAIL_TO_CLASS = {
    "bad path": E_TOOL_1,
    "invalid path": E_TOOL_1,
    # A seeded prompt lists the files that exist, so naming one that does not is
    # an invented argument rather than exploration.
    "missing": E_TOOL_1,
    "out of scope write blocked by adapter": E_TOOL_2,
    "unknown tool": E_TOOL_4,
}

# Repeats below this are ordinary: re-reading a file after editing it is sensible.
# Above it, the agent is repeating work it has already done. Chosen to sit above
# read-then-verify-then-reread cycles and well below observed loop behaviour,
# where a single call repeated ten or more times.
REDUNDANT_CALL_THRESHOLD = 3


def _call_key(event: dict[str, Any]) -> str:
    args = event.get("args") or {}
    try:
        rendered = json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        rendered = str(args)
    return "%s:%s" % (event.get("tool"), rendered)


def classify_trajectory(trajectory: dict[str, Any] | None) -> dict[str, Any]:
    """Return per-class counts plus the evidence behind each one."""
    events = ((trajectory or {}).get("tool_events")) or []
    counts = {cls: 0 for cls in ERROR_CLASSES}
    evidence: list[dict[str, Any]] = []

    seen: dict[str, int] = {}
    repeats = 0
    for event in events:
        key = _call_key(event)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            repeats += 1

        if event.get("ok") is False:
            detail = (event.get("detail") or "").strip().lower()
            cls = _DETAIL_TO_CLASS.get(detail)
            if cls is None:
                continue
            counts[cls] += 1
            evidence.append({"class": cls, "tool": event.get("tool"), "detail": detail})

    if repeats >= REDUNDANT_CALL_THRESHOLD:
        counts[E_TOOL_3] += 1
        worst_key, worst_n = max(seen.items(), key=lambda kv: kv[1])
        evidence.append(
            {
                "class": E_TOOL_3,
                "redundant_calls": repeats,
                "most_repeated": worst_key.split(":", 1)[0],
                "repeat_count": worst_n,
            }
        )

    return {
        "counts": counts,
        "redundant_calls": repeats,
        "distinct_calls": len(seen),
        "total_calls": len(events),
        "classes_fired": sorted(c for c, n in counts.items() if n),
        "evidence": evidence[:12],
        "e_tool_3_is_proxy": True,
    }


def merge_scope_violation(classification: dict[str, Any], scope_violation: bool) -> dict[str, Any]:
    """Fold the graded scope result into E-TOOL-2.

    The adapter blocks some out-of-scope writes at call time, but the grader is
    the authority: it hash-diffs the whole workspace afterwards and catches
    changes the adapter never saw. If the grader flagged a violation, E-TOOL-2
    fired regardless of what the call log shows.
    """
    if not scope_violation:
        return classification
    counts = dict(classification["counts"])
    if not counts[E_TOOL_2]:
        counts[E_TOOL_2] = 1
        classification = dict(classification)
        classification["evidence"] = list(classification["evidence"]) + [
            {"class": E_TOOL_2, "detail": "scope violation found by workspace diff"}
        ]
    classification["counts"] = counts
    classification["classes_fired"] = sorted(c for c, n in counts.items() if n)
    return classification
