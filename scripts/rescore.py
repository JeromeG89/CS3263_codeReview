#!/usr/bin/env python
"""Re-score stored LLM records with the current parser and witness validator.

Model outputs are kept verbatim in each record's transcript, so verdict parsing
and witness validation can be recomputed after fixes without new model calls.
Z3 verdicts come from the solver and are unchanged; only witness statuses of the
final attempts are re-validated. Do not run while run_eval.py is writing.

  python scripts/rescore.py            # all LLM runs
  python scripts/rescore.py --runs local
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck.dataset import ROOT, load_dataset  # noqa: E402
from invcheck.parse import parse_verdict  # noqa: E402
from invcheck.z3run import validate_witness  # noqa: E402

RUNS = ROOT / "results" / "runs"


def rescore(rec: dict, inst) -> dict:
    if rec["approach"] in ("direct", "direct_cot"):
        if rec.get("error") or not rec.get("transcript"):
            return rec
        p = parse_verdict(rec["transcript"][-1]["content"])
        rec.update(verdict=p["verdict"], violation=p["violation"], parse=p["parse"], explanation=p["explanation"],
                   witness=None, witness_status=None, witness_detail="", exec_kind=None)
        if p["verdict"] == "UNSAFE":
            ws, detail, kind, vals = validate_witness(inst, p["witness"])
            rec.update(witness=vals if vals is not None else p["witness"], witness_status=ws,
                       witness_detail=detail, exec_kind=kind)
    elif rec["approach"].startswith("z3") and rec.get("attempts"):
        last = rec["attempts"][-1]
        if last.get("status") == "sat" and last.get("witness") is not None:
            ws, detail, kind, vals = validate_witness(inst, last["witness"])
            last.update(witness_status=ws, witness_detail=detail, exec_kind=kind)
            rec.update(witness_status=ws, witness_detail=detail, exec_kind=kind)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*")
    args = ap.parse_args()
    insts = {i.id: i for i in load_dataset()}
    for path in sorted(RUNS.glob("*/records.jsonl")):
        run = path.parent.name
        if run in ("baselines", "smoke") or (args.runs and run not in args.runs):
            continue
        recs = [json.loads(l) for l in path.open()]
        before = Counter((r["approach"], r["verdict"], r.get("witness_status")) for r in recs)
        new = [rescore(r, insts[r["instance"]]) for r in recs]
        after = Counter((r["approach"], r["verdict"], r.get("witness_status")) for r in new)
        shutil.copy(path, path.with_suffix(".jsonl.bak"))
        with path.open("w") as f:
            for r in new:
                f.write(json.dumps(r) + "\n")
        changed = sum(((before - after) + (after - before)).values())
        print(f"{run}: {len(recs)} records re-scored; {changed} (approach, verdict, witness) counts changed")


if __name__ == "__main__":
    main()
