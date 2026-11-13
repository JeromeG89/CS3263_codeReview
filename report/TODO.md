# Submission TODO

Deadlines: presentation week of 9 Nov 2026 (15 min + 5 min Q&A, possibly recorded); report Fri 13 Nov 2026 (Canvas, PDF).

## Needs team input

- [x] **Emails** for all three members (from the proposal).
- [ ] **Division of Labour** table: filled from the proposal's *planned* split. Each member checks their row matches what they actually did and edits it if not (guidelines allow the actual split to differ from the proposal). Marks are deducted if this is missing or vague.
- [ ] **Use of AI Assistance** section in `SUBMIT_REPORT.md`: list honestly which parts Claude produced (benchmark instances, harness code, analysis scripts, report text, ...) and which were the team's own.
- [x] Project proposal written (`CS3263 Project Proposal (2).pdf`). Confirm it was actually submitted on Canvas.
- [ ] Every member reads the whole report and can explain any part of it (guideline: all members must understand the entire work).

## Report

- [x] Cut to ~4,900 words body (incl. tables), 1 figure. **Verify ≤ 10 pages once rendered**; if still over, next cuts: §6.1 sentence, §3 semantic-traps paragraph, §9 bullets.
- [ ] **Render to PDF** and check page count: `brew install pandoc basictex`, then from `report/`: `pandoc SUBMIT_REPORT.md -o report.pdf -V geometry:margin=1in -V fontsize=11pt` (or paste into Google Docs / Word).
- [ ] Check figures in `report/figures/` (regenerated with 3.8 Flash) look right in the PDF.
- [ ] Decide whether long-form `REPORT.md` is shared at all. If yes, update it: it still says 3.8 Flash was not evaluated (§1.3, §5.6, §6 notice, §6.9, §7.6, §9.3, §10).
- [ ] `results/runs/gemini/STOP_NOTE.txt` is stale (says 3.8 Flash not run); delete or mark as historical.

## Presentation

- [x] Slide deck drafted: `report/SLIDES.md` (Marp, 18 slides, speaker split and Q&A notes in comments). Render with `npx @marp-team/marp-cli report/SLIDES.md --pdf` (or the Marp VS Code extension).
- [ ] Adjust the speaker split in the first slide's notes to match who presents what.
- [ ] Rehearse timing and Q&A; check whether the presentation must be recorded and uploaded.

## Known caveats to be ready to explain in Q&A

- `thinkingBudget: 0` does not fully disable 3.8 Flash's hidden reasoning; 3.5 Flash-Lite had none. 3.8's "direct" is not purely direct.
- 3.8 Flash scores 100% on direct, CoT and Z3 + repair: the benchmark is saturated for it.
- llama3.2:3b `z3_repair` was skipped (only 3/120 guided scripts executed).
- Single greedy sample per (model, approach, instance).
