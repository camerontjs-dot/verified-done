# Task authoring standard (verified-done)

Published task-quality bar, generalized from the selftest and aligned with Terminal-Bench-style authoring standards. Every demo-split task must pass this checklist before merge. Direction-2 claim authoring reuses the same principles (see twin and critic rules below).

## Required properties

### 1. Specificity

- [ ] Prompt states the observable end state (what must be true after the change).
- [ ] Allowed files are listed explicitly; nothing outside that set is required.
- [ ] No hidden dependencies on unstated environment or network.

### 2. Solvability

- [ ] A reference solution exists under `solution/` and is minimal.
- [ ] Selftest: start workspace **fails** the verifier; solution overlay **passes**.
- [ ] A competent human can solve from the prompt alone in under ~15 minutes.

### 3. Integrity (verifier)

- [ ] Verifier is deterministic (exit code only; no LLM).
- [ ] Verifier runs in a disposable copy; never mutates the task tree.
- [ ] Cheap hard-code passes are hard (prefer behavioral checks over string equality on the whole file).
- [ ] Scope: at least one task in the suite proves scope detection (allowed set is real).

### 4. Honesty surface

- [ ] Category is one of the six published categories (see METHODOLOGY.md).
- [ ] Two-file and scope-restraint tasks are preferred for honesty stress; do not flood the suite with only mechanical edits.
- [ ] Claim channel is independent: grading never infers "done" from a passing verifier alone.

### 5. Twin / contrastive rule (construction invariant)

Where the suite tests a labeled behavior, prefer pairs:

- [ ] **Scope twin:** same fix, but one variant tempts an edit outside `allowed_files`.
- [ ] **Honesty twin:** task that is easy to half-finish (two-file) vs fully specified single-file.

For the document surface (direction-2), the hard rule is stronger: **every claim must have a twin where the gold label flips** under a single controlled perturbation (near-miss passage, version swap, or deviation removal), so always-supported / always-insufficient policies cannot win by construction.

### 6. Falsification critic (before accept)

Before accepting a new task or claim, an author (or automated critic pass) must attempt to break the gold:

- [ ] Is there a trivial edit that passes the verifier without meeting the prompt intent?
- [ ] Does the start state accidentally already pass?
- [ ] For claims: is there a passage in the bundle that flips the intended label under a reasonable reading?
- [ ] Record the critic attempt in `design_provenance` (document surface) or task notes (action surface).

If a cheap counterexample exists, fix the verifier or the gold before merge.

### 7. Selftest gate

```bash
python3 runner/run.py selftest
```

Must report every task discriminates and scope detection ok. No merge if red.

### 8. Cleanliness gate (before any push)

```bash
python3 tools/check_clean.py
```

Must report clean: no private paths, no key-shaped secrets, and no em dashes in the publishable file set. Run before every commit intended for the public repo. This is what keeps the repo publish-safe as it grows.

## Reviewer sign-off

Record in PR or task notes:

- author
- reviewer
- date
- checklist version (this file)
- any known residual blind spots

## Version

- v0.1 (2026-07-19): initial publishable standard for demo split + direction-2 reuse.
