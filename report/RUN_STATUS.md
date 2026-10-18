# Evaluation run status

_Generated 2026-10-18 12:54 by `scripts/run_status.py`. Progress is read from `results/runs/<run>/records.jsonl`._

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

**583 instance-runs remaining.**

**Why it stopped** (from `results/runs/gemini/STOP_NOTE.txt`):

> gemini-3.8-flash has only 17 answers (15 direct and 2 bare Z3, the first instances in order): stopped again on 2026-10-18
> (UTC+8) when the daily cap was hit. Earlier stop: 2026-10-15 16:50.
> 
> Reason: Google's free tier allows only 20 requests per day per project for gemini-3.8-flash
> ("generate_content_free_tier_requests, limit: 20", HTTP 429, "retry in 15h"). The evaluation needs
> about 750 requests for this model (5 approaches x 120 instances, plus repair rounds), so a free key
> would take about a month. gemini-3.5-flash-lite has no such cap here and completed all five approaches.
> 
> To continue gemini-3.8-flash you need an API key whose Google project has a higher quota
> (for example one with billing enabled). With the key in .env, run the resume command below; it skips
> everything already recorded. If you only have a free key, run the same command once a day: it stops
> cleanly after 5 consecutive failures, and nothing failed is ever recorded.

| Model | Approach | Done | Status |
|---|---|---|---|
| `gemini:gemini-3.5-flash-lite` | `direct` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `direct_cot` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `z3` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `z3_guided` | 120 / 120 | complete |
| `gemini:gemini-3.5-flash-lite` | `z3_repair` | 120 / 120 | complete |
| `gemini:gemini-3.8-flash` | `direct` | 15 / 120 | **incomplete** |
| `gemini:gemini-3.8-flash` | `direct_cot` | 0 / 120 | **incomplete** |
| `gemini:gemini-3.8-flash` | `z3` | 2 / 120 | **incomplete** |
| `gemini:gemini-3.8-flash` | `z3_guided` | 0 / 120 | **incomplete** |
| `gemini:gemini-3.8-flash` | `z3_repair` | 0 / 120 | **incomplete** |

To resume (from the repo root, on an up-to-date clone of `main`):

```bash
cp .env.example .env            # then put your own GEMINI_API_KEY in .env
.venv/bin/python scripts/list_gemini_models.py --filter flash   # check the model ids still work
.venv/bin/python scripts/run_eval.py --config configs/gemini.yaml --models gemini-3.8-flash
.venv/bin/python scripts/rescore.py && .venv/bin/python scripts/analyze.py
.venv/bin/python scripts/run_status.py   # refresh this file
```

Then commit `results/runs/gemini/records.jsonl` so the next person continues from there.

Notes: the free tier allows roughly 10 requests/minute per project (the client throttles to that), and the daily quota resets at midnight Pacific time. A different API key gives the same models and settings, so results from several keys can be combined. The local response cache (`results/cache/`) is not committed, so a resumed `z3_repair` re-queries its first attempt instead of reusing the `z3_guided` answer; at temperature 0 this is usually but not always identical.
