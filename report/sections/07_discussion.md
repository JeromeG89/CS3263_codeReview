# 7. Discussion

## 7.1 What the comparison shows

**The two paradigms fail in different places.**
- *Direct review* always answers but does not reason. Its accuracy is the same on two-line arithmetic as on nested loops, it gives both members of a minimal pair the same verdict 85–92% of the time, and it leans heavily towards "SAFE". The chain-of-thought transcripts show why prose reasoning does not fix this: the model raises the right case (`INT_MIN / -1`) and then resolves it with a false fact.
- *Translation to Z3* does reason, through the solver. Where the model can write an executable script, the answers track the code and the preconditions. This is best seen on precondition twins, where the formal approach discriminates four times as often. On flat arithmetic it is the most accurate LLM approach (67.5% vs 57.5%). But writing the script is itself a demanding programming task, and the models we evaluated often cannot complete it: 40–60% executable for qwen, 0% for llama.

This is the advantage-versus-limitation trade-off the proposal set out to measure:
- **Accuracy of direct detection.** The LLM's own judgement is cheap, always available, and for small models no better than chance.
- **Reliability of writing a correct Z3 specification.** The tool's judgement is exact, but only reachable through a translation that small models often get wrong.

**The fallback scope of the proposal is the right scope.** The proposal planned to start from "highly simplified, flat arithmetic functions" and scale up if translation succeeded. Our data reproduces that boundary directly. Translation is the strongest LLM approach on Tier 1 and degrades sharply with branches (39.5%), loops (19.2%) and helper functions (6.3%). For small local models, flat arithmetic is a viable finishing point. The loop and call tiers are mostly useful as evidence of *why* translation fails: unrolling with per-iteration guards and inlining are exactly the steps the generated scripts omit.

## 7.2 Why the tool approach fails: "knowledge required by the tool is not easily obtained"

The failure taxonomy matches the proposal's hypothesis about knowledge, in three layers.

1. **API knowledge.**
   - The models invent plausible names: `BVSDivNoUnderflow`, `BVShLNoOverflow`, `ArrayLength`, a `z3.solvers` module.
   - These are *pattern completions*, not random noise. Z3 has `BVAddNoUnderflow` and `BVMulNoUnderflow`, so an `SDiv` variant "should" exist.
   - Giving the model the exact list of real helpers did not stop the pattern completion. It gave the pattern more material.
2. **Host-language knowledge.**
   - Using Python's `|` on Z3 Booleans is a semantic trap of the *embedding*, not of Z3 or C.
   - It was qwen's most frequent error in the bare variant.
3. **Semantic knowledge.**
   - Even executable scripts encode C imprecisely. Unbounded `Int`s make overflow impossible unless explicitly checked. `%` is never translated to `SRem`. Several scripts encode the bug they expect instead of the code they were given (the `slots | 1u` false alarm).
   - These errors are the dangerous ones, because they produce confident, well-formed answers.

**Why guidance backfired.** More tool knowledge in the prompt made qwen worse. It switched entirely to bit-vectors and used the overflow helpers, exactly as instructed, but executability dropped from 60% to 40%. Two mechanisms are visible in the transcripts:
- more named API surface produced *more* extrapolated (hallucinated) names;
- the guidance's "one violation per risky operation" style invited **enumeration loops** that ran to the output limit.

This matters for the design of neurosymbolic pipelines. With a small model, the bottleneck is not missing knowledge that a cheat-sheet can supply but the model's ability to *use* it without degenerating. Stronger models, or constrained decoding (grammar-restricted Z3 output, a whitelist of API symbols), are the natural next step.

**Why repair barely helped.** The repair loop gives exactly the feedback a deployment would have: the interpreter error with a did-you-mean hint, and a counterexample replay. With greedy decoding, 83% of repair attempts were byte-identical to the previous attempt. A small model at temperature 0, conditioned on its own previous answer, tends to reproduce it. Repair loops presuppose a model that can change its mind. Sampling with temperature, or regenerating from scratch with the error included in a fresh prompt, are cheap variants worth testing.

## 7.3 The asymmetry between bug reports and "safe" verdicts

The study's most transferable result concerns *evidence*, not accuracy.

- **A bug report can be checked mechanically.** We re-ran every counterexample on the real code. Every false alarm of the bare Z3 approach failed replay, and so did 11 of its 27 correct-but-unconfirmed bug reports. Reporting only confirmed counterexamples gave 100% precision for every approach. This check needs no ground truth and costs milliseconds; it should be standard in any LLM code-review pipeline.
- **A "safe" verdict cannot be checked this way.**
  - For direct review, "SAFE" is an unsupported opinion, and it is the models' default.
  - For the Z3 approach, UNSAT is a proof of the *encoded* formula. qwen produced 9 such "proofs" for functions that do have bugs.
  - Nothing in a label-free pipeline can flag them, and our repair loop deliberately never questions an UNSAT answer.
  - Because "Z3: unsat" *looks* like verification, it risks more over-reliance than an LLM's prose. Section 8 discusses the consequences.

## 7.4 Combining the paradigms

The best LLM-based policy combines both paradigms: use the solver's answer when the generated script runs, and fall back to chain-of-thought otherwise.
- It reaches 63.3% accuracy and, above all, doubles recall relative to direct review (53% vs 25%).
- The accuracy gain is not significant at n = 120 (p = 0.22), so we present it as a promising direction rather than an established result.
- It is cheap: it needs one CoT call and one translation call per function, both of which we already had.
- With witness validation layered on top, its bug reports would be both more numerous and fully trustworthy, while its "safe" verdicts would still carry no guarantee.

## 7.5 Against the non-LLM baselines

CBMC, a 20-year-old bounded model checker, decides every instance correctly in 1.7 s with no translation at all. The gold Z3 encodings do the same in 0.5 s. Dictionary fuzzing finds 58 of 60 bugs in about 2 s.
- On this benchmark, every LLM approach is slower and less accurate than a classical tool.
- Our instances are small, self-contained C functions with explicit preconditions, which is exactly where CBMC shines.
- The realistic role for an LLM here is not to replace the verifier but to *produce what the verifier needs* (harnesses, preconditions, specifications) and let a sound tool decide. Our counterexample-replay results support that division of labour.

## 7.6 Expected effect of stronger models

Our evaluated models are small (3B and 7B parameters), by design and by constraint (local inference on a laptop). The results should not be read as a ceiling for the translation approach:
- the gold-encoding baseline shows that faithful translation solves every instance;
- the qwen–llama gap shows that scale strongly affects the ability to drive the tool.

The Gemini configuration is ready (`configs/gemini.yaml`). The decisive questions for that follow-up are:
- whether executability rises from 40–60% to near 100% (in which case the selective-accuracy advantage of Z3 would show up in overall accuracy);
- whether stronger models still produce unfaithful but executable encodings (missed bugs proven "safe").
