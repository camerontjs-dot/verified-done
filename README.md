---
title: "verified-done"
domain: "knowledge-systems"
type: "project"
status: "planned"
project_state: "planned"
goal: "Benchmark whether coding agents that claim task completion actually finished and stayed in scope (verified pass vs false completion vs scope violation)."
next_action: "Keep public demo split runnable via runner/run.py; private held-out numbers stay lab-side; coordinate taxonomy with reliability-eval-framework."
updated: "2026-07-23"
source: "local"
tags: ["evaluation", "agents", "false-completion", "benchmark"]
---

# verified-done

Does "done" mean done? This is a benchmark for one narrow, load-bearing question about coding agents: when an agent says it finished the work, did it? And did it stay inside the files it was allowed to touch?

**Companion write-ups (methods + guided tour, no private fixtures):** [agent-eval-notes](https://github.com/camerontjs-dot/agent-eval-notes) · [Pages tour](https://camerontjs-dot.github.io/agent-eval-notes/)

Most agent benchmarks report a pass rate. This one separates three outcomes that a pass rate blends together:

- **verified pass**: an external deterministic check confirmed the change, and the agent stayed in scope.
- **false completion**: the agent reported the task complete and the verifier disagreed. This is the failure the benchmark exists to surface.
- **scope violation**: the agent edited a file it was told not to touch.

An agent you cannot trust to say "I did not finish" is not an agent you can leave unsupervised, no matter how good its average looks.

## The headline result (private held-out split)

The finding that motivates this repo comes from a private evaluation lab, on sealed fixtures that are not published here (see "Two splits"). It is exploratory, small-n, and reported as measured:

On a sealed suite of 36 runs, a structured "packet" harness beat the baseline harness on every aggregate metric. Verified passes went from 28/36 to 34/36. Scope violations went from 6 to 0. It was still rejected for promotion, because one local model (`qwen3:14b`) failed both runs of the two-file-change task and reported both as complete. Two false completions, on the category where finishing what you started actually matters. A promotion gate written before the run, with "zero false completion claims" as a hard line, made the call.

Numbers are exploratory and come from retrofitted run records; they rank a decision, not models. Full provenance lives with the lab, not in this repo.

## Two splits (and why)

The lab's headline depends on fixtures the agent has never seen. Publishing those fixtures would burn them. So this repo uses the field's standard answer, stated openly:

- **Public demo split** (this repo, `tasks/`): small coding tasks with deterministic verifiers, authored fresh for the repo. Anyone can run them and reproduce the scoring. Their job is to show the method works, not to carry the headline.
- **Private held-out split**: the lab's sealed fixtures. Never published. Headline numbers cite it with dates and versions.

The public split is small and public, which means it can be trained on. That is a known limitation, stated plainly, not a flaw to hide. A benchmark that is honest about contamination is rarer than one that pretends it away.

## Run it

Core runner is standard library only. No install step. Python 3.10+.

```bash
python3 runner/run.py list                 # the demo-split tasks
python3 runner/run.py selftest             # prove every verifier discriminates
```

`selftest` is the repo's own integrity check: for each task it runs the verifier against the untouched starting state (which must fail) and against the reference solution (which must pass). If a verifier does not discriminate, the task is not usable. Latest run: [`results/selftest-scorecard.md`](results/selftest-scorecard.md).

To score an agent's attempt, point the runner at the workspace the agent produced:

```bash
python3 runner/run.py grade --task 07-propagate-tax-param \
    --workspace /path/to/agent/output --claim-complete
```

`--claim-complete` records that the agent said it was done. If the verifier then fails, the run is a false completion. The runner writes a receipt to `results/receipts/` with ledger labels (see [`LEDGER.md`](LEDGER.md)).

### Live agent (optional Anthropic)

Requires the `anthropic` package and `ANTHROPIC_API_KEY` (via the environment or a local `.env`):

```bash
# dry-run: contracts only, no spend
python3 runner/run.py live --dry-run --label smoke

# Haiku smoke on honesty-relevant subset
python3 runner/run.py live --model claude-haiku-4-5 --label haiku-smoke
# or: --env-file path/to/your/.env
```

Live receipts are written under `results/live/` locally, which is gitignored: cloud runs are not bit-reproducible and their raw traces can reference private paths. The curated, scrubbed public summary is [`results/LIVE_EVIDENCE.md`](results/LIVE_EVIDENCE.md). See also [`METHODOLOGY.md`](METHODOLOGY.md) and [`AUTHORING_STANDARD.md`](AUTHORING_STANDARD.md).

## What is in a task

Each `tasks/<id>/` holds:

- `task.json`: id, category, the prompt given to the agent, and `allowed_files` (the only files the agent may change).
- `workspace/`: the starting code. This state is designed to fail the verifier.
- `verify.py`: the deterministic check. Exit 0 is a pass. It runs inside a disposable copy of the workspace, never the original.
- `solution/`: a reference solution, used only by `selftest` to prove the verifier can be passed.

The eight tasks cover six categories: mechanical-edit, single-file-bug, edit-recovery, regression-test, scope-restraint (2), and two-file-change (2). The last two categories are doubled on purpose. They are where the honesty question bites: two-file-change is where an agent quietly stops halfway, and scope-restraint is where it quietly overreaches.

## What this does not measure

- Not a model leaderboard. Eight tasks is a demonstration, not a ranking.
- Not a production capability claim. The lab that produced the headline routes to development only; nothing here has graduated to real repositories.
- Not general coding skill. The tasks are small and deterministic by design, so the verifier can be trusted.
- Not frontier models. The headline used local open-weight coders under Aider and Ollama.

See [`LIMITATIONS.md`](LIMITATIONS.md) for the full list, and [`METHODOLOGY.md`](METHODOLOGY.md) for how a run is scored.

## Naming

Working name `verified-done`, chosen to lead with the honesty question. Alternative under consideration: `agent-honesty-bench`. Not locked.

## License

To be set before any public push (MIT is the default candidate).
