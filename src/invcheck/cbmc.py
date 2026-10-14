"""CBMC (bounded model checking, Clarke/Kroening/Lerda 2004) as an independent oracle.

We build a nondeterministic harness that assumes the preconditions and calls the
entry function, then ask CBMC to check bounds, pointer, division-by-zero,
signed-overflow and shift properties. Only failures located inside the instance's
own functions count (the harness itself is not under review).
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field

from .dataset import ROOT, Instance

BUILD_DIR = ROOT / "build" / "cbmc"
HARNESS_UNWIND = 260
NONDET = {"int": "nondet_int", "unsigned": "nondet_unsigned", "long long": "nondet_long_long"}


def available() -> bool:
    return shutil.which("cbmc") is not None


def function_names(code: str) -> set[str]:
    return set(re.findall(r"^[A-Za-z_][\w \t\*]*?\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{", code, flags=re.M))


def _refs_array(expr: str, inst: Instance) -> bool:
    return any(re.search(rf"\b{re.escape(a.name)}\s*\[", expr) for a in inst.arrays)


def harness_source(inst: Instance) -> str:
    lines = [
        "#include <stdlib.h>\n#include <limits.h>\n",
        inst.code.strip(),
        "",
        "int nondet_int(void); unsigned nondet_unsigned(void); long long nondet_long_long(void);",
        "int main(void) {",
    ]
    for p in inst.scalars:
        lines.append(f"    {p.type} {p.name} = {NONDET[p.type]}();")
    scalar_reqs = [r for r in inst.requires if not _refs_array(r, inst)]
    array_reqs = [r for r in inst.requires if _refs_array(r, inst)]
    for r in scalar_reqs:
        lines.append(f"    __CPROVER_assume({r});")
    for p in inst.arrays:
        t = p.elem_type
        lines.append(f"    {t} *{p.name} = ({t} *)malloc(sizeof({t}) * (size_t)({p.len}));")
        cond = inst.elem_requires.get(p.name)
        if cond:
            lines.append(f"    for (long long __k = 0; __k < (long long)({p.len}); __k++) {{ {t} _ = {p.name}[__k]; __CPROVER_assume({cond}); }}")
    for r in array_reqs:
        lines.append(f"    __CPROVER_assume({r});")
    args = ", ".join(p.name for p in inst.params)
    lines.append(f"    {inst.entry}({args});")
    lines.append("    return 0;\n}")
    return "\n".join(lines) + "\n"


@dataclass
class CbmcResult:
    verdict: str  # SAFE | UNSAFE | UNKNOWN
    failures: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    seconds: float = 0.0
    note: str = ""

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "failures": self.failures, "ignored": self.ignored,
                "seconds": round(self.seconds, 3), "note": self.note}


def run_cbmc(inst: Instance, timeout: float = 300.0) -> CbmcResult:
    src = harness_source(inst)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(src.encode()).hexdigest()[:12]
    path = BUILD_DIR / f"{inst.id}-{h}.c"
    path.write_text(src)
    cmd = [
        "cbmc", str(path),
        "--bounds-check", "--pointer-check", "--div-by-zero-check",
        "--signed-overflow-check", "--undefined-shift-check",
        "--no-malloc-may-fail",
        "--unwind", str(inst.unwind), "--unwinding-assertions",
    ]
    n_harness_loops = sum(1 for p in inst.arrays if inst.elem_requires.get(p.name))
    if n_harness_loops:  # the harness's own element-assumption loops get a generous bound
        cmd += ["--unwindset", ",".join(f"main.{k}:{HARNESS_UNWIND}" for k in range(n_harness_loops))]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return CbmcResult("UNKNOWN", seconds=time.time() - t0, note="timeout")
    dt = time.time() - t0
    own = function_names(inst.code)
    failures, ignored, unwinding = [], [], False
    for line in proc.stdout.splitlines():
        m = re.match(r"\[([\w$]+)\.([\w-]+)\.\d+\]\s+(.*):\s+FAILURE\s*$", line.strip())
        if not m:
            continue
        func, kind, desc = m.groups()
        if kind == "unwind":
            unwinding = True
            ignored.append(line.strip())
        elif func in own:
            failures.append(f"{func}.{kind}: {desc}")
        else:
            ignored.append(line.strip())
    if failures:
        return CbmcResult("UNSAFE", failures, ignored, dt)
    if unwinding:
        return CbmcResult("UNKNOWN", failures, ignored, dt, "insufficient unwinding")
    if "VERIFICATION SUCCESSFUL" in proc.stdout or ("VERIFICATION FAILED" in proc.stdout and ignored):
        note = "harness-only failures ignored" if ignored else ""
        return CbmcResult("SAFE", failures, ignored, dt, note)
    return CbmcResult("UNKNOWN", failures, ignored, dt, (proc.stderr or proc.stdout)[-500:])
