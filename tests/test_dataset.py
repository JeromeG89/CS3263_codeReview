"""Dataset loading, precondition evaluation and witness normalisation."""
from __future__ import annotations

from collections import defaultdict

import pytest

from invcheck.dataset import (C_CONSTANTS, INSTANCES_DIR, MAX_ARRAY_LEN, _raw_docs, _to_int, array_lengths,
                              c_expr_to_py, check_preconditions, elem_ok, normalise_witness)


# ----------------------------------------------------------------------------- loading
def test_size_and_unique_ids(dataset):
    assert len(dataset) == 120
    ids = [i.id for i in dataset]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)
    assert not any(i.startswith("STRESS") for i in ids), "stress instances must stay out of the evaluation set"


def test_pairs_have_one_safe_and_one_unsafe(dataset):
    pairs = defaultdict(list)
    for inst in dataset:
        pairs[inst.pair].append(inst)
    assert len(pairs) == 60
    for pair, members in pairs.items():
        assert sorted(m.label for m in members) == ["safe", "unsafe"], pair
        u, s = sorted(members, key=lambda m: m.label, reverse=True)
        assert (u.id, s.id) == (f"{pair}-U", f"{pair}-S")
        # twins differ only in code or in preconditions, never in the interface
        assert (u.tier, u.category, u.twin, u.entry) == (s.tier, s.category, s.twin, s.entry), pair
        assert [(p.name, p.type, p.len) for p in u.params] == [(p.name, p.type, p.len) for p in s.params], pair
        if u.twin == "precondition":
            assert u.code == s.code, pair
            assert (u.requires, u.elem_requires) != (s.requires, s.elem_requires), pair
        else:
            assert u.code != s.code, pair


def test_balanced_labels_and_tiers(dataset):
    assert sum(i.is_unsafe for i in dataset) == 60
    assert {i.tier for i in dataset} == {1, 2, 3, 4}
    assert {i.category for i in dataset} == {"bounds", "div_zero", "overflow", "shift"}
    assert all(i.gold_verdict == ("UNSAFE" if i.is_unsafe else "SAFE") for i in dataset)


def test_code_from_resolution(by_id):
    raw = {d["id"]: d for p in INSTANCES_DIR.glob("*.yaml") for d in _raw_docs(p)}
    linked = {k: d["code_from"] for k, d in raw.items() if "code_from" in d}
    assert linked, "expected some precondition twins to use code_from"
    for iid, src in linked.items():
        assert "code" not in raw[iid]
        assert by_id[iid].code == by_id[src].code
    assert by_id["T1-BND-01-S"].code == by_id["T1-BND-01-U"].code


def test_every_unsafe_has_valid_witness(dataset):
    for inst in dataset:
        if not inst.is_unsafe:
            assert inst.witness is None, inst.id
            continue
        nw = normalise_witness(inst, inst.witness, strict=True)
        assert nw.ok, (inst.id, nw.problems)
        assert check_preconditions(inst, nw.values) == (True, None), inst.id


def test_render_shows_preconditions_not_labels(by_id):
    inst = by_id["T2-BND-02-U"]
    text = inst.render()
    assert inst.code.strip() in text
    assert "every element _ of a satisfies: -1000000 <= _ && _ <= 1000000" in text
    assert "a points to an array of exactly n elements of type int" in text
    assert inst.id not in text and "unsafe" not in text.lower()


def test_examples(example):
    assert example.id == "EX-01" and example.elem_requires
    nw = normalise_witness(example, example.witness, strict=True)
    assert nw.ok and check_preconditions(example, nw.values)[0]


# ----------------------------------------------------------------------- preconditions
@pytest.mark.parametrize("c, py", [
    ("1 <= n && n <= 64", "1 <= n  and  n <= 64"),
    ("a < 0 || b < 0", "a < 0  or  b < 0"),
    ("x != 0", "x != 0"),
    ("!(x == 0)", " not (x == 0)"),
])
def test_c_expr_to_py(c, py):
    assert c_expr_to_py(c) == py


@pytest.mark.parametrize("expr, env, expected", [
    ("1 <= n && n <= 64", {"n": 64}, True),
    ("1 <= n && n <= 64", {"n": 65}, False),
    ("x > INT_MIN || y", {"x": -(2**31), "y": 0}, False),
    ("!(x != 0) && y == 1", {"x": 0, "y": 1}, True),
])
def test_c_expr_semantics(expr, env, expected):
    assert bool(eval(c_expr_to_py(expr), {"__builtins__": {}}, {**C_CONSTANTS, **env})) is expected


