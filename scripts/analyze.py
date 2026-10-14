#!/usr/bin/env python
"""Turn evaluation records into tables (CSV + Markdown), statistics and figures.

Outputs: results/analysis/*.csv|.md|summary.json and report/figures/*.png
"""
from __future__ import annotations

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
                               cross_model_tests, derived_policies, load_records, pairwise_tests,
                               repair_curve, short_model, summary, z3_outcomes)
from invcheck.dataset import ROOT  # noqa: E402

OUT = ROOT / "results" / "analysis"
FIG = ROOT / "report" / "figures"

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
    return df.to_markdown(index=False, floatfmt=floatfmt)


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
        ax.set_xticks(x, [APPROACH_LABEL[a].replace(" + ", "\n+ ").replace("LLM→Z3 ", "LLM→Z3\n") for a in g.index],
                      fontsize=7.5)
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
                 "false alarm (spurious cex)", "missed bug (unsat)", "error: hallucinated API",
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


# ------------------------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = load_records()
    if df.empty:
        print("no records yet")
        return
    llm = df[df["model"] != "tool"]
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

    dp = derived_policies(llm)
    sd = summary(dp) if len(dp) else pd.DataFrame()
    comps = [("direct", "direct_cot"), ("direct", "z3"), ("direct_cot", "z3_repair"), ("z3", "z3_guided"),
             ("z3_guided", "z3_repair"), ("direct", "z3_repair")]
    pt = pairwise_tests(llm, comps)
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
    (OUT / "tables.md").write_text("\n".join(parts))

    summary_json = {
        "systems": s.to_dict(orient="records"), "derived": sd.to_dict(orient="records") if len(sd) else [],
        "mcnemar": pt.to_dict(orient="records"), "cross_model": cm.to_dict(orient="records"),
        "repair_curve": rc.to_dict(orient="records"), "by_tier": st.to_dict(orient="records"),
        "by_category": pd.concat([sc, tools_c]).to_dict(orient="records") if len(tools_c) else sc.to_dict(orient="records"),
        "by_twin": stw.to_dict(orient="records"),
        "z3_outcomes": zo.groupby(["model", "approach", "outcome"]).size().reset_index(name="n").to_dict(orient="records"),
        "code_features": cf.groupby(["model", "approach"]).mean(numeric_only=True).reset_index().to_dict(orient="records") if len(cf) else [],
    }
    (OUT / "summary.json").write_text(json.dumps(summary_json, indent=1, default=float))
    print((OUT / "tables.md").read_text()[:6000])


if __name__ == "__main__":
    main()
