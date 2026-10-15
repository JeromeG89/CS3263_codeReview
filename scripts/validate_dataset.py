#!/usr/bin/env python
"""Triple-validate every instance's ground-truth label.

For each instance:
  1. The C code compiles under ASan+UBSan.
  2. UNSAFE: the hand-written witness satisfies the preconditions and triggers a sanitizer report.
  3. The reference Z3 encoding (authored by Claude) returns the gold verdict; for UNSAFE its model,
     executed concretely, reproduces a violation.
  4. CBMC (independent bounded model checker) returns the gold verdict.
  5. SAFE: N precondition-respecting fuzz inputs produce no sanitizer report.
Writes results/validation.json (shown per instance in report/APPENDIX.md); exits non-zero on any disagreement.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck import cbmc  # noqa: E402
from invcheck.cexec import CompileError, compile_instance, run_witness  # noqa: E402
from invcheck.dataset import ROOT, check_preconditions, load_dataset, load_examples, normalise_witness  # noqa: E402
from invcheck.fuzz import fuzz  # noqa: E402
from invcheck.z3run import run_and_interpret  # noqa: E402


def validate(inst, fuzz_n: int, use_cbmc: bool) -> dict:
    row = {"id": inst.id, "label": inst.label, "tier": inst.tier, "category": inst.category, "problems": []}
    P = row["problems"]
    try:
        compile_instance(inst)
    except CompileError as exc:
        P.append(str(exc)[:400])
        return row
    if inst.is_unsafe:
        nw = normalise_witness(inst, inst.witness, strict=True)
        if not nw.ok:
            P.append(f"witness malformed: {nw.problems}")
        ok, clause = check_preconditions(inst, nw.values)
        if not ok:
            P.append(f"witness violates precondition {clause}")
        res = run_witness(inst, nw.values)
        row["witness_kind"] = res.kind
        if not res.violated:
            P.append("witness does not trigger a violation")
        elif res.kind != inst.category:
            row.setdefault("notes", []).append(f"witness triggers {res.kind}, category is {inst.category}")
    z = run_and_interpret(inst.reference_z3, inst, timeout_ms=120000)
    row["ref_z3"] = z.verdict
    row["ref_z3_witness"] = z.witness_status
    if z.status == "error":
        P.append(f"reference z3 error: {z.error_type}: {z.error[:300]}")
    elif z.verdict != inst.gold_verdict:
        P.append(f"reference z3 says {z.verdict}")
    elif inst.is_unsafe and z.witness_status != "confirmed":
        P.append(f"reference z3 model not confirmed: {z.witness_status} {z.witness_detail[:200]} {z.witness}")
    if use_cbmc:
        c = cbmc.run_cbmc(inst)
        row["cbmc"] = c.verdict
        row["cbmc_s"] = round(c.seconds, 2)
        if c.verdict != inst.gold_verdict:
            P.append(f"cbmc says {c.verdict} {c.note} {c.failures[:3]}")
    if not inst.is_unsafe:
        f = fuzz(inst, n=fuzz_n, seed=1)
        row["fuzz_cases"] = f.cases_executed
        if f.found:
            P.append(f"fuzzing found a violation in SAFE instance: {f.exec.message} with {f.witness}")
        if f.cases_generated < min(200, fuzz_n):
            row.setdefault("notes", []).append(f"only {f.cases_generated} fuzz cases satisfied the preconditions")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuzz", type=int, default=3000)
    ap.add_argument("--no-cbmc", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--examples", action="store_true", help="validate the few-shot examples instead")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    insts = load_examples() if args.examples else load_dataset()
    if args.only:
        insts = [i for i in insts if any(i.id.startswith(o) for o in args.only)]
    use_cbmc = cbmc.available() and not args.no_cbmc
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(lambda i: validate(i, args.fuzz, use_cbmc), insts))
    bad = [r for r in rows if r["problems"]]
    for r in rows:
        mark = "FAIL" if r["problems"] else "ok  "
        extra = " | ".join(r["problems"] + r.get("notes", []))
        print(f"{mark} {r['id']:<22} {r['label']:<7} ref={r.get('ref_z3', '-'):<7} cbmc={r.get('cbmc', '-'):<7} {extra}")
    print(f"\n{len(rows) - len(bad)}/{len(rows)} instances validated")
    if not args.only and not args.examples:
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results" / "validation.json").write_text(json.dumps(rows, indent=1))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
