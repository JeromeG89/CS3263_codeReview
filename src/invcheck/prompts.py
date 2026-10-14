"""Prompt templates for every approach. Kept in one place so the report can quote them.

Approaches
  direct      LLM answers SAFE/UNSAFE + witness immediately (no reasoning text).
  direct_cot  LLM reasons step by step, then answers.
  z3          LLM translates the problem into a Z3 script (bare protocol only).
  z3_guided   As z3, plus "tool knowledge": C-to-Z3 semantic pitfalls and a worked example.
  z3_repair   As z3_guided, plus up to K feedback rounds on execution errors and on
              counterexamples that fail to reproduce when the real C code is executed.
"""
from __future__ import annotations

from .dataset import SAFETY_SPEC, Instance

SYSTEM = (
    "You are an expert C code reviewer and formal-methods engineer. You check whether C functions "
    "can violate memory- and arithmetic-safety invariants, given the preconditions their callers guarantee."
)


def _problem(inst: Instance) -> str:
    return (
        f"{SAFETY_SPEC}\n\n"
        f"Parameters of `{inst.entry}`: {inst.signature_summary()}\n\n"
        f"```c\n{inst.render()}```\n"
    )


_WITNESS_RULES = (
    "If UNSAFE, \"witness\" must give concrete integer values for EVERY parameter of the function that satisfy "
    "all preconditions and trigger the violation. Give array parameters as JSON lists with exactly the "
    "required number of elements. If SAFE, \"witness\" is null."
)

_JSON_SCHEMA = (
    '{"verdict": "SAFE" or "UNSAFE", "violation": "bounds" | "div_zero" | "overflow" | "shift" | "none", '
    '"witness": {"<param>": <value>, ...} or null, "explanation": "<one sentence>"}'
)


def direct(inst: Instance) -> str:
    return (
        f"Decide whether the following function is SAFE or UNSAFE.\n\n{_problem(inst)}\n"
        f"Answer immediately with ONLY a JSON object (no reasoning, no markdown):\n{_JSON_SCHEMA}\n"
        f"{_WITNESS_RULES}"
    )


def direct_cot(inst: Instance) -> str:
    return (
        f"Decide whether the following function is SAFE or UNSAFE.\n\n{_problem(inst)}\n"
        "Think step by step. For every array access, division/modulo, signed arithmetic operation and shift, "
        "derive the range of values its operands can take under the preconditions and the path conditions that "
        "reach it, and check the corresponding invariant. Then search for a concrete counterexample and "
        "double-check it against the preconditions.\n\n"
        f"Finish your answer with the final JSON object in a ```json code block:\n{_JSON_SCHEMA}\n{_WITNESS_RULES}"
    )


Z3_PROTOCOL = """\
Write a Python script using the `z3` package (`from z3 import *`) that encodes this question as a
satisfiability problem, following this protocol EXACTLY:
  1. Declare one Z3 constant per function parameter, using exactly the parameter's name as the Z3 name
     (e.g. `n = BitVec('n', 32)` or `n = Int('n')`). Declare array parameters as Z3 arrays named after
     the parameter (e.g. `a = Array('a', BitVecSort(32), BitVecSort(32))`).
  2. Create the solver with `s = Solver()`.
  3. Add every precondition to `s`.
  4. Add ONE constraint to `s` stating that at least one invariant is violated: a disjunction over every
     potentially-unsafe operation, each conjoined with the path condition under which it executes.
Then `s` is satisfiable exactly when the function is UNSAFE, and any model is a counterexample.
Do NOT call s.check(), do NOT use push()/pop(), and do not print anything; we run the solver ourselves.
Reply with a single ```python code block containing the complete script."""


