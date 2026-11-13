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


@pytest.mark.parametrize("z3_approach", ["z3", "z3_repair"])
def test_hybrid_copies_selected_answer_and_preserves_inputs(z3_approach):
    z = _records().assign(model="m", approach=z3_approach)
    z["witness"] = [{"x": 0}, None, {"x": 99}, {"x": 2}]
    z["witness_detail"] = ["Z3 confirmed", "", "Z3 failed", "Z3 spurious"]
    z["violation"] = [None, None, None, None]
    z["exec_kind"] = ["bounds", None, None, None]
    z["explanation"] = [None, None, None, None]
    z["parse"] = [None, None, None, None]
    z["transcript"] = [[{"role": "assistant", "content": "Z3 script"}]] * len(z)
    z["z3_status"] = ["sat", "unsat", "error", "sat"]
    z["attempts"] = [[{"status": st}] for st in z["z3_status"]]
    c = _records().assign(model="m", approach="direct_cot",
                          verdict=["SAFE", "UNSAFE", "UNSAFE", "SAFE"],
                          witness_status=[None, "confirmed", "confirmed", None])
    c["witness"] = [None, {"x": 10}, {"x": 1}, None]
    c["witness_detail"] = ["", "CoT confirmed", "CoT confirmed", ""]
    c["violation"] = ["none", "overflow", "overflow", "none"]
    c["exec_kind"] = [None, "overflow", "overflow", None]
    c["explanation"] = ["CoT says safe", "CoT found overflow", "CoT found overflow", "CoT says safe"]
    c["parse"] = "json"
    c["transcript"] = [[{"role": "assistant", "content": "CoT answer"}]] * len(c)
    # CoT rows need not arrive in the same order as Z3 rows.
    records = pd.concat([z, c.iloc[::-1]], ignore_index=True)
    before = records.copy(deep=True)

    derived = derived_policies(records)
    hybrid = derived[derived["approach"] == f"hybrid_{z3_approach}_else_cot"].set_index("instance")
    z = z.set_index("instance")
    c = c.set_index("instance")
    answer_fields = ["verdict", "violation", "witness", "witness_status", "witness_detail",
                     "exec_kind", "explanation", "parse", "transcript"]
    for iid in z.index:
        expected = c.loc[iid] if z.loc[iid, "verdict"] == "UNKNOWN" else z.loc[iid]
        pd.testing.assert_series_equal(hybrid.loc[iid, answer_fields], expected[answer_fields])
        assert hybrid.loc[iid, "answer_source"] == expected["approach"]
        assert hybrid.loc[iid, "correct"] == (expected["verdict"] == expected["gold"])
        assert hybrid.loc[iid, "decided"] == (expected["verdict"] != "UNKNOWN")
        assert hybrid.loc[iid, "z3_status"] == z.loc[iid, "z3_status"]
        assert hybrid.loc[iid, "attempts"] == z.loc[iid, "attempts"]
    pd.testing.assert_frame_equal(records, before)
    assert metrics(hybrid)["witness_confirmed"] == 2


@pytest.mark.parametrize("cot_verdict", ["SAFE", "UNKNOWN"])
def test_hybrid_fallback_clears_stale_witness(cot_verdict):
    z = _records().iloc[[2]].assign(model="m", approach="z3", witness_status="not_reproduced")
    z["witness"] = [{"x": 99}]
    z["witness_detail"] = "Old Z3 counterexample"
    c = z.assign(approach="direct_cot", verdict=cot_verdict, witness=None,
                 witness_status=None, witness_detail="")

    derived = derived_policies(pd.concat([z, c], ignore_index=True))
    answer = derived[derived["approach"] == "hybrid_z3_else_cot"].iloc[0]
    assert answer["verdict"] == cot_verdict
    assert answer["answer_source"] == "direct_cot"
    assert pd.isna(answer["witness"]) and pd.isna(answer["witness_status"])
    assert answer["witness_detail"] == ""
    assert answer["decided"] == (cot_verdict != "UNKNOWN")


@pytest.mark.parametrize("z3_approach", ["z3", "z3_repair"])
@pytest.mark.parametrize("cot_verdict", ["SAFE", "UNSAFE", "UNKNOWN"])
def test_hybrid_counts_only_used_calls_and_tokens(z3_approach, cot_verdict):
    z = _records().assign(model="m", approach=z3_approach,
                          input_tokens=[100, 200, 300, 400], llm_latency_s=2.0)
    z["llm_calls"] = [1, 2, 3, 4] if z3_approach == "z3_repair" else 1
    c = _records().assign(model="m", approach="direct_cot",
                          verdict=["SAFE", "UNSAFE", cot_verdict, "SAFE"],
                          input_tokens=[1000, 2000, 3000, 4000],
                          output_tokens=[110, 120, 130, 140], llm_calls=1, llm_latency_s=5.0)
    records = pd.concat([z, c.iloc[::-1]], ignore_index=True)
    before = records.copy(deep=True)

    derived = derived_policies(records)
    hybrid = derived[derived["approach"] == f"hybrid_{z3_approach}_else_cot"].set_index("instance")
    costs = ["llm_calls", "input_tokens", "output_tokens"]
    expected = z.set_index("instance")[costs].copy()
    # Only B-U needs fallback. Count CoT even if it also returns UNKNOWN.
    expected.loc["B-U"] = [4 if z3_approach == "z3_repair" else 2, 3300, 160]
    pd.testing.assert_frame_equal(hybrid[costs], expected)
    assert (hybrid["cost_basis"] == "estimated_sequential").all()
    assert hybrid["wall_s"].isna().all() and hybrid["llm_latency_s"].isna().all()
    assert metrics(hybrid)["mean_llm_calls"] == expected["llm_calls"].mean()
    assert metrics(hybrid)["mean_out_tokens"] == expected["output_tokens"].mean()
    assert math.isnan(metrics(hybrid)["mean_wall_s"])
    pd.testing.assert_frame_equal(records, before)


def test_hybrid_does_not_treat_missing_token_usage_as_zero():
    z = _records().iloc[[2]].assign(model="m", approach="z3", input_tokens=100)
    c = z.assign(approach="direct_cot", verdict="SAFE", input_tokens=math.nan, llm_calls=1)

    derived = derived_policies(pd.concat([z, c], ignore_index=True))
    answer = derived[derived["approach"] == "hybrid_z3_else_cot"].iloc[0]
    assert pd.isna(answer["input_tokens"])
    assert answer["llm_calls"] == 3
