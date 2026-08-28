"""Keep the code the agent actually wrote, instead of throwing it away.

## The gap this fills

Every live run copies the task's starting workspace to a temp dir, lets an agent
edit it, scores it against an external verifier, and then deletes it. What
survived was the *verdict* — `verify_pass`, `false_completion`, `changed_files`,
the verifier's stderr — and never the code.

118 runs had happened that way, 107 of them failing. Each failure was a piece of
AI-written code broken in a known way, with a reference solution stating what
correct looks like and a deterministic verifier that had already ruled on it.
That is a labelled defect specimen, and 107 of them were `rmtree`-d.

Human-written defect corpora (QuixBugs, BugsInPy) are typos and off-by-ones.
Those are not what models get wrong, so a corpus of what models actually get
wrong has to be built, and this bench was already producing one as exhaust.

## Passes are kept too, and they are not filler

A defect corpus with no negative class cannot distinguish "this layer detects
defects" from "this layer rejects everything". The passing runs are the control
set that makes a false-rejection rate measurable at all, which is the metric the
generated-code-assurance work promoted to co-primary. Keeping only failures would
build a corpus that can only ever confirm.

## The diff is the artifact

The workspace tree is kept because it is 8 KB and re-deriving it is impossible,
but `diff.patch` against the task's starting state is what is actually readable:
it is exactly what the model changed, with everything it left alone removed.

## The directory names are honesty labels, not correctness labels

A specimen's directory is its ledger class, and the ledger classifies what the
agent did, not whether the code works. `honestly-abstained` and
`false-completion` both hold programs the verifier rejected; they differ only in
whether the agent claimed to be finished. `pass` is the only class that means
the code is correct.

Anything consuming this corpus as a labelled dataset must take ground truth from
`verify_pass` in `specimen.json`, never from the path. Reading `false-completion/`
as "the defects" silently drops every defect the agent was honest about, and
scoring a detector that correctly flags those as false positives inverts the
result on exactly the metric a false-rejection ceiling is measured against.

## Not published by default

`results/specimens/` is gitignored, for the same reason `results/mutants/` is: a
public corpus of task solutions is a public corpus of task solutions, and this
bench's whole argument is that a memorized instrument is not an instrument. A
release, if there is one, is a deliberate act with its own contamination note —
not a side effect of running the suite.
"""
from __future__ import annotations

import difflib
import json
import os
import shutil
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SPECIMENS_DIR = REPO / "results" / "specimens"
TASKS_DIR = REPO / "tasks"

# Text files only. A specimen is for reading a diff, and a binary blob in a patch
# is noise that also makes the record non-reviewable.
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".cfg", ".ini", ".yaml", ".yml", ""}


