# 5. Approaches and Evaluation Protocol

All approaches receive the same problem rendering (`prompts._problem`): the safety specification of Section 3.1 verbatim, a parameter summary (e.g. "`a`: array of int (length `n`), `n`: int"), and the C code preceded by a comment that lists the preconditions. Every call uses the same system prompt:

> *You are an expert C code reviewer and formal-methods engineer. You check whether C functions can violate memory- and arithmetic-safety invariants, given the preconditions their callers guarantee.*

All prompt templates live in `src/invcheck/prompts.py`.

## 5.1 Direct review

**Direct.** The model is asked to "Decide whether the following function is SAFE or UNSAFE" and to "Answer immediately with ONLY a JSON object (no reasoning, no markdown)". The answer must follow the schema `{"verdict": "SAFE"|"UNSAFE", "violation": "bounds"|"div_zero"|"overflow"|"shift"|"none", "witness": {...} or null, "explanation": "<one sentence>"}`. For UNSAFE, the witness must give concrete values for *every* parameter that satisfy all preconditions, with arrays as JSON lists of exactly the required length.

**Direct + CoT.** Same task and schema, but the model is first told to "Think step by step. For every array access, division/modulo, signed arithmetic operation and shift, derive the range of values its operands can take under the preconditions and the path conditions that reach it, and check the corresponding invariant. Then search for a concrete counterexample and double-check it against the preconditions". It finishes with the JSON in a code block. The instruction asks the model to do in natural language what the Z3 approach delegates to the solver: interval reasoning over operands, path conditions, and a counterexample search.

**Parsing.** The last JSON object in the reply that contains a `verdict` key is taken. The parser tolerates comments, trailing commas, Python literals, single quotes and bare `INT_MAX`-style constants. If no such object exists, the parser falls back to the last standalone `SAFE`/`UNSAFE` token, and otherwise the verdict is UNKNOWN. The verdict is scored as given. Raw replies are stored, and all records were re-scored with the final parser and validator after the runs (`scripts/rescore.py`), so every record is judged by the same code. The witness is validated separately (Section 5.3) and does not alter the verdict, except in the derived "witness-validated" policies (Section 5.5).

## 5.2 LLM-to-Z3 translation

**Protocol.** The model must write a Python script with `from z3 import *` that follows a fixed protocol:

> 1. Declare one Z3 constant per function parameter, using exactly the parameter's name as the Z3 name … Declare array parameters as Z3 arrays named after the parameter.
> 2. Create the solver with `s = Solver()`.
> 3. Add every precondition to `s`.
> 4. Add ONE constraint to `s` stating that at least one invariant is violated: a disjunction over every potentially-unsafe operation, each conjoined with the path condition under which it executes.
>
> Then `s` is satisfiable exactly when the function is UNSAFE, and any model is a counterexample. Do NOT call `s.check()`, do NOT use `push()`/`pop()`, and do not print anything; we run the solver ourselves.

The harness runs the script, calls `s.check()` itself with a 30 s solver time-out, maps sat/unsat/unknown to UNSAFE/SAFE/UNKNOWN, and on SAT reads parameter values back from the model *by name*. Missing scalars are set to 0, since an unconstrained value is arbitrary. Array contents are read for indices $0..L_a-1$ with model completion. The harness accepts a solver bound to `s`, to `solver`, or to the last `Solver` object defined.

We evaluate three variants, which form a cumulative ablation:

| Variant | Prompt content | Max LLM calls | Feedback |
|---|---|---|---|
| **LLM→Z3** (`z3`) | problem + protocol | 1 | none |
| **LLM→Z3 guided** (`z3_guided`) | modelling guidance + protocol + worked example + problem + protocol (repeated) | 1 | none |
| **LLM→Z3 guided + repair** (`z3_repair`) | as `z3_guided` | 4 (1 + 3 repair rounds) | execution errors and counterexample replay |

**Tool knowledge (guidance).** The guidance block (`Z3_GUIDANCE`) lists C-to-Z3 pitfalls:

