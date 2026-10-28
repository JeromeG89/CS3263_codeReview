"""Offline repair-budget and repeated-script stopping policies over saved attempts."""
from __future__ import annotations

import math

import pandas as pd

from .analysis import derived_policies


def repair_snapshot(record: dict, max_repairs: int = 3, stop_on_repeat: bool = False) -> dict:
    """Stop an existing trace without generating a new response or reading its label.

    A repeated script is an identical, nonempty string on consecutive attempts.
    The duplicate call has already happened; only subsequent calls can be saved.
    """
    if max_repairs < 0:
        raise ValueError("max_repairs must be nonnegative")
    attempts = record.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("repair analysis needs a nonempty saved attempt history")
    if record.get("llm_calls", len(attempts)) != len(attempts):
        raise ValueError("saved call count must match successful recorded attempts")
    used = min(max_repairs + 1, len(attempts))
    repeated = False
    if stop_on_repeat:
        for i in range(1, used):
            code = attempts[i].get("code")
            if isinstance(code, str) and code.strip() and code == attempts[i - 1].get("code"):
                used = i + 1
                repeated = True
                break
    last = attempts[used - 1]
    out = dict(record)
    for field in ("verdict", "witness", "witness_status", "witness_detail", "exec_kind"):
        out[field] = last.get(field, "UNKNOWN" if field == "verdict" else None)
    out.update(attempts=attempts[:used], llm_calls=used, repairs_used=used - 1,
               z3_status=last.get("status"), z3_error_type=last.get("error_type"),
               calls_saved=len(attempts) - used, repeated_script=repeated,
               cost_basis="estimated_saved_trace", wall_s=math.nan, llm_latency_s=math.nan)
    if used < len(attempts):
        # Aggregate tokens cannot be divided reliably across the saved turns.
        out["input_tokens"] = out["output_tokens"] = math.nan
    out["correct"] = out["verdict"] == out["gold"]
    out["decided"] = out["verdict"] != "UNKNOWN"
    return out


def _confirmed(frame: pd.DataFrame) -> pd.Series:
    return frame["gold"].eq("UNSAFE") & frame["verdict"].eq("UNSAFE") & frame["witness_status"].eq("confirmed")


