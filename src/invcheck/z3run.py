"""Run a Z3 script in an isolated subprocess and interpret the result for an instance.

Isolation (defence in depth for untrusted LLM-generated code):
  * separate interpreter (`python -I -B`), scrubbed environment (no API keys),
  * fresh temporary working directory, wall-clock timeout, CPU/memory rlimits,
  * on macOS, `sandbox-exec` denies network access and writes outside the temp dir.
"""
from __future__ import annotations

import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cexec import run_witness
from .dataset import Instance, c_expr_to_py, check_preconditions, elem_ok, normalise_witness

CHILD = Path(__file__).with_name("z3_child.py")
USE_SANDBOX = platform.system() == "Darwin" and shutil.which("sandbox-exec") is not None


def _limits():  # runs in the child before exec
    resource.setrlimit(resource.RLIMIT_CPU, (600, 610))
    try:
        resource.setrlimit(resource.RLIMIT_DATA, (4 << 30, 4 << 30))
    except (ValueError, OSError):
        pass


def _sandbox_profile(tmp: str) -> str:
    real = os.path.realpath(tmp)
    return (
        "(version 1)(allow default)(deny network*)"
        f'(deny file-write* (require-not (require-any (subpath "{real}") (subpath "{tmp}")'
        ' (literal "/dev/null") (literal "/dev/stdout") (literal "/dev/stderr") (regex #"^/dev/tty"))))'
    )


def execute_script(code: str, inst: Instance, timeout_ms: int = 30000, wall_s: float = 90.0) -> dict[str, Any]:
    job = {
        "code": code,
        "timeout_ms": timeout_ms,
        "params": [
            {"name": p.name, "array": p.is_array, "signed": p.signed,
             "length_expr": c_expr_to_py(str(p.len)) if p.is_array else None}
            for p in inst.params
        ],
    }
    env = {"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0", "HOME": "/nonexistent"}
    with tempfile.TemporaryDirectory(prefix="z3job-") as tmp:
        cmd = [sys.executable, "-I", "-B", str(CHILD)]
        if USE_SANDBOX:
            cmd = ["sandbox-exec", "-p", _sandbox_profile(tmp), *cmd]
        try:
            proc = subprocess.run(cmd, input=json.dumps(job), capture_output=True, text=True,
                                  timeout=wall_s, cwd=tmp, env=env, preexec_fn=_limits)
        except subprocess.TimeoutExpired:
            return {"status": "error", "error_type": "timeout", "error": f"script exceeded {wall_s}s", "model": {}}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "error_type": "crash",
                "error": (proc.stderr or proc.stdout)[-1500:] or f"exit code {proc.returncode}", "model": {}}


@dataclass
class Z3Outcome:
    verdict: str  # SAFE | UNSAFE | UNKNOWN
    status: str  # sat | unsat | unknown | error
    error_type: str | None
    error: str
    witness: dict[str, Any] | None = None
    witness_status: str | None = None  # confirmed | not_reproduced | precondition_violated | invalid
    witness_detail: str = ""
    exec_kind: str | None = None
    missing_params: list[str] = field(default_factory=list)
    num_assertions: int | None = None

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _repair_elements(inst: Instance, values: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Replace array elements that violate their element precondition by a value that
    satisfies it. Models often leave elements the function never reads unconstrained;
    such elements cannot influence execution. If a replaced element *is* read, the
    witness will simply fail to reproduce (conservative)."""
    from .fuzz import harvest_constants

    out = dict(values)
    changed = False
    cands = [0, 1, -1, 2] + harvest_constants(inst)
    scalars = {p.name: values[p.name] for p in inst.scalars}
    env_ok = lambda cond, x: elem_ok(cond, x, scalars)  # noqa: E731
    for name, cond in inst.elem_requires.items():
        good = next((c for c in cands if env_ok(cond, c)), None)
        if good is None:
            continue
        arr = list(out[name])
        for j, x in enumerate(arr):
            if not env_ok(cond, x):
                arr[j] = good
                changed = True
        out[name] = arr
    return out, changed


def validate_witness(inst: Instance, raw: dict[str, Any] | None) -> tuple[str, str, str | None, dict | None]:
    """Return (status, detail, violation kind, normalised values)."""
    if not raw:
        return "invalid", "no witness", None, None
    nw = normalise_witness(inst, raw)
    hard = [p for p in nw.problems if any(k in p for k in
            ("outside range", "not executable", "not an integer", "missing value", "cannot compute"))]
    if hard:
        return "invalid", "; ".join(nw.problems), None, nw.values
    values = nw.values
    ok, clause = check_preconditions(inst, values)
    repaired = False
    if not ok and inst.elem_requires:
        values, repaired = _repair_elements(inst, values)
        ok, clause = check_preconditions(inst, values)
    if not ok:
        return "precondition_violated", f"violates precondition: {clause}", None, values
    res = run_witness(inst, values)
    note = " (array elements violating element preconditions were replaced)" if repaired else ""
    if res.violated:
        return "confirmed", res.message + note, res.kind, values
    if res.timed_out:
        return "not_reproduced", "execution timed out", None, nw.values
    return "not_reproduced", "execution completed without any violation", None, nw.values


def run_and_interpret(code: str, inst: Instance, timeout_ms: int = 30000, wall_s: float | None = None) -> Z3Outcome:
    r = execute_script(code, inst, timeout_ms=timeout_ms, wall_s=wall_s if wall_s is not None else timeout_ms / 1000 + 60)
    status = r.get("status", "error")
    out = Z3Outcome(
        verdict={"sat": "UNSAFE", "unsat": "SAFE"}.get(status, "UNKNOWN"),
        status=status,
        error_type=r.get("error_type"),
        error=r.get("error", "") or "",
        missing_params=r.get("missing_params", []),
        num_assertions=r.get("num_assertions"),
    )
    if status == "sat":
        ws, detail, kind, vals = validate_witness(inst, r.get("model"))
        out.witness, out.witness_status, out.witness_detail, out.exec_kind = vals, ws, detail, kind
    return out
