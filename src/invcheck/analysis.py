"""Metrics, statistics and derived policies over evaluation records."""
from __future__ import annotations

import json
import math
import re
import subprocess
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from .dataset import ROOT, load_dataset

RUNS = ROOT / "results" / "runs"
EXCLUDE_RUNS = {"smoke"}

APPROACH_ORDER = ["direct", "direct_cot", "z3", "z3_guided", "z3_repair"]
TOOL_ORDER = ["reference_z3", "cbmc", "fuzz_dict", "fuzz_random"]
APPROACH_LABEL = {
    "direct": "Direct", "direct_cot": "Direct + CoT", "z3": "LLM→Z3",
    "z3_guided": "LLM→Z3 guided", "z3_repair": "LLM→Z3 guided + repair",
    "reference_z3": "Gold Z3 (Claude)", "cbmc": "CBMC", "fuzz_dict": "Fuzz (dictionary)",
    "fuzz_random": "Fuzz (random)",
    "hybrid_z3_else_cot": "Hybrid: LLM→Z3, else CoT", "hybrid_z3_repair_else_cot": "Hybrid: Z3+repair, else CoT", "validated_direct_cot": "CoT, witness-validated",
    "validated_z3_repair": "Z3+repair, witness-validated", "validated_direct": "Direct, witness-validated",
    "validated_z3": "LLM→Z3, witness-validated", "validated_z3_guided": "Z3 guided, witness-validated",
    "strict_direct_cot": "CoT (replay required)",
    "strict_z3_repair": "Z3+repair (replay required)",
    "strict_hybrid_z3_else_cot": "Hybrid: Z3, else CoT (replay required)",
    "strict_hybrid_z3_repair_else_cot": "Hybrid: Z3+repair, else CoT (replay required)",
}


def short_model(m: str) -> str:
    return m.replace("ollama:", "").replace("gemini:", "").replace("tool", "—")


# ----------------------------------------------------------------------------- loading
def _final_truncated(r: dict) -> bool:
    """True if the last model reply was cut off mid-code-block (runaway generation that hit
    the output-token limit, typically a repetition loop)."""
    msgs = [m for m in r.get("transcript") or [] if m.get("role") == "assistant"]
    if not msgs:
        return False
    text = msgs[-1].get("content", "")
    if r.get("approach", "").startswith("z3"):
        return text.count("```") % 2 == 1
    return r.get("verdict") == "UNKNOWN" and text.count("```") % 2 == 1


def resolve_records_ref(ref: str) -> str:
    """Resolve a local Git revision without changing the checkout or fetching."""
    return subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"],
        cwd=ROOT, text=True, encoding="utf-8",
    ).strip()


def load_records(include_transcripts: bool = False, records_ref: str | None = None) -> pd.DataFrame:
    """Read working-tree records, or read them from an existing local Git revision."""
    if records_ref is None:
        sources = [(path.parent.name, path.read_text(encoding="utf-8"))
                   for path in sorted(RUNS.glob("*/records.jsonl"))]
    else:
        commit = resolve_records_ref(records_ref)
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", commit, "--", "results/runs"],
            cwd=ROOT, text=True, encoding="utf-8",
        ).splitlines()
        sources = [(Path(path).parent.name, subprocess.check_output(
            ["git", "show", f"{commit}:{path}"], cwd=ROOT, text=True, encoding="utf-8",
        )) for path in paths if path.endswith("/records.jsonl")]
    rows = []
    for run, contents in sources:
        if run in EXCLUDE_RUNS:
            continue
        for line in contents.splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            r["final_truncated"] = _final_truncated(r)
            if not include_transcripts:
                r.pop("transcript", None)
            r["run"] = run
            rows.append(r)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # keep the latest record per (model, approach, instance, sample)
    df = df.drop_duplicates(["model", "approach", "instance", "sample"], keep="last")
    meta = pd.DataFrame([{"instance": i.id, "pair": i.pair, "tier": i.tier, "category": i.category,
                          "twin": i.twin, "label": i.label, "tags": ",".join(i.tags)} for i in load_dataset()])
    df = df.merge(meta, on="instance", how="inner")
    # Each analysed sample must cover the entire dataset; partial runs stay in RUN_STATUS.md.
    full = df.groupby(["model", "approach", "sample"])["instance"].transform("nunique") == len(meta)
    df = df[full | (df["model"] == "tool")].copy()
    df["correct"] = df["verdict"] == df["gold"]
    df["decided"] = df["verdict"] != "UNKNOWN"
    df["system"] = df["model"] + " | " + df["approach"]
    return df


