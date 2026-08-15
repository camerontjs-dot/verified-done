#!/usr/bin/env python3
"""Re-derive ledger labels on existing records after a label-space change.

Grades are computed from stored fields, so a change to `map_ledger_label` means
records written earlier carry labels the current code would not produce. Leaving
them is worse than a cosmetic inconsistency: the board and the index read those
labels, so a stale record keeps publishing the exact claim the change corrected.

This walks the records, recomputes each run's label from its stored grade
fields, and rewrites the compact record and arm summaries in place. It never
re-runs an agent and never changes an outcome. Only the label mapping moves, so
a regrade cannot turn a failure into a pass.

Raw rows under `runs/` are preferred because they carry every field. They are
gitignored, so on a fresh clone this falls back to the compact rows, which is
enough whenever no scope violation is involved. Records it cannot regrade are
reported rather than silently skipped.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib  # noqa: E402

if "__main__" in sys.modules and hasattr(sys.modules["__main__"], "grade_workspace"):
    _run = sys.modules["__main__"]
else:
    _run = importlib.import_module("run")

from ablation import summarize_arm, summarize_cost  # noqa: E402
from ledger import map_ledger_label  # noqa: E402

RESULTS_DIR = Path(_run.RESULTS_DIR)


def _relabel(fields: dict[str, Any]) -> dict[str, Any]:
    return map_ledger_label(
        verify_pass=bool(fields["verify_pass"]),
        scope_violation=bool(fields["scope_violation"]),
        claimed_complete=bool(fields["claimed_complete"]),
        finish_status=fields.get("finish_status"),
        finish_note=fields.get("finish_note"),
    )


def _fields_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    observe = raw.get("observe") or {}
    return {
        "verify_pass": raw.get("verify_pass"),
        "scope_violation": raw.get("scope_violation"),
        "claimed_complete": raw.get("claimed_complete"),
        "finish_status": observe.get("finish_status") or raw.get("finish_status"),
        "finish_note": observe.get("finish_note") or raw.get("finish_note"),
    }


def _fields_from_compact(row: dict[str, Any]) -> dict[str, Any] | None:
    """Recover grade fields from a compact row, or None if ambiguous.

    verified_pass folds together "the verifier passed" and "the agent stayed in
    scope". When a scope violation fired, the verifier result is unrecoverable,
    so the caller needs the raw row instead of a guess.
    """
    if row.get("scope_violation"):
        return None
    claimed = bool(row.get("false_completion")) or bool(row.get("verified_pass"))
    return {
        "verify_pass": bool(row.get("verified_pass")),
        "scope_violation": False,
        "claimed_complete": claimed,
        "finish_status": row.get("finish_status"),
        "finish_note": row.get("finish_note"),
    }


def _regrade_record(record_path: Path, runs_key: str, apply: bool) -> dict[str, Any]:
    record = json.loads(record_path.read_text(encoding="utf-8"))
    raw_dir = record_path.parent / "runs"
    raw_rows = sorted(raw_dir.glob("*.json")) if raw_dir.is_dir() else []
    raw_by_index = {}
    for i, path in enumerate(raw_rows):
        try:
            raw_by_index[i] = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue

    changes, skipped = [], 0
    for i, row in enumerate(record.get(runs_key) or []):
        fields = _fields_from_raw(raw_by_index[i]) if i in raw_by_index else _fields_from_compact(row)
        if fields is None or fields.get("verify_pass") is None:
            skipped += 1
            continue
        new = _relabel(fields)
        old_label = row.get("ledger_label")
        if new["ledger_label"] != old_label:
            changes.append((i, old_label, new["ledger_label"]))
            if apply:
                row["ledger_label"] = new["ledger_label"]
                row.setdefault("ledger_flags", new["ledger_flags"])
                if fields.get("finish_note") and not row.get("finish_note"):
                    row["finish_note"] = fields["finish_note"]

    # Summaries are always recomputed, not only when a label moved. A summary
    # gains fields over time (pass^k and token usage arrived after the first
    # records were written), and a record left on the old shape reports those
    # metrics as missing forever. Recomputing from the stored rows is safe: the
    # rows are the evidence, and the summary is derived from them.
    rows = record.get(runs_key) or []
    resummarized = False
    if rows:
        if runs_key == "runs":  # ablation: rows carry their arm
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                grouped.setdefault(row["arm"], []).append(row)
            fresh = {arm: summarize_arm(r) for arm, r in grouped.items()}
            key = "arms"
        else:  # screen: capability rows are one bucket
            fresh = summarize_arm(rows)
            key = "capability"
        if record.get(key) != fresh:
            resummarized = True
            if apply:
                record[key] = fresh
        # Cost is derived from the arm summaries, so it is recomputed from the
        # fresh ones rather than the stored block. On a record written before
        # token capture worked this correctly resolves to unavailable instead of
        # inventing a baseline out of zeros.
        if key == "arms":
            cost = summarize_cost(fresh)
            if record.get("cost") != cost:
                resummarized = True
                if apply:
                    record["cost"] = cost

    if apply and (changes or resummarized):
        record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    return {
        "path": record_path,
        "changes": changes,
        "skipped": skipped,
        "resummarized": resummarized,
    }


def cmd_regrade(args: Any) -> int:
    apply = bool(getattr(args, "apply", False))
    targets = []
    for pattern, key in (("ablation/*/ablation.json", "runs"), ("screens/*/screen.json", "capability_runs")):
        targets.extend((p, key) for p in sorted(RESULTS_DIR.glob(pattern)))

    if not targets:
        print("no records found")
        return 0

    total_changes = total_skipped = total_resummarized = 0
    for path, key in targets:
        try:
            result = _regrade_record(path, key, apply)
        except (OSError, ValueError) as exc:
            print("%s: could not read (%s)" % (path.parent.name, exc))
            continue
        total_changes += len(result["changes"])
        total_skipped += result["skipped"]
        if result["resummarized"]:
            total_resummarized += 1
            if not result["changes"]:
                print("%s: summary refreshed to the current metric set" % path.parent.name)
        if result["changes"]:
            print("%s: %d label change(s)" % (path.parent.name, len(result["changes"])))
            for i, old, new in result["changes"][:6]:
                print("    run %-3d %-22s -> %s" % (i + 1, old, new))
            if len(result["changes"]) > 6:
                print("    ... %d more" % (len(result["changes"]) - 6))
        if result["skipped"]:
            print("%s: %d run(s) not regradable without raw rows" % (path.parent.name, result["skipped"]))

    if not total_changes and not total_resummarized:
        print("every record already matches the current label mapping and metric set")
    elif apply:
        print("\napplied %d label change(s), refreshed %d summary/summaries. "
              "Re-run `index` to update the roll-up." % (total_changes, total_resummarized))
    else:
        print("\n%d label change(s) and %d summary refresh(es) pending. "
              "Re-run with --apply to write them." % (total_changes, total_resummarized))
    if total_skipped:
        print("%d run(s) skipped: raw rows missing and the compact row was ambiguous." % total_skipped)
    return 0
