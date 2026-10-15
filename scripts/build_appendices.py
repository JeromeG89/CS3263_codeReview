#!/usr/bin/env python
"""Generate report/APPENDIX.md directly from the code and data, so it can never
drift from what was actually run:

  Appendix A  every instance: what the model saw, preconditions, witness, reference Z3, validation result
  Appendix B  every prompt template, rendered verbatim
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invcheck import prompts  # noqa: E402
from invcheck.cbmc import harness_source as cbmc_harness  # noqa: E402
from invcheck.cexec import harness_source as exec_harness  # noqa: E402
from invcheck.dataset import ROOT, SAFETY_SPEC, load_dataset, load_examples  # noqa: E402

REPORT = ROOT / "report"
CAT = {"bounds": "array bounds", "div_zero": "division by zero", "overflow": "signed overflow", "shift": "invalid shift"}
TIER = {1: "T1 flat", 2: "T2 branches", 3: "T3 loops", 4: "T4 calls + nested"}


def fence(lang: str, body: str) -> str:
    body = body.rstrip("\n")
    ticks = "````" if "```" in body else "```"
    return f"{ticks}{lang}\n{body}\n{ticks}"


def dataset_appendix() -> str:
    insts = load_dataset()
    val = {}
    vp = ROOT / "results" / "validation.json"
    if vp.exists():
        val = {r["id"]: r for r in json.loads(vp.read_text())}
    pairs: dict[str, list] = {}
    for i in insts:
        pairs.setdefault(i.pair, []).append(i)
    out = [
        "# Appendix A — Dataset catalogue",
        "",
                f"{len(insts)} instances in {len(pairs)} minimal pairs. For each instance this appendix lists, verbatim:",
        "",
        "- **What the model saw**: the C code exactly as rendered into every prompt (the preconditions appear as a C comment).",
        "- **Preconditions in machine form**: the `requires` clauses (C syntax, evaluated over mathematical integers), "
        "array lengths, and element preconditions (`_` stands for each element).",
        "- **Witness**: for UNSAFE instances, the hand-written input that triggers the violation under the sanitizers.",
        "- **Reference Z3 encoding**: the exact script given to the solver for the gold baseline (same protocol the LLMs must follow).",
        "- **Validation**: the result of each independent check.",
        "",
        "Labels, descriptions, bug explanations, tags, witnesses and reference encodings are **never shown to the models**.",
        "",
        "## Index",
        "",
        "| Pair | Tier | Bug class | Twin | Function | UNSAFE version (the bug) | SAFE twin |",
        "|---|---|---|---|---|---|---|",
    ]
    for pid, ps in sorted(pairs.items()):
        u = next(i for i in ps if i.is_unsafe)
        s = next(i for i in ps if not i.is_unsafe)
        cell = lambda x: x.replace("|", "\\|")  # noqa: E731
        out.append(f"| [{pid}](#{pid.lower()}) | {TIER[u.tier]} | {CAT[u.category]} | {u.twin} | `{u.entry}` | "
                   f"{cell(u.bug_explanation)} | {cell(s.description)} |")
    counts = Counter((i.tier, i.category) for i in insts)
    out += ["", "### Instances per tier and bug class", "", "| Tier | bounds | div_zero | overflow | shift | total |",
            "|---|---|---|---|---|---|"]
    for t in (1, 2, 3, 4):
        row = [counts[(t, c)] for c in CAT]
        out.append(f"| {TIER[t]} | " + " | ".join(map(str, row)) + f" | {sum(row)} |")
    out.append("")

    for pid, ps in sorted(pairs.items()):
        u = next(i for i in ps if i.is_unsafe)
        s = next(i for i in ps if not i.is_unsafe)
        out += [f"## {pid}", "",
                f"**{TIER[u.tier]} · {CAT[u.category]} · {u.twin} twin** — tags: {', '.join(u.tags)}", "",
                f"- **UNSAFE version:** {u.description}",
                f"- **Bug:** {u.bug_explanation}",
                f"- **SAFE version:** {s.description}", ""]
        for inst in (u, s):
            v = val.get(inst.id, {})
            checks = []
            if inst.is_unsafe:
                checks.append(f"witness triggers `{v.get('witness_kind', '?')}`")
            checks.append(f"reference Z3 → {v.get('ref_z3', '?')}")
            checks.append(f"CBMC → {v.get('cbmc', '?')}")
            if not inst.is_unsafe:
                checks.append(f"{v.get('fuzz_cases', '?')} fuzz inputs, no violation")
            status = "all checks pass" if v and not v.get("problems") else f"PROBLEMS: {v.get('problems')}"
            out += [f"### {inst.id} — {inst.label.upper()}", "",
                    "What the model saw:", "", fence("c", inst.render()), "",
                    "Preconditions (machine form):", ""]
            out += [f"- `{r}`" for r in inst.requires] or ["- _(none)_"]
            for p in inst.arrays:
                out.append(f"- length of `{p.name}` = `{p.len}`")
            for k, c in inst.elem_requires.items():
                out.append(f"- every element `_` of `{k}`: `{c}`")
            if inst.witness:
                out += ["", f"Witness: `{json.dumps(inst.witness)}`"]
            out += ["", f"Reference Z3 encoding (unwind bound for CBMC: {inst.unwind}):", "",
                    fence("python", inst.reference_z3), "",
                    f"Validation: {'; '.join(checks)} — **{status}**.", ""]
    stress = ROOT / "dataset" / "stress" / "stress.yaml"
    if stress.exists():
        out += ["## Excluded stress pair", "",
                "Neither the reference Z3 encoding nor CBMC decides this pair within the time limits "
                "(32-bit nonlinear multiplication combined with division), so it has no oracle-confirmed label "
                "and is excluded from scoring. Source:", "", fence("yaml", stress.read_text()), ""]
    ex = next(iter(load_dataset()))
    out += ["## Execution harnesses (example: " + ex.id + ")", "",
            "Sanitizer driver used to execute witnesses and fuzz inputs "
            "(`clang -std=c11 -O0 -g -fsanitize=address,undefined -fno-sanitize-recover=all`):", "",
            fence("c", exec_harness(ex)), "",
            "CBMC harness (run with `--bounds-check --pointer-check --div-by-zero-check --signed-overflow-check "
            "--undefined-shift-check --no-malloc-may-fail --unwind N --unwinding-assertions`):", "",
            fence("c", cbmc_harness(ex)), ""]
    return "\n".join(out)


def prompts_appendix() -> str:
    insts = {i.id: i for i in load_dataset()}
    sample = insts["T1-BND-03-U"]
    example = load_examples()[0]
    out = [
        "# Appendix B — Prompts, verbatim",
        "",
                "Every call sends one **system prompt** and one or more **user messages**. Below, each template is rendered "
        f"for the sample instance `{sample.id}` (a hash-bucket lookup where C's `%` can be negative). "
        "Every other instance is rendered the same way with its own code, parameters and preconditions.",
        "",
        "## B.1 System prompt (all approaches)", "", fence("text", prompts.SYSTEM), "",
        "## B.2 Safety specification (embedded in every user prompt)", "", fence("text", SAFETY_SPEC), "",
        "## B.3 `direct`", "", fence("text", prompts.direct(sample)), "",
        "## B.4 `direct_cot`", "", fence("text", prompts.direct_cot(sample)), "",
        "## B.5 `z3` (bare protocol)", "", fence("text", prompts.z3(sample)), "",
        "## B.6 `z3_guided` and first turn of `z3_repair`",
        "",
        "Guidance block + protocol + worked example (`dataset/examples/example.yaml`, never scored) + the problem + "
        "the protocol again (repeated at the end because small models attend most to the end of long prompts).",
        "", fence("text", prompts.z3_guided(sample, example)), "",
        "## B.7 Repair feedback messages (`z3_repair`, rounds 2–4)",
        "",
        "The conversation keeps all previous turns; one of these is appended as the next user message.",
        "",
        "### Script failed (example: a hallucinated function name)",
        "",
        fence("text", prompts.repair_error(
            "name_error",
            'File "<z3_script>", line 16, in <module>\nNameError: name \'BVModNoOverflow\' is not defined\n'
            "Hint: `BVModNoOverflow` does not exist in the z3 module. Similar existing names: BVMulNoOverflow, "
            "BVAddNoOverflow, BVSubNoOverflow")), "",
        "### Counterexample did not reproduce on the real C code", "",
        fence("text", prompts.repair_counterexample({"table": [0, 0, 0, 0], "size": 4, "h": 5},
                                                    "execution completed without any violation", "not_reproduced")),
        "",
        "### Counterexample violates the preconditions", "",
        fence("text", prompts.repair_counterexample({"table": [0], "size": 0, "h": 5},
                                                    "violates precondition: 1 <= size && size <= 64",
                                                    "precondition_violated")),
        "",
        "### Counterexample has invalid values", "",
        fence("text", prompts.repair_counterexample({"table": [], "size": 4, "h": 4294967296},
                                                    "h=4294967296 outside range of int", "invalid")),
        "",
    ]
    return "\n".join(out)


def demote(md: str) -> str:
    """Push every Markdown heading down one level, leaving code blocks untouched."""
    out, in_code = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        out.append("#" + line if (not in_code and line.startswith("#")) else line)
    return "\n".join(out)


def main():
    REPORT.mkdir(exist_ok=True)
    head = (
        "# Appendix\n\n"
        "_Generated by `scripts/build_appendices.py` from `dataset/`, `results/validation.json` and "
        "`src/invcheck/prompts.py`. Do not edit by hand; re-run the script after changing the dataset or prompts._\n\n"
        "- [Appendix A: Dataset catalogue](#appendix-a--dataset-catalogue): every instance, exactly as the models saw it, "
        "with its preconditions, witness, reference Z3 encoding and validation result.\n"
        "- [Appendix B: Prompts, verbatim](#appendix-b--prompts-verbatim): every prompt and repair message.\n"
    )
    body = head + "\n" + demote(dataset_appendix()) + "\n\n" + demote(prompts_appendix()) + "\n"
    (REPORT / "APPENDIX.md").write_text(body)
    print("APPENDIX.md", len(body.split()), "words")


if __name__ == "__main__":
    main()
