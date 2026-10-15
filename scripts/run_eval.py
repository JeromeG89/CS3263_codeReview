#!/usr/bin/env python
"""Run (model x approach x instance) evaluations. Resumable: finished triples are skipped.

  python scripts/run_eval.py --config configs/local.yaml
  python scripts/run_eval.py --config configs/gemini.yaml --approaches direct z3_repair --only T1
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck.approaches import APPROACHES  # noqa: E402
from invcheck.dataset import ROOT, load_dataset, load_examples  # noqa: E402
from invcheck.llm import make_llm  # noqa: E402

RUNS = ROOT / "results" / "runs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--approaches", nargs="*")
    ap.add_argument("--models", nargs="*", help="substring filter on model names")
    ap.add_argument("--only", nargs="*", help="instance id prefixes")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    run_dir = RUNS / cfg["run_name"]
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "records.jsonl"
    done = set()
    if out_path.exists():
        for line in out_path.open():
            r = json.loads(line)
            done.add((r["model"], r["approach"], r["instance"], r.get("sample", 0)))

    insts = load_dataset()
    if args.only:
        insts = [i for i in insts if any(i.id.startswith(o) for o in args.only)]
    if args.limit:
        insts = insts[: args.limit]
    example = load_examples()[0]
    approaches = args.approaches or cfg["approaches"]
    workers = args.workers or cfg.get("workers", 1)
    samples = int(cfg.get("samples", 1))

    jobs = []
    for spec in cfg["models"]:
        for sample in range(samples):
            llm = make_llm({**spec, "seed": spec.get("seed", 0) + sample})
            if args.models and not any(m in llm.name for m in args.models):
                continue
            for approach in approaches:
                for inst in insts:
                    if (llm.name, approach, inst.id, sample) not in done:
                        jobs.append((llm, approach, inst, sample))
    print(f"{len(jobs)} jobs ({len(done)} already done) -> {out_path}", flush=True)
    lock = threading.Lock()
    t_start = time.time()

    state = {"api_failures": 0, "stopped": False}
    max_failures = int(cfg.get("max_consecutive_api_failures", 5))

    def work(job):
        llm, approach, inst, sample = job
        if state["stopped"]:
            return None
        t0 = time.time()
        rec = APPROACHES[approach](llm, inst, example=example, max_repairs=cfg.get("max_repairs", 3))
        rec.update(sample=sample, gold=inst.gold_verdict, wall_s=round(time.time() - t0, 2))
        with lock:
            if rec.get("error"):  # the API call itself failed (quota, network): never record it, retry next run
                state["api_failures"] += 1
                if state["api_failures"] >= max_failures and not state["stopped"]:
                    state["stopped"] = True
                    print(f"stopping: {max_failures} consecutive API failures (last: {rec['error'][:300]}). "
                          "Re-run the same command later to resume.", flush=True)
                return None
            state["api_failures"] = 0
            with out_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        return rec

    n_ok = 0
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(work, j) for j in jobs]
        for k, fut in enumerate(as_completed(futs), 1):
            try:
                rec = fut.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[{k}/{len(jobs)}] job crashed: {exc!r}", flush=True)
                continue
            if rec is None:
                continue
            n_ok += rec["verdict"] == rec["gold"]
            el = time.time() - t_start
            print(f"[{k}/{len(jobs)}] {rec['model']:<26} {rec['approach']:<11} {rec['instance']:<13} "
                  f"gold={rec['gold']:<6} got={rec['verdict']:<7} wit={rec.get('witness_status') or '-':<14} "
                  f"err={rec.get('z3_error_type') or rec.get('error') or '-'} "
                  f"({rec['wall_s']}s, eta {el / k * (len(jobs) - k) / 60:.0f}m)", flush=True)
    print(f"done: {n_ok}/{len(jobs)} correct in this batch")


if __name__ == "__main__":
    main()
