# Evaluation run status

_Generated 2026-10-24 19:08 by `scripts/run_status.py`. Progress is read from `results/runs/<run>/records.jsonl`._

Every finished (model, approach, instance) is one line in the run's `records.jsonl`. `scripts/run_eval.py` skips those, so a stopped run continues exactly where it stopped. Answers that failed at the API level (quota, network) are never recorded, so they are simply retried.

## Run `local` (`configs/local.yaml`)

**Complete.** Nothing to resume.

| Model | Approach | Done | Status |
|---|---|---|---|
| `ollama:qwen2.5-coder:7b` | `direct` | 120 / 120 | complete |
| `ollama:qwen2.5-coder:7b` | `direct_cot` | 120 / 120 | complete |
| `ollama:qwen2.5-coder:7b` | `z3` | 120 / 120 | complete |
| `ollama:qwen2.5-coder:7b` | `z3_guided` | 120 / 120 | complete |
| `ollama:qwen2.5-coder:7b` | `z3_repair` | 120 / 120 | complete |

## Run `local_llama` (`configs/local_llama.yaml`)

**Complete.** Nothing to resume.

| Model | Approach | Done | Status |
|---|---|---|---|
| `ollama:llama3.2:3b` | `direct` | 120 / 120 | complete |
| `ollama:llama3.2:3b` | `direct_cot` | 120 / 120 | complete |
| `ollama:llama3.2:3b` | `z3` | 120 / 120 | complete |
| `ollama:llama3.2:3b` | `z3_guided` | 120 / 120 | complete |
| `ollama:llama3.2:3b` | `z3_repair` | 0 / 120 | skipped by decision (see report §6.6) |

## Run `gemini` (`configs/gemini.yaml`)

**Complete.** Nothing to resume.

| Model | Approach | Done | Status |
|---|---|---|---|
| `gemini:gemini-3.5-flash-lite` | `direct` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `direct_cot` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `z3` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `z3_guided` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `z3_repair` | 120 / 120 | complete |
| `gemini:gemini-3.8-flash` | `direct` | 120 / 120 | complete |
| `gemini:gemini-3.8-flash` | `direct_cot` | 120 / 120 | complete |
| `gemini:gemini-3.8-flash` | `z3` | 120 / 120 | complete |
| `gemini:gemini-3.8-flash` | `z3_guided` | 120 / 120 | complete |
| `gemini:gemini-3.8-flash` | `z3_repair` | 120 / 120 | complete |