# ----------------------------------------------------------------------------- stats
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar(a: pd.Series, b: pd.Series) -> tuple[int, int, float]:
    """Exact McNemar test on paired correctness vectors (aligned by index)."""
    b01 = int(((~a) & b).sum())
    b10 = int((a & (~b)).sum())
    n = b01 + b10
    p = 1.0 if n == 0 else binomtest(b10, n, 0.5).pvalue
    return b10, b01, p


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[idx]))
        adj[idx] = running
    return adj


# ----------------------------------------------------------------------------- metrics
def metrics(g: pd.DataFrame) -> dict:
    n = len(g)
    k = int(g["correct"].sum())
    uns = g[g["gold"] == "UNSAFE"]
    saf = g[g["gold"] == "SAFE"]
    tp = int((uns["verdict"] == "UNSAFE").sum())
    fn_ = int((uns["verdict"] == "SAFE").sum())
    tn = int((saf["verdict"] == "SAFE").sum())
    fp = int((saf["verdict"] == "UNSAFE").sum())
    unk = int((g["verdict"] == "UNKNOWN").sum())
    prec = tp / (tp + fp) if tp + fp else math.nan
    rec = tp / len(uns) if len(uns) else math.nan
    if math.isnan(prec) or math.isnan(rec):
        f1 = math.nan
    else:
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    lo, hi = wilson(k, n)
    dec = g[g["decided"]]
    pairs = g.groupby("pair")["correct"].agg(["all", "count"])
    pairs = pairs[pairs["count"] == 2]
    same = g.groupby("pair")["verdict"].agg(lambda v: v.nunique() == 1 and len(v) == 2)
    uns_pred = g[(g["verdict"] == "UNSAFE")]
    has_wit = len(uns_pred) and "witness_status" in uns_pred and uns_pred["witness_status"].notna().any()
    confirmed = int((uns_pred["witness_status"] == "confirmed").sum()) if has_wit else 0
    return {
        "n": n, "accuracy": k / n if n else math.nan, "acc_lo": lo, "acc_hi": hi,
        "tpr": rec, "tnr": tn / len(saf) if len(saf) else math.nan, "precision": prec, "f1": f1,
        "fp": fp, "fn": fn_, "unknown": unk, "coverage": 1 - unk / n if n else math.nan,
        "selective_acc": dec["correct"].mean() if len(dec) else math.nan,
        "pair_acc": pairs["all"].mean() if len(pairs) else math.nan,
        "pair_same_verdict": same.mean() if len(same) else math.nan,
        "unsafe_claims": len(uns_pred), "witness_confirmed": confirmed,
        "witness_confirm_rate": confirmed / len(uns_pred) if has_wit else math.nan,
        "mean_out_tokens": g["output_tokens"].mean() if "output_tokens" in g else math.nan,
        "mean_llm_calls": g["llm_calls"].mean() if "llm_calls" in g else math.nan,
        "mean_wall_s": g["wall_s"].mean() if "wall_s" in g else math.nan,
    }


