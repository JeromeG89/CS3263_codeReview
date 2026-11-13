#!/usr/bin/env python
"""Turn evaluation records into tables (CSV + Markdown), statistics and figures.

Outputs: results/analysis/*.csv|.md|summary.json and report/figures/*.png.
Duplicate repair-analysis notes and provenance go to ignored build/analysis/.

  python scripts/analyze.py --comparison-only
  python scripts/analyze.py --comparison-only --records-ref origin/main
  python scripts/analyze.py --repair-analysis-only --records-ref ecc7f3a
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck.analysis import (APPROACH_LABEL, APPROACH_ORDER, TOOL_ORDER, code_features,  # noqa: E402
                               cross_model_tests, derived_policies, hybrid_case_changes, hybrid_comparison,
                               load_records, pairwise_tests, repair_curve, resolve_records_ref,
                               short_model, summary, z3_outcomes)
from invcheck.dataset import ROOT  # noqa: E402
from invcheck.repair_analysis import repair_efficiency  # noqa: E402
from invcheck.sensitivity import pair_sensitivity  # noqa: E402

OUT = ROOT / "results" / "analysis"
FIG = ROOT / "report" / "figures"
DETAILS = ROOT / "build" / "analysis"

# Reference palette (dataviz skill, light mode): categorical slots in fixed order.
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
APPROACH_COLOR = {a: SLOTS[i] for i, a in enumerate(APPROACH_ORDER)}
TOOL_COLOR = {"reference_z3": "#52514e", "cbmc": "#7d7c78", "fuzz_dict": "#a9a8a3", "fuzz_random": "#c9c8c3"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
    "axes.titleweight": "bold", "legend.frameon": False, "axes.axisbelow": True,
})


def md(df: pd.DataFrame, floatfmt=".2f") -> str:
    try:
        return df.to_markdown(index=False, floatfmt=floatfmt)
    except ImportError:  # comparison-only analysis also works without optional tabulate
        def cell(value):
            if pd.isna(value):
                return "N/A"
            if isinstance(value, (float, np.floating)):
                return format(value, floatfmt)
            return str(value).replace("|", "\\|").replace("\n", " ")
        rows = [list(df.columns), ["---"] * len(df.columns), *df.itertuples(index=False, name=None)]
        return "\n".join("| " + " | ".join(cell(v) for v in row) + " |" for row in rows)


def pct(x):
    return "–" if pd.isna(x) else f"{100 * x:.1f}%"


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=200, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------------------ figures
def fig_accuracy(s: pd.DataFrame, tools: pd.DataFrame, models: list[str]):
    fig, axes = plt.subplots(1, len(models) + 1, figsize=(3.2 * (len(models) + 1), 3.6), sharey=True,
                             gridspec_kw={"width_ratios": [1] * len(models) + [0.9]})
    for ax, m in zip(axes, models):
        g = s[(s["model"] == m) & s["approach"].isin(APPROACH_ORDER)].set_index("approach").reindex(APPROACH_ORDER)
        x = np.arange(len(g))
        ax.bar(x, g["accuracy"], width=0.62, color=[APPROACH_COLOR[a] for a in g.index], zorder=2)
        ax.errorbar(x, g["accuracy"], yerr=[g["accuracy"] - g["acc_lo"], g["acc_hi"] - g["accuracy"]],
                    fmt="none", ecolor=INK2, elinewidth=1, capsize=2, zorder=3)
        for xi, v, hi in zip(x, g["accuracy"], g["acc_hi"]):
            if not np.isnan(v):
                ax.text(xi, hi + 0.015, f"{100 * v:.0f}", ha="center", va="bottom", fontsize=8, color=INK2)
        short_lbl = {"direct": "Direct", "direct_cot": "CoT", "z3": "Z3", "z3_guided": "Z3\nguided", "z3_repair": "Z3\n+repair"}
        ax.set_xticks(x, [short_lbl[a] for a in g.index], fontsize=8)
        for xi, v in zip(x, g["accuracy"]):
            if np.isnan(v):
                ax.text(xi, 0.03, "not\nrun", ha="center", va="bottom", fontsize=8, color=INK2)
        ax.set_title(short_model(m))
        ax.axhline(0.5, color=INK2, lw=0.8, ls=(0, (1, 2)))
    ax = axes[-1]
    t = tools.set_index("approach").reindex([a for a in TOOL_ORDER if a in set(tools["approach"])])
    x = np.arange(len(t))
    ax.bar(x, t["accuracy"], width=0.62, color=[TOOL_COLOR[a] for a in t.index], zorder=2)
    for xi, v in zip(x, t["accuracy"]):
        ax.text(xi, v + 0.02, f"{100 * v:.0f}", ha="center", va="bottom", fontsize=8, color=INK2)
    short = {"reference_z3": "Gold Z3\n(Claude)", "cbmc": "CBMC", "fuzz_dict": "Fuzz\ndict.", "fuzz_random": "Fuzz\nrandom"}
    ax.set_xticks(x, [short[a] for a in t.index], fontsize=7.5)
    ax.set_title("Non-LLM reference points")
    ax.axhline(0.5, color=INK2, lw=0.8, ls=(0, (1, 2)))
    axes[0].set_ylabel("Accuracy (120 instances)")
    axes[0].set_ylim(0, 1.12)
    fig.suptitle("Verdict accuracy by approach (95% Wilson CI; dotted line = chance on the balanced set)",
                 fontsize=10, color=INK2, y=1.02)
    save(fig, "fig1_accuracy.png")


def fig_tpr_tnr(s: pd.DataFrame, models: list[str]):
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    markers = ["o", "s", "^", "D", "v", "P"]
    for mi, m in enumerate(models):
        for a in APPROACH_ORDER:
            r = s[(s["model"] == m) & (s["approach"] == a)]
            if len(r):
                ax.scatter(r["tnr"], r["tpr"], s=70, color=APPROACH_COLOR[a], marker=markers[mi % 6],
                           edgecolor=SURF, linewidth=2, zorder=3)
    ax.plot([0, 1], [1, 0], color=INK2, lw=0.8, ls=(0, (1, 2)))
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel("Specificity: SAFE instances judged SAFE")
    ax.set_ylabel("Recall: UNSAFE instances judged UNSAFE")
    ax.text(0.02, 0.03, "below dotted line:\nworse than a coin flip", fontsize=8, color=INK2)
    h1 = [plt.Line2D([], [], marker="o", ls="", color=APPROACH_COLOR[a], markersize=8, label=APPROACH_LABEL[a])
          for a in APPROACH_ORDER]
    h2 = [plt.Line2D([], [], marker=markers[i % 6], ls="", color=INK2, markersize=8, label=short_model(m))
          for i, m in enumerate(models)]
    ax.legend(handles=h1 + h2, fontsize=7.5, loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.set_title("Where the errors go: missed bugs vs false alarms")
    save(fig, "fig2_tpr_tnr.png")


def fig_by_tier(st: pd.DataFrame, models: list[str]):
    fig, axes = plt.subplots(1, len(models), figsize=(4 * len(models), 3.4), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], models):
        for a in APPROACH_ORDER:
            g = st[(st["model"] == m) & (st["approach"] == a)].sort_values("tier")
            if len(g):
                ax.plot(g["tier"], g["accuracy"], color=APPROACH_COLOR[a], lw=2, marker="o", markersize=5,
                        markeredgecolor=SURF, markeredgewidth=1.5, label=APPROACH_LABEL[a])
        ax.set_xticks([1, 2, 3, 4], ["T1 flat", "T2 branches", "T3 loops", "T4 calls+nested"], fontsize=8)
        ax.set_title(short_model(m))
        ax.set_ylim(0, 1.05)
    axes[0][0].set_ylabel("Accuracy")
    axes[0][-1].legend(fontsize=7.5, loc="center left", bbox_to_anchor=(1.01, 0.5))
    save(fig, "fig3_accuracy_by_tier.png")


def fig_category_heatmap(sc: pd.DataFrame, tools_c: pd.DataFrame):
    d = pd.concat([sc, tools_c])
    d = d[d["approach"].isin(APPROACH_ORDER + ["reference_z3", "cbmc", "fuzz_dict"])]
    d["row"] = d.apply(lambda r: (short_model(r["model"]) + " · " if r["model"] != "tool" else "") +
                       APPROACH_LABEL[r["approach"]], axis=1)
    piv = d.pivot_table(index="row", columns="category", values="accuracy", sort=False)
    piv = piv[[c for c in ["bounds", "div_zero", "overflow", "shift"] if c in piv]]
    fig, ax = plt.subplots(figsize=(5.6, 0.32 * len(piv) + 1.2))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seqblue", ["#f4f8fd", "#9ec5f4", "#3987e5", "#1c5cab", "#0d366b"])
    ax.imshow(piv.values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.grid(False)
    for (i, j), v in np.ndenumerate(piv.values):
        if not np.isnan(v):
            ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=7.5,
                    color="white" if v > 0.55 else INK)
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), piv.index, fontsize=7.5)
    ax.set_title("Accuracy (%) by bug class")
    save(fig, "fig4_category_heatmap.png")


OUTCOME_ORDER = ["proved safe", "bug found (cex confirmed)", "bug found (cex not reproduced)",
                 "false alarm (spurious cex)", "missed bug (unsat)", "error: runaway output (token limit)", "error: hallucinated API",
                 "error: type/operator misuse", "error: Z3 sort/API misuse", "error: syntax", "error: runtime",
                 "error: no code", "error: protocol", "error: timeout", "error: solver unknown"]
OUTCOME_COLOR = {"proved safe": SLOTS[0], "bug found (cex confirmed)": SLOTS[2],
                 "bug found (cex not reproduced)": "#8fd9bd", "false alarm (spurious cex)": SLOTS[1],
                 "missed bug (unsat)": SLOTS[7]}


def fig_z3_outcomes(zo: pd.DataFrame):
    zo = zo.copy()
    zo["row"] = zo["model"].map(short_model) + " · " + zo["approach"].map(APPROACH_LABEL)
    tab = zo.groupby(["row", "outcome"]).size().unstack(fill_value=0)
    cols = [c for c in OUTCOME_ORDER if c in tab.columns]
    tab = tab[cols]
    greys = ["#3d3c39", "#5f5e5a", "#7d7c78", "#9b9a95", "#b5b4af", "#cfceca", "#e0dfdb", "#ebeae6", "#f1f0ec"]
    colors, gi = [], 0
    for c in cols:
        if c in OUTCOME_COLOR:
            colors.append(OUTCOME_COLOR[c])
        else:
            colors.append(greys[min(gi, len(greys) - 1)])
            gi += 1
    fig, ax = plt.subplots(figsize=(8.5, 0.45 * len(tab) + 1.4))
    left = np.zeros(len(tab))
    for c, col in zip(cols, colors):
        ax.barh(range(len(tab)), tab[c], left=left, color=col, height=0.6, edgecolor=SURF, linewidth=1.5, label=c)
        left += tab[c].values
    ax.set_yticks(range(len(tab)), tab.index, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Instances (final attempt)")
    ax.grid(axis="y", visible=False)
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    ax.set_title("What happened to each LLM-written Z3 script")
    save(fig, "fig5_z3_outcomes.png")


def fig_repair(rc: pd.DataFrame, models: list[str]):
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    for i, m in enumerate(models):
        g = rc[rc["model"] == m]
        for ax, col in zip(axes, ["executable", "accuracy"]):
            ax.plot(g["k"], g[col], color=SLOTS[i], lw=2, marker="o", markersize=5, markeredgecolor=SURF,
                    markeredgewidth=1.5, label=short_model(m))
    axes[0].set_title("Scripts that run (sat/unsat)")
    axes[1].set_title("Verdict accuracy")
    for ax in axes:
        ax.set_xlabel("Feedback rounds allowed")
        ax.set_xticks(range(int(rc["k"].max()) + 1))
        ax.set_ylim(0, 1.05)
    axes[1].legend(fontsize=8)
    save(fig, "fig6_repair_rounds.png")


def fig_twin(stw: pd.DataFrame, models: list[str]):
    fig, axes = plt.subplots(1, len(models), figsize=(4 * len(models), 3.2), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], models):
        g = stw[stw["model"] == m]
        x = np.arange(len(APPROACH_ORDER))
        for k, (tw, col) in enumerate([("code", SLOTS[0]), ("precondition", SLOTS[1])]):
            v = g[g["twin"] == tw].set_index("approach").reindex(APPROACH_ORDER)["pair_acc"]
            ax.bar(x + (k - 0.5) * 0.36, v, width=0.34, color=col, label=f"{tw} twins", zorder=2)
        ax.set_xticks(x, [APPROACH_LABEL[a].replace(" + ", "\n+ ").replace("LLM→Z3 ", "LLM→Z3\n")
                          for a in APPROACH_ORDER], fontsize=7)
        ax.set_title(short_model(m))
    axes[0][0].set_ylabel("Pair accuracy (both twins right)")
    axes[0][-1].legend(fontsize=8)
    save(fig, "fig7_twin_type.png")


# ------------------------------------------------------------------- hybrid comparison
def fig_review_evidence(comparison: pd.DataFrame) -> None:
    """Keep original verdict accuracy separate from successful bug-input replay."""
    approaches = [("direct_cot", "CoT", SLOTS[0]),
                  ("z3_repair", "Z3 + repair", SLOTS[1]),
                  ("hybrid_z3_repair_else_cot", "Z3 + repair, else CoT", SLOTS[2])]
    models = sorted(comparison.loc[comparison["approach"].eq("z3_repair"), "model"].unique())
    if not models:
        return
    selected = comparison.set_index(["model", "approach"])
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.1))
    x = np.arange(len(models))
    width = 0.23
    for ax, metric, denominator, title in (
            (axes[0], "correct_verdicts", "n", "Correct classifications"),
            (axes[1], "confirmed_bugs", "unsafe_cases", "Bugs with working example inputs")):
        for i, (approach, label, color) in enumerate(approaches):
            rows = selected.loc[[(model, approach) for model in models]]
            values = rows[metric].to_numpy()
            totals = rows[denominator].to_numpy()
            positions = x + (i - 1) * width
            ax.bar(positions, values / totals * 100, width=width, color=color, label=label, zorder=2)
            for pos, value, total in zip(positions, values, totals):
                ax.text(pos, value / total * 100 + 1.3, f"{value}/{total}",
                        ha="center", va="bottom", fontsize=8, rotation=90)
        ax.set_xticks(x, [short_model(model).replace("gemini-", "Gemini ") for model in models], fontsize=8)
        ax.set_ylim(0, 123)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_ylabel("Percent of cases" if metric == "correct_verdicts" else "Percent of unsafe cases")
        ax.set_title(title)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=9)
    fig.text(0.5, 0.015, "Original verdict scoring; hybrid falls back only on UNKNOWN. "
             "Working inputs use saved replay statuses. Llama repair was not run.",
             ha="center", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.06, 1, 0.90))
    save(fig, "fig9_review_evidence.png")


def write_hybrid_comparison(df: pd.DataFrame, derived: pd.DataFrame, source: str) -> str:
    comparison = hybrid_comparison(df, derived)
    cases = hybrid_case_changes(df, derived)
    comparison.to_csv(OUT / "hybrid_comparison.csv", index=False)
    cases.to_csv(OUT / "hybrid_cases.csv", index=False)
    fig_review_evidence(comparison)
    parts = [
        "# CoT, Z3 and hybrid comparison", "",
        "_Generated by `scripts/analyze.py`; do not edit by hand._", "",
        f"**Saved-record source:** {source}. Dataset metadata comes from the working tree.", "",
        "No new model calls, solver executions or C replays were performed. These policies recombine "
        "the stored answers and replay statuses.", "",
        "**Original hybrid:** use Z3+repair unless it returns UNKNOWN, then use CoT. "
        "**Replay-required hybrid:** also fall back when Z3's final bug input is unconfirmed; "
        "if CoT's selected bug input is unconfirmed, return UNKNOWN. Existing repair attempts are already "
        "included in the saved Z3+repair answer.", "",
        "**Fair comparison:** rows marked 'replay required' apply the same rule to CoT alone and "
        "Z3+repair alone: an unconfirmed UNSAFE becomes UNKNOWN, never SAFE. Original verdict rows "
        "are retained so the effect of changing the reporting rule is visible.", "",
    ]
    for model, g in comparison.groupby("model", sort=False):
        table = pd.DataFrame({
            "Method": g["approach"].map(APPROACH_LABEL),
            "Correct verdicts": g.apply(lambda r: f"{r['correct_verdicts']}/{r['n']}", axis=1),
            "Bugs with working inputs": g.apply(lambda r: f"{r['confirmed_bugs']}/{r['unsafe_cases']}", axis=1),
            "UNKNOWN": g["unknown"],
            "Mean calls": g["mean_llm_calls"],
            "Mean input tokens": g["mean_input_tokens"],
            "Mean output tokens": g["mean_output_tokens"],
        })
        parts += [f"## {short_model(model)}", "", md(table), ""]
        if "z3_repair" not in set(g["approach"]):
            parts += ["Z3+repair was not evaluated for this model, so its repair-hybrid rows are omitted.", ""]
    parts += [
        "## Cases where the combination helps or hurts", "",
        "`hybrid_cases.csv` lists changed verdicts or confirmed evidence, including wins and losses. "
        "Each original hybrid is compared with original CoT; each replay-required hybrid with replay-required CoT.", "",
    ]
    if not cases.empty:
        counts = cases.groupby(["model", "hybrid_approach", "baseline_approach"], sort=False).agg(
            extra_correct=("verdict_change", lambda x: int(x.eq("hybrid_only_correct").sum())),
            lost_correct=("verdict_change", lambda x: int(x.eq("cot_only_correct").sum())),
            extra_working_inputs=("evidence_change", lambda x: int(x.eq("hybrid_only_confirmed").sum())),
            lost_working_inputs=("evidence_change", lambda x: int(x.eq("cot_only_confirmed").sum())),
        ).reset_index()
        counts["model"] = counts["model"].map(short_model)
        parts += [md(counts), ""]
    parts += [
        "## Reading the numbers", "",
        "- UNKNOWN counts as incorrect for accuracy. It is neither a confirmed bug nor an explicit SAFE claim.",
        "- A working input means an UNSAFE claim marked `confirmed` on a gold UNSAFE case. "
        "This uses the existing harness status; it does not strengthen or re-check that harness.",
        "- SAFE remains the selected method's claim. Requiring replay for bug claims does not prove SAFE answers.",
        "- Calls and tokens describe the responses needed by the policy. Hybrid totals include every "
        "recorded Z3 repair call, plus CoT only when selected. They are estimates, not a bill for fresh API calls.",
        "- Cached component times cannot establish hybrid runtime; no hybrid runtime is reported.",
        "- The CSV also includes accuracy, coverage, precision, confirmed-bug recall, false SAFE claims "
        "and UNKNOWN answers on buggy cases. Precision is N/A when there are no UNSAFE claims.",
        "- These comparisons are exploratory and are excluded from the existing Holm-corrected test family. "
        "A small observed gain does not establish general superiority.", "",
    ]
    report = "\n".join(parts)
    (OUT / "hybrid_comparison.md").write_text(report, encoding="utf-8")
    return report


# ------------------------------------------------------------------- Repair analysis
def write_repair_analysis(df: pd.DataFrame, derived: pd.DataFrame, source: str,
                        resamples: int = 20000, seed: int = 3263) -> None:
    efficiency, cases = repair_efficiency(df)
    sensitivity = pair_sensitivity(df, derived, resamples=resamples, seed=seed)
    efficiency.to_csv(OUT / "repair_efficiency.csv", index=False)
    cases.to_csv(OUT / "repair_cases.csv", index=False)
    sensitivity.to_csv(OUT / "pair_sensitivity.csv", index=False)
    metadata = {"records_source": source, "bootstrap_resamples": resamples, "seed": seed,
                "max_repairs": 3, "stop_rule": "first consecutive identical nonempty script, after executing duplicate",
                "models_with_repair": sorted(df.loc[df["approach"].eq("z3_repair"), "model"].unique()),
                "new_tests_in_family": len(sensitivity)}
    DETAILS.mkdir(parents=True, exist_ok=True)
    (DETAILS / "repair_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    parts = [
        "# Repair efficiency and paired statistical checks", "",
        "_Generated by `scripts/analyze.py`; do not edit by hand._", "",
        f"**Saved-record source:** {source}. No model calls, solver executions or C replays were performed.", "",
        "## What each repair round buys", "",
        "Zero repairs means one initial script. A cap of three repairs permits up to four model calls. "
        "Cases that already finished do not consume the remaining budget. The same saved prefix is "
        "also evaluated with the replay-required CoT fallback.", "",
    ]
    if not efficiency.empty:
        for model, g in efficiency.groupby("model", sort=False):
            parts += [f"### {short_model(model)}", ""]
            for system, title in (("z3_repair", "Z3 repair alone (original verdict scoring)"),
                                  ("strict_hybrid", "Combined with CoT, requiring replay for bug claims")):
                selected = g[g["system"].eq(system)]
                if selected.empty:
                    continue
                view = selected[["policy", "correct_verdicts", "confirmed_bugs", "unknown", "logical_calls",
                                 "extra_calls_vs_previous", "net_extra_correct", "calls_saved_vs_full",
                                 "lost_correct_vs_full", "gained_correct_vs_full"]]
                parts += [f"**{title}**", "", md(view), ""]
        parts += ["![Repair calls and accuracy](../../report/figures/fig8_repair_efficiency.png)", ""]
        models = efficiency["model"].unique()
        fig, axes = plt.subplots(1, len(models), figsize=(4.1 * len(models), 3.8), squeeze=False, sharey=True)
        for ax, model in zip(axes[0], models):
            for system, color, label in (("z3_repair", SLOTS[0], "Z3 repair"),
                                         ("strict_hybrid", SLOTS[2], "Z3 then CoT (bug inputs checked)")):
                g = efficiency[efficiency["model"].eq(model) & efficiency["system"].eq(system)]
                caps = g[g["policy"].str.startswith("cap_")].sort_values("repairs_allowed")
                if caps.empty:
                    continue
                ax.plot(caps["mean_calls"], caps["accuracy"], marker="o", color=color, label=label)
                for (calls, accuracy), same_point in caps.groupby(["mean_calls", "accuracy"], sort=False):
                    label_text = ",".join(str(k) for k in same_point["repairs_allowed"])
                    offset = (3, -12) if system == "z3_repair" else (3, 6)
                    ax.annotate(label_text, (calls, accuracy), xytext=offset,
                                textcoords="offset points", fontsize=8, color=color)
                stop = g[g["policy"].eq("stop_on_repeat")]
                ax.scatter(stop["mean_calls"], stop["accuracy"], marker="x", color=color, s=75, zorder=4)
            ax.set_title(short_model(model))
            ax.set_xlabel("Estimated LLM calls per case (fewer = left)")
            ax.set_ylim(0, 1.06)
        axes[0][0].set_ylabel("Correct answers / all cases (more = up)")
        axes[0][-1].legend(fontsize=8, loc="lower right")
        fig.suptitle("Repair cost and accuracy: numbers = repairs allowed (0 = initial script only); "
                     "crosses = stop on repeat", fontsize=9)
        fig.tight_layout()
        save(fig, "fig8_repair_efficiency.png")
    else:
        parts += ["No complete repair runs are available; no repair result is inferred for missing runs.", ""]
    parts += [
        "## What the repeated-script rule means", "",
        "Stop after the first consecutive identical, nonempty script. The duplicate response has already "
        "cost a call; only later calls are avoided. Missing code is not treated as a repeated script. "
        "The rule sees no labels or later answers. `repair_cases.csv` lists saved calls and any correct "
        "answers or working inputs gained or lost compared with the full saved trace.", "",
        "For the hybrid, the same stopping rule is followed by the normal replay-required CoT fallback. "
        "CoT calls count too. Raising the repair cap can sometimes save a CoT fallback, so the hybrid's "
        "extra-call count can be negative. No live runner or prompt has been changed.", "",
        "**Token limitation:** the logs contain aggregate token usage for each full repair run, not "
        "usage per turn. Truncated traces therefore have unknown token cost. We count logical calls "
        "without fabricating token savings or claiming measured runtime savings.", "",
        "## Do the gains survive treating twins as related?", "",
        f"Each complete safe/unsafe pair is one cluster. We resample whole clusters {resamples:,} times "
        f"with seed {seed}, keeping both methods aligned. If there are multiple samples, they remain "
        "inside their original pair cluster. The intervals below are 95% percentile bootstrap intervals "
        "for B minus A; positive values favour B. UNKNOWN counts as incorrect for accuracy. "
        "Confirmed-bug recall counts only working bug inputs on gold UNSAFE cases.", "",
    ]
    if not sensitivity.empty:
        focus = sensitivity[sensitivity["B"].eq("strict_hybrid_z3_repair_else_cot")].copy()
        view = pd.DataFrame({
            "Model": focus["model"].map(short_model), "Outcome": focus["outcome"],
            "B minus A (points)": focus["difference"] * 100,
            "95% low (points)": focus["lo95"] * 100, "95% high (points)": focus["hi95"] * 100,
            "Pairwise p": focus["p_cluster"], "Sensitivity Holm p": focus["p_holm_sensitivity"],
        })
        parts += ["**Focus: replay-required hybrid versus replay-required CoT**", "", md(view, ".4f"), ""]
    parts += [
        "The CSV also compares CoT with Z3+repair, original CoT with the original hybrid, and guided "
        "Z3 with repair. For each comparison we swap method assignments for whole pairs, using an "
        "exact two-sided sign-flip test when at most 16 pair differences are nonzero; otherwise "
        "we use the seeded Monte Carlo test with a plus-one correction. The Holm column corrects "
        "only this new sensitivity-test family across all listed comparisons and outcomes; the original "
        "McNemar results are untouched.", "",
        "**Limits:** this constructed benchmark is not a random sample of production code. "
        "These are exploratory sensitivity checks. Pairs are treated as independent of other pairs, "
        "although templates can still be related. A zero-width bootstrap interval at a ceiling or "
        "with no observed differences does not prove equivalence or the absence of unseen errors. "
        "An interval containing zero does not establish an improvement.", "",
        "Method references: [paired bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) "
        "and [paired permutations](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html).", "",
    ]
    (DETAILS / "repair_analysis.md").write_text("\n".join(parts), encoding="utf-8")


# ------------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--comparison-only", action="store_true", help="write only the hybrid comparison and case list")
    mode.add_argument("--repair-analysis-only", action="store_true", help="write only repair efficiency and pair-based sensitivity checks")
    parser.add_argument("--records-ref", help="read saved records from an existing local Git revision, without checkout or fetch")
    parser.add_argument("--resamples", type=int, default=20000, help="Pair-level bootstrap and Monte Carlo draws (default 20000)")
    parser.add_argument("--seed", type=int, default=3263, help="Pair-level resampling seed (default 3263)")
    args = parser.parse_args()
    commit = resolve_records_ref(args.records_ref) if args.records_ref else None
    source = f"Git commit `{commit}`" if commit else "working-tree records"
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_records(records_ref=commit)
    if df.empty:
        print("no records yet")
        return
    llm = df[df["model"] != "tool"]
    dp = derived_policies(llm)
    if args.repair_analysis_only:
        write_repair_analysis(llm, dp, source, args.resamples, args.seed)
        print(f"Wrote repair efficiency, case changes, pair sensitivity and figure from {source}.")
        return
    write_hybrid_comparison(llm, dp, source)
    if args.comparison_only:
        print(f"Wrote hybrid_comparison.csv, hybrid_cases.csv and hybrid_comparison.md from {source}.")
        return
    write_repair_analysis(llm, dp, source, args.resamples, args.seed)
    tools = df[df["model"] == "tool"]
    models = sorted(llm["model"].unique())
    s = summary(df)
    s.to_csv(OUT / "summary.csv", index=False)
    st = summary(llm, ["tier"])
    sc = summary(llm, ["category"])
    stw = summary(llm, ["twin"])
    tools_s = summary(tools) if len(tools) else pd.DataFrame()
    tools_c = summary(tools, ["category"]) if len(tools) else pd.DataFrame()
    for name, d in [("by_tier", st), ("by_category", sc), ("by_twin", stw)]:
        d.to_csv(OUT / f"{name}.csv", index=False)

    sd = summary(dp) if len(dp) else pd.DataFrame()
    comps = [("direct", "direct_cot"), ("direct", "z3"), ("direct_cot", "z3_repair"), ("z3", "z3_guided"),
             ("z3_guided", "z3_repair"), ("direct", "z3_repair")]
    comps += [("direct", "hybrid_z3_else_cot"), ("direct_cot", "hybrid_z3_else_cot")]
    pt = pairwise_tests(pd.concat([llm, dp], ignore_index=True) if len(dp) else llm, comps)
    pt.to_csv(OUT / "mcnemar.csv", index=False)
    cm = cross_model_tests(llm, APPROACH_ORDER)
    zo = z3_outcomes(llm)
    zo_tab = zo.groupby(["model", "approach", "outcome"]).size().unstack(fill_value=0)
    zo_tab.to_csv(OUT / "z3_outcomes.csv")
    rc = repair_curve(llm)
    rc.to_csv(OUT / "repair_curve.csv", index=False)
    cf = code_features(llm)
    cf.to_csv(OUT / "z3_code_features.csv", index=False)

    # ---- figures
    if models:
        fig_accuracy(s[s["model"] != "tool"], tools_s if len(tools_s) else s.iloc[:0], models)
        fig_tpr_tnr(s, models)
        fig_by_tier(st, models)
        fig_category_heatmap(sc, tools_c if len(tools_c) else sc.iloc[:0])
        if len(zo):
            fig_z3_outcomes(zo)
        if len(rc):
            fig_repair(rc, models)
        fig_twin(stw, models)

    # ---- markdown tables
    def main_table(d):
        t = d.copy()
        t["Model"] = t["model"].map(short_model)
        t["Approach"] = t["approach"].map(lambda a: APPROACH_LABEL.get(a, a))
        t["Accuracy [95% CI]"] = t.apply(lambda r: f"{pct(r['accuracy'])} [{pct(r['acc_lo'])}, {pct(r['acc_hi'])}]", axis=1)
        for c, src in [("Recall (UNSAFE)", "tpr"), ("Specificity (SAFE)", "tnr"), ("Pair acc.", "pair_acc"),
                       ("Coverage", "coverage"), ("Witness confirmed", "witness_confirm_rate")]:
            t[c] = t[src].map(pct)
        t["False alarms"] = t["fp"]
        t["Missed bugs"] = t["fn"]
        t["Unknown"] = t["unknown"]
        return t[["Model", "Approach", "Accuracy [95% CI]", "Recall (UNSAFE)", "Specificity (SAFE)", "Pair acc.",
                  "False alarms", "Missed bugs", "Unknown", "Witness confirmed"]]

    parts = ["# Generated results tables", "", "_Produced by `scripts/analyze.py`; do not edit by hand._", ""]
    parts += ["## Main results", "", md(main_table(s)), ""]
    if len(sd):
        parts += ["## Derived policies (post hoc, no extra model calls)", "", md(main_table(sd)), ""]
    parts += ["## CoT versus Z3+repair and their combination", "",
              "See [hybrid_comparison.md](hybrid_comparison.md) for the original and replay-required policies, "
              "their costs, and cases where the combination helps or hurts.", ""]
    piv = st.pivot_table(index=["model", "approach"], columns="tier", values="accuracy", sort=False).reset_index()
    piv["model"] = piv["model"].map(short_model)
    piv["approach"] = piv["approach"].map(APPROACH_LABEL)
    parts += ["## Accuracy by tier", "", md(piv.rename(columns={1: "T1", 2: "T2", 3: "T3", 4: "T4"})), ""]
    pc = pd.concat([sc, tools_c]) if len(tools_c) else sc
    piv = pc.pivot_table(index=["model", "approach"], columns="category", values="accuracy", sort=False).reset_index()
    piv["model"] = piv["model"].map(short_model)
    piv["approach"] = piv["approach"].map(lambda a: APPROACH_LABEL.get(a, a))
    parts += ["## Accuracy by bug class", "", md(piv), ""]
    piv = stw.pivot_table(index=["model", "approach"], columns="twin", values="pair_acc", sort=False).reset_index()
    piv["model"] = piv["model"].map(short_model)
    piv["approach"] = piv["approach"].map(APPROACH_LABEL)
    parts += ["## Pair accuracy by twin type (code fix vs precondition change)", "", md(piv), ""]
    if len(pt):
        t = pt.copy()
        t["model"] = t["model"].map(short_model)
        parts += ["## McNemar exact tests (paired by instance, Holm-corrected)", "", md(t, ".3f"), ""]
    if len(cm):
        t = cm.copy()
        t["A"], t["B"] = t["A"].map(short_model), t["B"].map(short_model)
        parts += ["## Model comparison per approach (McNemar)", "", md(t, ".3f"), ""]
    if len(zo_tab):
        t = zo_tab.reset_index()
        t["model"] = t["model"].map(short_model)
        parts += ["## Z3 pipeline outcomes (final attempt)", "", md(t, ".0f"), ""]
    if len(rc):
        t = rc.copy()
        t["model"] = t["model"].map(short_model)
        parts += ["## Effect of repair rounds", "", md(t), ""]
    if len(cf):
        g = cf.groupby(["model", "approach"]).agg(
            n=("correct", "size"), acc=("correct", "mean"), bitvec=("uses_bitvec", "mean"),
            int_sort=("uses_int_sort", "mean"), srem=("uses_srem", "mean"),
            ovf_helpers=("uses_overflow_helpers", "mean"), push_pop=("uses_push_pop", "mean"),
            lines=("lines", "median")).reset_index()
        g["model"] = g["model"].map(short_model)
        parts += ["## Static features of the generated Z3 code (final attempt)", "", md(g), ""]
        rows = []
        for f in ["uses_bitvec", "uses_int_sort", "uses_overflow_helpers", "uses_srem"]:
            for val in (True, False):
                sub = cf[cf[f] == val]
                if len(sub):
                    rows.append({"feature": f, "present": val, "n": len(sub), "accuracy": sub["correct"].mean()})
        parts += ["### Accuracy conditioned on code features (all models, all Z3 approaches)", "",
                  md(pd.DataFrame(rows)), ""]
    cost = s[s["model"] != "tool"][["model", "approach", "mean_llm_calls", "mean_out_tokens", "mean_wall_s"]].copy()
    cost["model"] = cost["model"].map(short_model)
    cost["approach"] = cost["approach"].map(APPROACH_LABEL)
    if len(tools_s):
        tc = tools_s[["approach", "mean_wall_s"]].copy()
        tc["approach"] = tc["approach"].map(APPROACH_LABEL)
        parts += ["## Cost", "", md(cost), "", "Tools (mean wall-clock seconds per instance):", "", md(tc), ""]
    (OUT / "tables.md").write_text("\n".join(parts), encoding="utf-8")

    summary_json = {
        "records_source": source,
        "systems": s.to_dict(orient="records"), "derived": sd.to_dict(orient="records") if len(sd) else [],
        "mcnemar": pt.to_dict(orient="records"), "cross_model": cm.to_dict(orient="records"),
        "repair_curve": rc.to_dict(orient="records"), "by_tier": st.to_dict(orient="records"),
        "by_category": pd.concat([sc, tools_c]).to_dict(orient="records") if len(tools_c) else sc.to_dict(orient="records"),
        "by_twin": stw.to_dict(orient="records"),
        "z3_outcomes": zo.groupby(["model", "approach", "outcome"]).size().reset_index(name="n").to_dict(orient="records"),
        "code_features": cf.groupby(["model", "approach"]).mean(numeric_only=True).reset_index().to_dict(orient="records") if len(cf) else [],
    }
    (OUT / "summary.json").write_text(json.dumps(summary_json, indent=1, default=float), encoding="utf-8")
    print(f"Wrote result tables, hybrid comparisons and figures from {source}.")


if __name__ == "__main__":
    main()
