#!/usr/bin/env python3
"""Dynamic task mutation, so a public benchmark can stay a benchmark.

Publishing an instrument is what makes a finding checkable by someone else. It
is also what lets the next model train on it. These eight tasks have been public
since 2026-08-08, and a static suite's scores drift upward as models memorize it.

Mutation resolves that rather than trading one against the other. The *generator*
stays public and reproducible; each run's *instance* is freshly derived. A reader
can regenerate any instance from its seed and re-run the experiment, while no
fixed text sits in a crawler's reach long enough to be memorized.

Two transforms are applied, both from the contamination literature:

    M-AST-1  identifier perturbation   rename user-defined symbols
    M-VAL-3  boundary value shift      move authored numeric constants

M-FLOW-4 (control-flow permutation) is deliberately not implemented. The same
literature warns that heavier rewrites drift task semantics, and the value it
adds does not justify the risk of silently changing what a task tests.

**Every mutation passes the same gate the static suite passes**: the mutated
start state must fail its verifier and the mutated reference solution must pass.
A mutation that cannot clear that gate is rejected and the original is used, so a
mutant can never quietly become an easier or impossible task.

Renaming works on token positions rather than an AST round-trip. `ast.unparse`
would discard comments and reformat code, changing what the agent reads for
reasons unrelated to the mutation. Rewriting exact source spans touches only the
identifiers, and `tokenize` distinguishes a NAME token from the same characters
inside a string or comment.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import shutil
import sys
import tokenize
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib  # noqa: E402

if "__main__" in sys.modules and hasattr(sys.modules["__main__"], "grade_workspace"):
    _run = sys.modules["__main__"]
else:
    _run = importlib.import_module("run")

TASKS_DIR = Path(_run.TASKS_DIR)
RESULTS_DIR = Path(_run.RESULTS_DIR)

CANARY_PREFIX = "VERIFIED_DONE_CANARY"

# Never rename these: they cross the boundary to the stdlib, the runner, or the
# task contract, and renaming them changes what the task is rather than how it
# is spelled.
PROTECTED_NAMES = frozenset(
    {
        "self", "cls", "__init__", "__name__", "__main__", "__file__",
        "main", "sys", "os", "json", "math", "re", "decimal", "Decimal",
        "ROUND_HALF_UP", "dataclass", "field", "typing", "Any", "List", "Dict",
        "Optional", "assert_equal", "print", "len", "range", "int", "float",
        "str", "bool", "list", "dict", "set", "tuple", "round", "abs", "sum",
        "sorted", "enumerate", "zip", "min", "max", "isinstance", "type",
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    }
)


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def canary_for(task_id: str, seed: int) -> str:
    return "%s_%s" % (CANARY_PREFIX, _digest(task_id, str(seed), "canary")[:16].upper())


def collect_renamable(source: str) -> set[str]:
    """User-defined symbols in a module: functions, classes, args, assignments.

    Imported names are excluded. Renaming an import breaks the import, and a
    symbol that came from elsewhere is not this task's to rename.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    names: set[str] = set()
    imported: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imported.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                names.add(arg.arg)
            if node.args.vararg:
                names.add(node.args.vararg.arg)
            if node.args.kwarg:
                names.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)

    return {n for n in names - imported - PROTECTED_NAMES if not n.startswith("__")}


def build_rename_map(
    names: set[str],
    task_id: str,
    seed: int,
    protected: frozenset[str] | set[str] = frozenset(),
) -> dict[str, str]:
    """Deterministic new spelling per symbol, stable for a given seed.

    `protected` carries names that must keep their spelling even though they
    look renamable. Module stems are the important case: a task often defines a
    function with the same name as its file, as in `checkout.py` holding
    `def checkout`. Renaming the symbol rewrites `from checkout import checkout`
    on both sides while the file on disk keeps its name, and the import fails.
    File names are fixed by `allowed_files` in the task contract, so the symbol
    is what has to stay put.
    """
    mapping = {}
    for name in sorted(names - set(protected)):
        suffix = _digest(task_id, str(seed), name)[:6]
        mapping[name] = "%s_%s" % (name, suffix)
    return mapping


def apply_renames(source: str, mapping: dict[str, str]) -> str:
    """Rewrite NAME tokens in place, leaving strings, comments and layout alone."""
    if not mapping:
        return source
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        return source

    lines = source.splitlines(keepends=True)
    # Offsets shift as replacements are applied, so rewrite back to front.
    edits = []
    for tok in tokens:
        if tok.type != tokenize.NAME:
            continue
        new = mapping.get(tok.string)
        if new is None:
            continue
        edits.append((tok.start, tok.end, new))

    for (srow, scol), (erow, ecol), new in sorted(edits, reverse=True):
        if srow != erow:  # a NAME never spans lines
            continue
        line = lines[srow - 1]
        lines[srow - 1] = line[:scol] + new + line[ecol:]
    return "".join(lines)


def _shift_constants(source: str, spec: list[dict[str, Any]]) -> str:
    """M-VAL-3, driven by authored replacements only.

    Boundary values are not mutated automatically. A verifier's expected result
    usually depends on the constant, so blind perturbation breaks the ground
    truth and the gate rejects every candidate. Tasks opt in by declaring exact
    from/to pairs in `task.json`, which keeps the semantics a human decision.
    """
    for item in spec:
        frm, to = str(item.get("from")), str(item.get("to"))
        if frm and to:
            source = source.replace(frm, to)
    return source


def _python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.name != "_verify.py")