def summary(df: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    keys = ["model", "approach"] + (by or [])
    rows = []
    for key, g in df.groupby(keys):
        rows.append({**dict(zip(keys, key if isinstance(key, tuple) else (key,))), **metrics(g)})
    out = pd.DataFrame(rows)
    out["_a"] = out["approach"].map(lambda a: (APPROACH_ORDER + TOOL_ORDER + list(APPROACH_LABEL)).index(a)
                                    if a in APPROACH_LABEL else 99)
    return out.sort_values(["model", "_a"] + (by or [])).drop(columns="_a").reset_index(drop=True)


# ----------------------------------------------------------------------- derived policies
def _require_replay(records: pd.DataFrame) -> pd.DataFrame:
    """Reject unconfirmed bug claims without consulting the ground-truth label."""
    out = records.copy()
    out["original_verdict"] = out["verdict"]
    unconfirmed = out["verdict"].eq("UNSAFE") & out["witness_status"].ne("confirmed")
    out["abstention_reason"] = ""
    out.loc[unconfirmed, "verdict"] = "UNKNOWN"
    out.loc[unconfirmed, "abstention_reason"] = "unconfirmed_witness"
    return out


def _hybrid(z: pd.DataFrame, c: pd.DataFrame, zv: str, strict: bool = False) -> pd.DataFrame:
    common = z.index.intersection(c.index)
    h = z.loc[common].copy()
    use_cot = h["verdict"].eq("UNKNOWN")
    h["fallback_reason"] = ""
    h.loc[use_cot, "fallback_reason"] = "z3_unknown"
    if strict:
        rejected = h["verdict"].eq("UNSAFE") & h["witness_status"].ne("confirmed")
        use_cot = use_cot | rejected
        h.loc[rejected, "fallback_reason"] = "z3_unconfirmed_witness"
    answer_columns = [col for col in (
        "verdict", "violation", "witness", "witness_status", "witness_detail",
        "exec_kind", "explanation", "parse", "transcript",
    ) if col in h.columns]
    h.loc[use_cot, answer_columns] = c.loc[h.index[use_cot], answer_columns]
    h["answer_source"] = zv
    h.loc[use_cot, "answer_source"] = "direct_cot"
    cost_columns = [col for col in (
        "llm_calls", "input_tokens", "output_tokens",
    ) if col in h.columns]
    h.loc[use_cot, cost_columns] = (
        z.loc[h.index[use_cot], cost_columns] + c.loc[h.index[use_cot], cost_columns]
    )
    h["cost_basis"] = "estimated_sequential"
    for col in ("wall_s", "llm_latency_s"):
        if col in h.columns:
            h[col] = math.nan
    if strict:
        h = _require_replay(h)
    h["approach"] = f"{'strict_' if strict else ''}hybrid_{zv}_else_cot"
    return h.reset_index()


def derived_policies(df: pd.DataFrame) -> pd.DataFrame:
    """Post-hoc systems built from existing records (no extra model calls):
      hybrid_<z3 variant>_else_cot   use the Z3 verdict (bare or repair) when the script ran, else the CoT verdict
        Answer fields follow the selected approach, recorded in `answer_source`.
        Z3 attempts/status remain from the original Z3 record. Calls and tokens
        estimate sequential execution: always Z3, plus CoT only on fallback.
        Cached component timings do not provide a measured hybrid runtime.
      validated_<approach>   report UNSAFE only if that approach's witness reproduces under the sanitizers
      validated_z3_repair    report UNSAFE only if the Z3 counterexample reproduces
      strict_<approach>   turn unconfirmed UNSAFE into UNKNOWN, retaining original SAFE claims
      strict_hybrid_<z3 variant>_else_cot   also fall back on unconfirmed Z3 bug claims;
        if the selected CoT bug claim is unconfirmed, the final answer is UNKNOWN
    """
    out = []
    for model, g in df[df["model"] != "tool"].groupby("model"):
        index = ["instance", "sample"] if "sample" in g.columns else ["instance"]
        piv = {a: x.set_index(index) for a, x in g.groupby("approach")}
        for zv in ("z3", "z3_repair"):
            if zv in piv and "direct_cot" in piv:
                z, c = piv[zv], piv["direct_cot"]
                out.append(_hybrid(z, c, zv))
                out.append(_hybrid(z, c, zv, strict=True))
        for a in ("direct_cot", "z3_repair"):
            if a in piv:
                v = _require_replay(piv[a])
                v["approach"] = f"strict_{a}"
                out.append(v.reset_index())
        for a in APPROACH_ORDER:
            if a in piv:
                v = piv[a].copy()
                unconf = (v["verdict"] == "UNSAFE") & (v["witness_status"] != "confirmed")
                v.loc[unconf, "verdict"] = "SAFE"
                v["approach"] = f"validated_{a}"
                out.append(v.reset_index())
    if not out:
        return pd.DataFrame()
    d = pd.concat(out, ignore_index=True)
    d["correct"] = d["verdict"] == d["gold"]
    d["decided"] = d["verdict"] != "UNKNOWN"
    return d


COMPARISON_APPROACHES = (
    "direct_cot", "z3_repair", "hybrid_z3_repair_else_cot",
    "strict_direct_cot", "strict_z3_repair", "strict_hybrid_z3_repair_else_cot",
)


def hybrid_comparison(df: pd.DataFrame, derived: pd.DataFrame) -> pd.DataFrame:
    """Compare verdicts, reproducible findings, abstentions, and logical resource use."""
    rows = []
    systems = pd.concat([df, derived], ignore_index=True)
    for (model, approach), g in systems[systems["approach"].isin(COMPARISON_APPROACHES)].groupby(
        ["model", "approach"], sort=False
    ):
        m = metrics(g)
        bugs = g["gold"].eq("UNSAFE")
        confirmed = bugs & g["verdict"].eq("UNSAFE") & g["witness_status"].eq("confirmed")
        row = {
            "model": model, "approach": approach, "n": len(g),
            "correct_verdicts": int(g["correct"].sum()), "accuracy": m["accuracy"],
            "unsafe_cases": int(bugs.sum()), "confirmed_bugs": int(confirmed.sum()),
            "confirmed_bug_recall": confirmed.sum() / bugs.sum() if bugs.any() else math.nan,
            "unsafe_claims": m["unsafe_claims"], "precision": m["precision"],
            "false_safe": m["fn"], "unknown": m["unknown"],
            "unknown_on_unsafe": int((bugs & g["verdict"].eq("UNKNOWN")).sum()),
            "coverage": m["coverage"], "selective_accuracy": m["selective_acc"],
            "cost_basis": "estimated_sequential" if "hybrid_" in approach else "recorded_response_usage",
        }
        for field in ("llm_calls", "input_tokens", "output_tokens"):
            # An unknown component cost makes the overall mean unknown, not cheaper.
            row[f"mean_{field}"] = g[field].mean(skipna=False) if field in g else math.nan
        rows.append(row)
    columns = ["model", "approach", "n", "correct_verdicts", "accuracy", "unsafe_cases",
               "confirmed_bugs", "confirmed_bug_recall", "unsafe_claims", "precision", "false_safe",
               "unknown", "unknown_on_unsafe", "coverage", "selective_accuracy", "cost_basis",
               "mean_llm_calls", "mean_input_tokens", "mean_output_tokens"]
    out = pd.DataFrame(rows, columns=columns)
    if out.empty:
        return out
    out["_order"] = out["approach"].map(COMPARISON_APPROACHES.index)
    return out.sort_values(["model", "_order"]).drop(columns="_order").reset_index(drop=True)


def hybrid_case_changes(df: pd.DataFrame, derived: pd.DataFrame) -> pd.DataFrame:
    """List changes in verdict or confirmed evidence, including hybrid wins and losses.

    Strict hybrids are compared with strict CoT, applying the same replay rule to both.
    Ground truth is used only to score differences, never to select an answer.
    """
    rows = []
    keys = ["instance", "sample"] if "sample" in df else ["instance"]
    columns = ["model", "hybrid_approach", "baseline_approach", *keys, "pair", "tier", "category", "gold",
               "cot_verdict", "cot_witness_status", "hybrid_verdict", "hybrid_witness_status",
               "answer_source", "fallback_reason", "verdict_change", "evidence_change",
               "cot_witness", "hybrid_witness"]
    if derived.empty:
        return pd.DataFrame(columns=columns)
    for (model, approach), g in derived[derived["approach"].str.contains("hybrid_")].groupby(
        ["model", "approach"]
    ):
        strict = approach.startswith("strict_")
        baseline_approach = "strict_direct_cot" if strict else "direct_cot"
        pool = derived if strict else df
        baseline = pool[(pool["model"] == model) & (pool["approach"] == baseline_approach)].set_index(keys)
        for key, h in g.set_index(keys).iterrows():
            c = baseline.loc[key]
            hc = h["verdict"] == "UNSAFE" and h["witness_status"] == "confirmed"
            cc = c["verdict"] == "UNSAFE" and c["witness_status"] == "confirmed"
            if h["verdict"] == c["verdict"] and hc == cc:
                continue
            row = {"model": model, "hybrid_approach": approach, "baseline_approach": baseline_approach,
                   "instance": h.name[0] if isinstance(h.name, tuple) else h.name}
            if "sample" in keys:
                row["sample"] = h.name[1]
            for field in ("pair", "tier", "category", "gold"):
                row[field] = h.get(field)
            row.update(
                cot_verdict=c["verdict"], cot_witness_status=c["witness_status"],
                hybrid_verdict=h["verdict"], hybrid_witness_status=h["witness_status"],
                answer_source=h["answer_source"], fallback_reason=h.get("fallback_reason", ""),
                verdict_change=("hybrid_only_correct" if h["correct"] and not c["correct"] else
                                "cot_only_correct" if c["correct"] and not h["correct"] else "same_correctness"),
                evidence_change=("hybrid_only_confirmed" if hc and not cc else
                                 "cot_only_confirmed" if cc and not hc else "same_confirmation"),
                cot_witness=json.dumps(c["witness"], sort_keys=True) if isinstance(c.get("witness"), dict) else "null",
                hybrid_witness=json.dumps(h["witness"], sort_keys=True) if isinstance(h.get("witness"), dict) else "null",
            )
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)


