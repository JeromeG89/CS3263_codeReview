"""Statistics and metrics over evaluation records (synthetic data only; never reads results/)."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from invcheck.analysis import derived_policies, holm, mcnemar, metrics, wilson


def test_wilson():
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    lo, hi = wilson(10, 10)
    assert lo == pytest.approx(0.7225, abs=1e-4) and hi == 1.0
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-4)
    assert all(math.isnan(x) for x in wilson(0, 0))


def test_mcnemar():
    a = pd.Series([True, True, True, True, True, False, False])
    b = pd.Series([False, False, False, False, False, False, True])
    b10, b01, p = mcnemar(a, b)
    assert (b10, b01) == (5, 1)
    assert p == pytest.approx(14 / 64)  # two-sided exact binomial: 2 * P(X <= 1 | n=6, 1/2)
    a = pd.Series([False] * 5)
    b = pd.Series([True] * 5)
    assert mcnemar(a, b) == (0, 5, pytest.approx(2 / 32))
    assert mcnemar(a, a)[2] == 1.0  # no discordant pairs


def test_holm():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm([0.5, 0.9]) == pytest.approx([1.0, 1.0])  # capped at 1 and monotone
    assert holm([0.02]) == [0.02]


def _records() -> pd.DataFrame:
    rows = [  # pair A answered perfectly; pair B: unknown on the bug, false alarm on the fix
        dict(instance="A-U", pair="A", gold="UNSAFE", verdict="UNSAFE", witness_status="confirmed"),
        dict(instance="A-S", pair="A", gold="SAFE", verdict="SAFE", witness_status=None),
        dict(instance="B-U", pair="B", gold="UNSAFE", verdict="UNKNOWN", witness_status=None),
        dict(instance="B-S", pair="B", gold="SAFE", verdict="UNSAFE", witness_status="not_reproduced"),
    ]
    df = pd.DataFrame(rows)
    df["correct"] = df["verdict"] == df["gold"]
    df["decided"] = df["verdict"] != "UNKNOWN"
    df["output_tokens"] = [10, 20, 30, 40]
    df["llm_calls"] = [1, 1, 2, 4]
    df["wall_s"] = 1.0
    return df


def test_metrics():
    m = metrics(_records())
    assert m["n"] == 4 and m["accuracy"] == 0.5
    assert (m["fp"], m["fn"], m["unknown"]) == (1, 0, 1)  # UNKNOWN on a bug is not counted as fn
    assert m["tpr"] == 0.5 and m["tnr"] == 0.5 and m["precision"] == 0.5 and m["f1"] == 0.5
    assert m["coverage"] == 0.75 and m["selective_acc"] == pytest.approx(2 / 3)
    assert m["pair_acc"] == 0.5 and m["pair_same_verdict"] == 0.0
    assert (m["unsafe_claims"], m["witness_confirmed"], m["witness_confirm_rate"]) == (2, 1, 0.5)
    assert m["mean_out_tokens"] == 25 and m["mean_llm_calls"] == 2
    assert (m["acc_lo"], m["acc_hi"]) == wilson(2, 4)


def test_derived_policies():
    z = _records().assign(model="m", approach="z3_repair")
    c = _records().assign(model="m", approach="direct_cot", verdict=["UNSAFE", "SAFE", "UNSAFE", "UNSAFE"],
                          witness_status=["confirmed", None, "not_reproduced", "not_reproduced"])
    d = derived_policies(pd.concat([z, c], ignore_index=True)).set_index(["approach", "instance"])["verdict"]
    assert d["hybrid_z3_repair_else_cot", "B-U"] == "UNSAFE"  # Z3 was UNKNOWN -> fall back to CoT
    assert d["hybrid_z3_repair_else_cot", "B-S"] == "UNSAFE"  # Z3 decided -> keep Z3
    assert d["validated_direct_cot", "B-U"] == "SAFE"  # unconfirmed UNSAFE claims are dropped
    assert d["validated_direct_cot", "A-U"] == "UNSAFE"
    assert d["validated_z3_repair", "B-S"] == "SAFE"