def mutate_task(task_id: str, seed: int, dest_root: Path) -> dict[str, Any]:
    """Write a mutated copy of one task. Returns metadata; does not gate."""
    src = TASKS_DIR / task_id
    dest = dest_root / task_id
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    task = json.loads((dest / "task.json").read_text(encoding="utf-8"))

    # One rename map for the whole task: workspace, solution and verifier must
    # agree, or the verifier stops matching the code it grades.
    names: set[str] = set()
    targets = _python_files(dest / "workspace") + _python_files(dest / "solution")
    verify_path = dest / "verify.py"
    for path in targets:
        names |= collect_renamable(path.read_text(encoding="utf-8"))

    # Module stems are part of the task contract and cannot move with the symbol.
    module_stems = {p.stem for p in targets} | {
        Path(rel).stem for rel in task.get("allowed_files", [])
    }
    mapping = build_rename_map(names, task_id, seed, protected=module_stems)
    const_spec = task.get("mutable_constants") or []

    for path in targets + ([verify_path] if verify_path.exists() else []):
        text = path.read_text(encoding="utf-8")
        text = apply_renames(text, mapping)
        text = _shift_constants(text, const_spec)
        path.write_text(text, encoding="utf-8")

    canary = canary_for(task_id, seed)
    prompt = task.get("prompt", "")
    for old, new in mapping.items():
        # Keep the prompt describing the code the agent will actually see.
        prompt = prompt.replace(old, new)
    task["prompt"] = prompt
    task["mutation"] = {
        "seed": seed,
        "transforms": ["M-AST-1"] + (["M-VAL-3"] if const_spec else []),
        "renamed_symbols": len(mapping),
        "instance_id": canary,
        "source_task": task_id,
        # Renaming hands us a contamination detector for free, and a sharper one
        # than an injected token. Nothing in a mutated instance uses the original
        # spellings, so an agent that writes them was not reading the code in
        # front of it. Seeing `def total(` in a workspace whose every reference
        # says `total_d7342d` is memorization, observed directly.
        "contamination_tripwires": sorted(mapping.keys()),
    }
    (dest / "task.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")

    return {
        "task": task_id,
        "seed": seed,
        "path": dest,
        "renamed_symbols": len(mapping),
        "rename_map": mapping,
        "canary": canary,
        "constants_shifted": len(const_spec),
    }


def gate_mutation(task_id: str, mutated_root: Path) -> dict[str, Any]:
    """The mutated start state must fail and the mutated solution must pass.

    This is the same discrimination check the static suite runs. Without it a
    rename could quietly produce a task that is trivially passed or impossible,
    and the score would move for a reason unrelated to the model.
    """
    original_tasks_dir = _run.TASKS_DIR
    _run.TASKS_DIR = str(mutated_root)
    try:
        row = _run.selftest_one(task_id)
    finally:
        _run.TASKS_DIR = original_tasks_dir
    return {
        "task": task_id,
        "start_fails": row["start_fails"],
        "solution_passes": row["solution_passes"],
        "discriminates": row["discriminates"],
        "solution_output": row.get("solution_output", ""),
    }


def detect_contamination(text: str, tripwires: list[str], mapping_values: list[str]) -> list[str]:
    """Original symbol names appearing in agent output for a mutated instance.

    A hit is evidence the model is reproducing remembered code rather than
    reading the workspace. Names that are also substrings of their mutated form
    are ignored, since `total_d7342d` contains `total` and would match trivially.
    """
    hits = []
    for name in tripwires:
        scrubbed = text
        for mutated in mapping_values:
            scrubbed = scrubbed.replace(mutated, "")
        if name in scrubbed:
            hits.append(name)
    return hits


def cmd_mutate(args: Any) -> int:
    tasks = [args.task] if args.task else _run.discover_tasks()
    dest_root = Path(args.out) if args.out else RESULTS_DIR / "mutants" / ("seed-%d" % args.seed)
    dest_root.mkdir(parents=True, exist_ok=True)

    print("mutating %d task(s) at seed %d" % (len(tasks), args.seed))
    print("output: %s" % dest_root)

    rows, rejected = [], []
    for task_id in tasks:
        info = mutate_task(task_id, args.seed, dest_root)
        gate = gate_mutation(task_id, dest_root)
        info["gate"] = gate
        rows.append(info)
        status = "ok" if gate["discriminates"] else "REJECTED"
        print(
            "  %-28s symbols=%-3d %s"
            % (task_id, info["renamed_symbols"], status)
        )
        if not gate["discriminates"]:
            rejected.append(task_id)
            # A mutant that does not discriminate is not usable. Remove it so it
            # cannot be picked up by a later run.
            shutil.rmtree(info["path"], ignore_errors=True)
            if gate["solution_output"]:
                print("      solution failed: %s" % gate["solution_output"][:160])

    manifest = {
        "seed": args.seed,
        "transforms": ["M-AST-1", "M-VAL-3 (authored only)", "M-DOC-2 canary"],
        "accepted": [r["task"] for r in rows if r["gate"]["discriminates"]],
        "rejected": rejected,
        "instance_ids": {r["task"]: r["canary"] for r in rows if r["gate"]["discriminates"]},
        "renamed_symbols": {r["task"]: r["renamed_symbols"] for r in rows},
        "contamination_tripwires": {
            r["task"]: sorted(r["rename_map"].keys())
            for r in rows
            if r["gate"]["discriminates"]
        },
        "gate": "mutated start must fail and mutated solution must pass",
        "reproduce": "python3 runner/run.py mutate --seed %d" % args.seed,
    }
    (dest_root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    ok = len(manifest["accepted"])
    print("\n%d/%d mutants passed the gate" % (ok, len(tasks)))
    if rejected:
        print("rejected (originals remain authoritative): %s" % ", ".join(rejected))
    print("manifest: %s" % (dest_root / "MANIFEST.json"))
    return 0 if ok else 1
