# Abstract

Large language models are increasingly used as automated code reviewers, but they cannot prove the absence of the mathematical edge cases that make C code unsafe: out-of-bounds access, division by zero, signed overflow and invalid shifts. We compare two ways of using an LLM for this task:
- **direct review**, where the model judges the code;
- **translation to a tool**, where the model writes a Z3 specification and the SMT solver decides it.

**Benchmark.** 120 C functions in 60 minimal pairs. Each UNSAFE function has a SAFE twin that differs by a one-line fix or only by a tighter caller precondition. Every label is validated by sanitizer-executed witnesses, reference Z3 encodings, CBMC and fuzzing. Every bug claim from every system is re-executed on the real code.

**Direct review is at chance.** With two small open-weight models (qwen2.5-coder 7B and llama3.2 3B), direct review scores 54–56%, flat across difficulty tiers. The models label both members of 85–92% of minimal pairs identically, and they catch only 10–25% of bugs. Chain of thought does not help.

**Translation to Z3:**
- *Where it runs, it reasons.* qwen's bare translation is the most accurate LLM approach on flat arithmetic (67.5%) and discriminates precondition twins four times as often as direct review.
- *It often does not run.* Only 60% of qwen's scripts execute, and almost none of llama's (0 of 120 bare, 3 of 120 guided), because of hallucinated APIs, Python/Z3 operator confusion and runaway repetition.
- *Guidance and repair do not fix this.* Adding C-to-Z3 guidance lowered qwen's accuracy (40% → 23%). Execution-feedback repair recovered little, because 83% of greedy repair attempts repeated the previous script.

**Combining the paradigms helps.** Using Z3 when its script runs and chain of thought otherwise gives the best LLM system: 63% accuracy, doubling recall. Re-executing counterexamples makes every reported bug genuine (precision 100%).

**But classical tools win.** CBMC and the gold encodings decide all 120 instances in under 2 s each.

**Implication.** An UNSAT answer from an LLM-written specification is only as trustworthy as the translation behind it, so bug reports from such pipelines can be checked automatically, but their "safe" verdicts cannot.