- Model `int` as `BitVec(…, 32)` and `long long` as `BitVec(…, 64)`. `<`, `/`, `>>` on bit-vectors are signed; use `ULT`/`UDiv`/`URem`/`LShR` for `unsigned`.
- C's `%` is `SRem`, not Z3's `%`.
- The exact names of the eight overflow predicates (`BVAddNoOverflow`, `BVAddNoUnderflow`, `BVSubNoOverflow`, `BVSubNoUnderflow`, `BVMulNoOverflow`, `BVMulNoUnderflow`, `BVSDivNoOverflow`, `BVSNegNoOverflow`), with a warning that "Only use functions that exist in z3". A 64-bit `SignExt` range check is an alternative.
- If `Int` is used, division rounds differently from C and every intermediate value must be range-checked.
- Use `Or`/`And`/`Not`/`Implies`, never Python `|`, `&`, `or`, `and` on comparisons.
- `SignExt(32, x)` for mixed-width arithmetic.
- SSA naming and `If(cond, a, b)` merges after branches.
- Unroll loops up to the precondition-implied bound, guarding iteration $t$ by its execution condition.
- Inline function calls.
- Element preconditions are needed only for elements that are read.
- Conjoin every check with its path condition, and remember that "an earlier violation does not need to 'stop' execution".

**Worked example.** One example (`dataset/examples/example.yaml`, `EX-01`) is shown in full with a correct reference script. It is not part of the evaluation set. `scaled_get` returns early if `i > n` and otherwise computes `a[i] * k + 1`. Its bug is the off-by-one `i == n`. The example script demonstrates array declaration, guarded element preconditions, a path condition (`reach = Not(i > n)`), and the overflow predicates.

**Repair loop with execution feedback.** In `z3_repair` the conversation continues for up to three rounds after the first attempt. The loop stops at the first attempt that yields UNSAT, or SAT with a confirmed counterexample. Feedback is given in three cases:

- *No code block*, or *script error*: syntax error, `NameError`, `TypeError`, `Z3Exception`, other runtime error, no solver found, time-out, or solver `unknown`. The model receives "Running your script failed (<error type>):" followed by up to 1,500 characters of the traceback, restricted to frames in the generated script. It is then asked for a complete corrected script that still follows the protocol. For a `NameError` on an identifier, the child process appends a *did-you-mean* hint computed by fuzzy matching against the names that actually exist in the `z3` module: "Hint: `X` does not exist in the z3 module. Similar existing names: …". This targets the hallucinated-API failure mode directly.
- *Counterexample does not reproduce.* If the solver returns SAT but the model's input is invalid (out-of-range values), violates the preconditions, or runs on the real C code without any sanitizer report, the model is told "Z3 reported a counterexample: {…} However, …" with the specific reason. The three reasons are: "your preconditions are encoded incorrectly or incompletely"; "check bit-widths and value ranges"; and "we executed the real C function on these inputs and NO invariant was violated, so this counterexample is spurious and your encoding of the C semantics is inaccurate somewhere". The model is asked to re-examine operator semantics, path conditions, preconditions and bit-widths. It is reminded that "If after re-examination you believe the function cannot violate any invariant, your script should be unsatisfiable".
- *UNSAT* is never questioned, because without ground truth there is no signal that an UNSAT answer is wrong.

The feedback is therefore **label-free**: it uses only the interpreter, the solver and the sanitizer-instrumented binary, all available to a real deployment. This asymmetry is intended. Feedback can correct false alarms and crashes but not missed bugs, which is relevant to RQ3 and Section 8.

The verdict of `z3_repair` is the verdict of its final attempt. Because responses are cached on the exact (model, parameters, system prompt, message history) key and decoding is greedy, the first attempt of `z3_repair` is by construction identical to `z3_guided`. The accuracy after $k$ rounds ($k = 0..3$) is read off the attempt history [FIG: repair rounds — `fig6_repair_rounds.png`].

**Script extraction.** The longest fenced code block mentioning `z3` or `Solver` is used. Failing that, the text from the first `import` onwards is used if the reply contains unfenced code.

## 5.3 Counterexample validation by concrete execution

Every UNSAFE claim with a witness, from direct review, a Z3 model or fuzzing, is replayed on the real code (`z3run.validate_witness`):

