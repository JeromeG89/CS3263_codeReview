"""Problem-instance model: loading, validation of fields, precondition evaluation,
witness normalisation and rendering of instances for prompts.

An instance is a C function plus caller-guaranteed preconditions. The question is
whether some input satisfying the preconditions makes the function violate one of
the safety invariants in SAFETY_SPEC. Instances come in minimal pairs (an UNSAFE
version and a SAFE "twin" that differs by a code fix or a tighter precondition).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
INSTANCES_DIR = ROOT / "dataset" / "instances"
EXAMPLES_DIR = ROOT / "dataset" / "examples"

# C scalar types supported for parameters: name -> (bits, signed)
SCALAR_TYPES: dict[str, tuple[int, bool]] = {
    "int": (32, True),
    "unsigned": (32, False),
    "long long": (64, True),
}

CATEGORIES = ("bounds", "div_zero", "overflow", "shift")
LABELS = ("safe", "unsafe")

C_CONSTANTS = {
    "INT_MAX": 2**31 - 1,
    "INT_MIN": -(2**31),
    "UINT_MAX": 2**32 - 1,
    "LLONG_MAX": 2**63 - 1,
    "LLONG_MIN": -(2**63),
}

MAX_ARRAY_LEN = 1 << 16  # refuse to materialise larger arrays when executing witnesses

SAFETY_SPEC = """\
Safety invariants (C semantics; `int` is 32-bit two's complement, `long long` is 64-bit):
  1. bounds   - every array/pointer access (read or write) uses an index i with 0 <= i < length of that array.
  2. div_zero - the right operand of every `/` and `%` is non-zero.
  3. overflow - no signed integer arithmetic overflows: +, -, *, unary -, and also
                INT_MIN / -1 and INT_MIN % -1. (Unsigned wraparound is well-defined and NOT a violation.)
  4. shift    - for `a << b` and `a >> b`: 0 <= b < bit-width of the (promoted) left operand;
                additionally for signed `a << b`: a >= 0 and the result must be representable.
The function is UNSAFE if there EXISTS an input satisfying all preconditions that makes the
function (including any function it calls) violate at least one invariant. Otherwise it is SAFE."""


@dataclass
class Param:
    name: str
    type: str
    len: str | int | None = None  # arrays only: length expression over scalar params, or literal

    @property
    def is_array(self) -> bool:
        return self.type.endswith("[]")

    @property
    def elem_type(self) -> str:
        return self.type[:-2].strip() if self.is_array else self.type

    @property
    def bits(self) -> int:
        return SCALAR_TYPES[self.elem_type][0]

    @property
    def signed(self) -> bool:
        return SCALAR_TYPES[self.elem_type][1]

    @property
    def lo(self) -> int:
        return -(2 ** (self.bits - 1)) if self.signed else 0

    @property
    def hi(self) -> int:
        return 2 ** (self.bits - 1) - 1 if self.signed else 2**self.bits - 1


@dataclass
class Instance:
    id: str
    pair: str
    label: str
    tier: int
    category: str
    twin: str
    entry: str
    params: list[Param]
    requires: list[str]
    code: str
    reference_z3: str
    elem_requires: dict[str, str] = field(default_factory=dict)
    witness: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)
    description: str = ""
    bug_explanation: str = ""
    unwind: int = 40
    path: Path | None = None

    # ------------------------------------------------------------------ params
    @property
    def scalars(self) -> list[Param]:
        return [p for p in self.params if not p.is_array]

    @property
    def arrays(self) -> list[Param]:
        return [p for p in self.params if p.is_array]

    def param(self, name: str) -> Param:
        for p in self.params:
            if p.name == name:
                return p
        raise KeyError(name)

    @property
    def is_unsafe(self) -> bool:
        return self.label == "unsafe"

    @property
    def gold_verdict(self) -> str:
        return "UNSAFE" if self.is_unsafe else "SAFE"

    # ------------------------------------------------------------- rendering
    def precondition_lines(self) -> list[str]:
        lines = list(self.requires)
        for p in self.arrays:
            n = p.len
            lines.append(f"{p.name} points to an array of exactly {n} elements of type {p.elem_type}")
        for name, cond in self.elem_requires.items():
            lines.append(f"every element _ of {name} satisfies: {cond}")
        return lines

    def render(self) -> str:
        """C source shown to the models: preconditions as a comment, then the code."""
        pre = "\n".join(f" *   {ln}" for ln in self.precondition_lines())
        header = (
            f"/* Function under review: {self.entry}\n"
            f" * Preconditions (guaranteed by every caller of {self.entry}):\n{pre}\n */\n"
        )
        return header + self.code.strip() + "\n"

    def signature_summary(self) -> str:
        parts = []
        for p in self.params:
            if p.is_array:
                parts.append(f"{p.name}: array of {p.elem_type} (length {p.len})")
            else:
                parts.append(f"{p.name}: {p.type}")
        return ", ".join(parts)


# --------------------------------------------------------------------------- loading
def _parse_instance(data: dict, path: Path | None) -> Instance:
    params = [Param(**p) for p in data["params"]]
    inst = Instance(
        id=data["id"],
        pair=data.get("pair", data["id"]),
        label=data["label"],
        tier=int(data["tier"]),
        category=data["category"],
        twin=data.get("twin", "code"),
        entry=data["entry"],
        params=params,
        requires=[str(r) for r in data.get("requires", [])],
        elem_requires=dict(data.get("elem_requires", {}) or {}),
        code=data["code"],
        reference_z3=data["reference_z3"],
        witness=data.get("witness"),
        tags=list(data.get("tags", [])),
        description=data.get("description", ""),
        bug_explanation=data.get("bug_explanation", ""),
        unwind=int(data.get("unwind", 40)),
        path=path,
    )
    _check_instance(inst)
    return inst


def _check_instance(inst: Instance) -> None:
    assert inst.label in LABELS, f"{inst.id}: bad label {inst.label}"
    assert inst.category in CATEGORIES, f"{inst.id}: bad category {inst.category}"
    assert inst.twin in ("code", "precondition"), f"{inst.id}: bad twin kind"
    for p in inst.params:
        assert p.elem_type in SCALAR_TYPES, f"{inst.id}: unsupported type {p.type}"
        if p.is_array:
            assert p.len is not None, f"{inst.id}: array {p.name} needs len"
    if inst.is_unsafe:
        assert inst.witness is not None, f"{inst.id}: unsafe instance needs a witness"
    assert re.search(rf"\b{re.escape(inst.entry)}\s*\(", inst.code), f"{inst.id}: entry not in code"


def _raw_docs(path: Path) -> list[dict]:
    with open(path) as f:
        docs = [d for d in yaml.safe_load_all(f) if d]
    out: list[dict] = []
    for d in docs:
        out.extend(d if isinstance(d, list) else [d])
    return out


def load_dataset(directory: Path = INSTANCES_DIR) -> list[Instance]:
    raw: list[tuple[dict, Path]] = []
    for path in sorted(directory.glob("*.yaml")):
        raw.extend((d, path) for d in _raw_docs(path))
    by_id = {d["id"]: d for d, _ in raw}
    for d, _ in raw:  # precondition twins share code: `code_from: <id>`
        if "code_from" in d:
            d["code"] = by_id[d.pop("code_from")]["code"]
    insts = [_parse_instance(d, p) for d, p in raw]
    ids = [i.id for i in insts]
    dup = {x for x in ids if ids.count(x) > 1}
    assert not dup, f"duplicate ids: {dup}"
    return sorted(insts, key=lambda i: i.id)


def load_examples() -> list[Instance]:
    return load_dataset(EXAMPLES_DIR)


# ---------------------------------------------------------------- preconditions
def c_expr_to_py(expr: str) -> str:
    """Translate the restricted C expression syntax used in preconditions to Python.

    Preconditions are interpreted over mathematical integers (no overflow) and must
    not use `/` or `%` on negative operands (Python and C disagree there)."""
    e = expr.replace("&&", " and ").replace("||", " or ")
    e = re.sub(r"!(?!=)", " not ", e)
    return e


def _len_value(p: Param, scalars: dict[str, int]) -> int:
    if isinstance(p.len, int):
        return p.len
    return int(eval(c_expr_to_py(str(p.len)), {"__builtins__": {}}, {**C_CONSTANTS, **scalars}))


def array_lengths(inst: Instance, values: dict[str, Any]) -> dict[str, int]:
    scalars = {p.name: values[p.name] for p in inst.scalars if p.name in values}
    return {p.name: _len_value(p, scalars) for p in inst.arrays}


def elem_ok(cond: str, x: int, scalars: dict[str, int]) -> bool:
    """Evaluate an element precondition (`_` is the element; scalar params are in scope)."""
    return bool(eval(c_expr_to_py(cond), {"__builtins__": {}}, {**C_CONSTANTS, **scalars, "_": x}))


def check_preconditions(inst: Instance, values: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (ok, first failing clause). `values` must be normalised."""
    env = {**C_CONSTANTS, **values}
    try:
        for clause in inst.requires:
            if not eval(c_expr_to_py(clause), {"__builtins__": {}}, env):
                return False, clause
        scalars = {p.name: values[p.name] for p in inst.scalars}
        for name, cond in inst.elem_requires.items():
            for x in values[name]:
                if not elem_ok(cond, x, scalars):
                    return False, f"every element of {name}: {cond}"
    except (IndexError, KeyError, TypeError, ZeroDivisionError) as exc:
        return False, f"error evaluating preconditions: {exc!r}"
    return True, None


# -------------------------------------------------------------- witness handling
def _to_int(x: Any) -> int:
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, str):
        s = re.sub(r"(?i)(?<=\d)(ull|ul|ll|lu|llu|u|l)\b", "", x.strip())  # C suffixes: 10u, 5LL
        if s in C_CONSTANTS:
            return C_CONSTANTS[s]
        if re.fullmatch(r"[+-]?\d+", s):
            return int(s, 10)  # also accepts leading zeros
        if re.fullmatch(r"[+-]?0[xX][0-9a-fA-F]+", s):
            return int(s, 16)
        # simple constant arithmetic such as "INT_MAX - 1", "-INT_MAX", "(1 << 30)"
        if re.fullmatch(r"[\sA-Z_0-9xXa-fA-F+\-*()<>]+", s) and re.search(r"[A-Z_0-9]", s):
            try:
                v = eval(s, {"__builtins__": {}}, dict(C_CONSTANTS))
                if isinstance(v, int):
                    return v
            except Exception:  # noqa: BLE001
                pass
    raise ValueError(f"not an integer: {x!r}")


