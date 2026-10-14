"""Sandboxed execution of (untrusted) Z3 scripts and interpretation of their results."""
from __future__ import annotations

import socket
import time

import pytest

from invcheck.z3run import USE_SANDBOX, execute_script, run_and_interpret, validate_witness

FAST_REFERENCE = [
    "T1-BND-01-U", "T1-BND-01-S", "T1-BND-03-U", "T1-BND-03-S", "T1-DIV-01-U", "T1-DIV-01-S",
    "T1-DIV-05-U", "T1-DIV-05-S", "T1-OVF-02-U", "T1-OVF-02-S", "T1-SHF-01-U", "T1-SHF-01-S",
    "T2-BND-02-U", "T2-BND-02-S",
]

needs_sandbox = pytest.mark.skipif(not USE_SANDBOX, reason="sandbox-exec is only used on macOS")


def _with_solver(body: str) -> str:
    return f"{body}\nfrom z3 import *\ns = Solver()\n"


# ---------------------------------------------------------------- reference encodings
@pytest.mark.parametrize("iid", FAST_REFERENCE)
def test_reference_encoding_gives_gold_verdict(by_id, iid):
    inst = by_id[iid]
    out = run_and_interpret(inst.reference_z3, inst)
    assert out.error_type is None, out.error
    assert out.verdict == inst.gold_verdict
    if inst.is_unsafe:
        assert out.status == "sat" and out.witness_status == "confirmed", out.witness_detail
    else:
        assert out.status == "unsat" and out.witness is None


@pytest.mark.slow
def test_all_tier1_reference_encodings(dataset):
    for inst in dataset:
        if inst.tier == 1:
            out = run_and_interpret(inst.reference_z3, inst)
            assert out.verdict == inst.gold_verdict, inst.id
            assert not inst.is_unsafe or out.witness_status == "confirmed", inst.id


def test_model_values_signed_unsigned_and_arrays(by_id):
    r = execute_script(by_id["T1-OVF-02-U"].reference_z3, by_id["T1-OVF-02-U"])
    assert r["status"] == "sat" and r["model"] == {"x": -(2**31), "d": -1}  # signed decoding
    inst = by_id["T1-DIV-05-U"]  # unsigned total, slots
    r = execute_script("from z3 import *\ntotal, slots = BitVecs('total slots', 32)\ns = Solver()\n"
                       "s.add(total == 1, slots == 0xFFFFFFFF)", inst)
    assert r["model"] == {"total": 1, "slots": 2**32 - 1}  # unsigned decoding
    inst = by_id["T1-BND-01-U"]
    r = execute_script(inst.reference_z3, inst)
    assert r["status"] == "sat" and len(r["model"]["buf"]) == r["model"]["n"]


def test_missing_params_default_to_zero(by_id):
    inst = by_id["T1-DIV-01-U"]
    r = execute_script("from z3 import *\ncount = Int('count')\ns = Solver()\ns.add(count == 0)", inst)
    assert r["status"] == "sat" and r["missing_params"] == ["total"] and r["model"] == {"total": 0, "count": 0}


def test_solver_named_solver_is_accepted(by_id):
    r = execute_script("from z3 import *\nsolver = Solver()\nsolver.add(False)", by_id["T1-DIV-01-U"])
    assert r["status"] == "unsat" and r["solver_var"] == "solver"


# ------------------------------------------------------------------- witness checking
def test_witness_statuses(by_id):
    inst = by_id["T1-DIV-01-U"]
    base = "from z3 import *\ntotal, count = BitVecs('total count', 32)\ns = Solver()\n"
    out = run_and_interpret(base + "s.add(total == 5, count == 1)", inst)
    assert (out.verdict, out.witness_status) == ("UNSAFE", "not_reproduced")  # spurious cex
    out = run_and_interpret(base + "s.add(total == -5, count == 0)", inst)
    assert out.witness_status == "precondition_violated"
    out = run_and_interpret("from z3 import *\ntotal, count = Ints('total count')\ns = Solver()\n"
                            "s.add(total == 2**40, count == 0)", inst)
    assert out.witness_status == "invalid" and "outside range" in out.witness_detail


def test_validate_witness_direct(by_id):
    inst = by_id["T1-DIV-01-U"]
    assert validate_witness(inst, None)[0] == "invalid"
    assert validate_witness(inst, {"total": "10", "count": "0"})[:3] == (
        "confirmed", "runtime error: division by zero", "div_zero")
    assert validate_witness(inst, {"total": 10, "count": 5})[0] == "not_reproduced"
    assert validate_witness(inst, {"total": "INT_MAX", "count": 0})[0] == "precondition_violated"


