# Contributing to Verified Done

What happened when your coding agent said it was done? You can contribute a run, a place where the instructions broke down, or a small task that would expose a missed change.

If you have a regression test for an existing verifier, a PR with the smallest failing example and the expected outcome is welcome. Describe which requirement it checks so someone else can reproduce it.

If you'd like to make a small code change, [help a tester keep two grades of the same task](https://github.com/camerontjs-dot/verified-done/issues/5). The issue describes the current behavior and a way to check the change.

## Share a run or a setup problem

Start with the [README walkthrough](README.md). Then [open a run report](https://github.com/camerontjs-dot/verified-done/issues/new?template=run-report.md). A clean pass is worth reporting. So is the first command that stopped you. A few sentences are enough.

For an attempt with your own coding agent, use a fresh copy of the task's starting files. From the repository root, these commands work in a macOS or Linux shell:

```bash
task=07-propagate-tax-param
trial=$(mktemp -d)
git init -q "$trial"
attempt="$trial/attempt"
cp -R "tasks/$task/workspace" "$attempt"
export PYTHONDONTWRITEBYTECODE=1
printf 'Open this folder in your agent: %s\n' "$attempt"
cat "tasks/$task/task.json"
```

Give the agent the `prompt`, the `allowed_files` list and the copied folder as its workspace. Keep the verifier and reference solution outside that folder. Keep the original starting files intact so the grader can detect what changed. When the agent stops, record what it actually said.

```bash
python3 runner/run.py grade --task "$task" --workspace "$attempt" --claim-complete
```

Use `--claim-complete` only if the agent explicitly claimed completion. Otherwise replace it with `--no-claim` and say whether the agent declined, stopped, or never reached a final reply. Pass the entire resulting workspace to the grader, including unchanged files. Files created by a tool, such as caches inside that folder, count in the scope check too.

A successful `grade` command means a score was recorded. Read `verify_pass`, `verified_pass`, `false_completion` and `scope_violation` in its output for the outcome. Each grade of the same task replaces its local `results/receipts/<task>.json`; save a separate copy before grading that task again if you want to keep both. Share the outcome fields or a short description. Raw receipts and tracebacks can contain local paths.

## Suggest a task

[Open a task idea](https://github.com/camerontjs-dot/verified-done/issues/new?template=task-idea.md) with the intended behavior, what an agent could plausibly miss, and how someone else could check the difference. For example, a discount might appear on the screen while the exported invoice still shows the full price. A written example is enough to start. Use synthetic or shareable details.

## Build your own task

You can try a task in your own checkout first. The [pagination example](tasks/02-paginate-last-page/) has a single source file and a verifier you can read in a few lines. From the repository root:

```bash
cp -R tasks/02-paginate-last-page tasks/my-discount-case
```

1. In `task.json`, set `id` to the directory name (`my-discount-case`), write a title and a prompt with an observable result, choose a [task category](METHODOLOGY.md#task-categories), and list the exact editable paths in `allowed_files`. Remove the copied optional `optimal_steps` fields unless you have derived them for your task.
2. Replace `workspace/` with the full, deliberately unfinished starting code. Put the minimal correct edits at matching relative paths under `solution/`. The runner overlays them on a copy of the start.
3. Replace `verify.py` with a deterministic Python check. It runs in a copy of the candidate workspace. Check behavior the user would observe, include a case a plausible partial fix misses, and exit successfully only if the requirements hold. Keep the demo offline and standard-library only.
4. Run `python3 runner/run.py selftest --task my-discount-case`. Look for `yes` in both the `start fails` and `solution passes` columns. To try a partial solution, grade a fresh workspace copy using the procedure above with `task=my-discount-case`. Identify hand-made examples as controls when reporting them.

For a pull request, follow the [task authoring standard](AUTHORING_STANDARD.md), including the attempt to find a false pass. From the repository root, regenerate the scorecard and index, then run the same checks used by CI:

```bash
python3 runner/run.py selftest
python3 runner/run.py index
python3 -m unittest discover -s runner -p 'test_*.py' -t runner
python3 tools/check_clean.py
```

Include the task and its updated `results/selftest-latest.json`, `results/selftest-scorecard.md`, and `results/INDEX.json`. In the PR, describe the intended behavior, the near miss you tried, what happened, and any blind spots a reviewer should check. The [ledger](LEDGER.md) explains the outcome labels.