def repair_efficiency(df: pd.DataFrame, max_repairs: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return budget/early-stop summaries and cases changed from the full trace.

    Both the raw repair verdicts and the replay-required repair/CoT hybrid are
    scored. Calls include CoT only when that policy actually falls back.
    """
    rows, cases = [], []
    for model, group in df[df["approach"].eq("z3_repair")].groupby("model", sort=True):
        key = ["instance", "sample"] if "sample" in group else ["instance"]
        available = max(len(a) - 1 for a in group["attempts"])
        if available > max_repairs:
            raise ValueError("max_repairs would omit part of the saved baseline")
        cot = df[df["model"].eq(model) & df["approach"].eq("direct_cot")]
        plans = [(f"cap_{k}", k, False) for k in range(max_repairs + 1)]
        plans.append(("stop_on_repeat", max_repairs, True))
        evaluated = {}
        for policy, k, repeat in plans:
            snap = pd.DataFrame([repair_snapshot(r, k, repeat) for r in group.to_dict("records")])
            evaluated[policy, "z3_repair"] = snap.set_index(key).sort_index()
            if not cot.empty:
                if set(map(tuple, group[key].to_numpy())) != set(map(tuple, cot[key].to_numpy())):
                    raise ValueError("repair and CoT need matching instance/sample records")
                derived = derived_policies(pd.concat([snap, cot], ignore_index=True))
                hybrid = derived[derived["approach"].eq("strict_hybrid_z3_repair_else_cot")]
                evaluated[policy, "strict_hybrid"] = hybrid.set_index(key).sort_index()
        for (policy, system), g in evaluated.items():
            baseline = evaluated[f"cap_{max_repairs}", system]
            correct = g["verdict"].eq(g["gold"])
            before = baseline["verdict"].eq(baseline["gold"])
            confirmed, base_confirmed = _confirmed(g), _confirmed(baseline)
            is_cap = policy.startswith("cap_")
            k = int(policy.removeprefix("cap_")) if is_cap else max_repairs
            previous = evaluated.get((f"cap_{k - 1}", system)) if is_cap and k else None
            prev_correct = previous["verdict"].eq(previous["gold"]) if previous is not None else None
            prev_confirmed = _confirmed(previous) if previous is not None else None
            added_calls = int(g["llm_calls"].sum() - previous["llm_calls"].sum()) if previous is not None else math.nan
            net_correct = int(correct.sum() - prev_correct.sum()) if previous is not None else math.nan
            net_confirmed = int(confirmed.sum() - prev_confirmed.sum()) if previous is not None else math.nan
            rows.append({
                "model": model, "system": system, "policy": policy, "repairs_allowed": k,
                "n": len(g), "correct_verdicts": int(correct.sum()), "accuracy": correct.mean(),
                "confirmed_bugs": int(confirmed.sum()), "unsafe_cases": int(g["gold"].eq("UNSAFE").sum()),
                "unknown": int(g["verdict"].eq("UNKNOWN").sum()),
                "false_safe": int((g["gold"].eq("UNSAFE") & g["verdict"].eq("SAFE")).sum()),
                "logical_calls": int(g["llm_calls"].sum()), "mean_calls": g["llm_calls"].mean(),
                "calls_saved_vs_full": int(baseline["llm_calls"].sum() - g["llm_calls"].sum()),
                "extra_calls_vs_previous": added_calls, "net_extra_correct": net_correct,
                "gained_correct_vs_previous": int((correct & ~prev_correct).sum()) if previous is not None else math.nan,
                "lost_correct_vs_previous": int((~correct & prev_correct).sum()) if previous is not None else math.nan,
                "net_extra_confirmed": net_confirmed,
                "calls_per_net_extra_correct": added_calls / net_correct if net_correct > 0 else math.nan,
                "calls_per_net_extra_confirmed": added_calls / net_confirmed if net_confirmed > 0 else math.nan,
                "lost_correct_vs_full": int((before & ~correct).sum()),
                "gained_correct_vs_full": int((~before & correct).sum()),
                "lost_confirmed_vs_full": int((base_confirmed & ~confirmed).sum()),
                "gained_confirmed_vs_full": int((~base_confirmed & confirmed).sum()),
                "mean_output_tokens": g["output_tokens"].mean(skipna=False) if "output_tokens" in g else math.nan,
            })
            changed = (g["llm_calls"].ne(baseline["llm_calls"]) | g["verdict"].ne(baseline["verdict"])
                       | confirmed.ne(base_confirmed))
            for index, r in g[changed].iterrows():
                old = baseline.loc[index]
                entry = {"model": model, "system": system, "policy": policy,
                         "instance": index[0] if isinstance(index, tuple) else index,
                         "gold": r["gold"], "full_verdict": old["verdict"], "policy_verdict": r["verdict"],
                         "full_confirmed": bool(base_confirmed.loc[index]), "policy_confirmed": bool(confirmed.loc[index]),
                         "full_calls": old["llm_calls"], "policy_calls": r["llm_calls"],
                         "calls_saved": old["llm_calls"] - r["llm_calls"],
                         "correct_lost": bool(before.loc[index] and not correct.loc[index]),
                         "correct_gained": bool(not before.loc[index] and correct.loc[index])}
                if "sample" in key:
                    entry["sample"] = index[1]
                cases.append(entry)
    if not rows:
        return (pd.DataFrame(columns=["model", "system", "policy", "correct_verdicts", "confirmed_bugs", "logical_calls"]),
                pd.DataFrame(columns=["model", "system", "policy", "instance", "calls_saved"]))
    case_columns = ["model", "system", "policy", "instance", "sample", "gold", "full_verdict", "policy_verdict",
                    "full_confirmed", "policy_confirmed", "full_calls", "policy_calls", "calls_saved",
                    "correct_lost", "correct_gained"]
    return pd.DataFrame(rows), pd.DataFrame(cases, columns=case_columns)
