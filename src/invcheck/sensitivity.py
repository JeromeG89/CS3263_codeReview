"""Exploratory sensitivity checks that keep each safe/unsafe twin pair together."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis import holm


SENSITIVITY_COMPARISONS = (
    ("direct_cot", "z3_repair"),
    ("direct_cot", "hybrid_z3_repair_else_cot"),
    ("strict_direct_cot", "strict_z3_repair"),
    ("strict_direct_cot", "strict_hybrid_z3_repair_else_cot"),
    ("z3_guided", "z3_repair"),
)


def pair_resampling(differences, resamples: int = 20000, seed: int = 3263) -> dict:
    """Resample pair-level score differences; flip whole-pair method assignments.

    Percentile bootstrap intervals describe observed benchmark variation. They
    cannot establish equivalence or reveal unseen errors at an accuracy ceiling.
    """
    d = np.asarray(differences, dtype=float)
    if d.ndim != 1 or not len(d) or not np.isfinite(d).all():
        raise ValueError("need a nonempty finite vector of pair differences")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(d), size=(resamples, len(d)))
    boot = d[draws].mean(axis=1)
    lo, hi = np.quantile(boot, [0.025, 0.975])
    nonzero = d[d != 0]
    n = len(nonzero)
    target = abs(d.sum()) - 1e-12
    if n <= 16:
        count = 2 ** n
        signs = 2 * ((np.arange(count, dtype=np.uint64)[:, None]
                      >> np.arange(n, dtype=np.uint64)) & 1).astype(float) - 1
        extreme = int((np.abs(signs @ nonzero) >= target).sum())
        p = extreme / count
        method = "exact_pair_sign_flip"
    else:
        count = resamples
        signs = rng.choice([-1, 1], size=(count, n))
        extreme = int((np.abs(signs @ nonzero) >= target).sum())
        p = (extreme + 1) / (count + 1)
        method = "monte_carlo_pair_sign_flip"
    return {"difference": d.mean(), "lo95": lo, "hi95": hi, "p_cluster": p,
            "p_method": method, "permutation_draws": count, "n_pairs": len(d),
            "nonzero_pairs": n, "resamples": resamples, "seed": seed}


def pair_sensitivity(df: pd.DataFrame, derived: pd.DataFrame, resamples: int = 20000,
                     seed: int = 3263, comparisons=SENSITIVITY_COMPARISONS) -> pd.DataFrame:
    """Compare methods using complete benchmark pairs as the sampling unit.

    Multiple samples stay in their original pair cluster. The two methods must
    cover the same cases and samples; incomplete twins are rejected.
    """
    all_records = pd.concat([df, derived], ignore_index=True)
    keys = ["instance", "sample"] if "sample" in all_records else ["instance"]
    rows = []
    for model, records in all_records[all_records["model"].ne("tool")].groupby("model", sort=True):
        by_approach = {a: g.set_index(keys).sort_index() for a, g in records.groupby("approach")}
        for a, b in comparisons:
            if a not in by_approach or b not in by_approach:
                continue
            ga, gb = by_approach[a], by_approach[b]
            if ga.index.has_duplicates or gb.index.has_duplicates or not ga.index.equals(gb.index):
                raise ValueError("paired comparisons require matching unique instance/sample keys")
            if not ga["gold"].equals(gb["gold"]) or not ga["pair"].equals(gb["pair"]):
                raise ValueError("paired methods must agree on benchmark metadata")
            aligned = ga[["pair", "gold"]].reset_index()
            group_keys = ["pair", "sample"] if "sample" in aligned else ["pair"]
            for _, twin in aligned.groupby(group_keys):
                if len(twin) != 2 or set(twin["gold"]) != {"SAFE", "UNSAFE"}:
                    raise ValueError("each benchmark pair/sample must contain one SAFE and one UNSAFE twin")
            for outcome in ("accuracy", "confirmed_bug_recall"):
                mask = ga["gold"].eq("UNSAFE") if outcome == "confirmed_bug_recall" else pd.Series(True, index=ga.index)
                if outcome == "accuracy":
                    sa, sb = ga["verdict"].eq(ga["gold"]), gb["verdict"].eq(gb["gold"])
                else:
                    sa = ga["verdict"].eq("UNSAFE") & ga["witness_status"].eq("confirmed")
                    sb = gb["verdict"].eq("UNSAFE") & gb["witness_status"].eq("confirmed")
                scores = pd.DataFrame({"pair": ga.loc[mask, "pair"],
                                       "a": sa[mask].astype(float), "b": sb[mask].astype(float)})
                pairs = scores.groupby("pair", sort=True)[["a", "b"]].mean()
                stats = pair_resampling((pairs["b"] - pairs["a"]).to_numpy(), resamples, seed)
                rows.append({"model": model, "A": a, "B": b, "outcome": outcome,
                             "score_A": pairs["a"].mean(), "score_B": pairs["b"].mean(),
                             "n_instances": len(ga), **stats})
    columns = ["model", "A", "B", "outcome", "score_A", "score_B", "n_instances", "difference", "lo95", "hi95",
               "p_cluster", "p_method", "permutation_draws", "n_pairs", "nonzero_pairs", "resamples", "seed"]
    out = pd.DataFrame(rows, columns=columns)
    if len(out):
        # A separate family: do not change the project's original corrected tests.
        out["p_holm_sensitivity"] = holm(out["p_cluster"].tolist())
    else:
        out["p_holm_sensitivity"] = pd.Series(dtype=float)
    return out
