# 10. Conclusion and Future Work

We asked whether an LLM is a better code-safety reviewer when it judges code directly or when it translates the question into a constraint problem for Z3.

**Findings for small open-weight models:**
- **Direct review** answers every question but does not reason about the code. Its accuracy is at chance, insensitive to difficulty, and biased towards "safe".
- **Translation to Z3** reasons correctly far more often when the generated specification runs, especially about preconditions and on flat arithmetic. But writing an executable, faithful Z3 script is beyond these models' reliability: they hallucinate API names, confuse Python and Z3 operators, mistranslate C semantics, and fall into repetition loops.
- **More tool knowledge in the prompt made this worse**, and greedy repair loops mostly repeated themselves.
- **The two approaches complement each other.** Falling back to chain of thought when the solver cannot be used, and re-executing every counterexample, gives the best and most trustworthy LLM-based system we measured.
- **Classical verification tools remain far ahead** on this kind of code.

**Recommendations for practice:**
- Treat confirmed counterexamples as actionable.
- Treat UNSAT and "looks safe" as evidence requiring human review of the specification.
- Use LLMs to *draft* specifications and harnesses for sound tools, rather than to sign off on safety.

**Future work:**
1. Run the prepared Gemini configuration to test whether stronger models close the executability gap. Also test, with thinking enabled, whether they still produce executable but unfaithful encodings.
2. Try sampled or fresh-context repair instead of greedy continuation.
3. Constrain decoding to the real Z3 API.
4. Add a faithfulness check for UNSAT answers, e.g. differential checks against CBMC or mutation of the generated specification.
5. Extend the benchmark beyond single functions to pointers, structs and library calls.
