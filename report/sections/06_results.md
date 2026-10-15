# 6. Results

All numbers are over the 120 benchmark instances (60 UNSAFE, 60 SAFE) unless stated otherwise. Brackets give 95% Wilson intervals. Every LLM record was re-scored with the final parser and validator (`scripts/rescore.py`); for qwen this changed no verdict and no witness status. The full generated tables are in `results/analysis/tables.md`.

**Coverage of the runs.**
- `qwen2.5-coder:7b`: all five approaches on all 120 instances.
- `llama3.2:3b`: `direct`, `direct_cot`, `z3` and `z3_guided`. Its `z3_repair` run was not performed (§6.6).

## 6.1 Reference points: the problem is solvable

_(The non-LLM reference points are the right-hand panel of the accuracy figure in §6.2.)_

| System | Accuracy | Recall | Specificity | Mean time per instance |
|---|---|---|---|---|
| Gold Z3 (reference encodings) | 100% [96.9, 100] | 100% | 100% | 0.5 s |
| CBMC | 100% [96.9, 100] | 100% | 100% | 1.7 s |
| Dictionary fuzzing (1,000 inputs) | 98.3% [94.1, 99.5] | 96.7% | 100% | 2.2 s |
| Random fuzzing (1,000 inputs) | 85.0% [77.5, 90.3] | 70.0% | 100% | 3.6 s |

**The translation approach is sound in principle.** A faithful translation to Z3 decides every instance, in half a second on average, and every UNSAFE counterexample it produces reproduces under the sanitizers. Any shortfall of the LLM→Z3 approach is therefore a *translation* failure, not a solver failure (the excluded stress pair, §4.6, is the one exception).

**Fuzzing misses bugs that need a specific large input.**
- Dictionary fuzzing misses only the two accumulation bugs (T3-OVF-02-U, T4-OVF-02-U). Their failing input is a whole array of near-maximal values.
- Random fuzzing misses 18 bugs, mostly in T1–T2 overflow and shift instances.

## 6.2 RQ1: overall accuracy of the two paradigms

[FIG: accuracy — fig1_accuracy.png] [FIG: recall vs specificity — fig2_tpr_tnr.png]

| Model | Approach | Accuracy | Recall (UNSAFE) | Specificity (SAFE) | No answer | Pair acc. | Same verdict on both twins |
|---|---|---|---|---|---|---|---|
| qwen 7B | Direct | 55.8% [46.9, 64.4] | 25.0% | 86.7% | 0 | 13.3% | 85.0% |
| qwen 7B | Direct + CoT | 56.7% [47.7, 65.2] | 20.0% | 93.3% | 0 | 16.7% | 80.0% |
| qwen 7B | LLM→Z3 | 40.0% [31.7, 48.9] | 45.0% | 35.0% | 48 | 21.7% | 56.7% |
| qwen 7B | LLM→Z3 guided | 23.3% [16.7, 31.7] | 28.3% | 18.3% | 72 | 10.0% | 61.7% |
| qwen 7B | LLM→Z3 guided + repair | 27.5% [20.3, 36.1] | 33.3% | 21.7% | 61 | 13.3% | 58.3% |
| llama 3B | Direct | 54.2% [45.3, 62.8] | 10.0% | 98.3% | 0 | 8.3% | 91.7% |
| llama 3B | Direct + CoT | 46.7% [38.0, 55.6] | 33.3% | 60.0% | 0 | 18.3% | 56.7% |
| llama 3B | LLM→Z3 | 0.0% [0.0, 3.1] | 0% | 0% | 120 | 0% | – |
| llama 3B | LLM→Z3 guided | _run in progress_ | | | | | |

"No answer" counts UNKNOWN verdicts (the script failed, or no verdict could be parsed). UNKNOWN is scored as wrong but is neither a false alarm nor a missed bug.

**Direct review is at chance, and biased towards "SAFE".**
- Neither model's direct verdicts are distinguishable from a coin flip; every interval contains 50%.
- The errors are very lopsided. qwen catches 25% of the bugs and llama 10%, while both pass 87–98% of the safe functions.
- **The models barely look at the difference between the twins.** qwen gives both members of a pair the same verdict in 85% of pairs (llama: 92%). In 44 of 60 pairs qwen calls *both* versions SAFE (llama: 42).
- Pair accuracy (both twins right) is 13% for qwen and 8% for llama, below the 25% expected from random guessing.