# ---------------------------------------------------------------------- z3 pipeline detail
def z3_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Classify each final Z3 attempt: confirmed bug, proved safe, spurious cex, missed bug, error type."""
    z = df[df["approach"].str.startswith("z3")].copy()

    def cls(r):
        st = r.get("z3_status")
        if st == "sat":
            if r["gold"] == "UNSAFE":
                return "bug found (cex confirmed)" if r.get("witness_status") == "confirmed" else "bug found (cex not reproduced)"
            return "false alarm (spurious cex)"
        if st == "unsat":
            return "proved safe" if r["gold"] == "SAFE" else "missed bug (unsat)"
        et = r.get("z3_error_type") or "error"
        if r.get("final_truncated"):
            return "error: runaway output (token limit)"
        atts = r.get("attempts")
        last_err = (atts[-1].get("error") or "") if isinstance(atts, list) and atts else ""
        if "ModuleNotFoundError" in last_err or "ImportError" in last_err:
            return "error: hallucinated API"
        return {"syntax": "error: syntax", "name_error": "error: hallucinated API", "z3_api": "error: Z3 sort/API misuse",
                "type_error": "error: type/operator misuse", "no_code": "error: no code", "no_solver": "error: protocol",
                "timeout": "error: timeout", "solver_unknown": "error: solver unknown"}.get(et, "error: runtime")
    z["outcome"] = z.apply(cls, axis=1)
    return z


def repair_curve(df: pd.DataFrame, max_k: int = 3) -> pd.DataFrame:
    """Accuracy / executable-rate if only the first k repair rounds were allowed."""
    rows = []
    for model, g in df[df["approach"] == "z3_repair"].groupby("model"):
        for k in range(max_k + 1):
            ok = runs = 0
            for _, r in g.iterrows():
                atts = r.get("attempts") or []
                if not isinstance(atts, list) or not atts:
                    continue
                a = atts[min(k, len(atts) - 1)]
                v = a.get("verdict", "UNKNOWN")
                ok += v == r["gold"]
                runs += a.get("status") in ("sat", "unsat")
            rows.append({"model": model, "k": k, "accuracy": ok / len(g), "executable": runs / len(g)})
    return pd.DataFrame(rows)


CODE_FEATURES = {
    "uses_bitvec": r"BitVec\(|BitVecs\(|BitVecSort",
    "uses_int_sort": r"\bInt\(|\bInts\(|IntSort",
    "uses_srem": r"SRem\(",
    "uses_overflow_helpers": r"BV(Add|Sub|Mul|SDiv|SNeg)No(Over|Under)flow",
    "uses_arrays": r"Array\(",
    "uses_push_pop": r"\.push\(|\.pop\(",
    "calls_check": r"\.check\(",
    "uses_python_bool_ops": r"[)\w]\s*[|&]\s*\(?\s*\w+\s*[<>=!]=?",
}


def code_features(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in df[df["approach"].str.startswith("z3")].iterrows():
        atts = r.get("attempts") or []
        if not isinstance(atts, list) or not atts:
            continue
        code = atts[-1].get("code") or ""
        f = {k: bool(re.search(p, code)) for k, p in CODE_FEATURES.items()}
        rows.append({"model": r["model"], "approach": r["approach"], "instance": r["instance"],
                     "category": r["category"], "correct": r["correct"], "lines": code.count("\n") + 1, **f})
    return pd.DataFrame(rows)


def pairwise_tests(df: pd.DataFrame, comparisons: list[tuple[str, str]]) -> pd.DataFrame:
    rows = []
    for model, g in df[df["model"] != "tool"].groupby("model"):
        piv = g.pivot_table(index="instance", columns="approach", values="correct", aggfunc="first")
        for a, b in comparisons:
            if a in piv and b in piv:
                sub = piv[[a, b]].dropna().astype(bool)
                b10, b01, p = mcnemar(sub[a], sub[b])
                rows.append({"model": model, "A": a, "B": b, "n": len(sub), "acc_A": sub[a].mean(),
                             "acc_B": sub[b].mean(), "A_only_correct": b10, "B_only_correct": b01, "p": p})
    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"] = holm(out["p"].tolist())
    return out


def cross_model_tests(df: pd.DataFrame, approaches: list[str]) -> pd.DataFrame:
    rows = []
    models = sorted(m for m in df["model"].unique() if m != "tool")
    for a in approaches:
        piv = df[df["approach"] == a].pivot_table(index="instance", columns="model", values="correct", aggfunc="first")
        for m1, m2 in combinations(models, 2):
            if m1 in piv and m2 in piv:
                sub = piv[[m1, m2]].dropna().astype(bool)
                b10, b01, p = mcnemar(sub[m1], sub[m2])
                rows.append({"approach": a, "A": m1, "B": m2, "n": len(sub), "acc_A": sub[m1].mean(),
                             "acc_B": sub[m2].mean(), "p": p})
    return pd.DataFrame(rows)
