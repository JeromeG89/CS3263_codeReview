# 3. Problem Formulation

## 3.1 Instances

An instance is a tuple $\iota = (f, \tau, P, \mathcal{I})$:

- $f$ is a C function (the *entry*), possibly calling static helper functions defined alongside it.
- $\tau$ assigns each parameter a type. Scalars are `int` (32-bit signed) or `unsigned` (32-bit). Arrays are `int[]` or `unsigned[]`, with a length given by an expression $L_a(x)$ over the scalar parameters, for example `len: n`. The type list in the code also admits `long long` (64-bit signed). No benchmark parameter uses it, but `long long` occurs inside function bodies (widening casts).
- $P$ is the precondition guaranteed by every caller. It has two parts: a conjunction of C-syntax clauses over the scalars (e.g. `1 <= n && n <= 64`), and optional *element preconditions* of the form "every element `_` of array $a$ satisfies $E_a(\_)$".
- $\mathcal{I}$ is the fixed safety specification shown verbatim to every model (`SAFETY_SPEC` in `dataset.py`). It has four invariants:
  1. **bounds:** every array access uses an index $i$ with $0 \le i < \text{len}$;
  2. **div_zero:** the right operand of every `/` and `%` is non-zero;
  3. **overflow:** no signed `+`, `-`, `*` or unary `-` overflows, and neither `INT_MIN / -1` nor `INT_MIN % -1` is evaluated. Unsigned wrap-around is well defined and explicitly *not* a violation;
  4. **shift:** for `a << b` and `a >> b`, $0 \le b <$ the width of the promoted left operand; for signed `a << b`, additionally $a \ge 0$ and the result is representable.

These are the C11 rules for undefined behaviour on these operators, restricted to the operations that occur in the benchmark. Right shifts of negative signed values are implementation-defined rather than undefined in C11 and are therefore not violations.

Let $X_\iota$ be the set of well-typed inputs: scalar values in range, and arrays of exactly $L_a(x)$ in-range elements. For an input $x$, let $\mathrm{Ops}(f, x)$ be the sequence of operation occurrences (each an access, division, arithmetic operation or shift, together with its operand values) executed by $f(x)$. Let $\varphi_o$ be the safety condition of occurrence $o$. Then

$$
\iota \text{ is UNSAFE} \iff \exists x \in X_\iota.\; P(x) \land \exists o \in \mathrm{Ops}(f,x).\; \lnot\varphi_o .
$$

The functions are deterministic, so "some execution" means the unique execution on $x$ up to the first undefined operation. A **witness** is any $x$ that makes the existential true.

## 3.2 Encoding as SMT satisfiability

The safety question is encoded as a single formula over the theory of fixed-width bit-vectors and arrays:

$$
\Phi_\iota \;=\; P(\vec{x}) \;\land\; \bigvee_{o \in \mathrm{Ops}(f)} \big(\pi_o(\vec{x}) \land \lnot\varphi_o(\vec{x})\big)
$$

- $\vec{x}$ are solver constants, one per parameter. Scalars are `BitVec(·, 32)` (or 64), and arrays are `Array(BitVecSort(32), BitVecSort(32))`.
- $\mathrm{Ops}(f)$ ranges over the *static* operation occurrences of $f$ after loop unrolling and inlining.
- Intermediate values are expressed in SSA form. Each assignment produces a fresh term, and values are merged after a branch with `If(c, a, b)`.
- $\pi_o$ is the *path condition* under which $o$ executes: the conjunction of branch conditions (and loop-iteration guards) on the path to $o$.
- $\varphi_o$ uses Z3's overflow predicates (`BVAddNoOverflow`, `BVSubNoUnderflow`, `BVMulNoOverflow`, `BVSDivNoOverflow`, `BVSNegNoOverflow`, …), explicit range checks for indices and shift amounts, and disequalities for divisors.

The scalar part of the precondition becomes ordinary constraints. An element precondition only needs to be asserted for the indices the function actually reads, guarded by $0 \le i < L_a$ (e.g. `Implies(And(0 <= i, i < n), a[i] >= 0)`). This avoids quantifiers.

