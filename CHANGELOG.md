# verified-done changelog

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
- Public push / license / final name
- Aider adapter path for private sealed fixtures
