"""Repair-analysis checks use invented records and no model, solver or C executions."""
from __future__ import annotations

import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import numpy as np
from scipy.stats import permutation_test

from invcheck.analysis import derived_policies
from invcheck.dataset import ROOT
from invcheck.repair_analysis import repair_efficiency, repair_snapshot
from invcheck.sensitivity import pair_resampling, pair_sensitivity


def attempt(code, verdict="UNKNOWN", confirmed=False):
    return {"code": code, "verdict": verdict,
            "status": {"UNKNOWN": "error", "SAFE": "unsat", "UNSAFE": "sat"}[verdict],
            "witness": {"x": 1} if verdict == "UNSAFE" else None,
            "witness_status": "confirmed" if confirmed else None,
            "witness_detail": "test replay", "exec_kind": "bounds" if confirmed else None}


def trace(iid="P-U", gold="UNSAFE", attempts=None, approach="z3_repair", sample=0):
    attempts = attempts or [attempt("a"), attempt("b"), attempt("c"), attempt("d", "UNSAFE", True)]
    return {"instance": iid, "pair": iid[:-2], "sample": sample, "model": "test-model",
            "approach": approach, "gold": gold, "attempts": attempts, **attempts[-1],
            "llm_calls": len(attempts), "input_tokens": 1000, "output_tokens": 500,
            "wall_s": 1.0, "correct": attempts[-1]["verdict"] == gold,
            "decided": attempts[-1]["verdict"] != "UNKNOWN"}


def paired_records(samples=1):
    rows = []
    for sample in range(samples):
        for n in range(3):
            for suffix, gold in (("U", "UNSAFE"), ("S", "SAFE")):
                iid = f"P{n}-{suffix}"
                rows.append(trace(iid, gold, [attempt("a")], "direct_cot", sample))
                rows.append(trace(iid, gold, [attempt("b", gold, gold == "UNSAFE")], sample=sample))
    return pd.DataFrame(rows)