Z3_GUIDANCE = """\
Modelling guidance (C semantics in Z3 -- common pitfalls):
  * Model `int` as BitVec(..., 32) and `long long` as BitVec(..., 64). With BitVecs, `<`, `<=`, `>`, `>=`, `/`
    and `>>` are SIGNED (C semantics for int). For `unsigned` use ULT/ULE/UGT/UGE, UDiv, URem, LShR.
  * C's `%` is NOT Z3's `%` on bit-vectors (Z3's follows the divisor's sign). Use SRem(a, b) for C's `a % b`.
  * Signed overflow of an operation: Not(BVAddNoOverflow(a, b, True)) or Not(BVAddNoUnderflow(a, b)) for +;
    Not(BVSubNoOverflow(a, b)) or Not(BVSubNoUnderflow(a, b, True)) for -; Not(BVMulNoOverflow(a, b, True)) or
    Not(BVMulNoUnderflow(a, b)) for *; Not(BVSDivNoOverflow(a, b)) for / and % (INT_MIN / -1);
    Not(BVSNegNoOverflow(a)) for unary minus. Alternatively compute in 64 bits with SignExt(32, a) and range-check.
  * If you use Int instead of BitVec: Int `/` and `%` are Euclidean division (the remainder is never negative),
    which differs from C's truncation toward zero for negative operands, and you must explicitly check every
    intermediate result lies in [-2**31, 2**31 - 1].
  * Combine conditions with Or(...), And(...), Not(...), Implies(...). Do NOT use Python's `|`, `&`, `or`, `and`
    on comparisons (`x < 0 | x > 5` parses as `x < (0 | x) > 5`).
  * Only use functions that exist in z3: the overflow helpers are exactly the eight named above.
  * Mixed int/long long arithmetic: convert with SignExt(32, x). Casts (long long)x likewise.
  * Statements execute in order: give each assignment a fresh name (SSA) or use Python variables holding Z3
    expressions, and use If(cond, a, b) to merge values after branches.
  * Loops: the preconditions bound the iteration count, so unroll the loop in Python up to that bound; guard
    every operation in iteration t with the condition that iteration t actually executes.
  * Function calls: inline the callee.
  * An access a[i] is in bounds iff 0 <= i and i < (length of a). Element preconditions only need to be added
    for the elements the function actually reads (e.g. s.add(Implies(And(0 <= i, i < n), a[i] >= 0))).
  * Report a violation only if it can actually execute: conjoin each check with its path condition, and remember
    that an earlier violation does not need to "stop" execution -- any reachable violation makes the function UNSAFE."""


def _example_block(example: Instance) -> str:
    return (
        "Worked example.\n"
        f"Parameters of `{example.entry}`: {example.signature_summary()}\n"
        f"```c\n{example.render()}```\n"
        f"A correct script:\n```python\n{example.reference_z3.strip()}\n```\n"
    )


def z3(inst: Instance) -> str:
    return f"{_problem(inst)}\n{Z3_PROTOCOL}"


def z3_guided(inst: Instance, example: Instance | None) -> str:
    ex = _example_block(example) + "\nNow the actual task.\n\n" if example is not None else ""
    return f"{Z3_GUIDANCE}\n\n{Z3_PROTOCOL}\n\n{ex}{_problem(inst)}\n{Z3_PROTOCOL}"


def repair_error(error_type: str, error: str) -> str:
    return (
        f"Running your script failed ({error_type}):\n```\n{error.strip()[:1500]}\n```\n"
        "Fix the problem and reply with the complete corrected script in a single ```python code block, "
        "still following the protocol (solver named `s`, parameters declared under their exact names, no s.check())."
    )


def repair_counterexample(witness: dict, detail: str, status: str) -> str:
    if status == "precondition_violated":
        why = f"these inputs do not satisfy the preconditions ({detail}), so your preconditions are encoded incorrectly or incompletely"
    elif status == "invalid":
        why = f"these inputs are not valid C values for the parameters ({detail}); check bit-widths and value ranges"
    else:
        why = ("we executed the real C function on these inputs and NO invariant was violated, so this "
               "counterexample is spurious and your encoding of the C semantics is inaccurate somewhere")
    return (
        f"Z3 reported a counterexample: {witness}\nHowever, {why}.\n"
        "Re-examine your encoding (semantics of each operator, path conditions, preconditions, bit-widths) "
        "and reply with the complete corrected script in a single ```python code block, following the same protocol. "
        "If after re-examination you believe the function cannot violate any invariant, your script should be unsatisfiable."
    )
