# 4. Dataset

## 4.1 Design goals

Existing bug benchmarks are either too large and noisy for a small-model, course-scale study, or likely to appear in model training data. We therefore built a focused benchmark of small C functions with four design goals:

1. **Exact ground truth.** Every label is a precise mathematical statement (Section 3.1) that can be checked mechanically.
2. **Controlled difficulty.** Control-flow complexity increases across four tiers, following the proposal's fallback plan of starting with flat arithmetic and scaling up to loops and calls.
3. **Resistance to shallow heuristics.** Instances come in minimal pairs in which the UNSAFE and SAFE versions look almost identical.
4. **Coverage of semantic traps.** These are cases where a reviewer's (or a translator's) mathematical intuition differs from C semantics.

## 4.2 Tiers, bug classes and minimal pairs

The benchmark has **120 instances forming 60 minimal pairs**. Each pair consists of an UNSAFE function (`-U`) and its SAFE twin (`-S`), so the label distribution is exactly balanced (60/60) overall and within every tier and bug class. A trivial classifier therefore scores 50% accuracy and 0% pair accuracy. Each pair has one *bug class*, the invariant that the UNSAFE version violates: **bounds**, **div_zero**, **overflow** or **shift**.

| Tier | Control flow | Pairs | Instances | bounds | div_zero | overflow | shift | Code twins | Precondition twins | Mean LoC |
|---|---|---|---|---|---|---|---|---|---|---|
| T1 | straight-line (at most a ternary) | 20 | 40 | 10 | 10 | 12 | 8 | 10 | 10 | ~3.1 |
| T2 | branches, guards, early returns, infeasible paths | 19 | 38 | 12 | 8 | 12 | 6 | 15 | 4 | ~7.3 |
| T3 | loops bounded by preconditions | 13 | 26 | 10 | 4 | 8 | 4 | 6 | 7 | ~7.5 |
| T4 | helper functions, nested loops, data-dependent control | 8 | 16 | 6 | 4 | 4 | 2 | 6 | 2 | ~11.7 |
| **Total** | | **60** | **120** | **38** | **26** | **36** | **20** | **37** | **23** | |

*Category columns count instances (half of each is UNSAFE). Twin columns count pairs. LoC = mean number of non-blank lines of C code per instance, helper functions included.*

Further structural statistics, computed from the instance files:

- 50 instances (25 pairs) take array parameters, and 24 instances carry element preconditions.
- Parameters are `int` or `unsigned` scalars and `int[]` / `unsigned[]` arrays. `long long` appears only inside function bodies (4 pairs), and `unsigned` arithmetic appears in the code of 9 pairs.
- 18 pairs contain loops (all 13 T3 pairs and 5 T4 pairs), and 6 pairs (all in T4) call static helper functions that must be inlined.

**Twin types.** Pairs come in two kinds, and the code enforces both definitions: every code-twin pair has identical parameters and preconditions, and every precondition-twin pair has byte-identical code.

- **Code twins (37 pairs)** keep the precondition and differ by a minimal fix of one or two changed lines. Examples: `(lo + hi) / 2` versus `lo + (hi - lo) / 2`; a ring-buffer wrap test `>` versus `>=`; a loop bound `i <= n` versus `i < n`. These test whether the model notices the bug *in the code*.
- **Precondition twins (23 pairs)** have identical code and differ only in what callers guarantee. Examples: `1 << k` with `k <= 31` versus `k <= 30`; a rectangle area with sides up to 50000 versus up to 46340 ($46340^2 \le$ `INT_MAX` $< 46341^2$); Euclid's GCD on arbitrary versus non-negative inputs. Here the code alone does not determine the answer. A model that pattern-matches "this looks like a known bug" without reading and reasoning about the precondition must get one of the two twins wrong. Precondition twins are therefore a direct test of whether the model performs the existential reasoning of Section 3.1 or merely recognises suspicious idioms.

We report **pair accuracy** (both twins correct) and the **same-verdict rate** (the model gives both twins the same answer, a symptom of not discriminating) alongside instance accuracy.

## 4.3 Tags: decoys and traps

Every instance is annotated with descriptive tags (70 distinct tags). Pair counts for the main families:

- **Off-by-one** (11 pairs): loop bounds, clamps to `[0, n]` instead of `[0, n-1]`, `(n+1)/2` medians, mirror indices `a[n - i]`, triangular storage.
- **Semantic traps** (`semantics_trap`, 5 pairs, plus related tags): C `%` on negative operands used as an index or shift amount (`negative_modulo`, 2 pairs), `INT_MIN / -1` and `INT_MIN % -1` (`int_min_div`, 2 pairs), `INT_MIN` negation (2 pairs), and well-defined unsigned wrap-around that nonetheless produces a zero divisor (`unsigned_wrap`).
- **Numeric boundaries** (5 pairs): the bug appears only at a specific magnitude, such as $13! >$ `INT_MAX` while $12!$ fits, or the sum of eight squares just above or below $2^{31}$.
- **Shift rules**: `sign_bit_shift` (4 pairs), `full_width_shift` (3 pairs), negative shift amounts, and left shifts of negative values.
- **Decoys and path reasoning**: `dead_code_decoy` / `path_feasibility` (`T2-BND-06`). In the SAFE twin the suspicious access `tbl[k + 2]` sits under `if (k > 5 && k < 3)`, which is unsatisfiable. In the UNSAFE twin the branch is reachable for `k` in 6..8. Related tags cover `ineffective_guard` (2 pairs), `broken_overflow_check` (an overflow check that itself overflows), `short_circuit_order` (`a[i] < b[j]` evaluated before the exhaustion test) and `disjunctive_precondition`.
- **Inductive reasoning**: `inductive_invariant` (`T3-OVF-04-S`, Section 3.3).

