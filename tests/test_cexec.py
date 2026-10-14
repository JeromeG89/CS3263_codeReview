"""Concrete execution under ASan+UBSan, and the fuzzing baseline built on it."""
from __future__ import annotations

import pytest

from invcheck.cexec import classify, encode_case, run_cases, run_witness
from invcheck.dataset import check_preconditions, normalise_witness
from invcheck.fuzz import fuzz, gen_cases, harvest_constants


@pytest.mark.parametrize("iid, kind", [
    ("T1-OVF-02-U", "overflow"),
    ("T1-DIV-01-U", "div_zero"),
    ("T1-SHF-01-U", "shift"),
    ("T1-BND-01-U", "bounds"),  # heap read past a malloc'd array (ASan)
    ("T1-BND-02-U", "bounds"),  # global table index (UBSan)
])
def test_witness_triggers_expected_kind(by_id, iid, kind):
    inst = by_id[iid]
    res = run_witness(inst, normalise_witness(inst, inst.witness).values)
    assert res.violated and res.kind == kind, res
    assert res.case_index == 0 and not res.timed_out


def test_safe_inputs_run_clean(by_id):
    inst = by_id["T1-OVF-02-S"]  # d > 0
    cases = [{"x": -(2**31), "d": 1}, {"x": 2**31 - 1, "d": 7}, {"x": -5, "d": 2}]
    assert all(check_preconditions(inst, c)[0] for c in cases)
    res = run_cases(inst, cases)
    assert not res.violated and res.cases_run == 3 and res.kind is None


def test_reports_first_violating_case(by_id):
    inst = by_id["T1-DIV-01-U"]
    res = run_cases(inst, [{"total": 5, "count": 1}, {"total": 5, "count": 0}, {"total": 1, "count": 1}])
    assert res.violated and res.kind == "div_zero" and res.case_index == 1 and res.cases_run == 1


def test_encode_case(by_id):
    inst = by_id["T1-BND-01-U"]  # params: buf[n], n, i
    assert encode_case(inst, {"buf": [7, -8], "n": 2, "i": 1}) == "2 7 -8 2 1"
    with pytest.raises(AssertionError):
        encode_case(inst, {"buf": [7], "n": 2, "i": 1})


@pytest.mark.parametrize("stderr, kind", [
    ("runtime error: division by zero", "div_zero"),
    ("runtime error: signed integer overflow: 2147483647 + 1", "overflow"),
    ("runtime error: negation of -2147483648 cannot be represented", "overflow"),
    ("runtime error: shift exponent 32 is too large", "shift"),
    ("runtime error: left shift of negative value -1", "shift"),
    ("ERROR: AddressSanitizer: heap-buffer-overflow on address", "bounds"),
    ("runtime error: index 12 out of bounds for type 'int[12]'", "bounds"),
    ("something else entirely", None),
])
def test_classify(stderr, kind):
    assert classify(stderr) == kind


@pytest.mark.slow
def test_all_dataset_witnesses_trigger_a_violation(dataset):
    for inst in dataset:
        if inst.is_unsafe:
            res = run_witness(inst, normalise_witness(inst, inst.witness).values)
            assert res.violated, inst.id


# ------------------------------------------------------------------------------ fuzzing
def test_harvest_constants(by_id):
    consts = harvest_constants(by_id["T1-SHF-01-U"])  # "0 <= k && k <= 31", code `1 << k`
    assert {29, 30, 31, 32, 33, -31}.issubset(consts)


def test_fuzz_cases_respect_preconditions(by_id):
    for iid in ("T2-BND-02-U", "T1-DIV-01-S"):
        inst = by_id[iid]
        cases = gen_cases(inst, 200, seed=0)
        assert len(cases) == 200
        assert all(check_preconditions(inst, c)[0] for c in cases)
        assert cases == gen_cases(inst, 200, seed=0)  # deterministic per seed


def test_fuzz_finds_easy_bug_and_not_in_safe_twin(by_id):
    found = fuzz(by_id["T1-DIV-01-U"], n=300)
    assert found.found and found.exec.kind == "div_zero" and found.witness["count"] == 0
    clean = fuzz(by_id["T1-DIV-01-S"], n=300)
    assert not clean.found and clean.cases_executed == 300
