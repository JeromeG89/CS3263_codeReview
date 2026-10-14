# 8. Responsible AI Considerations

An automated reviewer that says "this code is safe" changes how humans behave. This section discusses the risks of deploying either paradigm studied here, the safeguards built into our harness, and the practices we recommend. The discussion is framed by our formulation (Section 3) and will be grounded in the observed failure modes [REF: Section 6 results].

## 8.1 Over-reliance and automation bias

The central risk is **automation bias**: reviewers defer to the tool and stop checking for themselves. The two possible errors carry very different costs.

- A **false UNSAFE** (false alarm) costs reviewer time. Repeated false alarms also train reviewers to ignore the tool, which is a slower route to the same failure.
- A **false SAFE** (missed bug) is a *false assurance*. The defect ships, and the review record now says it was checked. In safety- or security-critical C code (parsers, kernels, embedded controllers), an out-of-bounds write or signed overflow is exactly the class of defect that becomes an exploitable vulnerability.

Accuracy alone hides this asymmetry, which is why we report recall and specificity separately [FIG: recall vs specificity]. For critical software, a system with high specificity but mediocre recall should be presented as a *bug finder*, never as a *verifier*.

## 8.2 The asymmetry between counterexamples and proofs

The translation approach gives its two verdicts very different evidential standing (Section 3.2).

- **SAT comes with a checkable artefact.** The solver's model is a concrete input. We execute it on the real code under sanitizers, and a confirmed counterexample is a reproducible bug report whose validity does not depend on trusting the LLM, the encoding or the solver. Our repair loop exploits this: a counterexample that does not reproduce is evidence of an unfaithful encoding and is fed back to the model.
- **UNSAT is only as good as the translation.** An UNSAT answer proves that the *encoded* formula has no model. If the LLM dropped a path, unrolled a loop too few times, used Z3's `%` instead of `SRem`, or over-constrained the precondition, Z3 has correctly proved *the wrong theorem*. Nothing in the pipeline flags this, and our repair loop deliberately never questions an UNSAT answer because no label-free signal exists. The formal-looking output ("Z3: unsat") may be *more* persuasive to a human than an LLM's prose "looks safe to me", even though it can be equally wrong. This is the main way the neurosymbolic approach can *increase* over-reliance compared with direct review.

The direct approach has a weaker version of the same asymmetry. A claimed witness can be checked, but a SAFE verdict comes with no artefact at all, only a natural-language explanation that may itself be hallucinated [Ji et al. 2023].

## 8.3 Hallucinated tools and APIs

Translation shifts hallucination from the *verdict* to the *specification*. Small models invent Z3 functions, misuse sorts and confuse Python with Z3 operators [TABLE: Z3 outcomes]. Errors of this kind are benign in our harness because they fail loudly: a `NameError` is caught, classified and repaired with a did-you-mean hint. The dangerous hallucinations are those that *execute*: a plausible but semantically wrong encoding that returns UNSAT. Tool output should therefore always be accompanied by the generated specification itself, not just its verdict.

## 8.4 Executing model-generated code safely

Running LLM-written code is a security decision. A model may emit code that reads files, opens network connections or exhausts resources. It may do so through error or because a prompt-injection payload is embedded in the code under review (for example in a comment). Our harness treats every script as untrusted (Section 5.9):

- separate isolated interpreter;
- scrubbed environment, so API keys present in the parent process are invisible to the script;
- throw-away working directory;
- CPU, memory and wall-clock limits;
- on macOS, an OS sandbox denying network access and writes outside the temporary directory.

These measures are defence in depth, not a security boundary we would certify. In particular, the OS sandbox is platform-specific. Any production deployment should use a proper container or VM sandbox. The C code under review is executed too, under sanitizers, but in our study it comes from the benchmark. In a real deployment, executing submitted code also requires isolation.

## 8.5 Data contamination and benchmark validity

Public bug benchmarks may appear in the training data of the models being evaluated, which inflates scores through memorisation. Our instances are newly written, which reduces but does not remove this risk. Several are deliberately built around well-known idioms (the `(lo + hi) / 2` midpoint, overflow checks that themselves overflow, absolute value of `INT_MIN`), and models may recognise the idiom rather than reason about it. The minimal-pair design is our main mitigation. In precondition twins both versions contain the identical idiom, so recognising it helps on one twin and hurts on the other. Code twins still require noticing the precise one- or two-line fix. Pair accuracy and the same-verdict rate expose this behaviour [FIG: twin type]. If the benchmark is released publicly, it should carry a canary string so that future contamination can be detected.

## 8.6 Cost, energy and access

The two paradigms have different resource profiles. Direct review costs one LLM call per function. The repair variant costs up to four calls plus solver and sanitizer runs [TABLE: cost]. Local 3–7B models run on a laptop with no per-token charge and no data leaving the machine, which matters for proprietary code, but they consume local energy and time. API models (Gemini) are faster and stronger but involve per-token cost, rate limits, and sending source code to a third party. A tool that only works well with a paid frontier model is not equally available to students, open-source maintainers or organisations in lower-resource settings. Reporting results for small local models is part of an honest picture of what is accessible. Classical tools (CBMC, fuzzing) remain the cheapest and most reliable option where they apply, and an LLM-based reviewer should be justified against them, not only against other LLMs [FIG: accuracy, non-LLM panel].

## 8.7 Accountability and human-in-the-loop recommendations

Responsibility for shipped code remains with the engineers who approve it; a tool cannot be accountable. Based on the structure of the evidence each verdict carries, we recommend the following.

1. **Treat SAT + confirmed witness as actionable.** A reproducible input that triggers a sanitizer report is a bug report a developer can verify in seconds. It should block merging until fixed.
2. **Treat SAT without confirmation as a hint, not a finding.** Show it, label it as unreproduced, and do not count it as a bug (this is our "witness-validated" policy, Section 5.5).
3. **Treat UNSAT as evidence that requires review of the specification.** Display the generated Z3 script next to the code so a reviewer can check its preconditions, path conditions, loop bounds and operator semantics. Never present "verified" without the artefact that was verified.
4. **Never present a direct-LLM SAFE verdict as verification.** It is an opinion with no artefact.
5. **Escalate by risk.** For critical code, require a sound tool with known guarantees (e.g. CBMC with unwinding assertions) or human proof review, and use the LLM to *draft* specifications and harnesses, not to sign them off.
6. **Log and audit.** Keep the prompts, model versions, generated specifications and solver outputs, as our cache and records already do, so that a later failure can be traced to its cause.

## 8.8 Disclosure of AI assistance

In line with the transparency we ask of automated reviewers, we disclose that an AI assistant (Claude) helped author the benchmark instances, witnesses and reference encodings. To avoid circularity, no label was accepted on the assistant's word. Every label was mechanically validated by sanitizer execution, solver-model replay, CBMC and fuzzing (Section 4.5), and the evaluated models are from other vendors. Residual bias from AI-assisted authoring is discussed as a threat to validity in Section 9.