class RepairBudgetTests(unittest.TestCase):
    def test_cap_zero_uses_only_initial_attempt(self):
        r = trace()
        before = copy.deepcopy(r)
        out = repair_snapshot(r, max_repairs=0)
        self.assertEqual(out["llm_calls"], 1)
        self.assertEqual(out["verdict"], "UNKNOWN")
        self.assertEqual(out["calls_saved"], 3)
        self.assertTrue(math.isnan(out["input_tokens"]) and math.isnan(out["output_tokens"]))
        self.assertEqual(r, before)

    def test_full_trace_keeps_known_aggregate_tokens(self):
        out = repair_snapshot(trace(), max_repairs=3)
        self.assertEqual(out["llm_calls"], 4)
        self.assertEqual(out["verdict"], "UNSAFE")
        self.assertEqual(out["output_tokens"], 500)

    def test_duplicate_call_is_paid_and_later_success_can_be_lost(self):
        r = trace(attempts=[attempt("same"), attempt("same"), attempt("b"), attempt("c", "UNSAFE", True)])
        out = repair_snapshot(r, stop_on_repeat=True)
        self.assertTrue(out["repeated_script"])
        self.assertEqual(out["llm_calls"], 2)
        self.assertEqual(out["calls_saved"], 2)
        self.assertEqual(out["verdict"], "UNKNOWN")

    def test_missing_empty_or_nonconsecutive_code_is_not_a_duplicate(self):
        for codes in ((None, None, "a", "b"), ("", "", "a", "b"),
                      (" ", " ", "a", "b"), ("a", "b", "a", "c"), ("a", "a ", "b", "c")):
            with self.subTest(codes=codes):
                out = repair_snapshot(trace(attempts=[attempt(c) for c in codes]), stop_on_repeat=True)
                self.assertEqual(out["llm_calls"], 4)
                self.assertFalse(out["repeated_script"])

    def test_duplicate_on_last_turn_saves_no_calls(self):
        out = repair_snapshot(trace(attempts=[attempt("a"), attempt("a")]), stop_on_repeat=True)
        self.assertTrue(out["repeated_script"])
        self.assertEqual(out["calls_saved"], 0)

    def test_stopping_does_not_consult_gold_label(self):
        r = trace(attempts=[attempt("a"), attempt("a"), attempt("b")])
        one = repair_snapshot(r, stop_on_repeat=True)
        two = repair_snapshot({**r, "gold": "SAFE"}, stop_on_repeat=True)
        for field in ("verdict", "llm_calls", "calls_saved", "repeated_script"):
            self.assertEqual(one[field], two[field])

    def test_invalid_histories_are_rejected(self):
        for r, k in ((trace(), -1), ({**trace(), "attempts": []}, 3), ({**trace(), "llm_calls": 99}, 3)):
            with self.subTest(k=k, calls=r["llm_calls"]), self.assertRaises(ValueError):
                repair_snapshot(r, max_repairs=k)

    def test_round_counts_and_zero_gain_cost_are_honest(self):
        df = pd.DataFrame([trace(), trace("P-S", "SAFE", [attempt("s", "SAFE")])])
        before = df.to_json()
        summary, cases = repair_efficiency(df)
        summary = summary.set_index("policy")
        self.assertEqual(summary.loc["cap_0", "logical_calls"], 2)
        self.assertEqual(summary.loc["cap_2", "correct_verdicts"], 1)
        self.assertEqual(summary.loc["cap_3", "logical_calls"], 5)
        self.assertEqual(summary.loc["cap_3", "net_extra_correct"], 1)
        self.assertEqual(summary.loc["cap_3", "extra_calls_vs_previous"], 1)
        self.assertTrue(math.isnan(summary.loc["cap_2", "calls_per_net_extra_correct"]))
        self.assertFalse(cases.empty)
        self.assertEqual(df.to_json(), before)

    def test_early_stop_hybrid_counts_fallback_and_can_recover_a_lost_bug(self):
        df = pd.DataFrame([
            trace(attempts=[attempt("a"), attempt("a"), attempt("b"), attempt("c", "UNSAFE", True)]),
            trace("P-S", "SAFE", [attempt("s", "SAFE")]),
            trace(attempts=[attempt("cot", "UNSAFE", True)], approach="direct_cot"),
            trace("P-S", "SAFE", [attempt("cot", "SAFE")], "direct_cot"),
        ])
        summary, _ = repair_efficiency(df)
        stop = summary[summary["policy"].eq("stop_on_repeat")].set_index("system")
        self.assertEqual(stop.loc["z3_repair", "lost_correct_vs_full"], 1)
        self.assertEqual(stop.loc["strict_hybrid", "lost_correct_vs_full"], 0)
        self.assertEqual(stop.loc["strict_hybrid", "confirmed_bugs"], 1)
        self.assertEqual(stop.loc["strict_hybrid", "logical_calls"], 4)
        self.assertEqual(stop.loc["strict_hybrid", "calls_saved_vs_full"], 1)


