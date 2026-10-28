"""Offline regression tests for replay-required policies and their exported comparison.

Run with pytest, or with PYTHONPATH=src and:
    python -m unittest discover -s tests -p test_hybrid_workflow.py
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from invcheck.analysis import derived_policies, hybrid_case_changes, hybrid_comparison, load_records
from invcheck.dataset import ROOT


def record(iid="A-U", verdict="UNSAFE", status="confirmed", gold="UNSAFE", sample=0, **extra):
    return {
        "model": "test-model", "instance": iid, "sample": sample, "pair": iid[:-2],
        "tier": 1, "category": "bounds", "gold": gold, "verdict": verdict,
        "witness_status": status, "witness": {"x": 1} if verdict == "UNSAFE" else None,
        "witness_detail": "recorded replay", "exec_kind": "bounds" if status == "confirmed" else None,
        "llm_calls": 1, "input_tokens": 100, "output_tokens": 80, "wall_s": 2.0,
        **extra,
    }


def prepare(z, c, zv="z3_repair"):
    df = pd.DataFrame([
        *[{**r, "approach": zv} for r in z],
        *[{**r, "approach": "direct_cot"} for r in reversed(c)],
    ])
    df["correct"] = df["verdict"] == df["gold"]
    df["decided"] = df["verdict"] != "UNKNOWN"
    return df, derived_policies(df)


def selected(derived, approach):
    return derived[derived["approach"] == approach].iloc[0]


class ReplayRequiredTests(unittest.TestCase):
    def test_unconfirmed_z3_claims_use_cot(self):
        for zv in ("z3", "z3_repair"):
            for status in ("not_reproduced", "invalid", "precondition_violated", None, math.nan):
                with self.subTest(approach=zv, status=status):
                    df, derived = prepare([record(status=status, witness={"x": 99})],
                                          [record(witness={"x": 1}, output_tokens=120)], zv)
                    before = df.copy(deep=True)
                    answer = selected(derived, f"strict_hybrid_{zv}_else_cot")
                    self.assertEqual(answer["verdict"], "UNSAFE")
                    self.assertEqual(answer["answer_source"], "direct_cot")
                    self.assertEqual(answer["witness"], {"x": 1})
                    self.assertEqual(answer["fallback_reason"], "z3_unconfirmed_witness")
                    self.assertEqual(answer["llm_calls"], 2)
                    self.assertEqual(answer["output_tokens"], 200)
                    old = selected(derived, f"hybrid_{zv}_else_cot")
                    self.assertEqual(old["answer_source"], zv)
                    self.assertEqual(old["witness"], {"x": 99})
                    pd.testing.assert_frame_equal(df, before)

    def test_accepted_z3_answers_do_not_use_cot(self):
        for verdict, status in (("SAFE", None), ("UNSAFE", "confirmed")):
            with self.subTest(verdict=verdict):
                _, derived = prepare([record(verdict=verdict, status=status)],
                                     [record(verdict="UNKNOWN", status=None)])
                answer = selected(derived, "strict_hybrid_z3_repair_else_cot")
                self.assertEqual(answer["verdict"], verdict)
                self.assertEqual(answer["answer_source"], "z3_repair")
                self.assertEqual(answer["llm_calls"], 1)

    def test_unconfirmed_cot_bug_claim_finishes_unknown(self):
        for zv in ("UNKNOWN", "UNSAFE"):
            with self.subTest(z3_verdict=zv):
                _, derived = prepare([record(verdict=zv, status="not_reproduced")],
                                     [record(status="not_reproduced")])
                answer = selected(derived, "strict_hybrid_z3_repair_else_cot")
                self.assertEqual(answer["verdict"], "UNKNOWN")
                self.assertEqual(answer["original_verdict"], "UNSAFE")
                self.assertEqual(answer["abstention_reason"], "unconfirmed_witness")
                self.assertEqual(answer["answer_source"], "direct_cot")
                self.assertEqual(answer["llm_calls"], 2)
                self.assertFalse(answer["decided"])

    def test_cot_safe_and_unknown_answers_are_retained(self):
        for verdict in ("SAFE", "UNKNOWN"):
            with self.subTest(cot_verdict=verdict):
                _, derived = prepare([record(status="not_reproduced")],
                                     [record(verdict=verdict, status=None)])
                answer = selected(derived, "strict_hybrid_z3_repair_else_cot")
                self.assertEqual(answer["verdict"], verdict)
                self.assertIsNone(answer["witness"])
                self.assertEqual(answer["llm_calls"], 2)

    def test_policy_does_not_consult_gold_labels(self):
        df, derived = prepare([record(status="not_reproduced")], [record()])
        flipped = df.assign(gold="SAFE")
        second = derived_policies(flipped)
        pd.testing.assert_frame_equal(derived.drop(columns=["gold", "correct"]),
                                      second.drop(columns=["gold", "correct"]))

    def test_fallback_matches_instance_and_sample(self):
        _, derived = prepare(
            [record(verdict="UNKNOWN", status=None, sample=0),
             record(verdict="SAFE", status=None, sample=1, input_tokens=200)],
            [record(sample=0, input_tokens=300), record(sample=1, input_tokens=900)],
        )
        h = derived[derived["approach"] == "strict_hybrid_z3_repair_else_cot"].set_index("sample")
        self.assertEqual(h.loc[0, "input_tokens"], 400)
        self.assertEqual(h.loc[1, "input_tokens"], 200)
        self.assertEqual(h.loc[0, "answer_source"], "direct_cot")
        self.assertEqual(h.loc[1, "answer_source"], "z3_repair")


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.df, self.derived = prepare(
            [record(), record("A-S", "SAFE", None, "SAFE"),
             record("B-U", status="not_reproduced"),
             record("C-S", status="not_reproduced", gold="SAFE")],
            [record(verdict="SAFE", status=None), record("A-S", "SAFE", None, "SAFE"),
             record("B-U", status="not_reproduced"), record("C-S", "SAFE", None, "SAFE")],
        )

    def test_table_counts_answers_evidence_and_abstentions(self):
        table = hybrid_comparison(self.df, self.derived).set_index("approach")
        h = table.loc["strict_hybrid_z3_repair_else_cot"]
        self.assertEqual(h["correct_verdicts"], 3)
        self.assertEqual(h["n"], 4)
        self.assertEqual(h["confirmed_bugs"], 1)
        self.assertEqual(h["unsafe_cases"], 2)
        self.assertEqual(h["confirmed_bug_recall"], 0.5)
        self.assertEqual(h["unknown"], 1)
        self.assertEqual(h["unknown_on_unsafe"], 1)
        self.assertEqual(h["false_safe"], 0)
        self.assertEqual(h["coverage"], 0.75)
        self.assertEqual(h["mean_llm_calls"], 1.5)
        self.assertEqual(table.loc["strict_direct_cot", "correct_verdicts"], 2)
        self.assertTrue(math.isnan(table.loc["strict_direct_cot", "precision"]))

    def test_case_export_includes_both_wins_and_losses(self):
        cases = hybrid_case_changes(self.df, self.derived)
        old = cases[cases["hybrid_approach"] == "hybrid_z3_repair_else_cot"].set_index("instance")
        self.assertEqual(old.loc["A-U", "verdict_change"], "hybrid_only_correct")
        self.assertEqual(old.loc["C-S", "verdict_change"], "cot_only_correct")
        strict = cases[cases["hybrid_approach"] == "strict_hybrid_z3_repair_else_cot"]
        self.assertTrue(strict["baseline_approach"].eq("strict_direct_cot").all())
        self.assertEqual(strict.iloc[0]["instance"], "A-U")

    def test_evidence_gain_is_exported_even_when_verdicts_agree(self):
        df, derived = prepare([record()], [record(status="not_reproduced")])
        cases = hybrid_case_changes(df, derived)
        old = cases[cases["hybrid_approach"] == "hybrid_z3_repair_else_cot"].iloc[0]
        self.assertEqual(old["verdict_change"], "same_correctness")
        self.assertEqual(old["evidence_change"], "hybrid_only_confirmed")
        self.assertEqual(json.loads(old["hybrid_witness"]), {"x": 1})

    def test_missing_usage_is_not_hidden_by_average(self):
        df, derived = prepare([record(verdict="UNKNOWN", status=None)],
                              [record(input_tokens=math.nan)])
        table = hybrid_comparison(df, derived).set_index("approach")
        self.assertTrue(math.isnan(table.loc["strict_hybrid_z3_repair_else_cot", "mean_input_tokens"]))

    def test_no_llm_runs_produces_empty_comparison_with_headers(self):
        df = self.df.iloc[:0]
        derived = derived_policies(df)
        comparison = hybrid_comparison(df, derived)
        cases = hybrid_case_changes(df, derived)
        self.assertTrue(comparison.empty and cases.empty)
        self.assertIn("correct_verdicts", comparison.columns)
        self.assertIn("verdict_change", cases.columns)

    def test_writer_creates_comparison_and_case_files(self):
        spec = importlib.util.spec_from_file_location("analyze_for_test", ROOT / "scripts" / "analyze.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp, patch.object(module, "OUT", Path(tmp)), \
                patch.object(module, "FIG", Path(tmp) / "figures"):
            with patch.object(pd.DataFrame, "to_markdown", side_effect=ImportError("tabulate absent")):
                text = module.write_hybrid_comparison(self.df, self.derived, "test records")
            self.assertIn("test records", text)
            self.assertIn("Bugs with working inputs", text)
            self.assertIn("lost_correct", text)
            self.assertEqual(len(pd.read_csv(Path(tmp) / "hybrid_comparison.csv")), 6)
            self.assertFalse(pd.read_csv(Path(tmp) / "hybrid_cases.csv").empty)
            self.assertEqual((Path(tmp) / "hybrid_comparison.md").read_text(encoding="utf-8"), text)
            self.assertTrue((Path(tmp) / "figures" / "fig9_review_evidence.png").exists())


class RecordLoadingTests(unittest.TestCase):
    def test_incomplete_runs_are_not_mistaken_for_complete_benchmarks(self):
        instances = [SimpleNamespace(id=f"I{k}", pair=f"P{k}", tier=1, category="bounds",
                                     twin="code", label="safe", tags=[]) for k in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "partial"
            run.mkdir()
            (run / "records.jsonl").write_text(
                json.dumps(record("I0", "SAFE", None, "SAFE", approach="direct_cot")), encoding="utf-8")
            with patch("invcheck.analysis.RUNS", Path(tmp)), patch("invcheck.analysis.load_dataset", return_value=instances):
                self.assertTrue(load_records().empty)

    def test_each_sample_must_cover_the_full_dataset(self):
        instances = [SimpleNamespace(id=f"I{k}", pair=f"P{k}", tier=1, category="bounds",
                                     twin="code", label="safe", tags=[]) for k in range(3)]
        rows = [record(f"I{k}", "SAFE", None, "SAFE", approach="direct_cot") for k in range(3)]
        rows.append(record("I0", "SAFE", None, "SAFE", sample=1, approach="direct_cot"))
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "samples"
            run.mkdir()
            (run / "records.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            with patch("invcheck.analysis.RUNS", Path(tmp)), patch("invcheck.analysis.load_dataset", return_value=instances):
                loaded = load_records()
                self.assertEqual(len(loaded), 3)
                self.assertTrue(loaded["sample"].eq(0).all())


if __name__ == "__main__":
    unittest.main()
