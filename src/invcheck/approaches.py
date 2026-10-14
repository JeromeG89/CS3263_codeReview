"""The evaluated approaches. Each returns a JSON-serialisable record for one
(model, approach, instance) triple. Records never contain ground truth except
in the explicit `gold` field added by the runner."""
from __future__ import annotations

import time
from typing import Any, Callable

from . import prompts
from .dataset import Instance
from .llm import LLM
from .parse import extract_python, parse_verdict
from .z3run import run_and_interpret, validate_witness


def _base(llm: LLM | None, approach: str, inst: Instance) -> dict[str, Any]:
    return {"instance": inst.id, "model": llm.name if llm else "none", "approach": approach,
            "verdict": "UNKNOWN", "violation": None, "witness": None, "witness_status": None,
            "witness_detail": "", "exec_kind": None, "llm_calls": 0, "input_tokens": 0,
            "output_tokens": 0, "llm_latency_s": 0.0, "error": None, "transcript": []}


def _account(rec: dict, comp) -> None:
    rec["llm_calls"] += 1
    rec["input_tokens"] += comp.input_tokens
    rec["output_tokens"] += comp.output_tokens
    rec["llm_latency_s"] += comp.latency_s


def run_direct(llm: LLM, inst: Instance, cot: bool = False, **_) -> dict[str, Any]:
    rec = _base(llm, "direct_cot" if cot else "direct", inst)
    prompt = prompts.direct_cot(inst) if cot else prompts.direct(inst)
    comp = llm.chat(prompts.SYSTEM, [{"role": "user", "content": prompt}])
    _account(rec, comp)
    rec["transcript"].append({"role": "assistant", "content": comp.text})
    if comp.error:
        rec["error"] = comp.error
        return rec
    p = parse_verdict(comp.text)
    rec.update(verdict=p["verdict"], violation=p["violation"], parse=p["parse"], explanation=p["explanation"])
    if p["verdict"] == "UNSAFE":
        ws, detail, kind, vals = validate_witness(inst, p["witness"])
        rec.update(witness=vals if vals is not None else p["witness"], witness_status=ws,
                   witness_detail=detail, exec_kind=kind)
    return rec


def run_z3(llm: LLM, inst: Instance, *, guided: bool = False, example: Instance | None = None,
           max_repairs: int = 0, cex_feedback: bool = False, approach: str | None = None, **_) -> dict[str, Any]:
    name = approach or ("z3_guided" if guided else "z3")
    rec = _base(llm, name, inst)
    rec["attempts"] = []
    user = prompts.z3_guided(inst, example) if guided else prompts.z3(inst)
    messages = [{"role": "user", "content": user}]
    for attempt in range(max_repairs + 1):
        comp = llm.chat(prompts.SYSTEM, messages)
        _account(rec, comp)
        rec["transcript"].append({"role": "assistant", "content": comp.text})
        if comp.error:
            rec["error"] = comp.error
            break
        messages.append({"role": "assistant", "content": comp.text})
        code = extract_python(comp.text)
        att: dict[str, Any] = {"attempt": attempt, "code": code}
        if code is None:
            att.update(status="error", error_type="no_code", error="no Python code block found in the reply",
                       verdict="UNKNOWN")
            rec["attempts"].append(att)
            feedback = prompts.repair_error("no_code", "No ```python code block was found in your reply.")
        else:
            t0 = time.time()
            out = run_and_interpret(code, inst)
            att.update(out.as_dict())
            att["solver_s"] = round(time.time() - t0, 3)
            rec["attempts"].append(att)
            if out.status == "error" or out.status == "unknown":
                feedback = prompts.repair_error(out.error_type or "error", out.error or "solver returned unknown")
            elif out.status == "sat" and cex_feedback and out.witness_status != "confirmed":
                feedback = prompts.repair_counterexample(out.witness, out.witness_detail, out.witness_status)
            else:
                break
        if attempt < max_repairs:
            messages.append({"role": "user", "content": feedback})
            rec["transcript"].append({"role": "user", "content": feedback})
    last = rec["attempts"][-1] if rec["attempts"] else {}
    rec.update(
        verdict=last.get("verdict", "UNKNOWN"),
        witness=last.get("witness"),
        witness_status=last.get("witness_status"),
        witness_detail=last.get("witness_detail", ""),
        exec_kind=last.get("exec_kind"),
        z3_status=last.get("status"),
        z3_error_type=last.get("error_type"),
        repairs_used=max(0, len(rec["attempts"]) - 1),
        first_attempt_verdict=rec["attempts"][0].get("verdict", "UNKNOWN") if rec["attempts"] else "UNKNOWN",
    )
    return rec


def run_reference_z3(inst: Instance) -> dict[str, Any]:
    """Gold (Claude-authored) translation: the upper bound for the tool approach."""
    rec = _base(None, "reference_z3", inst)
    out = run_and_interpret(inst.reference_z3, inst)
    rec.update(model="reference", verdict=out.verdict, witness=out.witness, witness_status=out.witness_status,
               witness_detail=out.witness_detail, exec_kind=out.exec_kind, z3_status=out.status,
               z3_error_type=out.error_type, error=out.error or None)
    return rec


APPROACHES: dict[str, Callable[..., dict[str, Any]]] = {
    "direct": lambda llm, inst, **kw: run_direct(llm, inst, cot=False),
    "direct_cot": lambda llm, inst, **kw: run_direct(llm, inst, cot=True),
    "z3": lambda llm, inst, **kw: run_z3(llm, inst, guided=False),
    "z3_guided": lambda llm, inst, example=None, **kw: run_z3(llm, inst, guided=True, example=example),
    "z3_repair": lambda llm, inst, example=None, **kw: run_z3(
        llm, inst, guided=True, example=example, max_repairs=kw.get("max_repairs", 3), cex_feedback=True,
        approach="z3_repair"),
}