def test_array_length_expressions(by_id):
    inst = by_id["T4-BND-02-U"]  # len: n * (n + 1) / 2
    n = 5
    assert array_lengths(inst, {"n": n, **{p.name: 0 for p in inst.scalars if p.name != "n"}}) == {
        p.name: n * (n + 1) // 2 for p in inst.arrays}


def test_check_preconditions(by_id):
    inst = by_id["T1-DIV-01-U"]  # 0 <= total <= 1e6, 0 <= count <= 1000
    assert check_preconditions(inst, {"total": 10, "count": 0}) == (True, None)
    ok, clause = check_preconditions(inst, {"total": -1, "count": 0})
    assert not ok and clause == "0 <= total && total <= 1000000"
    ok, clause = check_preconditions(inst, {"total": 0, "count": 1001})
    assert not ok and clause == "0 <= count && count <= 1000"


def test_check_preconditions_elements(by_id):
    inst = by_id["T2-BND-02-U"]  # elements in [-1e6, 1e6]
    vals = {"a": [1, 2], "n": 2, "i": 0, "j": 5}
    assert check_preconditions(inst, vals) == (True, None)
    ok, clause = check_preconditions(inst, {**vals, "a": [1, 10**7]})
    assert not ok and clause.startswith("every element of a")
    ok, clause = check_preconditions(inst, {**vals, "a": None})  # unnormalised input does not crash
    assert not ok and "error evaluating" in clause


def test_elem_ok():
    assert elem_ok("-1000 <= _ && _ <= 1000", 1000, {})
    assert not elem_ok("-1000 <= _ && _ <= 1000", -1001, {})
    assert elem_ok("_ < n", 3, {"n": 4}) and not elem_ok("_ < n", 4, {"n": 4})
    assert elem_ok("_ != INT_MIN", 0, {})


# ------------------------------------------------------------------------- witnesses
@pytest.mark.parametrize("raw, value", [
    (5, 5), (True, 1), (7.0, 7), ("42", 42), (" -3 ", -3), ("0x10", 16), ("10u", 10), ("5LL", 5),
    ("INT_MIN", -(2**31)), ("INT_MAX", 2**31 - 1), ("UINT_MAX", 2**32 - 1), ("LLONG_MIN", -(2**63)),
])
def test_to_int(raw, value):
    assert _to_int(raw) == value


@pytest.mark.parametrize("raw", [1.5, "abc", None, [1]])
def test_to_int_rejects(raw):
    with pytest.raises((ValueError, TypeError)):
        _to_int(raw)


def test_normalise_scalars(by_id):
    inst = by_id["T1-OVF-02-U"]  # x, d: int
    nw = normalise_witness(inst, {"x": "INT_MIN", "d": "-1"})
    assert nw.ok and nw.values == {"x": -(2**31), "d": -1}
    nw = normalise_witness(inst, {"x": 2**31, "d": 1})
    assert nw.problems == ["x=2147483648 outside range of int"]
    nw = normalise_witness(inst, {"x": 1})
    assert nw.values["d"] == 0 and nw.problems == ["missing value for d"]
    nw = normalise_witness(inst, {"x": 1.5, "d": 1})
    assert nw.values["x"] == 0 and any("not an integer" in p for p in nw.problems)
    assert not normalise_witness(inst, None).ok


def test_normalise_unsigned_range(by_id):
    inst = by_id["T1-DIV-05-U"]  # total, slots: unsigned
    assert normalise_witness(inst, {"total": 1, "slots": "UINT_MAX"}).ok
    assert normalise_witness(inst, {"total": 1, "slots": "0xFFFFFFFF"}).values["slots"] == 2**32 - 1
    assert "slots=-1 outside range of unsigned" in normalise_witness(inst, {"total": 1, "slots": -1}).problems


def test_normalise_arrays(by_id):
    inst = by_id["T1-BND-01-U"]  # buf: int[n]
    nw = normalise_witness(inst, {"buf": [7, 8, 9], "n": "2", "i": 0})  # lenient: truncate
    assert nw.ok and nw.values == {"n": 2, "i": 0, "buf": [7, 8]}
    nw = normalise_witness(inst, {"buf": [7], "n": 3, "i": 0}, strict=True)  # strict: report, still pad
    assert nw.values["buf"] == [7, 0, 0] and nw.problems == ["array buf has 1 elements, expected 3"]
    nw = normalise_witness(inst, {"buf": "abc", "n": 1, "i": 0})
    assert nw.values["buf"] == [0] and "array buf is not a list" in nw.problems
    nw = normalise_witness(inst, {"n": 2, "i": 0})
    assert nw.values["buf"] == [0, 0] and "missing contents for array buf" in nw.problems
    nw = normalise_witness(inst, {"buf": [2**31], "n": 1, "i": 0})
    assert any("out-of-range elements" in p for p in nw.problems)
    for n in (-1, MAX_ARRAY_LEN + 1):
        nw = normalise_witness(inst, {"buf": [], "n": n, "i": 0})
        assert nw.values["buf"] == [] and any("not executable" in p for p in nw.problems)


@pytest.mark.parametrize("raw,expected", [
    ("INT_MAX - 1", 2**31 - 2), ("-INT_MAX", -(2**31 - 1)), ("007", 7), ("0x10", 16), ("10u", 10),
    ("5LL", 5), ("INT_MIN", -(2**31)), (" 42 ", 42),
])
def test_to_int_accepts_c_style_values(raw, expected):
    assert _to_int(raw) == expected


@pytest.mark.parametrize("raw", ["zero", "", "1.5", "__import__('os')", "n"])
def test_to_int_rejects_garbage(raw):
    with pytest.raises(ValueError):
        _to_int(raw)
