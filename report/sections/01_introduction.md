# 1. Introduction

## 1.1 Motivation

Code review is the main line of defence against defects that type checkers and test suites miss. It is good at catching design problems and logic slips that are visible in the text. It is much worse at *mathematical edge cases*: an index that equals the array length only when a counter reaches its maximum, a midpoint `(lo + hi) / 2` that overflows only when both operands exceed $2^{30}$, a divisor that is zero only on one branch, or a shift whose amount reaches the bit-width only for the largest permitted input. In C these defects are *undefined behaviour*: the program may crash, silently compute garbage, or be "optimised" in surprising ways. They are also the kind of defect that a reviewer convinces themselves is impossible after a quick reading.

Large language models (LLMs) are now routinely used as automated code reviewers. They read code fluently and can explain their verdicts. However, they produce a verdict, not a proof. They can hallucinate a bug that does not exist, or, more dangerously, confidently declare unsafe code safe [Ji et al. 2023]. Whether LLMs can reason reliably about program invariants is still an open question [Pei et al. 2023].

Formal methods solve the opposite half of the problem. An SMT solver such as Z3 [de Moura & Bjørner 2008] decides the satisfiability of logical formulas over bit-vectors, arrays and integers. Once a safety question has been written as a formula, the solver's answer is exact: a satisfying assignment is a concrete counterexample, and unsatisfiability is a proof that none exists. The hard part is writing the formula. It requires a faithful translation of C semantics (two's-complement wrap-around, truncating division, shift rules, path conditions, loops) into the solver's language. That translation is itself a specialised programming task. Recent neurosymbolic work proposes giving it to an LLM and letting a solver do the reasoning [Pan et al. 2023; Ye et al. 2023].

This project compares the two paradigms directly on code-safety verification.

## 1.2 Problem statement

We study the following decision problem. Given a C function $f$, a *precondition* $P$ that every caller guarantees, and a fixed set of safety invariants $\mathcal{I}$ (array bounds, non-zero divisors, absence of signed overflow, well-defined shifts), decide whether **there exists** an input satisfying $P$ on which $f$ violates an invariant in $\mathcal{I}$ (UNSAFE), or not (SAFE). For UNSAFE verdicts we also ask for a concrete *witness* input. We check every witness by executing the real C code under sanitizers.

We compare two ways of using an LLM:

1. **Direct review.** The LLM reads the code and the preconditions and states a verdict and a witness. It does this either immediately or after step-by-step reasoning (chain of thought, CoT).
2. **Translation to a tool.** The LLM writes a Python script that encodes the question as an SMT satisfiability problem. Z3 then decides it: SAT means UNSAFE, and the model is a counterexample; UNSAT means SAFE. The translation can also be supported by *tool knowledge* (a list of C-to-Z3 pitfalls and a worked example) and by *execution feedback* (error messages and counterexample replay, over up to three repair rounds).

## 1.3 Research questions

- **RQ1 (accuracy).** How accurate is direct LLM review compared with LLM-to-Z3 translation? How does accuracy vary with control-flow complexity (four tiers: straight-line code, branches, loops, inter-procedural code with nested loops) and with the bug class (bounds, division by zero, overflow, shift)?
- **RQ2 (specification reliability).** How reliably can LLMs write Z3 specifications that are *executable* (the script runs and the solver returns an answer) and *faithful* (the answer matches the ground truth)? What goes wrong? We build a failure taxonomy that separates hallucinated APIs, sort/type misuse, syntax errors, solver time-outs, spurious counterexamples and missed bugs.
- **RQ3 (closing the gap).** Does tool knowledge (guidance plus a worked example) close the gap? Does execution feedback (repair rounds driven by interpreter errors and by counterexamples that fail to reproduce on the real code) close it further?
- **RQ4 (model scale).** How does model scale and quality change the picture? We evaluate two small open-weight models served locally (`qwen2.5-coder:7b`, `llama3.2:3b`). Commercial API models (Gemini 2.5 Flash / Flash-Lite) are planned as a follow-up.

## 1.4 Contributions

1. **A benchmark of 120 C verification instances arranged as 60 minimal pairs.** Each UNSAFE function has a SAFE twin. The twin differs either by a one- or two-line code fix or *only* by a tightened precondition, so a model cannot succeed by pattern matching on the code alone. Instances span four control-flow tiers and four bug classes, and include deliberate semantic traps (C `%` on negative operands, `INT_MIN / -1`, unsigned wrap-around) and decoys (provably dead code).
2. **Validated ground truth.** We validate every label with independent oracles. For UNSAFE instances we execute a witness under AddressSanitizer and UndefinedBehaviorSanitizer. Every instance has a reference Z3 encoding whose counterexamples we re-execute. We also run the CBMC bounded model checker [Clarke et al. 2004] and precondition-respecting fuzzing on SAFE instances.
3. **An evaluation harness for LLM-generated specifications.** It runs untrusted LLM-written Z3 scripts in a sandbox. It replays every solver counterexample on the real C code, so a "bug found" verdict is either *confirmed* or flagged as spurious. Execution errors and non-reproducing counterexamples are fed back to the model for repair. None of this needs the ground-truth label.
4. **A controlled comparison.** We compare five LLM approaches (direct, direct + CoT, Z3, Z3 guided, Z3 guided + repair), three post-hoc combined policies and four non-LLM reference points (gold Z3 encodings, CBMC, dictionary fuzzing, random fuzzing). We report paired significance tests and a failure taxonomy of the generated specifications.
5. **A Responsible-AI analysis of automated review.** We focus on the asymmetry between a checkable counterexample and an UNSAT "proof" that is only as good as the translation behind it, and derive recommendations for keeping humans in the loop.

The rest of the report is organised as follows. Section 2 reviews background and related work. Section 3 formalises the problem. Section 4 describes the dataset and Section 5 the approaches and evaluation protocol. Sections 6–7 present and discuss results [SECTIONS: results/discussion]. Section 8 discusses responsible-AI considerations and Section 9 threats to validity.