1. **Normalisation.** Values are converted to C integers. C suffixes, named constants such as `INT_MIN` and simple constant expressions such as `"INT_MAX - 1"` are accepted. Missing or unparseable scalars, out-of-range scalars and unexecutable array lengths make the witness *invalid*. (Z3 models never miss a scalar: the harness fills unconstrained parameters with 0.) Arrays of the wrong length are padded with zeros or truncated.
2. **Precondition check.** The scalar clauses and element preconditions are evaluated over mathematical integers. A failure makes the witness *precondition_violated*.
3. **Element repair.** Solvers often leave array elements that the function never reads unconstrained, so these may violate the element precondition even though they cannot influence execution. Before declaring a precondition violation, each offending element is replaced by the first value from $[0, 1, -1, 2, \text{constants harvested from the code and preconditions}]$ that satisfies the element condition. If the replaced element *is* read, the witness may simply fail to reproduce, so the rule cannot manufacture a confirmation of an encoding that depends on an illegal element value. The rule applies identically to all systems and is recorded in the witness detail.
4. **Execution.** The witness runs in the ASan+UBSan harness of Section 4.5 with a 20 s time-out. It is *confirmed* if a sanitizer report occurs, of any class (Section 3.2), and *not_reproduced* otherwise.

## 5.4 Non-LLM reference points

These run once per instance (`scripts/run_baselines.py`) and use the same record format:

- **Gold Z3 (Claude).** The reference encodings, run through the identical sandbox and validation pipeline. This is an upper bound for a perfect LLM translator under our protocol.
- **CBMC.** The configuration of Section 4.5, with a 300 s time-out. Insufficient unwinding or a time-out yields UNKNOWN.
- **Dictionary fuzzing.** 1,000 precondition-respecting inputs, generated by rejection sampling with seed 0 (a different seed from validation). Values are drawn from a mixture: small integers in $[-16, 16]$ (30%); constants harvested from the code and preconditions, with their negations and $\pm 2$ neighbours (25%); uniform values up to the largest harvested magnitude, capped at $10^7$ (15%); boundary values of the C type (15%); and uniform values over the full type range (15%). Fuzzed arrays are capped at 64 elements.
- **Random fuzzing.** The same budget and rejection sampling, drawing each value as a small integer (50%) or uniformly from the full type range (50%).

A fuzzer reports UNSAFE only with a confirmed witness. Otherwise it reports SAFE, which means absence of evidence: fuzzers never output UNKNOWN, so their specificity is trivially perfect on this benchmark.

## 5.5 Derived policies

Three post-hoc systems are computed from existing records without additional model calls (`analysis.derived_policies`):

- **Hybrid (Z3, else CoT):** use the `z3_repair` verdict when the script produced SAT or UNSAT, and the Direct + CoT verdict when it ended UNKNOWN.
- **CoT, witness-validated:** report UNSAFE only if the CoT witness is confirmed by execution; otherwise SAFE.
- **Z3 + repair, witness-validated:** the same rule applied to `z3_repair`.

The validated policies model a deployment in which a reviewer acts only on reproducible bug reports. They trade recall for precision by construction.

## 5.6 Models and decoding

| Model | Provider | Status | Decoding |
|---|---|---|---|
| `qwen2.5-coder:7b` | Ollama (local) | evaluated | temperature 0, seed 0, `num_ctx` 8192, max 3,072 output tokens |
| `llama3.2:3b` | Ollama (local) | evaluated | same |
| Gemini 2.5 Flash, Gemini 2.5 Flash-Lite | Google API | planned | temperature 0, thinking disabled (`thinkingBudget: 0`), client-side rate limiting |

We draw one sample per (model, approach, instance), giving 120 instances × 5 approaches per model. All responses are stored in a persistent SQLite cache keyed on the full request, which makes runs resumable and exactly reproducible from the cache. Failed requests are retried with exponential back-off and are never cached.

## 5.7 Metrics

Let TP be UNSAFE instances judged UNSAFE, TN SAFE instances judged SAFE, and FP/FN the corresponding errors. UNKNOWN counts as incorrect in accuracy but is neither FP nor FN.