For a code-review assistant this is the most dangerous profile: confident, almost uniform "looks safe".

**Chain of thought does not help.**
- qwen: 55.8% → 56.7%. The models disagree on 29 instances, split 14/15 (McNemar p = 1.0).
- llama: CoT moves it towards UNSAFE (recall 10% → 33%, specificity 98% → 60%) with no net gain (46.7%, p = 0.23).
- The CoT transcripts show *confident wrong reasoning*. For `scale_down` (`return x / d;` with precondition `d != 0`), qwen raises exactly the right case, then dismisses it: *"division by −1 can lead to overflow if x is INT_MIN. Specifically, INT_MIN / −1 results in INT_MAX, which is within the range of a 32-bit signed integer"*. It answers SAFE. The true result, 2³¹, is not representable.

**Translation to Z3 is worse overall but better when it runs.** qwen's bare LLM→Z3 scores 40.0%, significantly below direct review (uncorrected p = 0.020; see §6.7 for the corrected family). But 48 of its 120 scripts never produced a verdict. On the **72 instances where the script ran**:

| | Accuracy on the 72 executed instances |
|---|---|
| Z3 | **66.7%** |
| Direct, same instances | 58.3% |
| Direct + CoT, same instances | 55.6% |

These subset differences are not significant (p = 0.41 and p = 0.27). The Z3 approach is also the only LLM approach whose errors are not dominated by "SAFE": it has the highest recall of any LLM system (45%).

## 6.3 RQ1: control-flow complexity and bug class

[FIG: accuracy by tier — fig3_accuracy_by_tier.png] [FIG: category heat map — fig4_category_heatmap.png]

| qwen 7B | T1 flat | T2 branches | T3 loops | T4 calls + nested |
|---|---|---|---|---|
| Direct | 57.5% | 52.6% | 57.7% | 56.3% |
| Direct + CoT | 55.0% | 57.9% | 61.5% | 50.0% |
| LLM→Z3 | **67.5%** | 39.5% | 19.2% | 6.3% |
| LLM→Z3 guided | 42.5% | 23.7% | 7.7% | 0.0% |
| LLM→Z3 guided + repair | 47.5% | 31.6% | 7.7% | 0.0% |

**Direct accuracy does not depend on difficulty.** It is flat across tiers for both models (qwen 53–58%, llama 50–55%). That is what a classifier not engaging with the code would look like: if the models were reasoning, they would do better on two-line arithmetic functions than on nested loops.

