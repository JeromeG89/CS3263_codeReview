"""Robust extraction of verdict JSON and Python code from free-form model output."""
from __future__ import annotations

import json
import re
from typing import Any


def _json_candidates(text: str) -> list[str]:
    cands = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    # balanced-brace scan for bare objects, last ones first (final answers come last)
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                cands.append(text[start:i + 1])
    return cands


def _outside_strings(text: str, pattern: str, repl) -> str:
    """re.sub that leaves double-quoted JSON strings untouched."""
    rx = re.compile(r'"(?:\\.|[^"\\])*"|(' + pattern + ")")
    return rx.sub(lambda m: m.group(0) if m.group(1) is None else repl(re.match(pattern, m.group(1))), text)


def _loads_lenient(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    t = _outside_strings(s, r"//[^\n]*", lambda m: "")  # comments
    t = re.sub(r",\s*([}\]])", r"\1", t)  # trailing commas
    t = re.sub(r"\bNone\b", "null", t)
    t = re.sub(r"\bTrue\b", "true", t)
    t = re.sub(r"\bFalse\b", "false", t)
    t = re.sub(r"(?<![\w\"])'([^'\n]*)'", r'"\1"', t)  # single-quoted strings
    t = _outside_strings(t, r"-?\b(?:INT_MAX|INT_MIN|UINT_MAX|LLONG_MAX|LLONG_MIN)\b", lambda m: f'"{m.group(0)}"')
    return json.loads(t)


def parse_verdict(text: str) -> dict[str, Any]:
    """Return {verdict: SAFE|UNSAFE|UNKNOWN, violation, witness, explanation, parse: how}."""
    for cand in reversed(_json_candidates(text)):
        try:
            d = _loads_lenient(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(d, dict) and "verdict" in d:
            v = str(d.get("verdict", "")).strip().upper()
            if v in ("SAFE", "UNSAFE"):
                w = d.get("witness")
                return {"verdict": v, "violation": d.get("violation"),
                        "witness": w if isinstance(w, dict) else None,
                        "explanation": d.get("explanation", ""), "parse": "json"}
    # fallback: last standalone SAFE/UNSAFE token
    toks = re.findall(r"\b(UNSAFE|SAFE)\b", text)
    if toks:
        return {"verdict": toks[-1], "violation": None, "witness": None, "explanation": "", "parse": "keyword"}
    return {"verdict": "UNKNOWN", "violation": None, "witness": None, "explanation": "", "parse": "failed"}


def extract_python(text: str) -> str | None:
    text = text.replace("\r\n", "\n")
    blocks = re.findall(r"```(?:python|py|Python)?[ \t]*\n(.*?)```", text, flags=re.S)
    blocks = [b for b in blocks if "z3" in b or "Solver" in b] or blocks
    if blocks:
        return max(blocks, key=len)
    if "Solver" in text and ("from z3" in text or "import z3" in text):
        # unfenced code: take from the import onwards
        m = re.search(r"(from z3 import|import z3)", text)
        return text[m.start():] if m else text
    return None