**SAT gives a counterexample.** If $\Phi_\iota$ is satisfiable, any model assigns concrete values to $\vec{x}$. On the model's input, take the *earliest* operation on the executed path whose check fails. All operations before it are well defined, so their bit-vector semantics agree with C, and that operation is genuinely reached with its safety condition false. The model therefore describes an input that triggers *some* violation, though not necessarily the one in the satisfied disjunct. Two consequences follow. First, an encoding need not model "execution stops at the first violation" (the guidance given to the LLMs says so explicitly). Second, our witness check accepts a sanitizer report of any class.

**UNSAT gives a proof, relative to the encoding.** If $\Phi_\iota$ is unsatisfiable, no input satisfying $P$ can reach a violated check *in the encoded program*. This transfers to the real program only if the encoding **over-approximates** $f$: every real execution, every reachable operation and every relevant safety condition must be represented. Under-approximation produces an unsound UNSAT, a correct proof of the wrong theorem. Examples are unrolling too few loop iterations, omitting an operation, using the wrong sort, strengthening the precondition or mis-encoding a C operator. Over-approximation can only produce spurious SAT answers, and those are detectable by executing the model on the real code. This asymmetry drives both our evaluation design (counterexample validation, Section 5.3) and our Responsible-AI discussion (Section 8).

**Relation to the AIMA view.** With $KB = P \land \mathrm{Sem}(f)$ and $\alpha = \bigwedge_o (\pi_o \Rightarrow \varphi_o)$, $\Phi_\iota$ is exactly $KB \land \lnot\alpha$, so UNSAT is the refutation proof of $KB \models \alpha$. Equivalently, $\Phi_\iota$ is a finite-domain CSP whose solutions are the bugs.

## 3.3 Loops

Loop-free code (Tiers 1–2) and inlined helpers yield a finite $\mathrm{Ops}(f)$ directly. For loops we use two techniques.

**Bounded unrolling justified by the precondition.** In almost every looping instance, the precondition bounds the trip count, for example `1 <= n && n <= 8`. The loop body is then unrolled $K$ times in Python, iteration $t$ is guarded by the condition that it executes (e.g. `run = i_t < n`), and the loop state is threaded through `If(run, new, old)`. When $K$ is at least the maximal trip count under $P$, the unrolling is complete and UNSAT is a proof. This is the BMC construction of Biere et al. [1999] with a bound that is sufficient by construction. In the reference encodings the sufficiency of $K$ is argued by hand (e.g. "`hi - lo <= 72`"). It is cross-checked independently by CBMC, whose unwinding assertions fail if the per-instance `unwind` bound is too small (Section 4.4). For an UNSAFE instance a short unrolling already suffices to exhibit the bug. For example, the reference encoding of the GCD instance `T3-OVF-04-U` unrolls only two iterations.

**Inductive invariant (T3-OVF-04-S).** Euclid's algorithm `while (b != 0) { t = a % b; a = b; b = t; }` has no simple syntactic trip-count bound. The SAFE twin restricts $0 \le a, b \le 10^6$, which excludes the `INT_MIN % -1` trap and negative remainders. Its reference encoding uses the inductive invariant $\mathit{inv}(x,y) \equiv x \ge 0 \land y \ge 0$ at the loop head, with fresh head variables $x, y$, and asserts the disjunction of three conditions:
(i) $\lnot\mathit{inv}(a,b)$ (initiation fails);
(ii) $\mathit{inv}(x,y) \land y \ne 0 \land \lnot\mathit{inv}(y, x \,\mathrm{srem}\, y)$ (consecution fails);
(iii) $\mathit{inv}(x,y) \land y \ne 0 \land (y = 0 \lor \lnot\texttt{BVSDivNoOverflow}(x,y))$ (an invariant violation is possible from an $\mathit{inv}$-state).
UNSAT proves safety for *any* number of iterations. This is a 1-inductive argument, a step beyond BMC. CBMC reaches the same verdict on this instance by plain unrolling, because Euclid's algorithm on inputs up to $10^6$ terminates within the configured bound of 33 iterations.

**Lemma abstraction (T3-OVF-02).** The function `sum_squares` accumulates `s += a[i] * a[i]` for up to eight elements. With eight symbolic 32-bit multiplications feeding a chain of additions, the bit-blasted formula became intractable: an earlier version of the SAFE reference encoding exceeded our 90-second budget. The current reference encodings split the reasoning.