def test_validate_witness_repairs_unread_elements(example):
    # EX-01 reads only a[i]; a[0] violates the element precondition but is never read
    status, detail, kind, vals = validate_witness(example, {"a": [10**6, 0, 0], "n": 3, "i": 3, "k": 1})
    assert status == "confirmed" and kind == "bounds" and "replaced" in detail and vals["a"][0] != 10**6


def test_unparseable_witness_value_is_invalid(by_id):
    assert validate_witness(by_id["T1-DIV-01-U"], {"total": 10, "count": "zero"})[0] == "invalid"


# ---------------------------------------------------------------- robustness / sandbox
def test_syntax_error(by_id):
    r = execute_script("from z3 import *\ns = Solver(\n", by_id["T1-DIV-01-U"])
    assert r["status"] == "error" and r["error_type"] == "syntax" and "line" in r["error"]


def test_hallucinated_function_gets_hint(by_id):
    code = "from z3 import *\nx = BitVec('x', 32)\ns = Solver()\ns.add(Not(BVAddNoOverflw(x, x, True)))"
    r = execute_script(code, by_id["T1-DIV-01-U"])
    assert r["error_type"] == "name_error"
    assert "Similar existing names:" in r["error"] and "BVAddNoOverflow" in r["error"]


def test_z3_api_misuse(by_id):
    r = execute_script("from z3 import *\ns = Solver()\ns.add(BitVec('a', 32) == BitVec('b', 8))", by_id["T1-DIV-01-U"])
    assert r["status"] == "error" and r["error_type"] == "z3_api"


def test_no_solver(by_id):
    r = execute_script("from z3 import *\nx = Int('x')", by_id["T1-DIV-01-U"])
    assert r["error_type"] == "no_solver"


def test_runtime_error_and_exit(by_id):
    inst = by_id["T1-DIV-01-U"]
    assert execute_script("from z3 import *\ns = Solver()\n1 / 0", inst)["error_type"] == "runtime"
    r = execute_script("import sys\nsys.exit(3)", inst)
    assert r["error_type"] == "runtime" and "exit(3)" in r["error"]
    r = execute_script("import os\nos._exit(3)", inst)  # child dies without writing JSON
    assert r["status"] == "error" and r["error_type"] == "crash"


def test_print_output_captured_not_mixed_into_protocol(by_id):
    r = execute_script("print('hello')\nfrom z3 import *\ns = Solver()\ns.add(False)", by_id["T1-DIV-01-U"])
    assert r["status"] == "unsat" and r["stdout"] == "hello\n"


def test_script_raising_stop_iteration(by_id):
    r = execute_script("next(iter([]))", by_id["T1-DIV-01-U"])
    assert r["status"] == "error" and r["error_type"] is not None and r["error"]


def test_infinite_loop_hits_wall_timeout(by_id):
    t0 = time.time()
    r = execute_script("while True:\n    pass", by_id["T1-DIV-01-U"], wall_s=2)
    assert r["error_type"] == "timeout" and time.time() - t0 < 10


def test_environment_is_scrubbed(by_id, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-should-not-leak")
    r = execute_script(_with_solver("import os\nprint(sorted(os.environ.items()))"), by_id["T1-DIV-01-U"])
    assert r["status"] == "sat" and "test-secret-should-not-leak" not in r["stdout"]
    assert "GEMINI_API_KEY" not in r["stdout"]


def test_can_write_inside_own_temp_dir(by_id):
    r = execute_script(_with_solver("open('scratch.txt', 'w').write('ok')"), by_id["T1-DIV-01-U"])
    assert r["status"] == "sat"


@needs_sandbox
def test_cannot_write_outside_temp_dir(by_id, tmp_path):
    target = tmp_path / "escaped.txt"
    r = execute_script(_with_solver(f"open({str(target)!r}, 'w').write('x')"), by_id["T1-DIV-01-U"])
    assert r["status"] == "error" and "Operation not permitted" in r["error"]
    assert not target.exists()


@needs_sandbox
def test_network_is_denied(by_id):
    # a local listener stands in for "the network": no packet ever leaves the machine
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.setblocking(False)
    port = srv.getsockname()[1]
    try:
        code = _with_solver(f"import socket\nsocket.create_connection(('127.0.0.1', {port}), timeout=3)")
        r = execute_script(code, by_id["T1-DIV-01-U"])
        assert r["status"] == "error" and "Operation not permitted" in r["error"]
        with pytest.raises(BlockingIOError):
            srv.accept()
    finally:
        srv.close()


def test_missing_scalar_in_llm_witness_is_invalid(by_id):
    assert validate_witness(by_id["T1-DIV-01-U"], {"total": 10})[0] == "invalid"