@dataclass
class NormalisedWitness:
    values: dict[str, Any]
    problems: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems


def normalise_witness(inst: Instance, raw: dict[str, Any] | None, *, strict: bool = False) -> NormalisedWitness:
    """Convert a witness (from the dataset, an LLM answer or a Z3 model) into concrete
    C values. Problems (missing params, out-of-range values, wrong array lengths) are
    recorded; with strict=False we repair what we can (pad arrays with zeros)."""
    problems: list[str] = []
    values: dict[str, Any] = {}
    raw = dict(raw or {})
    for p in inst.scalars:
        if p.name not in raw or raw[p.name] is None:
            problems.append(f"missing value for {p.name}")
            values[p.name] = 0
            continue
        try:
            v = _to_int(raw[p.name])
        except (ValueError, TypeError) as exc:
            problems.append(str(exc))
            v = 0
        if not (p.lo <= v <= p.hi):
            problems.append(f"{p.name}={v} outside range of {p.type}")
        values[p.name] = v
    try:
        lens = array_lengths(inst, values)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"cannot compute array length: {exc!r}")
        lens = {p.name: 0 for p in inst.arrays}
    for p in inst.arrays:
        n = lens[p.name]
        if n < 0 or n > MAX_ARRAY_LEN:
            problems.append(f"array length {n} for {p.name} not executable")
            n = max(0, min(n, 0))
        arr = raw.get(p.name)
        if arr is None:
            arr = []
            if n:
                problems.append(f"missing contents for array {p.name}")
        if not isinstance(arr, (list, tuple)):
            problems.append(f"array {p.name} is not a list")
            arr = []
        try:
            arr = [_to_int(x) for x in arr]
        except (ValueError, TypeError) as exc:
            problems.append(str(exc))
            arr = []
        if len(arr) != n:
            if strict:
                problems.append(f"array {p.name} has {len(arr)} elements, expected {n}")
            arr = (arr + [0] * n)[:n]
        bad = [x for x in arr if not (p.lo <= x <= p.hi)]
        if bad:
            problems.append(f"array {p.name} has out-of-range elements {bad[:3]}")
        values[p.name] = arr
    return NormalisedWitness(values, problems)