- A one-variable *lemma* is proved by a separate solver call inside the script: for $e \in [-16000, 16000]$, $e \cdot e$ does not overflow and lies in $[0, 2.56\times10^8]$. The script asserts the lemma's UNSAT result.
- In the SAFE twin, each square is then replaced by a fresh variable constrained only to that range. This is an *over-approximation* of the program, so UNSAT of the abstracted formula remains a proof.
- The UNSAFE twin instead replaces $e \cdot e$ by an exact but cheaper $16{\times}16$-bit product of the magnitude. A lemma proves this equal to $e \cdot e$ on the element domain $[-20000, 20000]$.

The reasoning is modular: hard nonlinear facts are proved once, over one variable, and abstracted. The LLM translators are not told about this technique, but it illustrates that a *faithful* encoding is not always a *tractable* one.

## 3.4 Semantic traps

A translation can be syntactically valid yet semantically wrong. The benchmark deliberately exercises the most common C-to-Z3 mismatches (tag `semantics_trap` and related tags). The Z3 guidance prompt (Section 5.2) warns about most of them.

| C construct | C11 semantics | Naive Z3 rendering | Pitfall |
|---|---|---|---|
| `a % b` (signed) | truncated remainder; sign follows the dividend (`-7 % 2 == -1`) | Python `%` on `BitVec` = `bvsmod`, sign follows the divisor (gives `1`) | Use `SRem`. `T1-BND-03` uses a possibly negative remainder as an index, `T4-SHF-01` as a shift amount |
| `a / b` on `Int` sort | truncation toward zero | SMT-LIB integer `div` is Euclidean (`-7 div 2 = -4`, `-7 div -2 = 4`) | Wrong quotient for negative operands; `Int` also never overflows, so every intermediate needs explicit range checks |
| `INT_MIN / -1`, `INT_MIN % -1` | undefined (quotient not representable) | `bvsdiv` / `bvsrem` are total | Must add `Not(BVSDivNoOverflow(a, b))`. Instances `T1-OVF-02`, `T3-OVF-04` |
| `-x` | undefined for `x == INT_MIN` | `bvneg` wraps | `BVSNegNoOverflow`. Instances `T1-OVF-04`, `T2-OVF-05` |
| `a << b`, `a >> b` | undefined if $b < 0$ or $b \ge$ width; signed `<<` also requires $a \ge 0$ and a representable result | `bvshl` with $b \ge 32$ silently yields 0; `>>` on `BitVec` is arithmetic | The shift-amount and representability checks must be written explicitly. Reference encodings use $a \le \texttt{INT\_MAX} \gg b$ |
| `unsigned` arithmetic | wraps modulo $2^{32}$ (well defined) | signed comparison operators `<`, `/`, `>>` on `BitVec` | Use `ULT`, `UDiv`, `URem`, `LShR`. Do *not* report wrap-around as overflow (`T1-DIV-05`: `slots + 1u` wraps to 0, and the bug is the resulting division by zero) |
| `(long long)x * y` vs `(long long)(x * y)` | widening before vs after the multiply | mixing 32/64-bit sorts is a Z3 sort error | `SignExt(32, x)`. Instances `T1-OVF-05`, `T2-OVF-04`, `T4-OVF-01` |
| `x < 0 \| x > 5` in Python | n/a | Python precedence parses `x < (0 \| x) > 5` | Use `Or(...)`. Python operators on Z3 Booleans are a frequent silent bug |

The second row is a subtle case. SMT-LIB `div` is Euclidean, so it coincides with floor division only for positive divisors; for negative divisors it differs from both C and floor division. An early draft of our guidance prompt described `Int` division as "rounding toward minus infinity". We corrected it to "Euclidean" before any guided-Z3 run was executed, so no reported result used the inaccurate wording.

## 3.5 Output and correctness criteria

Every system outputs a verdict in {SAFE, UNSAFE, UNKNOWN}. UNKNOWN covers unparseable answers, scripts that fail to run, and solver time-outs. A verdict is *correct* iff it equals the gold label, and UNKNOWN is always incorrect. Independently, every UNSAFE verdict carries a witness, which is *confirmed* iff it satisfies $P$ and its concrete execution produces a sanitizer report (Section 5.3). Correctness of the verdict and confirmation of the witness are reported separately. A system can be right for the wrong reason (a correct UNSAFE verdict with a bogus witness), and the distinction matters for how much a reviewer should trust it.