**Translation depends strongly on difficulty.** On flat arithmetic (Tier 1, the proposal's fallback scope) qwen's LLM→Z3 is the best LLM system at 67.5%, ten points above direct review. It degrades steadily with control-flow complexity, and almost nothing survives loops and helper functions (19% and 6%). Writing a correct encoding for loops needs unrolling with per-iteration guards, and for helpers it needs inlining; the generated scripts rarely do either.

**Bug class matters less than tier.** Direct accuracy is 50–62% in every class. For qwen's bare Z3, overflow is the weakest class (31%): 95% of its bare scripts used unbounded `Int` sorts, in which overflow cannot occur unless an explicit range check is written.

## 6.4 RQ2: can the models write executable, faithful specifications?

[FIG: Z3 outcomes — fig5_z3_outcomes.png]

Outcome of the final script, per instance:

| Outcome | qwen LLM→Z3 | qwen guided | qwen guided + repair | llama LLM→Z3 | llama guided |
|---|---|---|---|---|---|
| Proved safe (correct UNSAT) | 21 | 11 | 13 | 0 | … |
| Bug found, counterexample confirmed | 16 | 11 | 12 | 0 | … |
| Bug found, counterexample not reproduced | 11 | 6 | 8 | 0 | … |
| False alarm (SAT on a SAFE instance) | 15 | 9 | 14 | 0 | … |
| Missed bug (UNSAT on an UNSAFE instance) | 9 | 11 | 12 | 0 | … |
| Error: runaway output (hit token limit) | 8 | 12 | 12 | 84 | … |
| Error: hallucinated API / module | 11 | 30 | 27 | 36 | … |
| Error: type / operator misuse | 17 | 16 | 11 | 0 | … |
| Error: Z3 sort / API misuse | 9 | 6 | 8 | 0 | … |
| Error: syntax | 3 | 7 | 3 | 0 | … |
| **Executable (SAT or UNSAT)** | **72 (60%)** | **48 (40%)** | **59 (49%)** | **0 (0%)** | … |

**Executability is the bottleneck.**
- qwen's scripts run 40–60% of the time. llama's never run.
- llama's scripts fail in two ways. They import a module that does not exist (`from z3.solvers import Solver`), or they fall into a repetition loop until the 3,072-token limit cuts them off mid-line.
- qwen's dominant errors:
  - Python's `|`/`&` applied to Z3 comparisons (e.g. `h < 0 | h >= size`), which Python parses as a chained comparison on `(0 | h)`;
  - hallucinated API names. The most frequent is `BVSDivNoUnderflow` (59 uses across attempts): a plausible but non-existent extrapolation from the real `BVAddNoUnderflow` / `BVMulNoUnderflow`.

**Executable is not the same as faithful.**
- **False alarms.** Of qwen's 42 SAT answers in the bare variant, 15 were on SAFE instances. Example: for the SAFE `per_slot` (divisor `slots | 1u`, never zero), qwen asserted `slots == 0` as the violation. It modelled the code it expected, not the code it was given.
- **Unconfirmed bugs.** On UNSAFE instances, 11 of 27 SAT answers had a counterexample that did *not* reproduce. The verdict was right for the wrong reason.
- **Missed bugs.** 9 UNSAT answers were on UNSAFE instances. These are "proofs of the wrong theorem", and no signal in the pipeline flags them.
- **`%` was never modelled correctly.** No generated script in any variant used `SRem`, so C's negative remainder never was. The negative-modulo instances (T1-BND-03-U, T4-SHF-01-U) were never solved correctly by any Z3 variant.

**Counterexample replay is an effective filter.** Every one of the 15 false alarms of qwen's bare LLM→Z3 failed to reproduce on the real code. Reporting only confirmed counterexamples (§6.8) makes every remaining bug report correct (precision 100%).

## 6.5 Precondition twins: the formal approach reads the preconditions

[FIG: twin type — fig7_twin_type.png]

| qwen 7B pair accuracy | Code twins (37 pairs) | Precondition twins (23 pairs) |
|---|---|---|
| Direct | 16% | 9% |
| Direct + CoT | 22% | 9% |
| LLM→Z3 | 14% | **35%** |
| LLM→Z3 guided + repair | 5% | 26% |

On precondition twins the code is identical and only the caller's guarantee differs. Direct review almost never gets both right: it answers from the code and ignores the precondition. The Z3 approach gets both right four times as often (35% vs 9%), because the protocol forces preconditions into the formula as constraints.

The clearest example is `area(w, h) = w * h`. Direct review called the 50,000-bound version SAFE, explaining that the product is "within the bounds of a 32-bit signed integer for the given precondition range". The bare Z3 script encoded `w * h > 2147483647` under the stated bounds. It returned the counterexample `w = 46139, h = 46598`, which the sanitizer confirmed, and it proved the 46,340-bound twin safe.

## 6.6 RQ3: does tool knowledge or execution feedback close the gap?

**Guidance made qwen worse.** Accuracy fell from 40.0% to 23.3% (McNemar p = 0.001, significant after Holm correction). The guidance *was* followed:

| qwen 7B | LLM→Z3 | LLM→Z3 guided |
|---|---|---|
| Uses 32-bit bit-vectors | 8% | 100% |
| Uses unbounded `Int` | 95% | 0% |
| Uses overflow helpers | 0% | 62% |
| Uses `SRem` | 0% | 0% |
| Executable | 60% | 40% |

Following it backfired in three ways:
1. **More API surface, more hallucination.** Having seen the eight real overflow helpers, the model invented the missing combinations: hallucinated-name errors rose from 11 to 30.
2. **Runaway generation.** Listing a violation per helper invites enumeration. The model kept appending near-identical `And(reach, Not(BVSDiv…(…, True, True, True)))` lines until the 3,072-token limit. Runaway outputs rose from 8 to 12.
3. **Harder sorts.** Bit-vector scripts are more exact but less forgiving. Scripts using the helpers were *less* often correct (16% vs 35%), largely because they failed to execute.

For llama, guidance did not rescue a single script either (run in progress).

**Execution feedback helped only slightly.**
- Up to three repair rounds raised qwen from 23.3% to 27.5% (+5 instances, p = 0.06, not significant) and executability from 40% to 49%.
- Almost all of the gain comes from the first round:

| Repair rounds allowed | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Executable | 40.0% | 48.3% | 48.3% | 49.2% |
| Accuracy | 23.3% | 26.7% | 26.7% | 27.5% |

[FIG: repair rounds — fig6_repair_rounds.png]

**Why so little?** With greedy decoding, **210 of the 253 repair attempts (83%) resubmitted exactly the same script as before**, despite an error message and a "did you mean" hint naming the correct function. In all 59 cases where the model called the non-existent `BVSDivNoUnderflow`, the error message listed the correct `BVSDivNoOverflow` among the "similar existing names", yet the model reproduced its earlier answer.

We did not run llama's repair variant. Its guided first attempts were all unexecutable or runaway, and each repair round costs up to a minute of generation per instance, so the expected yield did not justify about five hours of compute. The repair loop's first attempt is identical to `z3_guided` by construction, so llama's guided results bound what repair could start from.

## 6.7 Significance

Exact McNemar tests, paired by instance; Holm-corrected over all planned comparisons for both models:

[TABLE: McNemar — from results/analysis/tables.md, filled at assembly]

## 6.8 Derived policies: combining the paradigms

These are computed from existing records, with no extra model calls:

| qwen 7B policy | Accuracy | Recall | Specificity | Precision |
|---|---|---|---|---|
| Direct (for reference) | 55.8% | 25.0% | 86.7% | 65.2% |
| **Hybrid: LLM→Z3 when the script runs, else Direct + CoT** | **63.3%** | **53.3%** | 73.3% | 66.7% |
| Hybrid: Z3 + repair, else Direct + CoT | 56.7% | 40.0% | 73.3% | 60.0% |
| Direct, witness-validated | 59.2% | 18.3% | 100% | 100% |
| Direct + CoT, witness-validated | 58.3% | 16.7% | 100% | 100% |
| LLM→Z3, witness-validated | 43.3% | 26.7% | 60.0% | 100% |

**The hybrid is the best LLM-based system in the study.** It uses the tool where the model can drive it and falls back to natural-language reasoning where it cannot. It doubles recall relative to direct review (25% → 53%) at a cost of 13 points of specificity. Its accuracy gain over direct review (+7.5 points) is not significant with n = 120 (p = 0.22).

**Witness validation is a free precision upgrade.** Reporting a bug only when its witness reproduces removes every false alarm in every approach (precision 100%), at the cost of recall.

## 6.9 RQ4: model scale

- On direct review the two models are indistinguishable (qwen 55.8% vs llama 54.2%, p = 0.83). Both sit at chance.
- The difference appears in the translation approach: qwen 40.0% vs llama 0.0% (p < 10⁻⁴).
- Scale here buys the ability to drive the tool at all, not better judgement.

## 6.10 Cost

| qwen 7B | LLM calls | Output tokens | Wall-clock per instance |
|---|---|---|---|
| Direct | 1.0 | 61 | 3.3 s |
| Direct + CoT | 1.0 | 661 | 27.3 s |
| LLM→Z3 | 1.0 | 538 | 21.3 s |
| LLM→Z3 guided | 1.0 | 567 | 23.7 s |
| LLM→Z3 guided + repair | 3.1 | 2,108 | 66.7 s |
| *Gold Z3 (no LLM)* | – | – | 0.5 s |
| *CBMC (no LLM)* | – | – | 1.7 s |

On a laptop, every LLM approach costs 2–40× more time per instance than CBMC, which is both faster and exact on this benchmark.