| Metric | Definition | Answers |
|---|---|---|
| Accuracy (95% Wilson CI) | correct / 120 | overall quality (chance = 50%) |
| Recall (UNSAFE) | TP / #UNSAFE | missed bugs |
| Specificity (SAFE) | TN / #SAFE | false alarms |
| Precision, F1 | TP / (TP + FP); harmonic mean with recall | reliability of bug reports |
| Coverage | 1 − UNKNOWN / n | how often the system answers at all |
| Selective accuracy | accuracy on decided instances | quality when it answers |
| Pair accuracy | fraction of pairs with both twins correct | discrimination; chance-level classifiers ≈ 25%, constant ones 0% |
| Same-verdict rate | fraction of pairs given identical verdicts | failure to discriminate twins |
| Witness confirmation rate | confirmed witnesses / UNSAFE claims | how often a bug claim is backed by a reproducible input |
| Cost | mean LLM calls, output tokens, wall-clock seconds per instance | practicality |

For the Z3 approaches we additionally classify each final attempt into an **outcome taxonomy** [FIG: Z3 outcomes — `fig5_z3_outcomes.png`]:

- proved safe;
- bug found, counterexample confirmed;
- bug found, counterexample not reproduced;
- false alarm (spurious counterexample);
- missed bug (UNSAT on an UNSAFE instance);
- errors: hallucinated API (`NameError`), type/operator misuse (`TypeError`), Z3 sort/API misuse (`Z3Exception`), syntax, protocol violation (no solver), no code, time-out, solver unknown, other runtime.

We also record static features of the generated scripts: bit-vector versus `Int` sorts, use of `SRem` and of the overflow predicates, arrays, `push`/`pop`, explicit `check()` calls, and Python Boolean operators on comparisons. We relate them to correctness [TABLE: code features].

Results are broken down by tier [FIG: accuracy by tier — `fig3_accuracy_by_tier.png`], bug class [FIG: category heatmap — `fig4_category_heatmap.png`] and twin type [FIG: twin type — `fig7_twin_type.png`]. The overall picture appears in [FIG: accuracy — `fig1_accuracy.png`] and [FIG: recall vs specificity — `fig2_tpr_tnr.png`].

## 5.8 Statistical testing

All systems are evaluated on the same instances, so comparisons are paired. For each model we apply the **exact McNemar test**, a two-sided binomial test on the discordant pairs, to six planned comparisons:

- Direct vs Direct + CoT
- Direct vs LLM→Z3
- Direct + CoT vs LLM→Z3 guided + repair
- LLM→Z3 vs guided
- guided vs guided + repair
- Direct vs guided + repair

The **Holm–Bonferroni** correction is applied across the whole family (all comparisons × all models) [TABLE: McNemar]. Cross-model comparisons for a fixed approach use the same test and are reported without correction as exploratory. With $n = 120$, Wilson intervals are roughly ±9 percentage points at 50% accuracy, so we interpret only large or consistent differences.

## 5.9 Sandboxing LLM-generated code

LLM-written scripts are untrusted code and run in a separate process (`z3run.execute_script`) with several layers of protection:

- an isolated interpreter (`python -I -B`, ignoring user site-packages and environment hooks);
- a **scrubbed environment** containing only `PATH`, `PYTHONHASHSEED` and `HOME=/nonexistent`, so API keys loaded by the parent (e.g. `GEMINI_API_KEY`) are not visible to the script;
- a fresh temporary working directory;
- a wall-clock limit of the solver time-out plus 60 s (90 s in all LLM runs), a CPU `rlimit` and a 4 GiB data-segment `rlimit`;
- on macOS, a `sandbox-exec` profile that denies all network access and all file writes outside the temporary directory.

The child process communicates only through JSON on stdin/stdout and converts every exception into a structured error record, which feeds the taxonomy above. On platforms without `sandbox-exec` the network and file-system restrictions are absent and only the other layers apply. The C code executed under the sanitizers comes from the benchmark, not from the models. Models influence only the integer inputs passed to it.

## 5.10 Software

Python 3.11; Z3 via the `z3-solver` Python package; Apple clang 17 with AddressSanitizer and UndefinedBehaviorSanitizer; CBMC 6.11; Ollama for local inference. Code, prompts, instances, cached responses and raw records are in the project repository.