class PairSensitivityTests(unittest.TestCase):
    def test_identical_methods_have_no_observed_difference(self):
        r = pair_resampling([0, 0, 0], resamples=100, seed=1)
        self.assertEqual((r["difference"], r["lo95"], r["hi95"], r["p_cluster"]), (0, 0, 0, 1))

    def test_three_twin_pairs_are_three_units_not_six_independent_cases(self):
        df = paired_records()
        out = pair_sensitivity(df, pd.DataFrame(), resamples=100,
                               comparisons=[("direct_cot", "z3_repair")])
        for row in out.to_dict("records"):
            self.assertEqual(row["n_instances"], 6)
            self.assertEqual(row["n_pairs"], 3)
            self.assertEqual(row["difference"], 1)
            self.assertEqual(row["p_cluster"], 0.25)

    def test_additional_samples_remain_in_the_same_pair_cluster(self):
        one = pair_sensitivity(paired_records(1), pd.DataFrame(), resamples=100,
                               comparisons=[("direct_cot", "z3_repair")])
        two = pair_sensitivity(paired_records(2), pd.DataFrame(), resamples=100,
                               comparisons=[("direct_cot", "z3_repair")])
        self.assertTrue(two["n_instances"].eq(12).all())
        self.assertTrue(two["n_pairs"].eq(3).all())
        self.assertEqual(one["p_cluster"].tolist(), two["p_cluster"].tolist())

    def test_seeded_monte_carlo_is_repeatable_and_never_returns_zero_p(self):
        differences = [1] * 20
        a = pair_resampling(differences, resamples=500, seed=9)
        b = pair_resampling(differences, resamples=500, seed=9)
        self.assertEqual(a, b)
        self.assertEqual(a["p_method"], "monte_carlo_pair_sign_flip")
        self.assertGreater(a["p_cluster"], 0)

    def test_reversing_methods_reverses_effect_and_interval(self):
        a = pair_resampling([-1, 0, 0.5, 1], resamples=1000, seed=5)
        b = pair_resampling([1, 0, -0.5, -1], resamples=1000, seed=5)
        self.assertAlmostEqual(a["difference"], -b["difference"])
        self.assertAlmostEqual(a["lo95"], -b["hi95"])
        self.assertEqual(a["p_cluster"], b["p_cluster"])

    def test_small_exact_sign_flip_agrees_with_scipy(self):
        d = np.array([-1, 0.5, 1, 0.5])
        actual = pair_resampling(d, resamples=100)
        expected = permutation_test((d,), np.mean, permutation_type="samples", n_resamples=np.inf)
        self.assertAlmostEqual(actual["p_cluster"], expected.pvalue)

    def test_missing_twins_mismatched_cases_and_duplicates_are_rejected(self):
        df = paired_records()
        broken = [df[df["instance"].ne("P0-S")],
                  df[~(df["instance"].eq("P0-S") & df["approach"].eq("z3_repair"))],
                  pd.concat([df, df.iloc[[0]]], ignore_index=True)]
        for records in broken:
            with self.subTest(rows=len(records)), self.assertRaises(ValueError):
                pair_sensitivity(records, pd.DataFrame(), resamples=100,
                                 comparisons=[("direct_cot", "z3_repair")])

    def test_invalid_resampling_inputs_are_rejected(self):
        for differences, n in (([], 100), ([math.nan], 100), ([1], 0)):
            with self.subTest(differences=differences), self.assertRaises(ValueError):
                pair_resampling(differences, resamples=n)


class RepairAnalysisWriterTests(unittest.TestCase):
    def test_writer_exports_tables_metadata_and_figure(self):
        df = paired_records()
        derived = derived_policies(df)
        spec = importlib.util.spec_from_file_location("analyze_repair_test", ROOT / "scripts" / "analyze.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with patch.object(module, "OUT", dest), patch.object(module, "FIG", dest / "figures"), \
                    patch.object(module, "DETAILS", dest / "build" / "analysis"):
                module.write_repair_analysis(df, derived, "test saved records", resamples=100, seed=2)
            self.assertFalse(pd.read_csv(dest / "repair_efficiency.csv").empty)
            self.assertFalse(pd.read_csv(dest / "pair_sensitivity.csv").empty)
            self.assertTrue((dest / "build" / "analysis" / "repair_metadata.json").exists())
            self.assertFalse((dest / "repair_metadata.json").exists())
            self.assertFalse((dest / "repair_analysis.md").exists())
            self.assertTrue((dest / "figures" / "fig8_repair_efficiency.png").exists())
            text = (dest / "build" / "analysis" / "repair_analysis.md").read_text(encoding="utf-8")
            self.assertIn("test saved records", text)
            self.assertIn("not a random sample", text)
            self.assertIn("without fabricating token savings", text)


if __name__ == "__main__":
    unittest.main()
