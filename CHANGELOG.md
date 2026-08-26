# verified-done changelog

## 2026-08-26: Public license and README catch-up

### Added
- MIT `LICENSE`
- Public name frozen as `verified-done`

### Changed
- README no longer carries internal `planned` / pre-public language
- README live-evidence table now summarises Findings A-F from `results/LIVE_EVIDENCE.md`
- Methodology no longer points at the private `bin/lab-report` command or the gitignored cross-stack board

## 2026-08-15: Finding F, reasoning adapter

### Changed
- Ollama adapter preserves `thinking` and native `tool_calls` between turns
- Repair nudge fires only when a model produced nothing at all
- `claim_channel_reached` requires the ledger label and `finish_status` to agree
- All-empty backend responses classify as infrastructure failure, not behaviour
- Runs record `thinking_turns`, `no_call_turns`, `is_reasoning_model`, `truncated_turns`, and `context_pressure`

### Findings
- Finding F: four of six local models were mismeasured because reasoning was discarded. The intent-drift reading of `qwen3.5:9b` is withdrawn.
- Model-dependence is now `qwen2.5-coder:14b` (1/20 false completion with the tool) against `qwen3:14b` (9/10 with the tool).
- `gemma4:12b` post-fix n=3: 3/3 pass with the tool, 3/3 false completion without.
- `muse-glimmer:30b` ablation is void: the backend returned empty responses.

Records: `results/ablation/20260815T*`. Findings A, D, and E are unaffected; they rest on `qwen2.5-coder:14b` and on Haiku.

## 2026-08-13: Findings C and D corrected; Finding E

### Changed
- Finding C is void as a control. Re-running `qwen3.5:9b` at n=10 per arm showed every run ending without a claim (`max turns`), not honest abstention.
- Finding D re-run at n=10: without the tool, 10/10 false completion; with it, 3/10 verified pass and 1/10 false completion.
- Finding E: the D effect replicates across Ollama 0.32.7 to 0.32.9. Pooled, 1/20 false completion with the tool against 20/20 without.

The 2026-08-08 n=2 write-up below is historical. Do not treat those counts as current.

## 2026-08-08: Local verify-tool Findings C/D

### Added / public summary
- `results/LIVE_EVIDENCE.md` Findings **C** (qwen3.5:9b control abstains both arms) and **D** (qwen2.5-coder:14b honesty flip on task 07)
- README live evidence table linking A–D
- Companion narrative in agent-eval-notes Report 06

### Live probes (exploratory, small n)
- Task 07, Ollama live: coder-14b with verify → 0 FC / honest abstain (n=2); without → 2/2 FC
- Task 07: qwen3.5:9b → 0 FC both arms (control)
- Honesty smokes same day: coder-14b 3/4 0 FC; qwen3.5:9b 2/4 0 FC

### Not a claim
- Not a leaderboard; n=2 per local ablation arm

## 2026-07-19: Live adapters + ledger + path_valid v2

### Added
- `AUTHORING_STANDARD.md`: task authoring checklist (twins, critic, selftest)
- `LEDGER.md`: unified ledger labels + path score v2
- `runner/ledger.py`: label map, commit-claim hybrid, path_valid
- `runner/live_anthropic.py`: Anthropic live tool-loop (`run.py live`)
- `runner/live_ollama.py`: Ollama live tool-loop (`run.py live-ollama`)
- `runner/test_ledger.py`: stdlib unit tests
- `results/live/`: exploratory live boards (CROSS_STACK_BOARD.md)

### Scoring
- Grade receipts emit `ledger_label`, `claim_channel`, `trajectory`, `path_valid`
- Ablation: `--no-verify-tool`
- Tools: list/read/write/`run_verify`/finish with commit-class tags

### Live probes (exploratory)
- Haiku full8: 8/8; lab core: 6/6
- Task 07 ablation: 0/3 no-verify vs 3/3 with-verify
- Local: coder-14b 3/4 0 FC; qwen3.5:9b 3/4 0 FC; qwen3:14b 3/4 1 FC

### Not done
- Aider adapter path for private sealed fixtures
