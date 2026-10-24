---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section { font-size: 26px; }
  table { font-size: 20px; }
  h1 { font-size: 40px; }
---

<!-- _paginate: false -->

# Direct LLM Review vs. LLM-to-Z3 Translation for Verifying C Safety Invariants

**CS3263 Project, AI Assistant for Software Engineering**

Jerome Goh (leader) · Mothiki Eswara Anirudh · Goh Joon Xiang

<!--
Speaker split (15 min). Adjust to match who actually did what:
- Jerome: slides 1-4 (motivation, problem, formulation), 15-16 (CBMC, conclusion)   ~5 min
- Anirudh: slides 5-8 (benchmark, validation, direct-review results)                 ~5 min
- Joon Xiang: slides 9-14 (translation results, strong models, responsible AI)       ~5 min
-->

---

## The problem: code review misses mathematical edge cases

```c
int mid(int lo, int hi) { return (lo + hi) / 2; }   // overflows if lo + hi > INT_MAX
```

- Out-of-bounds access, division by zero, signed overflow, invalid shifts
- In C these are **undefined behaviour**, a common source of vulnerabilities
- LLM reviewers read code fluently but give a **verdict, not a proof**
- They can confidently call unsafe code safe

**Question:** should an LLM judge the code itself, or translate it for a solver that can prove the answer?

<!-- Motivation: AI assistant for software engineering. These bugs only appear for specific inputs, which is exactly where a human reviewer convinces themselves the code is fine. -->

---

## Two ways to use an LLM

| | Direct review | Translation to a tool |
|---|---|---|
| LLM does | reads code + preconditions, answers SAFE/UNSAFE + witness | writes a Python **Z3** script encoding the question |
| Who decides | the LLM | the SMT solver: SAT = bug, UNSAT = proof |
| Variants | direct, + chain of thought | bare, + guidance, + repair loop (3 rounds) |

**4 research questions:** accuracy by complexity (RQ1) · can LLMs write executable, faithful Z3? (RQ2) · do guidance and feedback help? (RQ3) · how does model strength matter? (RQ4)

---

## Formulation: safety as constraint satisfaction

$$\Phi = P(\vec{x}) \;\land\; \bigvee_{o} \big(\pi_o(\vec{x}) \land \lnot\varphi_o(\vec{x})\big)$$

- **Variables:** inputs + SSA intermediates · **Domains:** 32/64-bit bit-vectors, arrays
- **Constraints:** precondition $P$, path conditions $\pi_o$, a violated check $\lnot\varphi_o$
- **Entailment by refutation** (AIMA): $KB \models \alpha \iff KB \land \lnot\alpha$ is UNSAT
- **SAT** = concrete counterexample we can **execute** and check
- **UNSAT** = proof **only if the encoding over-approximates the code**

The difference between SAT and UNSAT here drives the whole evaluation and the Responsible AI section.

<!-- Loops: unroll up to the precondition-implied bound, which is BMC with a bound that is sufficient by construction. -->

---

## Benchmark: 120 C functions in 60 minimal pairs

- Each **UNSAFE** function has a **SAFE twin**
  - *Code twins* (37): a one-line fix, `(lo+hi)/2` vs `lo+(hi-lo)/2`
  - *Precondition twins* (23): **identical code**, only the caller guarantee differs (sides ≤ 50000 vs ≤ 46340)
- 4 tiers: straight-line → branches → loops → helpers/nested loops
- 4 bug classes: bounds, div-by-zero, overflow, shift
- Semantic traps: C `%` on negatives, `INT_MIN / -1`, unsigned wrap, dead-code decoys

A model that just recognises a suspicious pattern **must get one precondition twin wrong**.

---

## Ground truth: four independent oracles

| Oracle | Checks |
|---|---|
| Sanitizer-executed witness (ASan + UBSan) | the bug really happens |
| Reference Z3 encoding + replay | solver agrees; counterexample reproduces |
| CBMC bounded model checker (unwinding assertions) | full proof for SAFE |
| 3,000 precondition-respecting fuzz inputs | nothing triggers on SAFE |

**120/120 pass.** And every bug claim from every system is **re-executed on the real code**.

LLM scripts run sandboxed: no network, API keys hidden, resource limits.

---

## Models and baselines

- **Small, local:** qwen2.5-coder 7B, llama3.2 3B (Ollama)
- **Strong, API:** Gemini 3.5 Flash-Lite, Gemini 3.8 Flash
- Temperature 0, one sample per (model, approach, instance), 5 approaches × 120 instances each
- **Non-LLM baselines:** gold Z3, CBMC, dictionary fuzzing, random fuzzing

Caveat: `thinkingBudget: 0` does **not** fully disable 3.8 Flash's hidden reasoning.

---

## Small models: direct review is at chance

![w:820](figures/fig1_accuracy.png)