These tags support qualitative error analysis [TABLE: errors by tag]. They are not used by any system.

## 4.4 Instance format

Instances are YAML documents (`dataset/instances/tier{1..4}.yaml`). A precondition twin can reuse its sibling's code with `code_from:`.

| Field | Meaning |
|---|---|
| `id`, `pair`, `label`, `tier`, `category`, `twin` | identity, minimal pair, gold label (`safe`/`unsafe`), tier 1–4, bug class, `code` or `precondition` |
| `entry`, `params` | entry function and typed parameters; arrays carry `len` (an expression over scalars) |
| `requires` | scalar precondition clauses in C syntax |
| `elem_requires` | per-array element precondition over the placeholder `_` |
| `code` | the C source (entry function plus helpers) |
| `witness` | UNSAFE only: concrete input values that trigger a violation |
| `reference_z3` | reference Z3 encoding following the same protocol as the LLMs (Section 5.2) |
| `unwind` | CBMC loop-unwinding bound (default 40) |
| `tags`, `description`, `bug_explanation` | annotations, never shown to models |

Models see only the C code. It is preceded by a comment listing the preconditions, including the sentence "`a` points to an array of exactly `n` elements" and the element preconditions, followed by a one-line parameter summary and the safety specification. Labels, tags, descriptions, witnesses and reference encodings are never shown, with the single exception of the separate few-shot example (Section 5.2).

## 4.5 Ground-truth validation

Every label is checked by several independent oracles (`scripts/validate_dataset.py`):

1. **Sanitizer-executed witness (UNSAFE).** The instance is compiled by clang with `-fsanitize=address,undefined -fno-sanitize-recover=all -O0` into a driver that reads inputs from standard input. Arrays are heap-allocated with exactly the declared length, so any out-of-bounds access lands in an AddressSanitizer redzone. The hand-written witness must satisfy the preconditions (checked strictly, including array lengths) and must produce a sanitizer report. We also check that the reported class matches the instance's category.
2. **Reference Z3 encoding.** The Claude-authored `reference_z3` script must run in the same sandbox as LLM scripts and return the gold verdict. For UNSAFE instances, its model is extracted and *re-executed* under the sanitizers and must be confirmed. This also validates the counterexample-replay pipeline used for the LLMs.
3. **CBMC** (version 6.11) with bounds, pointer, division-by-zero, signed-overflow and undefined-shift checks, the per-instance unwinding bound, and unwinding assertions. It must return the gold verdict. Failures located in the harness rather than in the instance's own functions are ignored.
4. **Precondition-respecting fuzzing (SAFE).** Each SAFE instance receives 3,000 dictionary-fuzzing inputs (seed 1), and none may trigger a sanitizer report. On two instances fewer inputs satisfied the precondition within the generator's limits. `T1-BND-04-S` had 484, because its `rows × cols` grid must fit the 64-element cap on fuzzed arrays. `T4-SHF-01-S` had 2,356.

Fuzzing can only refute safety and CBMC is bounded, so a SAFE label rests on two complete arguments (the reference Z3 UNSAT and CBMC with passing unwinding assertions), backed by fuzzing. An UNSAFE label rests on an executed witness, a confirmed solver model and CBMC.

On the frozen dataset all **120/120** instances pass every check (`dataset/VALIDATION.md`): every UNSAFE witness triggers a sanitizer report of its labelled class, every reference encoding returns the gold verdict (with confirmed counterexamples for UNSAFE), CBMC agrees with every label, and no fuzzing input triggers a violation in any SAFE instance.

## 4.6 Excluded stress pair

A further pair, `STRESS-OVF-01` (`dataset/stress/stress.yaml`), is kept out of the evaluation set. It is a classic "is it safe to multiply?" helper. The UNSAFE version checks `a == 0 || (a * b) / a == b`, which performs the overflowing multiplication inside the check itself (witness `qty = price = 65536`). The SAFE version checks `b <= INT_MAX / a`. Both labels were established by reasoning and fuzzing. However, the reference Z3 encoding and CBMC both time out on this pair, because the formula combines a 32-bit nonlinear multiplication with a 32-bit division over unconstrained operands, a worst case for bit-blasting. Including the pair would have given an oracle-free label, so we excluded it. We report it instead as a finding about the translation approach: even a perfect LLM translation can fail on purely solver-side grounds, because a faithful encoding is not necessarily a tractable one (compare the lemma abstraction of Section 3.3).

## 4.7 Provenance and AI assistance

The instances, witnesses and reference Z3 encodings were authored with the help of an AI assistant (Claude, Anthropic), under the direction of and with review by the team. The few-shot example was authored the same way. We do not treat this authorship as a source of truth. Every label is accepted only after the mechanical validation of Section 4.5, whose oracles (clang sanitizers, CBMC, fuzzing) are independent of any language model. The reference encodings also serve as the "gold translation" upper bound in Section 5. The models under evaluation (Qwen, Llama, Gemini) come from different vendors than the authoring assistant. Authoring with an LLM may nevertheless bias the benchmark toward idioms that LLMs find natural; we discuss this threat in Section 9.
