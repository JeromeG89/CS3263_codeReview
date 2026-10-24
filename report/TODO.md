# Submission TODO

Deadlines: presentation week of 9 Nov 2026 (15 min + 5 min Q&A, possibly recorded); report Fri 13 Nov 2026 (Canvas, PDF).

## Needs team input

- [ ] **Emails** for all three members in the header table of `SUBMIT_REPORT.md`.
- [ ] **Division of Labour** table in `SUBMIT_REPORT.md`: one or two true lines per member. Marks are deducted if this is missing or vague.
- [ ] **Use of AI Assistance** section in `SUBMIT_REPORT.md`: list honestly which parts Claude produced (benchmark instances, harness code, analysis scripts, report text, ...) and which were the team's own.
- [ ] Confirm the **project proposal** was submitted (required to receive a project grade).
- [ ] Every member reads the whole report and can explain any part of it (guideline: all members must understand the entire work).

## Report

- [ ] **Cut to 10 pages** (11pt, single column, 1-in margins, excluding title page and references). Body is ~5,600 words, likely over. Candidate cuts: Z3-outcomes figure (§6.3), semantic-traps table (§3), qwen tier table (§6.2), tighten §2 and §8.
- [ ] **Render to PDF** and check page count: `brew install pandoc basictex`, then from `report/`: `pandoc SUBMIT_REPORT.md -o report.pdf -V geometry:margin=1in -V fontsize=11pt` (or paste into Google Docs / Word).
- [ ] Check figures in `report/figures/` (regenerated with 3.8 Flash) look right in the PDF.
- [ ] Decide whether long-form `REPORT.md` is shared at all. If yes, update it: it still says 3.8 Flash was not evaluated (§1.3, §5.6, §6 notice, §6.9, §7.6, §9.3, §10).
- [ ] `results/runs/gemini/STOP_NOTE.txt` is stale (says 3.8 Flash not run); delete or mark as historical.

## Presentation

- [ ] Make slides (15 min). Suggested arc: problem and formulation (CSP/SMT, entailment by refutation) → benchmark and validation → approaches → results (small models fail, strong models tie, CBMC wins) → evidence asymmetry and responsible AI → limitations.
- [ ] Rehearse timing and Q&A; check whether the presentation must be recorded and uploaded.

## Known caveats to be ready to explain in Q&A

- `thinkingBudget: 0` does not fully disable 3.8 Flash's hidden reasoning; 3.5 Flash-Lite had none. 3.8's "direct" is not purely direct.
- 3.8 Flash scores 100% on direct, CoT and Z3 + repair: the benchmark is saturated for it.
- llama3.2:3b `z3_repair` was skipped (only 3/120 guided scripts executed).
- Single greedy sample per (model, approach, instance).
