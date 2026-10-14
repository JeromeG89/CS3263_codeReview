"""Precondition-respecting random testing (a classic, non-AI baseline).

Values are drawn from a mixture of small integers, boundary values of the C type,
and integer constants harvested from the code and preconditions (a "dictionary"
in fuzzing terms). Cases violating the preconditions are rejected. A bug found by
fuzzing is always real (no false positives), but fuzzing can never prove safety.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

from .cexec import ExecResult, run_cases
from .dataset import C_CONSTANTS, Instance, Param, array_lengths, check_preconditions, elem_ok

MAX_FUZZ_ARRAY = 64


def harvest_constants(inst: Instance) -> list[int]:
    text = inst.code + "\n" + "\n".join(inst.requires) + "\n" + "\n".join(inst.elem_requires.values())
    consts: set[int] = set()
    for m in re.finditer(r"(?<![\w.])(0x[0-9a-fA-F]+|\d+)", text):
        consts.add(int(m.group(1), 0))
    for name, val in C_CONSTANTS.items():
        if name in text:
            consts.add(val)
    out: set[int] = set()
    for c in consts:
        for d in (-2, -1, 0, 1, 2):
            out.add(c + d)
            out.add(-c + d)
    return sorted(out)


def _draw(rng: random.Random, p: Param, consts: list[int], mode: str) -> int:
    lo, hi = p.lo, p.hi
    if mode == "naive":
        r = rng.random()
        v = rng.randint(-16, 16) if r < 0.5 else rng.randint(lo, hi)
        return min(max(v, lo), hi)
    r = rng.random()
    if r < 0.30:
        v = rng.randint(-16, 16)
    elif r < 0.55 and consts:
        v = rng.choice(consts)
    elif r < 0.70 and consts:
        m = min(max(abs(c) for c in consts), 10**7)
        v = rng.randint(-m - 2, m + 2)
    elif r < 0.85:
        v = rng.choice([lo, lo + 1, lo + 2, hi, hi - 1, hi - 2, -1, 0, 1, 2, hi // 2, lo // 2])
    else:
        v = rng.randint(lo, hi)
    return min(max(v, lo), hi)


def gen_cases(inst: Instance, n: int, seed: int = 0, mode: str = "dictionary",
              max_attempts: int = 400_000) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    consts = harvest_constants(inst)
    cases: list[dict[str, Any]] = []
    attempts = 0
    while len(cases) < n and attempts < max_attempts:
        attempts += 1
        vals: dict[str, Any] = {p.name: _draw(rng, p, consts, mode) for p in inst.scalars}
        try:
            lens = array_lengths(inst, vals)
        except Exception:  # noqa: BLE001
            continue
        if any(L < 0 or L > MAX_FUZZ_ARRAY for L in lens.values()):
            continue
        for p in inst.arrays:
            cond = inst.elem_requires.get(p.name)
            arr = []
            for _ in range(lens[p.name]):
                for _try in range(50):
                    x = _draw(rng, p, consts, mode)
                    if cond is None or elem_ok(cond, x, vals):
                        break
                arr.append(x)
            vals[p.name] = arr
        ok, _ = check_preconditions(inst, vals)
        if ok:
            cases.append(vals)
    return cases


@dataclass
class FuzzResult:
    found: bool
    witness: dict[str, Any] | None
    exec: ExecResult | None
    cases_generated: int
    cases_executed: int


def fuzz(inst: Instance, n: int = 2000, seed: int = 0, mode: str = "dictionary",
         batch: int = 500) -> FuzzResult:
    cases = gen_cases(inst, n, seed=seed, mode=mode)
    executed = 0
    for start in range(0, len(cases), batch):
        chunk = cases[start:start + batch]
        res = run_cases(inst, chunk)
        if res.violated or res.timed_out:
            idx = res.case_index if res.case_index is not None else 0
            executed += idx + 1
            if res.violated:
                return FuzzResult(True, chunk[idx], res, len(cases), executed)
            continue
        executed += len(chunk)
    return FuzzResult(False, None, None, len(cases), executed)
