#!/usr/bin/env python
"""Build the single-file HTML report page (report/site/report.html) from the
template, the chart code and results/analysis/summary.json."""
from __future__ import annotations

import datetime as dt
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck.analysis import (APPROACH_LABEL, APPROACH_ORDER, derived_policies, load_records,  # noqa: E402
                               summary)
from invcheck.dataset import ROOT, SAFETY_SPEC  # noqa: E402

SITE = ROOT / "report" / "site"
GH = "https://github.com/JeromeG89/CS3263_codeReview/blob/project-pipeline"
Q, L = "ollama:qwen2.5-coder:7b", "ollama:llama3.2:3b"


def pct(x, d=1):
    return "–" if x is None or x != x else f"{100 * x:.{d}f}%"


def short(m):
    return m.replace("ollama:", "").replace("gemini:", "")


def main():
    data = json.loads((ROOT / "results" / "analysis" / "summary.json").read_text())
    sysd = {(s["model"], s["approach"]): s for s in data["systems"]}
    tier = {(r["model"], r["approach"], r["tier"]): r for r in data["by_tier"]}
    twin = {(r["model"], r["approach"], r["twin"]): r for r in data["by_twin"]}
    df = load_records()
    der = summary(derived_policies(df[df["model"] == Q]))
    derd = {r["approach"]: r for r in der.to_dict(orient="records")}

    g = lambda m, a, k: sysd.get((m, a), {}).get(k)  # noqa: E731
    tok = {
        "asof": dt.date.today().strftime("%-d %b %Y"),
        "q_direct_acc": pct(g(Q, "direct", "accuracy"), 0), "l_direct_acc": pct(g(L, "direct", "accuracy"), 0),
        "q_direct_same": pct(g(Q, "direct", "pair_same_verdict"), 0), "q_direct_tpr": pct(g(Q, "direct", "tpr"), 0),
        "q_z3_t1": pct(tier[(Q, "z3", 1)]["accuracy"], 1), "q_direct_t1": pct(tier[(Q, "direct", 1)]["accuracy"], 1),
        "q_z3_t3": pct(tier[(Q, "z3", 3)]["accuracy"], 0), "q_z3_t4": pct(tier[(Q, "z3", 4)]["accuracy"], 0),
        "q_z3_selective": pct(g(Q, "z3", "selective_acc"), 1), "q_z3_exec": pct(g(Q, "z3", "coverage"), 0),
        "l_z3_exec": pct(g(L, "z3", "coverage"), 0), "q_z3_acc": pct(g(Q, "z3", "accuracy"), 0),
        "q_guided_acc": pct(g(Q, "z3_guided", "accuracy"), 0),
        "q_hybrid_acc": pct(derd["hybrid_z3_else_cot"]["accuracy"], 0),
        "q_hybrid_tpr": pct(derd["hybrid_z3_else_cot"]["tpr"], 0),
        "gh": GH, "safety_spec": html.escape(SAFETY_SPEC),
    }
    rows = []
    for m in (Q, L):
        for a in APPROACH_ORDER:
            s = sysd.get((m, a))
            if not s:
                rows.append(f"<tr><td>{short(m)}</td><td>{APPROACH_LABEL[a]}</td><td class='n' colspan='6'>not run</td></tr>")
                continue
            rows.append(f"<tr><td>{short(m)}</td><td>{APPROACH_LABEL[a]}</td><td class='n'>{pct(s['accuracy'])}</td>"
                        f"<td class='n'>{pct(s['acc_lo'], 0)}–{pct(s['acc_hi'], 0)}</td><td class='n'>{pct(s['tpr'], 0)}</td>"
                        f"<td class='n'>{pct(s['tnr'], 0)}</td><td class='n'>{s['unknown']}</td><td class='n'>{pct(s['pair_acc'], 0)}</td></tr>")
    for a in ("reference_z3", "cbmc", "fuzz_dict", "fuzz_random"):
        s = sysd.get(("tool", a))
        if s:
            rows.append(f"<tr><td>tool</td><td>{APPROACH_LABEL[a]}</td><td class='n'>{pct(s['accuracy'])}</td>"
                        f"<td class='n'>{pct(s['acc_lo'], 0)}–{pct(s['acc_hi'], 0)}</td><td class='n'>{pct(s['tpr'], 0)}</td>"
                        f"<td class='n'>{pct(s['tnr'], 0)}</td><td class='n'>{s['unknown']}</td><td class='n'>{pct(s['pair_acc'], 0)}</td></tr>")
    tok["main_table"] = "\n".join(rows)

    cols = [(m, a) for m in (Q, L) for a in ("z3", "z3_guided", "z3_repair")
            if any(r["model"] == m and r["approach"] == a for r in data["z3_outcomes"])]
    tok["outcome_head"] = "".join(f"<th class='n'>{short(m)}<br>{APPROACH_LABEL[a].replace('LLM→Z3 ', '').replace('LLM→Z3', 'bare')}</th>" for m, a in cols)
    order = ["proved safe", "bug found (cex confirmed)", "bug found (cex not reproduced)", "false alarm (spurious cex)",
             "missed bug (unsat)", "error: runaway output (token limit)", "error: hallucinated API",
             "error: type/operator misuse", "error: Z3 sort/API misuse", "error: syntax", "error: runtime",
             "error: no code", "error: protocol", "error: timeout", "error: solver unknown"]
    cnt = {(r["model"], r["approach"], r["outcome"]): r["n"] for r in data["z3_outcomes"]}
    orows = []
    for o in order:
        vals = [cnt.get((m, a, o), 0) for m, a in cols]
        if any(vals):
            orows.append(f"<tr><td>{html.escape(o)}</td>" + "".join(f"<td class='n'>{v}</td>" for v in vals) + "</tr>")
    ex = [sum(cnt.get((m, a, o), 0) for o in order[:5]) for m, a in cols]
    orows.append("<tr class='em'><td>Executable (SAT or UNSAT)</td>" + "".join(f"<td class='n'>{v}</td>" for v in ex) + "</tr>")
    tok["outcome_rows"] = "\n".join(orows)

    tok["twin_rows"] = "\n".join(
        f"<tr><td>{APPROACH_LABEL[a]}</td><td class='n'>{pct(twin[(Q, a, 'code')]['pair_acc'], 0)}</td>"
        f"<td class='n'>{pct(twin[(Q, a, 'precondition')]['pair_acc'], 0)}</td></tr>" for a in APPROACH_ORDER if (Q, a, "code") in twin)

    prow = []
    base = sysd[(Q, "direct")]
    prow.append(f"<tr><td>Direct (reference)</td><td class='n'>{pct(base['accuracy'])}</td><td class='n'>{pct(base['tpr'])}</td>"
                f"<td class='n'>{pct(base['tnr'])}</td><td class='n'>{pct(base['precision'])}</td></tr>")
    for a in ("hybrid_z3_else_cot", "hybrid_z3_repair_else_cot", "validated_direct", "validated_direct_cot", "validated_z3"):
        r = derd.get(a)
        if r:
            cls = " class='em'" if a == "hybrid_z3_else_cot" else ""
            prow.append(f"<tr{cls}><td>{APPROACH_LABEL[a]}</td><td class='n'>{pct(r['accuracy'])}</td><td class='n'>{pct(r['tpr'])}</td>"
                        f"<td class='n'>{pct(r['tnr'])}</td><td class='n'>{pct(r['precision'])}</td></tr>")
    tok["policy_rows"] = "\n".join(prow)

    keep = {k: data[k] for k in ("systems", "by_tier", "by_category", "z3_outcomes")}
    tok["data_json"] = json.dumps(keep, default=float).replace("</", "<\\/")
    tok["charts_js"] = (SITE / "charts.js").read_text()

    page = (SITE / "template.html").read_text()
    for k, v in tok.items():
        page = page.replace("{{" + k + "}}", str(v))
    import re
    left = re.findall(r"\{\{\w+\}\}", page)
    (SITE / "report.html").write_text(page)
    print(f"wrote report/site/report.html ({len(page) // 1024} KB); unfilled: {left}")


if __name__ == "__main__":
    main()
