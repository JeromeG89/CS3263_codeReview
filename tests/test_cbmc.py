"""CBMC as an independent oracle (needs the `cbmc` binary)."""
from __future__ import annotations

import pytest

from invcheck import cbmc

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not cbmc.available(), reason="cbmc not installed")]


@pytest.mark.parametrize("iid", ["T1-DIV-01-U", "T1-DIV-01-S", "T1-BND-01-U", "T1-BND-01-S",
                                 "T2-BND-02-U", "T2-BND-02-S"])
def test_cbmc_agrees_with_label(by_id, iid):
    inst = by_id[iid]
    res = cbmc.run_cbmc(inst, timeout=120)
    assert res.verdict == inst.gold_verdict, res.as_dict()
    if inst.is_unsafe:
        assert res.failures


def test_function_names():
    code = "static int helper(int a) {\n  return a;\n}\n\nint entry(const int *buf, int n) {\n  return helper(n);\n}\n"
    assert cbmc.function_names(code) == {"helper", "entry"}
