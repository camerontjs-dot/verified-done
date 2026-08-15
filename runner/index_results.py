#!/usr/bin/env python3
"""Build results/INDEX.json: one machine-readable list of every run record.

This exists so that published numbers and published figures read from the same
place the runs wrote to. A number in a write-up should be traceable to a row
here, and a figure should be generated from a row here rather than typed by
hand. Hand-copied numbers drift; generated ones cannot.

The index is deliberately thin. It carries identity, outcomes, and enough
provenance to find the full record, and nothing that would go stale.

**It indexes only committed sources.** Raw live-suite output under `results/live/`
is local, gitignored evidence, so indexing it would produce a file nobody else
could regenerate, and CI could not check it for staleness. An index that cannot
be reproduced from the tree is not an integrity mechanism. Live runs reach the
public surface two ways: promoted into a controlled ablation record, or curated
by hand into `results/LIVE_EVIDENCE.md`.
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

RESULTS_DIR = Path(_run.RESULTS_DIR)

INDEX_VERSION = 1


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def index_ablations() -> list[dict[str, Any]]:
    root = RESULTS_DIR / "ablation"
    if not root.is_dir():
        return []
    out = []
    for record_path in sorted(root.glob("*/ablation.json")):
        record = _load(record_path)
        if not record or "experiment" not in record:
            continue
        meta = record["experiment"]
        out.append(
            {
                "kind": "ablation",
                "id": record_path.parent.name,
                "stamp": meta.get("stamp"),
                "adapter": meta.get("adapter"),
                "model": meta.get("model"),
                "task": meta.get("task"),
                "factor": meta.get("factor"),
                "study_type": meta.get("study_type"),
                "n_per_arm": meta.get("n_per_arm"),
                "arms": {
                    arm: {
                        "n": summary.get("n"),
                        "verified_pass": summary.get("verified_pass"),
                        "false_completion": summary.get("false_completion"),
                        "scope_violation": summary.get("scope_violation"),
                        "honestly_abstained": summary.get("honestly_abstained"),
                        "no_claim_reached": summary.get("no_claim_reached"),
                        "pass_k": summary.get("pass_k"),
                        "consistency_claim_supported": summary.get("consistency_claim_supported"),
                        "usage": summary.get("usage"),
                    }
                    for arm, summary in (record.get("arms") or {}).items()
                },
                "record": "results/ablation/%s/ablation.json" % record_path.parent.name,
            }
        )
    return out


def index_screens() -> list[dict[str, Any]]:
    root = RESULTS_DIR / "screens"
    if not root.is_dir():
        return []
    out = []
    for record_path in sorted(root.glob("*/screen.json")):
        record = _load(record_path)
        if not record or "screen" not in record:
            continue
        meta = record["screen"]
        cap = record.get("capability") or {}
        out.append(
            {
                "kind": "screen",
                "id": record_path.parent.name,
                "stamp": meta.get("stamp"),
                "adapter": meta.get("adapter"),
                "model": meta.get("model"),
                "tier": meta.get("tier"),
                "study_type": meta.get("study_type"),
                "capability": {
                    "n": cap.get("n"),
                    "verified_pass": cap.get("verified_pass"),
                    "false_completion": cap.get("false_completion"),
                    "scope_violation": cap.get("scope_violation"),
                    "honestly_abstained": cap.get("honestly_abstained"),
                },
                "honesty": {
                    arm: {
                        "n": s.get("n"),
                        "verified_pass": s.get("verified_pass"),
                        "false_completion": s.get("false_completion"),
                    }
                    for arm, s in (record.get("honesty") or {}).items()
                },
                "verdict": (record.get("verdict") or {}).get("nominate_for_deeper_eval"),
                "record": "results/screens/%s/screen.json" % record_path.parent.name,
            }
        )
    return out


def index_selftest() -> dict[str, Any] | None:
    payload = _load(RESULTS_DIR / "selftest-latest.json")
    if not payload:
        return None
    rows = payload.get("selftest") or []
    scope = payload.get("scope_detection") or {}
    return {
        "kind": "selftest",
        "tasks": len(rows),
        "discriminating": sum(1 for r in rows if r.get("discriminates")),
        "scope_detection_ok": bool(
            scope.get("verify_pass")
            and scope.get("scope_violation")
            and not scope.get("verified_pass")
        ),
    }


def build_index() -> dict[str, Any]:
    return {
        "index_version": INDEX_VERSION,
        "note": (
            "Generated by `python3 runner/run.py index`. Published numbers and "
            "figures should read from this file rather than restate it. Indexes "
            "committed records only, so it is reproducible from the tree."
        ),
        "selftest": index_selftest(),
        "screens": index_screens(),
        "ablations": index_ablations(),
    }


def cmd_board(_args: Any) -> int:
    """Cross-model comparison from every screen and ablation on disk.

    Columns stay separate on purpose. There is no combined score here: a model
    that passes more tasks but lies about the ones it fails is not better, and
    averaging the two would say it is.
    """
    index = build_index()
    screens = index["screens"]
    ablations = index["ablations"]

    if screens:
        print("INTAKE SCREENS (soft tier, small n)\n")
        print("%-26s %-10s %-14s %-12s %-11s %s"
              % ("model", "capability", "false compl.", "scope viol.", "verify-off", "verdict"))
        print("%-26s %-10s %-14s %-12s %-11s %s"
              % ("-" * 26, "-" * 10, "-" * 14, "-" * 12, "-" * 11, "-" * 12))
        for row in screens:
            cap = row["capability"]
            off = (row.get("honesty") or {}).get("verify-off") or {}
            off_txt = ("%s/%s" % (off.get("false_completion"), off.get("n"))) if off else "-"
            print("%-26s %-10s %-14s %-12s %-11s %s"
                  % (
                      row["model"][:26],
                      "%s/%s" % (cap.get("verified_pass"), cap.get("n")),
                      "%s/%s" % (cap.get("false_completion"), cap.get("n")),
                      "%s/%s" % (cap.get("scope_violation"), cap.get("n")),
                      off_txt,
                      "nominate" if row.get("verdict") else "do not advance",
                  ))
        print("\ncapability = verified passes over the demo split, verify tool on.")
        print("verify-off = false completions on the two-file task with the tool removed.")

    if ablations:
        print("\n\nCONTROLLED ABLATIONS (higher n)\n")
        print("%-26s %-24s %-16s %s" % ("model", "task", "arm", "verified pass / false completion"))
        print("%-26s %-24s %-16s %s" % ("-" * 26, "-" * 24, "-" * 16, "-" * 32))
        for row in ablations:
            for arm, s in (row.get("arms") or {}).items():
                print("%-26s %-24s %-16s %s / %s"
                      % (row["model"][:26], row["task"][:24], arm,
                         "%s/%s" % (s.get("verified_pass"), s.get("n")),
                         "%s/%s" % (s.get("false_completion"), s.get("n"))))

        print("\n\nCONSISTENCY (pass^k: all k trials succeed)\n")
        print("%-26s %-16s %8s %8s %8s %8s" % ("model", "arm", "pass^1", "pass^2", "pass^4", "pass^8"))
        print("%-26s %-16s %8s %8s %8s %8s" % ("-" * 26, "-" * 16, "-" * 8, "-" * 8, "-" * 8, "-" * 8))
        for row in ablations:
            for arm, s in (row.get("arms") or {}).items():
                pk = s.get("pass_k") or {}
                cells = []
                for k in (1, 2, 4, 8):
                    v = pk.get("pass^%d" % k)
                    # "unmeasured" is not zero. n below k means we never looked.
                    cells.append("%.2f" % v if v is not None else "  n/a")
                print("%-26s %-16s %8s %8s %8s %8s"
                      % (row["model"][:26], arm, *cells))
        print("\nn/a means k exceeded the replicate count: unmeasured, not failed.")

    if not screens and not ablations:
        print("no screens or ablations on disk yet")
    return 0


def cmd_index(_args: Any) -> int:
    index = build_index()
    path = RESULTS_DIR / "INDEX.json"
    path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    selftest = index.get("selftest")
    if selftest:
        print(
            "selftest: %d/%d tasks discriminate, scope detection %s"
            % (
                selftest["discriminating"],
                selftest["tasks"],
                "ok" if selftest["scope_detection_ok"] else "BROKEN",
            )
        )
    print("ablations: %d" % len(index["ablations"]))
    for row in index["ablations"]:
        arms = row.get("arms") or {}
        parts = [
            "%s fc=%s/%s" % (arm, s.get("false_completion"), s.get("n"))
            for arm, s in arms.items()
        ]
        print("  %s %s  %s" % (row["model"], row["task"], "  ".join(parts)))
    print("\nwrote results/INDEX.json")
    return 0
