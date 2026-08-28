# Limitations

Read this before drawing any conclusion from the numbers. The limits are the point, not a disclaimer.

## Small n

The public demo split is eight tasks. The private headline result is 36 runs, two runs per cell. The false-completion finding rests on two runs of one model on one category, replicated once on a second sealed suite. That is enough to reject a promotion under a pre-registered gate. It is not enough to rank models or estimate a rate with any precision. Treat every number here as a demonstration of method, not a measurement you can extrapolate.

## Exploratory, not confirmatory

The headline numbers come from run records that were retrofitted into a pinned protocol after the fact, and are labeled exploratory in the source lab. They are reported as measured, never as validated or proven. No confirmatory claim is made about which harness or model is better in general.

## Contamination

The public demo split is small and openly published. Anything public can end up in a training set. So the public tasks are a reproducible demonstration of the scoring method, not held-out evidence. The headline evidence comes from a private split that is never published, precisely so it stays uncontaminated. If you fork this repo and run the public tasks against a model that has seen them, you are measuring recall, not capability. That is a property of any public benchmark, stated here rather than ignored.

## Verifiers can have blind spots

Each verifier is deterministic and is checked by selftest to confirm it fails on the starting state and passes on the reference solution. That does not prove a verifier is airtight. A determined or lucky agent might pass a check without doing the intended work, for example by hard-coding an expected value. The tasks are written to make that hard, and hardening against cheap passes is ongoing, but it is not a solved problem and should not be assumed.

## Narrow by construction

The tasks are small, self-contained, and deterministic so the verifier can be trusted. Real engineering is none of those things. This benchmark measures whether an agent finishes a bounded task and reports completion honestly. It says nothing about design judgment, large-codebase navigation, ambiguous requirements, or anything the verifier cannot check.

## The defect signal is concentrated in one task

Across 269 graded runs, 64 of 65 false completions are `07-propagate-tax-param`. The other seven tasks have 103 runs between them and one failure. The verify-tool result (Findings A, D, E) replicates across models, arms, and a runtime upgrade, but the task is close to a constant in all three.

Read the headline accordingly: this suite reports an eight-task split and, on its central measurement, is close to a one-task instrument. See [Finding G](results/LIVE_EVIDENCE.md), which also records how to count these runs without double counting them.

## A reported category with no observations

`out-of-scope` has zero observations in 269 runs. Both scope-restraint tasks (`05`, `06`) are easy to comply with: the required change is small and the forbidden files are not where a model would be tempted to go. The suite reports a scope-violation column it has never once filled, which is a claim to measure something it has not yet demonstrated it can detect.

## Not a production claim

The lab that produced the headline routes to development only. No result here implies any model is safe to delegate real work to unsupervised. The whole exercise is about measuring the gap between "the agent said done" and "done", not about certifying that any agent has closed it.

## Scope of the models

The headline used local open-weight coding models (qwen2.5-coder-14b, qwen3-14b, qwen3.5-9b) under Aider with Ollama. Results do not transfer to hosted frontier models by default.

Optional live Anthropic runs (`runner/run.py live`) produce separate, dated receipts under `results/live/`. Those are exploratory probes: different adapter, different model family, small n. Do not merge them with the private lab headline without an explicit cross-adapter design. Cloud runs are not bit-reproducible; receipts record served_model, request ids, and usage when available.

## Live adapter limits

The Anthropic live adapter is a minimal tool loop (list/read/write/finish), not a full IDE agent. It does not score rich trajectory constraints (temporal/causal research paths). Commit-class tagging and the commit-claim hybrid check are first steps toward AgentAbstain-style path honesty, not a complete port of GroundEval.
