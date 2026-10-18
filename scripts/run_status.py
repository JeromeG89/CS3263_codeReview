#!/usr/bin/env python
"""Write report/RUN_STATUS.md: how far every evaluation run got and how to resume it.

Progress is read from results/runs/<run>/records.jsonl (one line per finished
model x approach x instance). run_eval.py skips everything already in that file,
so anyone with the repo and their own API key can continue an interrupted run.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck.dataset import ROOT, load_dataset  # noqa: E402
from invcheck.llm import make_llm  # noqa: E402

RUNS = ROOT / "results" / "runs"
LOGS = ROOT / "results" / "logs"
CONFIGS = {"local": "configs/local.yaml", "local_llama": "configs/local_llama.yaml", "gemini": "configs/gemini.yaml", "groq": "configs/groq.yaml"}
# models whose records live in a different run than their config suggests
ONLY_MODELS = {"local": ["ollama:qwen2.5-coder:7b"]}
NOT_PLANNED = {("ollama:llama3.2:3b", "z3_repair"): "skipped by decision (see report §6.6)"}


def stop_reason(run: str) -> str | None:
    log = LOGS / f"{run}_run.log"
    if not log.exists():
        return None
    text = log.read_text()
    starts = [m.start() for m in re.finditer(r"^\d+ jobs \(", text, flags=re.M)]
    last = text[starts[-1]:] if starts else text
    m = re.search(r"^stopping: (.*)$", last, flags=re.M)
    if m:
        return m.group(1)
    if "done:" in last:
        return None
    return "the run is in progress or was interrupted (no clean end in the log)"


def main():
    n_inst = len(load_dataset())
    lines = [
        "# Evaluation run status",
        "",
        f"_Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by `scripts/run_status.py`. "
        "Progress is read from `results/runs/<run>/records.jsonl`._",
        "",
        "Every finished (model, approach, instance) is one line in the run's `records.jsonl`. "
        "`scripts/run_eval.py` skips those, so a stopped run continues exactly where it stopped. "
        "Answers that failed at the API level (quota, network) are never recorded, so they are simply retried.",
        "",
    ]
    for run, cfg_path in CONFIGS.items():
        cfg = yaml.safe_load(open(ROOT / cfg_path))
        rec_path = RUNS / cfg["run_name"] / "records.jsonl"
        done = Counter()
        if rec_path.exists():
            for line in rec_path.open():
                r = json.loads(line)
                done[(r["model"], r["approach"])] += 1
        models = [make_llm(dict(m)).name for m in cfg["models"]]
        models = [m for m in models if m in ONLY_MODELS.get(run, models)]
        approaches = cfg["approaches"]
        rows, remaining, total = [], Counter(), 0
        for m in models:
            for a in approaches:
                k = done[(m, a)]
                if (m, a) in NOT_PLANNED:
                    status = NOT_PLANNED[(m, a)]
                elif k >= n_inst:
                    status = "complete"
                else:
                    status = "**incomplete**"
                    remaining[m] += n_inst - k
                    total += n_inst - k
                rows.append(f"| `{m}` | `{a}` | {k} / {n_inst} | {status} |")
        lines += [f"## Run `{cfg['run_name']}` (`{cfg_path}`)", ""]
        note_path = RUNS / cfg["run_name"] / "STOP_NOTE.txt"  # committed, human-written reason for an unfinished run
        reason = stop_reason(cfg["run_name"]) if total else None
        note = note_path.read_text().strip() if (total and note_path.exists()) else None
        if total == 0:
            lines.append("**Complete.** Nothing to resume.")
        else:
            lines.append(f"**{total} instance-runs remaining.**" + (f" Last stop: {reason}" if reason and not note else ""))
        if note:
            lines += ["", "**Why it stopped** (from `" + str(note_path.relative_to(ROOT)) + "`):", ""] + ["> " + ln for ln in note.splitlines()]
        lines += ["", "| Model | Approach | Done | Status |", "|---|---|---|---|", *rows, ""]
        if total:
            lines += ["To resume (from the repo root, on an up-to-date clone of `main`):", "", "```bash"]
            if run == "groq":
                lines += ["cp .env.example .env            # then put your own GROQ_API_KEY in .env (free: console.groq.com/keys)",
                          ".venv/bin/python scripts/list_llm_limits.py --provider groq   # your per-model daily limits"]
            elif run == "gemini":
                lines += ["cp .env.example .env            # then put your own GEMINI_API_KEY in .env",
                          ".venv/bin/python scripts/list_gemini_models.py --filter flash   # check the model ids still work"]
            else:
                lines += ["ollama serve &   # and: " + " && ".join(f"ollama pull {m.split(':', 1)[1]}" for m in models)]
            only = sorted({m for m in remaining})
            filt = " --models " + " ".join(m.split(":", 1)[1] for m in only) if len(only) < len(models) else ""
            lines += [f".venv/bin/python scripts/run_eval.py --config {cfg_path}{filt}",
                      ".venv/bin/python scripts/rescore.py && .venv/bin/python scripts/analyze.py",
                      ".venv/bin/python scripts/run_status.py   # refresh this file", "```", "",
                      "Then commit `results/runs/" + cfg["run_name"] + "/records.jsonl` so the next person continues from there.", ""]
            if run == "gemini":
                lines += ["Notes: the free tier allows roughly 10 requests/minute per project (the client throttles to that), "
                          "and the daily quota resets at midnight Pacific time. A different API key gives the same models and settings, "
                          "so results from several keys can be combined. The local response cache (`results/cache/`) is not committed, so a "
                          "resumed `z3_repair` re-queries its first attempt instead of reusing the `z3_guided` answer; at temperature 0 this "
                          "is usually but not always identical.", ""]
    out = ROOT / "report" / "RUN_STATUS.md"
    out.write_text("\n".join(lines))
    print(out.read_text())


if __name__ == "__main__":
    main()
