# 2. Background and Related Work

## 2.1 Constraint satisfaction, SAT and SMT

A constraint satisfaction problem (CSP) consists of variables, domains and constraints. A solution assigns each variable a value from its domain so that every constraint holds [Russell & Norvig 2020]. Propositional satisfiability (SAT) is the special case of Boolean variables and clausal constraints. It is decided by complete backtracking search with unit propagation (DPLL and its conflict-driven descendants). Satisfiability modulo theories (SMT) extends SAT with background theories such as fixed-width bit-vectors, arrays and linear integer arithmetic. A SAT core enumerates Boolean structure, and theory solvers check the consistency of the theory literals. Z3 [de Moura & Bjørner 2008] is a widely used SMT solver of this kind. Its Python binding (github.com/Z3Prover/z3) lets a formula be built programmatically, which is the interface our LLMs target.

Our verification question maps directly onto this machinery:

- **Variables** are the function's inputs, plus one variable per intermediate value in static single-assignment (SSA) form.
- **Domains** are 32- or 64-bit two's-complement bit-vectors, and arrays from bit-vector indices to bit-vector values.
- **Constraints** are the caller's precondition, the semantics of each statement, and a disjunction stating that *some* safety check fails on a reachable path.

A solution of this CSP is a counterexample input. Bit-vector constraints are ultimately reduced to SAT by *bit-blasting*, translating each operation into a Boolean circuit. This makes linear operations cheap. Wide multiplications and divisions produce large circuits, which is a limitation we observe in Section 4.5.

## 2.2 Entailment by refutation

AIMA's treatment of logical agents states the key link between satisfiability and proof: a knowledge base $KB$ entails a sentence $\alpha$ iff $KB \land \lnot\alpha$ is unsatisfiable [Russell & Norvig 2020]. Program verification is an instance of this. Let $KB$ be the precondition together with the program semantics, and let $\alpha$ be "every safety invariant holds". If $KB \land \lnot\alpha$ is unsatisfiable, the code is safe, and the solver's UNSAT answer is a refutation proof. If it is satisfiable, any model is a concrete input that falsifies $\alpha$, i.e. a bug. The same model-checking view underlies the AIMA presentation of propositional inference, where satisfiability checkers such as DPLL are used as general-purpose reasoning engines.

## 2.3 Bounded model checking and CBMC

Biere et al. [1999] introduced *bounded model checking* (BMC). The transition relation of a system is unrolled for $k$ steps and conjoined with the negation of a property, and the resulting propositional formula is handed to a SAT solver. A satisfying assignment is a counterexample trace of length at most $k$. Clarke, Kroening and Lerda [2004] applied the idea to ANSI-C in CBMC. CBMC unwinds loops and inlines function calls up to a bound and translates the program to SSA form and then to SAT/SMT. It instruments the formula with checks for array bounds, pointer validity, division by zero and arithmetic overflow. *Unwinding assertions* additionally check that the bound was large enough. When they pass, a "verification successful" result is a proof for all executions and not merely bounded ones.

CBMC is therefore the classical, non-AI counterpart of our "translate to a solver" approach. It performs the C-to-logic translation mechanically and soundly for the language subset it supports. It serves as one of our ground-truth oracles and as a reference point. The question for the LLM approach is how close a *learned* translation can get to this engineered one, and at what cost.

## 2.4 LLMs reasoning about programs and invariants

Pei et al. [2023] ask whether large language models can reason about program invariants. They study whether models trained on code can predict invariants of the kind traditionally inferred by dynamic analysis. Their findings suggest that LLMs capture useful semantic regularities, but that predicted invariants are not guaranteed to hold and need checking. Our setting is complementary. The invariant is *given* (memory and arithmetic safety), and the model must decide whether the code can violate it under a precondition, an existential question over all inputs, not a property of observed executions.

A recurring concern is hallucination. Ji et al. [2023] survey the phenomenon in natural-language generation and distinguish *intrinsic* hallucinations (contradicting the source) from *extrinsic* ones (unverifiable additions). Both appear in code review. An intrinsic hallucination is claiming that an index is checked when the guard tests a different variable. An extrinsic hallucination is inventing a solver API function that does not exist. Our failure taxonomy (Section 5) separates these failure modes. Hallucinated Z3 APIs are detected mechanically as `NameError`s, and hallucinated bugs are detected by replaying the claimed witness on the real code.

## 2.5 Solver-augmented language models

Two closely related lines of work motivate the translation approach. **Logic-LM** [Pan et al. 2023] has an LLM translate a natural-language reasoning problem into a symbolic formulation (logic programming, first-order logic, CSP or SAT). A deterministic symbolic solver then performs the inference. A *self-refinement* step feeds solver error messages back to the LLM to repair formulations that fail to execute. **SatLM** [Ye et al. 2023] argues for having the LLM write a *declarative* specification of the problem rather than an imperative program that computes the answer. A SAT/SMT solver (Z3) does the search, which removes the burden of planning the solution procedure from the LLM.

Our Z3 approaches follow the same template: LLM as translator, solver as reasoner, error feedback for repair. Two differences matter:

1. The source language is C code with precise and unforgiving semantics, not natural language. A "faithful" translation is therefore well-defined and mechanically checkable.
2. We add a second kind of feedback that has no analogue in purely textual tasks. Every SAT answer comes with a model that we *execute* on the real program. A counterexample that does not reproduce exposes an unfaithful encoding even when the script runs without error, and we return this signal to the model. The ground-truth label is never used.

## 2.6 Positioning

| | Decides SAFE? | Gives checkable bug evidence? | Needs translation? | Failure mode |
|---|---|---|---|---|
| Fuzzing / testing | No (absence of evidence only) | Yes | No | Misses rare inputs |
| CBMC (BMC) | Yes, within bounds (full proof with unwinding assertions) | Yes | Mechanical | Bounds, solver time-outs, language coverage |
| LLM direct review | Yes (unjustified) | Sometimes (claimed witness) | No | Hallucination, ignoring preconditions |
| LLM → Z3 | Yes (relative to encoding) | Yes (model, replayable) | Learned | Unexecutable or unfaithful specifications |

The final row is the subject of this project. It inherits the strengths of a solver only to the extent that the LLM's translation is faithful, and quantifying that extent is the purpose of RQ2.
