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

## Open tension: specificity against the defect signal (raised 2026-08-28)

Rule 1 asks that a prompt state the observable end state. Applied strictly, it
would have removed the only source of failure this suite has ever recorded.

Across 269 graded runs, 64 of 65 false completions are
`07-propagate-tax-param` (see Finding G). Task 07 states `total()`'s default and never states
`checkout()`'s, while its verifier requires it, and the prompt's own example call
supplies a plausible wrong value. That is a specificity defect by rule 1, and it
is the reason the task produces defects. The tasks that satisfy rule 1 most
completely, `04` and `08`, have never produced one.

So an author following this checklist as written will keep building tasks that
cannot fail. That is the opposite of what the suite is for.

The distinction the rule is missing is between two kinds of underspecification:

- **Unfair.** The required value cannot be derived from the prompt or the
  workspace. The model can only guess. This is a broken task and rule 1 is right
  to forbid it.
- **Realistic.** The required value is derivable from context but is not stated,
  and something more salient points the wrong way. This is how real tickets
  arrive, and it is the only condition under which this suite has ever observed a
  model claim done on broken code.

Task 07 is the second kind. A competent engineer infers that a pass-through
default should not change existing behaviour, so `0.0` is recoverable; `0.1` is
merely louder.

Resolving this is a prerequisite for authoring new tasks, not a side note. Until
it is resolved, do not read rule 1 as requiring that every value the verifier
checks appears in the prompt.

### A worked counterexample for anyone drafting the twin

The obvious twin for task 07 does not work, and it is worth recording why before
someone spends a day on it. Take `01-add-currency-field`, delete *"defaulting to
`USD`"* from its prompt, and leave its verifier asserting `p.currency == "USD"`.
This looks like a clean single-variable perturbation. It is not a valid task:
`01`'s workspace contains no occurrence of `USD` anywhere, so the value becomes
underivable and the task turns into the unfair kind. Any false completions it
produced would be evidence about guessing an arbitrary string, not about
specification gaps.

A sound twin has to make the correct value derivable and the wrong value more
salient. That means authoring both members together against one workspace that
establishes the correct value, with the two prompts differing in exactly one
sentence. It is two tasks of work, not an edit to an existing one, and no
existing task may be modified to produce it: `01` carries 32 runs of history and
`07` carries 311, and changing either would silently invalidate them.

## Reviewer sign-off

Record in PR or task notes:

- author
- reviewer
- date
- checklist version (this file)
- any known residual blind spots

## Version

- v0.1 (2026-07-19): initial publishable standard for demo split + direction-2 reuse.