def _text_files(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = str(path.relative_to(root))
        if rel.startswith("_verify") or "__pycache__" in rel:
            continue
        try:
            out[rel] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return out


def build_patch(task_id: str, workspace: str | os.PathLike[str]) -> str:
    """Unified diff from the task's starting state to what the agent produced."""
    start = TASKS_DIR / task_id / "workspace"
    if not start.is_dir():
        return ""
    before, after = _text_files(start), _text_files(Path(workspace))

    chunks: list[str] = []
    for rel in sorted(set(before) | set(after)):
        a = before.get(rel, "").splitlines(keepends=True)
        b = after.get(rel, "").splitlines(keepends=True)
        if a == b:
            continue
        chunks.extend(
            difflib.unified_diff(
                a, b, fromfile=f"a/{rel}", tofile=f"b/{rel}", n=3
            )
        )
    return "".join(chunks)


# The corpus directory each ledger label files under. The ledger's own taxonomy,
# not a re-derivation of it: `runner/ledger.py` already worked out these
# distinctions and wrote down why, and a second classifier that disagrees with it
# is a second source of truth about what a run was.
LEDGER_TO_OUTCOME = {
    "out-of-scope": "scope-violation",
    "unsupported-assertion": "false-completion",
    "verified-supported": "pass",
    "honestly-abstained": "honestly-abstained",
    "no-claim-reached": "no-claim-reached",
}

# A run the adapter had to kill measured nothing about the model. Filed apart
# from every behavioural class so it can be counted and excluded, never summed
# into a defect rate.
NOT_ASSESSABLE = "not-assessable"


def outcome_of(result: dict[str, Any]) -> str:
    """The specimen's class, taken from the ledger label the run already carries.

    Not a pass/fail bit, and deliberately not a three-way one either. A corpus
    that sorts runs into `pass` and `fail` merges three different things under
    the second:

    - the agent broke the code and said it was done (`unsupported-assertion`) —
      the defect this bench exists to catch;
    - the agent could not finish and said so (`honestly-abstained`) — which
      `ledger.py` calls a *positive* outcome, because it is the behaviour the
      whole argument wants more of;
    - the run never reached a claim at all (`no-claim-reached`) — a turn budget
      running out, or the adapter erroring.

    Filing an honest abstention in a defect corpus mislabels the one behaviour
    the bench rewards. Filing an adapter crash there invents a defect that no
    model committed. This bench has already been bitten by the second: the
    2026-08-13 changelog voids Finding C because every `qwen3.5:9b` run ended at
    `max turns`, which the harness of the day recorded as honest abstention.

    Adapter errors are separated further, into `not-assessable`. `ledger.py`
    says to exclude them from behavioural analysis rather than read them as a
    result, and a corpus directory is where that instruction either holds or
    quietly stops holding.
    """
    label = result.get("ledger_label")
    if label in LEDGER_TO_OUTCOME:
        if label == "no-claim-reached" and "reason:adapter_error" in (
            result.get("ledger_flags") or ()
        ):
            return NOT_ASSESSABLE
        return LEDGER_TO_OUTCOME[label]

    # No ledger label: a caller predating the taxonomy. Fall back to the legacy
    # columns, which stay first-class per METHODOLOGY. This cannot recover the
    # abstained/no-claim split — those look identical in booleans alone — so it
    # says `unresolved` rather than guessing `fail` and inventing a defect.
    if result.get("scope_violation"):
        return "scope-violation"
    if result.get("false_completion"):
        return "false-completion"
    if result.get("verified_pass") or result.get("verify_pass"):
        return "pass"
    return "unresolved"


def retain(
    task_id: str,
    workspace: str | os.PathLike[str],
    result: dict[str, Any],
    *,
    stamp: str,
    label: str = "",
) -> Path | None:
    """Copy one scored workspace into the specimen corpus. Returns its directory.

    Called before the workspace is removed. Never raises into the caller: losing a
    specimen must not fail a run that otherwise succeeded, because that would make
    the corpus a reliability risk for the bench it is a byproduct of.
    """
    try:
        workspace = Path(workspace)
        if not workspace.is_dir():
            return None

        outcome = outcome_of(result)
        model = str(result.get("served_model") or result.get("model_requested") or "unknown")
        safe_model = "".join(c if c.isalnum() or c in "-._" else "-" for c in model)
        dest = SPECIMENS_DIR / task_id / outcome / f"{stamp}-{safe_model}"
        if label:
            dest = dest.parent / f"{dest.name}-{label}"
        dest.mkdir(parents=True, exist_ok=True)

        shutil.copytree(
            workspace,
            dest / "workspace",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "_verify.py", ".*"),
        )

        patch = build_patch(task_id, workspace)
        (dest / "diff.patch").write_text(patch, encoding="utf-8")

        (dest / "specimen.json").write_text(
            json.dumps(
                {
                    "schema_version": "verified-done-specimen-v1",
                    "task": task_id,
                    "category": result.get("category"),
                    "outcome": outcome,
                    "stamp": stamp,
                    "adapter": result.get("adapter"),
                    "model_requested": result.get("model_requested"),
                    "served_model": result.get("served_model"),
                    "enable_verify_tool": result.get("enable_verify_tool"),
                    # The labels an external verifier produced, not the agent's view.
                    "verify_pass": result.get("verify_pass"),
                    "verified_pass": result.get("verified_pass"),
                    "claimed_complete": result.get("claimed_complete"),
                    "false_completion": result.get("false_completion"),
                    "scope_violation": result.get("scope_violation"),
                    "ledger_label": result.get("ledger_label"),
                    # The flags carry the no-claim reason, which is the only
                    # thing separating a turn budget running out from an adapter
                    # crash. Without it the `not-assessable` split cannot be
                    # re-derived from the record.
                    "ledger_flags": result.get("ledger_flags"),
                    "changed_files": result.get("changed_files"),
                    "out_of_scope_files": result.get("out_of_scope_files"),
                    "patch_bytes": len(patch),
                    "patch_empty": not patch.strip(),
                    # Ground truth lives with the task, not in here: the reference
                    # solution and the verifier are the corpus's answer key, and
                    # copying them next to the specimen would let a reader train on
                    # the answer while thinking they were reading the question.
                    "reference": f"tasks/{task_id}/",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return dest
    except Exception:  # noqa: BLE001 - see docstring: never fail the run
        return None

def audit_retention(since: str = "20260827") -> dict[str, Any]:
    """Compare runs recorded against specimens kept, per task.

    `retain` swallows every exception so that losing a specimen cannot fail a
    run. That is the right trade, but it makes the failure silent: a permissions
    problem or a full disk would drop specimens indefinitely and the only
    evidence would be a corpus quietly smaller than the record. This is the
    check that makes it loud again, and it belongs with the code that takes the
    risk rather than in someone's shell history.

    `since` is the retention start date, because runs older than it were scored
    before any of this existed and have no specimen by design.
    """
    runs: dict[str, int] = {}
    for d in sorted((REPO / "results" / "ablation").iterdir()):
        if not d.is_dir() or d.name[:8] < since:
            continue
        record = d / "ablation.json"
        if not record.is_file():
            continue
        try:
            rows = json.loads(record.read_text(encoding="utf-8")).get("runs", [])
        except (json.JSONDecodeError, OSError):
            continue
        for r in rows:
            task = r.get("task")
            if task:
                runs[task] = runs.get(task, 0) + 1

    kept: dict[str, int] = {}
    for spec in SPECIMENS_DIR.rglob("specimen.json"):
        try:
            task = json.loads(spec.read_text(encoding="utf-8")).get("task")
        except (json.JSONDecodeError, OSError):
            continue
        if task:
            kept[task] = kept.get(task, 0) + 1

    missing = {t: runs[t] - kept.get(t, 0) for t in runs if kept.get(t, 0) < runs[t]}
    return {
        "runs": runs,
        "kept": kept,
        "missing": missing,
        "ok": not missing,
    }


if __name__ == "__main__":
    report = audit_retention()
    for task in sorted(set(report["runs"]) | set(report["kept"])):
        r, k = report["runs"].get(task, 0), report["kept"].get(task, 0)
        note = "" if r == k else "   <-- specimens missing"
        print(f"{task:32s} runs={r:4d} kept={k:4d}{note}")
    if report["ok"]:
        print("\nretention audit: clean, every recorded run kept a specimen")
    else:
        print(f"\nretention audit: {sum(report['missing'].values())} specimen(s) lost")
    raise SystemExit(0 if report["ok"] else 1)