- qwen 55.8%, llama 54.2%: every confidence interval contains 50%
- They catch only **10–25%** of bugs and give both twins the **same verdict in 85–92%** of pairs
- Chain of thought does not help: *"INT_MIN / −1 results in INT_MAX, which is within range"* (false)

---

## Small models: translation reasons, but rarely runs

| qwen 7B | T1 flat | T2 branches | T3 loops | T4 calls |
|---|---|---|---|---|
| Direct | 57.5% | 52.6% | 57.7% | 56.3% |
| **LLM→Z3** | **67.5%** | 39.5% | 19.2% | 6.3% |

- Only **60%** of qwen's scripts execute; llama's: **0%** (`from z3.solvers import Solver` does not exist)
- Errors: hallucinated APIs (`BVSDivNoUnderflow`), Python `|` on Z3 Booleans, runaway repetition
- But on **precondition twins**, Z3 gets both right **4× as often** (35% vs 9%): the protocol forces the precondition into the formula

---

## More tool knowledge made the small model *worse*

- Guidance (pitfall list + worked example): qwen **40% → 23%** (significant)
  - it *was* followed: bit-vectors 8% → 100%
  - but more API names led to more invented names (11 → 30)
- Repair loop with error messages and "did you mean" hints: 23% → 27.5% only
  - **83% of repair attempts resubmitted the identical script**

**Bottleneck: not missing knowledge, but the ability to use it.**

---

## Strong models reverse the picture

| Approach | 3.5 Flash-Lite | 3.8 Flash |
|---|---|---|
| Direct | 76.7% | **100%** |
| Direct + CoT | **98.3%** | **100%** |
| LLM→Z3 (bare) | 78.3% | 80.8% |
| Z3 guided | 82.5% | 95.8% |
| Z3 guided + repair | **97.5%** | **100%** |

- Guidance and repair now **help**: 78–81% → 97.5–100%
- No repair attempt repeated itself; "did you mean" fixed 9 of 10 invented names
- Best direct approach and Z3 + repair are **statistically tied**; the benchmark is saturated by 3.8 Flash

---

## What the solver adds: evidence, not accuracy

- A **bug report** can be checked automatically: replay the counterexample
  - witness-validated reporting gives **100% precision for every approach and model**
- A **"safe" verdict** cannot be checked that way
  - direct "SAFE" = opinion with no artefact
  - Z3 UNSAT = proof of the *encoded* formula (qwen made 9 "proofs" for buggy code)
- For strong models the Z3 route's value is an **auditable specification + proof**, not a higher score

---

## Is an LLM the right tool at all?

- **CBMC: 100% in 1.7 s per function**, no LLM, no translation
- Gold Z3: 100% in 0.5 s · dictionary fuzzing finds 58/60 bugs
- Our instances (small, explicit preconditions) are where model checkers excel
- Realistic LLM role: **produce what a sound verifier needs** (harnesses, preconditions, specs for messy code), and let the tool decide

---

## Responsible AI

- **Asymmetric harm:** a false alarm costs time; a false "SAFE" ships the bug *with a record saying it was checked*
- **Formal-looking but wrong:** "Z3: unsat" may invite *more* over-reliance than prose
- **Executing model code:** sandboxing; prompt injection via comments in reviewed code
- **Access and privacy:** the models that work send code to a third party and are rate-limited

**Recommendations:** act on confirmed counterexamples · show the spec next to every UNSAT · never present LLM "SAFE" as verification · use sound tools for critical code · log everything

---

## Limitations and assumptions

- Synthetic, short functions with **explicit** preconditions; real code has pointers and implicit contracts
- 50% bug rate, far above real review (precision would drop)
- One greedy sample; prompts not tuned or paraphrased
- Two strong models, one vendor; hidden reasoning not controlled
- Benchmark drafted with AI assistance (labels validated independently); saturated by 3.8 Flash

---

## Conclusion

1. **Small models:** direct review at chance; translation reasons better but rarely runs; more tool knowledge hurts
2. **Strong models:** both routes reach 97.5–100%, and guidance and repair now help
3. **Across models:** replayed counterexamples make bug reports trustworthy; "safe" verdicts stay unverifiable
4. **Classical tools still win** on this kind of code

**Future work:** harder, realistic code · more vendors with controlled thinking · checking UNSAT faithfulness · constrained decoding

---

<!-- _paginate: false -->

# Thank you. Questions?

<!--
Likely Q&A:
- Why not just use CBMC? It wins here; LLMs matter where its inputs (preconditions, harnesses) are missing.
- Is 3.8 Flash's 100% memorisation? Precondition twins have identical code, so pattern matching alone gets one wrong; also hidden reasoning caveat.
- Why did guidance hurt qwen? More API surface = more extrapolated names, plus enumeration loops.
- Why temperature 0? Reproducibility; it also caused the 83% repeated repairs.
- How do you know labels are right? Four independent oracles, none an LLM.
-->
