/* Data-driven SVG charts for the report page. Reads window.REPORT_DATA (summary.json subset).
   Colours come from CSS custom properties so light and dark themes both work. */
(function () {
  const D = window.REPORT_DATA;
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const NS = "http://www.w3.org/2000/svg";
  const APPROACHES = ["direct", "direct_cot", "z3", "z3_guided", "z3_repair"];
  const LABEL = {
    direct: "Direct", direct_cot: "Direct + CoT", z3: "LLM→Z3", z3_guided: "LLM→Z3 guided",
    z3_repair: "LLM→Z3 guided + repair", reference_z3: "Gold Z3", cbmc: "CBMC",
    fuzz_dict: "Fuzz (dictionary)", fuzz_random: "Fuzz (random)",
  };
  const SERIES = (a) => css("--s" + (APPROACHES.indexOf(a) + 1));
  const short = (m) => m.replace("ollama:", "").replace("gemini:", "");
  const pct = (x) => (x == null || isNaN(x) ? "–" : (100 * x).toFixed(1) + "%");
  const models = [...new Set(D.systems.filter((s) => s.model !== "tool").map((s) => s.model))].sort().reverse();

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, str, attrs) {
    const t = el("text", Object.assign({ x, y, fill: css("--ink2"), "font-size": 12 }, attrs || {}), parent);
    t.textContent = str;
    return t;
  }

  // ---------------------------------------------------------------- tooltip
  const tip = document.createElement("div");
  tip.className = "tip";
  tip.hidden = true;
  document.body.appendChild(tip);
  function showTip(evt, rows) {
    tip.replaceChildren();
    for (const [k, v, colour] of rows) {
      const r = document.createElement("div");
      r.className = "tip-row";
      if (colour) {
        const key = document.createElement("span");
        key.className = "tip-key";
        key.style.background = colour;
        r.appendChild(key);
      }
      const b = document.createElement("strong");
      b.textContent = v;
      const s = document.createElement("span");
      s.textContent = k;
      r.append(b, s);
      tip.appendChild(r);
    }
    tip.hidden = false;
    const x = Math.min(evt.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    tip.style.left = x + "px";
    tip.style.top = evt.clientY + 14 + "px";
  }
  function hideTip() { tip.hidden = true; }
  function hover(node, rowsFn) {
    node.setAttribute("tabindex", "0");
    node.addEventListener("pointermove", (e) => showTip(e, rowsFn()));
    node.addEventListener("pointerleave", hideTip);
    node.addEventListener("focus", () => {
      const r = node.getBoundingClientRect();
      showTip({ clientX: r.right, clientY: r.top }, rowsFn());
    });
    node.addEventListener("blur", hideTip);
  }

  function frame(host, w, h) {
    host.replaceChildren();
    const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", width: "100%" });
    host.appendChild(svg);
    return svg;
  }
  function yAxis(svg, x0, x1, y, h, ticks, fmt) {
    for (const t of ticks) {
      const yy = y(t);
      el("line", { x1: x0, x2: x1, y1: yy, y2: yy, stroke: css("--grid"), "stroke-width": 1 }, svg);
      text(svg, x0 - 6, yy + 4, fmt(t), { "text-anchor": "end", "font-size": 11 });
    }
  }

  // ------------------------------------------------- 1. accuracy by approach
  function approachLegend(host, withTools) {
    const legend = host.closest("figure") && host.closest("figure").querySelector(".legend");
    if (!legend) return;
    legend.replaceChildren();
    APPROACHES.forEach((a) => legend.appendChild(key(SERIES(a), LABEL[a], withTools ? "rect" : "circle")));
    if (withTools) ["reference_z3", "cbmc", "fuzz_dict", "fuzz_random"].forEach((a, i) => legend.appendChild(key(css("--tool" + (i + 1)), LABEL[a], "rect")));
  }
  function accuracyChart(host) {
    approachLegend(host, true);
    const groups = models.map((m) => ({ title: short(m), rows: APPROACHES.map((a) => D.systems.find((s) => s.model === m && s.approach === a)) }));
    const tools = ["reference_z3", "cbmc", "fuzz_dict", "fuzz_random"].map((a) => D.systems.find((s) => s.model === "tool" && s.approach === a)).filter(Boolean);
    const W = 760, H = 340, L = 44, B = 276, T = 40;
    const svg = frame(host, W, H);
    const y = (v) => B - v * (B - T);
    yAxis(svg, L, W - 8, y, H, [0, 0.25, 0.5, 0.75, 1], (t) => Math.round(t * 100) + "%");
    el("line", { x1: L, x2: W - 8, y1: y(0.5), y2: y(0.5), stroke: css("--ink2"), "stroke-dasharray": "2 3", "stroke-width": 1 }, svg);
    const panels = [...groups, { title: "Non-LLM tools", rows: tools, tools: true }];
    const pw = (W - L - 8) / panels.length;
    panels.forEach((p, pi) => {
      const x0 = L + pi * pw;
      text(svg, x0 + pw / 2, 14, p.title, { "text-anchor": "middle", fill: css("--ink"), "font-weight": 600, "font-size": 12 });
      const n = p.rows.length, bw = Math.min(22, (pw - 24) / n - 6);
      p.rows.forEach((r, i) => {
        const cx = x0 + 12 + (i + 0.5) * ((pw - 24) / n);
        if (!r) {
          text(svg, cx, B - 4, "n/a", { "text-anchor": "middle", "font-size": 10 });
          return;
        }
        const colour = p.tools ? css("--tool" + (i + 1)) : SERIES(r.approach);
        const g = el("g", { class: "mark" }, svg);
        const top = y(r.accuracy);
        el("path", { d: `M${cx - bw / 2},${B} V${top + 4} q0,-4 4,-4 h${bw - 8} q4,0 4,4 V${B} Z`, fill: colour }, g);
        if (!p.tools) {
          el("line", { x1: cx, x2: cx, y1: y(r.acc_lo), y2: y(r.acc_hi), stroke: css("--ink2"), "stroke-width": 1 }, g);
        }
        text(svg, cx, Math.min(top, y(r.acc_hi || r.accuracy)) - 5, Math.round(r.accuracy * 100), { "text-anchor": "middle", "font-size": 10.5 });
        el("rect", { x: cx - bw / 2 - 4, y: T, width: bw + 8, height: B - T, fill: "transparent" }, g);
        hover(g, () => [["accuracy", pct(r.accuracy), colour], [p.tools ? "tool" : "approach", LABEL[r.approach]],
          ["95% CI", `${pct(r.acc_lo)} – ${pct(r.acc_hi)}`], ["bugs caught (recall)", pct(r.tpr)],
          ["safe passed (specificity)", pct(r.tnr)], ["no usable answer", String(r.unknown)]]);
        const lbl = (LABEL[r.approach] || r.approach).replace("LLM→Z3 guided + repair", "Z3 +repair").replace("LLM→Z3 guided", "Z3 guided").replace("Direct + CoT", "CoT").replace("Fuzz (dictionary)", "Fuzz dict").replace("Fuzz (random)", "Fuzz rand");
        const t = text(svg, cx, B + 14, lbl, { "text-anchor": "end", "font-size": 10.5, transform: `rotate(-35 ${cx} ${B + 14})` });
        t.setAttribute("dx", "4");
      });
    });
  }

  // ------------------------------------------------- 2. recall vs specificity
  function scatterChart(host) {
    const W = 520, H = 400, L = 52, B = 350, R = 500, T = 16;
    const svg = frame(host, W, H);
    const x = (v) => L + v * (R - L), y = (v) => B - v * (B - T);
    for (const t of [0, 0.25, 0.5, 0.75, 1]) {
      el("line", { x1: L, x2: R, y1: y(t), y2: y(t), stroke: css("--grid") }, svg);
      el("line", { x1: x(t), x2: x(t), y1: T, y2: B, stroke: css("--grid") }, svg);
      text(svg, L - 6, y(t) + 4, Math.round(t * 100) + "%", { "text-anchor": "end", "font-size": 11 });
      text(svg, x(t), B + 16, Math.round(t * 100) + "%", { "text-anchor": "middle", "font-size": 11 });
    }
    el("line", { x1: x(0), y1: y(1), x2: x(1), y2: y(0), stroke: css("--ink2"), "stroke-dasharray": "2 3" }, svg);
    text(svg, (L + R) / 2, B + 34, "Specificity: SAFE functions passed", { "text-anchor": "middle" });
    text(svg, 14, (T + B) / 2, "Recall: bugs caught", { "text-anchor": "middle", transform: `rotate(-90 14 ${(T + B) / 2})` });
    text(svg, x(0.02), y(0.04), "worse than a coin flip", { "font-size": 10.5 });
    const shapes = ["circle", "square", "diamond"];
    D.systems.filter((s) => s.model !== "tool" && s.tnr != null && s.tpr != null).forEach((s) => {
      const mi = models.indexOf(s.model), cx = x(s.tnr), cy = y(s.tpr), c = SERIES(s.approach);
      const g = el("g", { class: "mark" }, svg);
      if (shapes[mi] === "circle") el("circle", { cx, cy, r: 6, fill: c, stroke: css("--surface"), "stroke-width": 2 }, g);
      else if (shapes[mi] === "square") el("rect", { x: cx - 6, y: cy - 6, width: 12, height: 12, rx: 2, fill: c, stroke: css("--surface"), "stroke-width": 2 }, g);
      else el("path", { d: `M${cx},${cy - 7} L${cx + 7},${cy} L${cx},${cy + 7} L${cx - 7},${cy} Z`, fill: c, stroke: css("--surface"), "stroke-width": 2 }, g);
      el("circle", { cx, cy, r: 13, fill: "transparent" }, g);
      const tag = { direct: "D", direct_cot: "CoT", z3: "Z3", z3_guided: "G", z3_repair: "R" }[s.approach];
      text(svg, cx + 9, cy - 7, tag + (models.length > 1 ? (mi === 0 ? "" : "′") : ""), { "font-size": 10.5, fill: css("--ink") });
      hover(g, () => [[LABEL[s.approach], short(s.model), c], ["recall", pct(s.tpr)], ["specificity", pct(s.tnr)], ["no usable answer", String(s.unknown)]]);
    });
    const legend = host.parentElement.querySelector(".legend");
    if (legend) {
      legend.replaceChildren();
      const tags = { direct: "D", direct_cot: "CoT", z3: "Z3", z3_guided: "G", z3_repair: "R" };
      APPROACHES.forEach((a) => legend.appendChild(key(SERIES(a), `${tags[a]} = ${LABEL[a]}`, "rect")));
      models.forEach((m, i) => legend.appendChild(key(css("--ink2"), short(m), shapes[i])));
    }
  }
  function key(colour, label, shape) {
    const span = document.createElement("span");
    span.className = "key";
    const sw = document.createElement("i");
    sw.className = "sw " + shape;
    sw.style.background = colour;
    const t = document.createElement("span");
    t.textContent = label;
    span.append(sw, t);
    return span;
  }

  // ------------------------------------------------- 3. accuracy by tier
  function tierChart(host) {
    host.replaceChildren();
    approachLegend(host, false);
    models.forEach((m) => {
      const box = document.createElement("div");
      box.className = "multiple";
      const h = document.createElement("h4");
      h.textContent = short(m);
      box.appendChild(h);
      host.appendChild(box);
      const W = 340, H = 220, L = 40, R = 300, B = 186, T = 10;
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%" }, box);
      const x = (t) => L + ((t - 1) / 3) * (R - L), y = (v) => B - v * (B - T);
      for (const t of [0, 0.5, 1]) {
        el("line", { x1: L, x2: R, y1: y(t), y2: y(t), stroke: css("--grid") }, svg);
        text(svg, L - 6, y(t) + 4, Math.round(t * 100) + "%", { "text-anchor": "end", "font-size": 11 });
      }
      ["T1 flat", "T2 branch", "T3 loops", "T4 calls"].forEach((lbl, i) => text(svg, x(i + 1), B + 18, lbl, { "text-anchor": "middle", "font-size": 10.5 }));
      APPROACHES.forEach((a) => {
        const pts = D.by_tier.filter((r) => r.model === m && r.approach === a).sort((p, q) => p.tier - q.tier);
        if (!pts.length) return;
        el("path", { d: pts.map((p, i) => `${i ? "L" : "M"}${x(p.tier)},${y(p.accuracy)}`).join(" "), fill: "none", stroke: SERIES(a), "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
        pts.forEach((p) => {
          const g = el("g", { class: "mark" }, svg);
          el("circle", { cx: x(p.tier), cy: y(p.accuracy), r: 4, fill: SERIES(a), stroke: css("--surface"), "stroke-width": 2 }, g);
          el("circle", { cx: x(p.tier), cy: y(p.accuracy), r: 12, fill: "transparent" }, g);
          hover(g, () => [[LABEL[a], "Tier " + p.tier, SERIES(a)], ["accuracy", pct(p.accuracy)], ["instances", String(p.n)]]);
        });
      });
    });
  }

  // ------------------------------------------------- 4. z3 outcomes (stacked)
  const OUTCOMES = [
    ["proved safe", "--ok1"], ["bug found (cex confirmed)", "--ok2"], ["bug found (cex not reproduced)", "--ok3"],
    ["false alarm (spurious cex)", "--bad1"], ["missed bug (unsat)", "--bad2"],
    ["error: runaway output (token limit)", "--e1"], ["error: hallucinated API", "--e2"], ["other script errors", "--e3"],
  ];
  const groupOutcome = (o) => (o.startsWith("error:") && !["error: runaway output (token limit)", "error: hallucinated API"].includes(o) ? "other script errors" : o);
  function outcomesChart(host) {
    const rows = [];
    models.forEach((m) => ["z3", "z3_guided", "z3_repair"].forEach((a) => {
      const raw = D.z3_outcomes.filter((r) => r.model === m && r.approach === a);
      const agg = {};
      raw.forEach((r) => { const k = groupOutcome(r.outcome); agg[k] = (agg[k] || 0) + r.n; });
      const recs = Object.entries(agg).map(([outcome, n]) => ({ outcome, n }));
      if (recs.length) rows.push({ m, a, recs });
    }));
    const W = 760, rowH = 30, L = 210, R = 740, T = 6, H = T + rows.length * rowH + 30;
    const svg = frame(host, W, H);
    const x = (v) => L + (v / 120) * (R - L);
    [0, 30, 60, 90, 120].forEach((t) => {
      el("line", { x1: x(t), x2: x(t), y1: T, y2: H - 24, stroke: css("--grid") }, svg);
      text(svg, x(t), H - 8, String(t), { "text-anchor": "middle", "font-size": 11 });
    });
    rows.forEach((row, i) => {
      const yy = T + i * rowH + 6;
      text(svg, L - 8, yy + 13, `${short(row.m)} · ${LABEL[row.a].replace("LLM→Z3 ", "").replace("LLM→Z3", "bare")}`, { "text-anchor": "end", "font-size": 11.5 });
      let acc = 0;
      OUTCOMES.forEach(([name, v]) => {
        const r = row.recs.find((q) => q.outcome === name);
        if (!r) return;
        const g = el("g", { class: "mark" }, svg);
        el("rect", { x: x(acc) + 1, y: yy, width: Math.max(0, x(acc + r.n) - x(acc) - 2), height: 18, fill: css(v) }, g);
        hover(g, () => [[name, String(r.n), css(v)], [short(row.m), LABEL[row.a]]]);
        acc += r.n;
      });
    });
    const legend = host.parentElement.querySelector(".legend");
    if (legend) {
      legend.replaceChildren();
      const seen = new Set();
      OUTCOMES.forEach(([name, v]) => {
        if (!D.z3_outcomes.some((r) => groupOutcome(r.outcome) === name) || seen.has(v + name)) return;
        seen.add(v + name);
        legend.appendChild(key(css(v), name, "rect"));
      });
    }
  }

  // ------------------------------------------------- 5. category heat table
  function categoryTable(host) {
    const cats = ["bounds", "div_zero", "overflow", "shift"];
    const rows = [];
    models.forEach((m) => APPROACHES.forEach((a) => {
      const r = cats.map((c) => D.by_category.find((q) => q.model === m && q.approach === a && q.category === c));
      if (r.some(Boolean)) rows.push({ label: `${short(m)} · ${LABEL[a]}`, r });
    }));
    ["reference_z3", "cbmc", "fuzz_dict"].forEach((a) => {
      const r = cats.map((c) => D.by_category.find((q) => q.model === "tool" && q.approach === a && q.category === c));
      if (r.some(Boolean)) rows.push({ label: LABEL[a], r });
    });
    const table = document.createElement("table");
    table.className = "heat";
    const thead = table.createTHead().insertRow();
    ["System", "bounds", "div. by zero", "overflow", "shift"].forEach((h) => { const th = document.createElement("th"); th.textContent = h; thead.appendChild(th); });
    const tb = table.createTBody();
    rows.forEach((row) => {
      const tr = tb.insertRow();
      const th = document.createElement("th");
      th.textContent = row.label;
      tr.appendChild(th);
      row.r.forEach((q) => {
        const td = tr.insertCell();
        if (!q) { td.textContent = "–"; return; }
        td.textContent = Math.round(q.accuracy * 100);
        td.style.setProperty("--v", q.accuracy.toFixed(3));
        td.className = q.accuracy > 0.6 ? "hi" : "";
      });
    });
    host.replaceChildren(table);
  }

  function renderAll() {
    const map = { accuracy: accuracyChart, scatter: scatterChart, tier: tierChart, outcomes: outcomesChart, category: categoryTable };
    document.querySelectorAll("[data-chart]").forEach((n) => map[n.dataset.chart] && map[n.dataset.chart](n));
  }
  renderAll();
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  if (mq.addEventListener) mq.addEventListener("change", renderAll);
  new MutationObserver(renderAll).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
