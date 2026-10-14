#!/usr/bin/env python
"""Non-LLM reference points, written in the same record format as LLM runs.

  reference_z3   Claude-authored gold Z3 encodings -> upper bound of the LLM-to-Z3 approach
  cbmc           classical bounded model checker on the C code (no translation needed)
  fuzz_random    1000 precondition-respecting random inputs (small ints / full-range mix)
  fuzz_dict      1000 inputs drawn from a dictionary of boundary values and code constants
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck import cbmc  # noqa: E402
from invcheck.approaches import run_reference_z3  # noqa: E402
from invcheck.dataset import ROOT, load_dataset  # noqa: E402
from invcheck.fuzz import fuzz  # noqa: E402

OUT = ROOT / "results" / "runs" / "baselines" / "records.jsonl"


def base(system: str, inst) -> dict:
    return {"instance": inst.id, "model": "tool", "approach": system, "sample": 0, "gold": inst.gold_verdict,
            "verdict": "UNKNOWN", "witness": None, "witness_status": None, "llm_calls": 0,
            "input_tokens": 0, "output_tokens": 0, "llm_latency_s": 0.0}


def do(system: str, inst, budget: int) -> dict:
    t0 = time.time()
    if system == "reference_z3":
        rec = run_reference_z3(inst)
        rec.update(model="tool", approach="reference_z3", sample=0, gold=inst.gold_verdict)
    elif system == "cbmc":
        rec = base(system, inst)
        c = cbmc.run_cbmc(inst)
        rec.update(verdict=c.verdict, cbmc=c.as_dict())
    else:
        rec = base(system, inst)
        f = fuzz(inst, n=budget, seed=0, mode="naive" if system == "fuzz_random" else "dictionary")
        rec.update(verdict="UNSAFE" if f.found else "SAFE", witness=f.witness,
                   witness_status="confirmed" if f.found else None,
                   exec_kind=f.exec.kind if f.found else None,
                   fuzz={"generated": f.cases_generated, "executed": f.cases_executed})
    rec["wall_s"] = round(time.time() - t0, 3)
    rec.pop("transcript", None)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="*", default=["reference_z3", "cbmc", "fuzz_random", "fuzz_dict"])
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    insts = load_dataset()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    recs = []
    for system in args.systems:
        with ThreadPoolExecutor(args.workers) as ex:
            rs = list(ex.map(lambda i: do(system, i, args.budget), insts))
        acc = sum(r["verdict"] == r["gold"] for r in rs) / len(rs)
        print(f"{system:<14} accuracy={acc:.3f}  mean time={sum(r['wall_s'] for r in rs) / len(rs):.2f}s")
        recs.extend(rs)
    keep = []
    if OUT.exists():
        keep = [json.loads(l) for l in OUT.open() if json.loads(l)["approach"] not in args.systems]
    with OUT.open("w") as f:
        for r in keep + recs:
            f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
