"""Concrete execution of instances under AddressSanitizer + UndefinedBehaviorSanitizer.

This is the ground-truth oracle for counterexamples: a witness is *confirmed* only if
running the real C code on it makes a sanitizer report a violation. Every instance is
compiled once into a small driver that reads many test cases from stdin, so fuzzing
thousands of inputs costs a single process.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import ROOT, Instance, array_lengths

BUILD_DIR = ROOT / "build" / "harness"
CC = os.environ.get("CC", "clang")
CFLAGS = [
    "-std=c11", "-O0", "-g", "-w",
    "-fsanitize=address,undefined",
    "-fno-sanitize-recover=all",
    "-fno-omit-frame-pointer",
]
RUN_ENV = {
    **os.environ,
    "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1:abort_on_error=0:print_summary=1",
    "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=0",
}

_KIND_PATTERNS = [
    ("div_zero", r"division by zero|remainder by zero"),
    ("overflow", r"signed integer overflow|negation of .* cannot be represented|division of .* by -1 cannot be represented"),
    ("shift", r"shift exponent|left shift of"),
    ("bounds", r"out of bounds|buffer-overflow|buffer-underflow|stack-buffer|heap-buffer|global-buffer|SEGV|BUS on unknown address|use-after|unknown-crash|wild"),
]


def classify(stderr: str) -> str | None:
    for kind, pat in _KIND_PATTERNS:
        if re.search(pat, stderr):
            return kind
    return None


def _c_type(elem: str) -> str:
    return elem  # "int" | "unsigned" | "long long"


def harness_source(inst: Instance) -> str:
    decls, reads, frees, args = [], [], [], []
    for p in inst.params:
        if p.is_array:
            t = _c_type(p.elem_type)
            decls.append(f"    long long L_{p.name}; {t} *a_{p.name};")
            reads.append(
                f"        if (scanf(\"%lld\", &L_{p.name}) != 1) break;\n"
                f"        a_{p.name} = ({t} *)malloc(sizeof({t}) * (size_t)L_{p.name});\n"
                f"        for (long long k = 0; k < L_{p.name}; k++) {{ long long e; if (scanf(\"%lld\", &e) != 1) return 3; a_{p.name}[k] = ({t})e; }}"
            )
            frees.append(f"        free(a_{p.name});")
            args.append(f"a_{p.name}")
        else:
            decls.append(f"    long long v_{p.name};")
            reads.append(f"        if (scanf(\"%lld\", &v_{p.name}) != 1) break;")
            args.append(f"({_c_type(p.type)})v_{p.name}")
    return (
        "#include <stdio.h>\n#include <stdlib.h>\n#include <limits.h>\n#include <string.h>\n\n"
        f"/* ---- instance {inst.id} ---- */\n{inst.code.strip()}\n/* ---- driver ---- */\n"
        "int main(void) {\n"
        "    setvbuf(stdout, NULL, _IONBF, 0);\n"
        + "\n".join(decls) + "\n"
        "    for (int c = 0;; c++) {\n"
        + "\n".join(reads) + "\n"
        "        printf(\"CASE %d\\n\", c);\n"
        f"        (void){inst.entry}({', '.join(args)});\n"
        "        printf(\"OK %d\\n\", c);\n"
        + "\n".join(frees) + "\n"
        "    }\n"
        "    printf(\"END\\n\");\n"
        "    return 0;\n"
        "}\n"
    )


_COMPILE_LOCK = threading.Lock()


class CompileError(RuntimeError):
    pass


def compile_instance(inst: Instance) -> Path:
    src = harness_source(inst)
    h = hashlib.sha256((src + " ".join(CFLAGS)).encode()).hexdigest()[:16]
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    exe = BUILD_DIR / f"{inst.id}-{h}"
    with _COMPILE_LOCK:
        if exe.exists():
            return exe
        c_file = BUILD_DIR / f"{inst.id}-{h}.c"
        c_file.write_text(src)
        tmp = exe.with_name(exe.name + f".tmp{os.getpid()}")
        proc = subprocess.run([CC, *CFLAGS, str(c_file), "-o", str(tmp)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise CompileError(f"{inst.id}: compile failed\n{proc.stderr[-2000:]}")
        os.replace(tmp, exe)
    return exe


def encode_case(inst: Instance, values: dict[str, Any]) -> str:
    lens = array_lengths(inst, values)
    toks: list[str] = []
    for p in inst.params:
        if p.is_array:
            arr = values[p.name]
            assert len(arr) == lens[p.name], f"{p.name}: len {len(arr)} != {lens[p.name]}"
            toks.append(str(len(arr)))
            toks.extend(str(int(x)) for x in arr)
        else:
            toks.append(str(int(values[p.name])))
    return " ".join(toks)


@dataclass
class ExecResult:
    violated: bool
    kind: str | None = None
    case_index: int | None = None
    message: str = ""
    timed_out: bool = False
    cases_run: int = 0

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("violated", "kind", "case_index", "message", "timed_out", "cases_run")}


def run_cases(inst: Instance, cases: list[dict[str, Any]], timeout: float = 60.0) -> ExecResult:
    """Execute normalised cases in order; stop at the first sanitizer report."""
    exe = compile_instance(inst)
    stdin = "\n".join(encode_case(inst, c) for c in cases) + "\n"
    try:
        proc = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, timeout=timeout, env=RUN_ENV)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        started = re.findall(r"CASE (\d+)", out)
        return ExecResult(False, None, int(started[-1]) if started else None, "timeout", True, len(started))
    started = re.findall(r"CASE (\d+)", proc.stdout)
    finished = set(re.findall(r"OK (\d+)", proc.stdout))
    if proc.returncode == 0 and "END" in proc.stdout:
        return ExecResult(False, cases_run=len(finished))
    idx = next((int(c) for c in started if c not in finished), None)
    msg = proc.stderr
    m = re.search(r"(runtime error: .*|ERROR: AddressSanitizer: \S+)", msg)
    return ExecResult(
        True,
        classify(msg) or "crash",
        idx,
        m.group(1)[:300] if m else msg[-300:],
        False,
        len(finished),
    )


def run_witness(inst: Instance, values: dict[str, Any], timeout: float = 20.0) -> ExecResult:
    return run_cases(inst, [values], timeout=timeout)
