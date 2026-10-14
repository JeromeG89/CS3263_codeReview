# CS3263 — Direct LLM review vs. LLM-to-Z3 translation for C safety invariants

CS3263 (NUS) project by **Jerome Goh** (lead), **Mothiki Eswara Anirudh** and **Goh Joon Xiang**.

Can an LLM tell whether a C function can violate a safety invariant (array bounds, division by zero,
signed overflow, invalid shifts) given the preconditions its callers guarantee? We compare two ways of
using the same model:

1. **Direct**: the LLM reads the code and answers `SAFE` / `UNSAFE` (with a concrete counterexample).
2. **LLM → Z3**: the LLM translates the question into a Z3 (Python) script, and *we* run the solver.
   `sat` means UNSAFE, and the model is a counterexample. `unsat` means SAFE.

Every counterexample from either approach is re-executed against the real C code, compiled with clang
AddressSanitizer + UndefinedBehaviorSanitizer. That tells a confirmed bug apart from a spurious one.

The benchmark has 120 hand-written instances in 60 minimal pairs. Each pair has an UNSAFE function and
a SAFE "twin" that differs either by a code fix or by a tighter precondition. The instances are spread
over four difficulty tiers and the four bug classes. Every label is checked independently with
sanitizers, a reference Z3 encoding, CBMC and fuzzing.

## Approaches and baselines

| name | what the LLM does |
|---|---|
| `direct` | answers immediately with a JSON verdict and witness (no reasoning text) |
| `direct_cot` | reasons step by step, then gives the JSON verdict |
| `z3` | writes a Z3 script following the bare protocol below |
| `z3_guided` | as `z3`, plus C-to-Z3 modelling guidance and one worked example (`dataset/examples/example.yaml`) |
| `z3_repair` | as `z3_guided`, plus up to `max_repairs` feedback rounds. Feedback covers execution errors and counterexamples that fail to reproduce in C |

The non-LLM reference points (`scripts/run_baselines.py`) are:

- `reference_z3`: the gold encodings (Claude-authored, validated as described below), which give the upper bound for the translation approach.
- `cbmc`: a classical bounded model checker run on the C code.
- `fuzz_random` and `fuzz_dict`: precondition-respecting random testing, either naive or with a
  dictionary of boundary values and code constants.

All prompts live in `src/invcheck/prompts.py`.

## Repository layout

```
configs/                 run configurations (models, approaches, workers, repair budget)
  local.yaml             qwen2.5-coder:7b + llama3.2:3b via Ollama
  local_llama.yaml       llama3.2:3b only
  smoke.yaml             quick end-to-end check (records excluded from analysis)
  gemini.yaml            gemini-2.5-flash-lite + gemini-2.5-flash via the Gemini API
dataset/
  instances/tier{1..4}.yaml   the 120 evaluation instances
  examples/example.yaml       few-shot example for the guided Z3 prompts (not evaluated)
  stress/stress.yaml          intractable-for-oracles instances, excluded from evaluation
  VALIDATION.md               generated ground-truth validation report
scripts/
  validate_dataset.py    triple-validates every label (writes VALIDATION.md, results/validation.json)
  run_baselines.py       reference Z3, CBMC, fuzzing -> results/runs/baselines/records.jsonl
  run_eval.py            LLM evaluations -> results/runs/<run_name>/records.jsonl (resumable)
  list_gemini_models.py  lists Gemini model ids available to your API key
  analyze.py             tables, statistics and figures
src/invcheck/
  dataset.py   instance model, loading, preconditions, witness normalisation, SAFETY_SPEC
  cexec.py     ASan+UBSan harness: compile once, run many cases from stdin
  fuzz.py      precondition-respecting fuzzing baseline
  cbmc.py      CBMC harness generation and result parsing
  z3run.py     sandboxed execution of Z3 scripts, witness validation
  z3_child.py  the child process that actually runs a Z3 script
  prompts.py   all prompt templates
  llm.py       Ollama / Gemini clients behind one interface, with a SQLite response cache
  parse.py     verdict-JSON and Python-code extraction from model output
  approaches.py  the five evaluated approaches
  analysis.py  metrics, Wilson CIs, McNemar + Holm, derived policies
tests/                   pytest suite
results/                 records, cache, analysis output (results/cache is gitignored)
report/figures/          figures written by analyze.py
build/                   compiled sanitizer harnesses and CBMC harnesses (gitignored)
```

## Setup

The project needs Python ≥ 3.10 and has been developed on macOS (Apple silicon).

```bash
# Python environment
uv venv
uv pip install -e ".[dev]"     # or: python -m venv .venv && .venv/bin/pip install -e ".[dev]"
source .venv/bin/activate

# C toolchain with sanitizers (Apple clang from the Command Line Tools works)
xcode-select --install
brew install cbmc

# Local models
brew install ollama
ollama serve                   # in a separate terminal (or run the Ollama app)
ollama pull qwen2.5-coder:7b
ollama pull llama3.2:3b
```

The scripts add `src/` to `sys.path` themselves, so the editable install is a convenience, not a
requirement. Set `CC` to use a compiler other than `clang`, and set `OLLAMA_HOST` if Ollama does not
run at `http://localhost:11434`. Copy `.env.example` to `.env` for these settings. `.env` is gitignored.

## Usage

All commands are run from the repository root.

### 1. Validate the dataset

```bash
python scripts/validate_dataset.py                 # all 120 instances; exits non-zero on any disagreement
python scripts/validate_dataset.py --only T1 T2-BND --no-cbmc --fuzz 500
python scripts/validate_dataset.py --examples      # validate the few-shot example instead
```

The flags are `--fuzz N` (fuzz cases per SAFE instance, default 3000), `--no-cbmc`, `--only PREFIX...`,
`--examples` and `--workers N` (default 6). A full run rewrites `dataset/VALIDATION.md` and
`results/validation.json`. A run with `--only` or `--examples` writes neither.

### 2. Run the baselines

```bash
python scripts/run_baselines.py                                  # reference_z3, cbmc, fuzz_random, fuzz_dict
python scripts/run_baselines.py --systems cbmc --budget 1000 --workers 4
```

Records for the systems you re-run are replaced in `results/runs/baselines/records.jsonl`. Records for
the other systems are kept.

### 3. Run local models (Ollama)

```bash
python scripts/run_eval.py --config configs/smoke.yaml --limit 2      # end-to-end smoke test
python scripts/run_eval.py --config configs/local.yaml
python scripts/run_eval.py --config configs/local.yaml --models qwen2.5-coder --approaches direct z3_repair --only T1 T2
```

The `run_eval.py` flags are:

- `--config` (required)
- `--approaches A...`: overrides the config
- `--models SUBSTR...`: substring filter on model names such as `ollama:qwen2.5-coder:7b`
- `--only PREFIX...`: instance-id prefixes
- `--workers N`
- `--limit N`: the first N instances

### 4. Run Gemini

```bash
cp .env.example .env              # then set GEMINI_API_KEY=... in .env
python scripts/list_gemini_models.py --filter flash     # check the ids in configs/gemini.yaml still exist
python scripts/run_eval.py --config configs/gemini.yaml
```

`configs/gemini.yaml` sets `thinking_budget: 0`, so `direct` really answers without hidden reasoning. It
also sets `rpm: 10`, a client-side rate limit shared by all Gemini models in the process. Extra keys in
a model entry are passed to the client as options (see `src/invcheck/llm.py`).

The config contains a commented-out ablation that enables thinking (`thinking_budget: -1`). An
ablation of a model that is already listed must set `label_suffix`, or its records collide with the
base model's records. HTTP 429 and 5xx responses are retried with exponential backoff and honour the
server's `retryDelay`.

### 5. Analyse

```bash
python scripts/analyze.py
```

This reads every `results/runs/*/records.jsonl` except `smoke`. When an
(model, approach, instance, sample) record appears more than once, the latest one is kept.

The script writes CSV tables, `tables.md` and `summary.json` to `results/analysis/`, and figures to
`report/figures/`. Statistics include:

- accuracy with Wilson 95% CIs
- recall and specificity
- pair accuracy (both twins right)
- exact McNemar tests between approaches, Holm-corrected
- a breakdown of Z3 pipeline outcomes
- the effect of each repair round
- post-hoc derived policies: Z3-else-CoT hybrid, and witness-validated verdicts

### 6. Tests

```bash
python -m pytest                    # full suite (~30 s)
python -m pytest -m "not slow"      # skip CBMC and full witness / reference sweeps (~10 s)
```

The tests need `clang`. CBMC tests are skipped if `cbmc` is not installed, and sandbox tests are
skipped off macOS. The tests make no network or LLM calls and never read or write `results/`.
`xfail` tests document known bugs.

## Safety invariants

This is the spec shown to every model (`SAFETY_SPEC` in `dataset.py`). `int` is 32-bit two's
complement and `long long` is 64-bit.

1. **bounds**: every array access uses an index `0 <= i < length`.
2. **div_zero**: the right operand of every `/` and `%` is non-zero.
3. **overflow**: no signed `+`, `-`, `*` or unary `-` overflows, and neither does `INT_MIN / -1` or
   `INT_MIN % -1`. Unsigned wraparound is *not* a violation.
4. **shift**: for `a << b` and `a >> b`, `0 <= b < width` of the promoted left operand. For signed
   `a << b`, `a >= 0` must also hold and the result must be representable.

A function is UNSAFE if *some* input satisfying all preconditions makes it (or any function it calls)
violate an invariant. Otherwise it is SAFE.

## Dataset format

The instances are multi-document YAML, with one document per instance separated by `---`:

| field | meaning |
|---|---|
| `id` | `T<tier>-<BND\|DIV\|OVF\|SHF>-<nn>-<U\|S>` |
| `pair` | the shared id of the two twins (`T1-BND-01`) |
| `label` | `safe` or `unsafe` |
| `tier` | 1 straight-line · 2 branching · 3 loops · 4 inter-procedural / nested loops |
| `category` | `bounds` · `div_zero` · `overflow` · `shift` |
| `twin` | `code`: the twins differ in code. `precondition`: the code is identical and the preconditions differ |
| `tags`, `description`, `bug_explanation` | metadata for analysis. **Never shown to the models** |
| `entry` | the function under review |
| `params` | a list of `{name, type}`. `type` is `int`, `unsigned`, `long long`, or one of these with `[]` for an array. Arrays need `len`, either a literal or an expression over scalar parameters such as `n` or `n * (n + 1) / 2` |
| `requires` | a list of C boolean expressions over scalar parameters (`&&`, `\|\|`, `!`, `INT_MAX`, `INT_MIN`, `UINT_MAX`, `LLONG_MAX`, `LLONG_MIN`). They are evaluated over mathematical integers |
| `elem_requires` | `{array: condition}`. The condition must hold for every element, with `_` standing for the element, e.g. `{a: "-1000 <= _ && _ <= 1000"}` |
| `witness` | required for `unsafe`. A concrete counterexample such as `{buf: [7], n: 1, i: 0}`. Arrays have exactly `len` elements. Values may be ints, or strings like `"INT_MIN"`, `"0x10"`, `"10u"` |
| `code` / `code_from` | the C source. A precondition twin may instead say `code_from: <id>` to reuse its partner's code |
| `reference_z3` | the gold Z3 script, following the protocol below |
| `unwind` | the CBMC loop-unwinding bound (default 40) |

Models see the preconditions as a comment above the code (`Instance.render()`). Array lengths and
element conditions are rendered as extra precondition lines.

## Z3 script protocol

The protocol below is for LLM-written and reference scripts alike (`Z3_PROTOCOL` in `prompts.py`):

1. Declare one Z3 constant per parameter **with exactly the parameter's name**, e.g.
   `n = BitVec('n', 32)` or `a = Array('a', BitVecSort(32), BitVecSort(32))`.
2. Create the solver as **`s = Solver()`**.
3. Add every precondition to `s`.
4. Add one constraint saying that at least one invariant is violated. This is a disjunction over the
   potentially unsafe operations, each conjoined with its path condition.
5. **Do not call `s.check()`**, do not `push()`/`pop()`, and do not print.

The runner (`z3_child.py`) does the rest:

- It looks up the solver as `s`. If there is no `s`, it falls back to `solver`, then to the last
  `Solver`/`Optimize` in scope.
- It calls `check()` with a 30 s solver timeout.
- On `sat`, it reads the parameters back **by name** from the model:
  - bit-vectors are decoded as signed or unsigned according to the C type;
  - arrays are read for their concrete length;
  - parameters missing from the model default to 0 and are recorded in `missing_params`.
- The counterexample is then normalised, checked against the preconditions, and executed under the
  sanitizers. Its `witness_status` is one of `confirmed`, `not_reproduced`, `precondition_violated` or
  `invalid`.
- Script failures are classified, and the classification is fed back in `z3_repair`. The classes are
  `syntax`, `name_error` (with a "Similar existing names" hint for hallucinated z3 functions),
  `z3_api`, `type_error`, `runtime`, `no_solver`, `timeout`, `solver_unknown` and `crash`.

## Sandboxing of generated code

LLM-written Z3 scripts are untrusted. `z3run.execute_script` uses several layers of defence:

- a separate interpreter (`python -I -B`) running `z3_child.py`, so a crash or `os._exit` cannot take
  down the runner;
- a scrubbed environment containing only `PATH`, `PYTHONHASHSEED` and `HOME=/nonexistent`, so no API
  keys are visible;
- a fresh temporary working directory per script, deleted afterwards;
- a 90 s wall-clock timeout, plus rlimits of 120 s CPU and 4 GiB data;
- on macOS, `sandbox-exec` with a profile that denies all network access and all file writes outside
  the temporary directory. On other platforms this layer is absent; the other layers still apply.

C code under test is our own dataset code. It is compiled with `-fsanitize=address,undefined
-fno-sanitize-recover=all` into a driver in `build/harness/` that reads test cases from stdin and stops
at the first sanitizer report.

## How ground truth is validated

`scripts/validate_dataset.py` checks every label with independent methods:

1. The code compiles under ASan+UBSan.
2. **Concrete execution.** For an UNSAFE instance, the hand-written witness satisfies the preconditions
   (checked strictly) and triggers a sanitizer report.
3. **Reference Z3.** The gold encoding returns the gold verdict. For an UNSAFE instance, the
   counterexample it finds also reproduces under the sanitizers.
4. **CBMC.** The bounded model checker returns the gold verdict. It runs a harness that assumes the
   preconditions and checks bounds, pointers, division by zero, signed overflow and shifts. Failures
   inside the harness itself are ignored, and insufficient unwinding counts as UNKNOWN.
5. **Fuzzing.** For a SAFE instance, 3000 precondition-respecting inputs (boundary values and code
   constants) produce no sanitizer report.

Steps 2–5 can each be wrong in isolation. An instance is accepted only when all of them agree with the
label. The current status is in `dataset/VALIDATION.md`. Instances that the oracles cannot decide go to
`dataset/stress/`, outside the evaluation set.

## Reproducibility

- **Deterministic decoding.** Every run uses temperature 0 and a fixed seed (`seed + sample`).
- **Response cache.** Every successful LLM response is cached in `results/cache/llm_cache.sqlite`. The
  key is the provider, model, temperature, max_tokens, seed, options, system prompt and messages.
  Re-running a configuration replays the cached responses without calling the model, and failed calls
  are never cached.
- **Resumable runs.** `run_eval.py` appends one JSON line per finished (model, approach, instance,
  sample) to `results/runs/<run_name>/records.jsonl` and skips triples that are already present. An
  interrupted run can simply be restarted.
- **No ground truth in records.** Records contain no ground truth except the explicit `gold` field
  added by the runner. Prompts never include instance ids, labels, descriptions or reference encodings,
  and a test enforces this.
- **Deterministic tools.** Fuzzing uses fixed seeds. CBMC and the sanitizer harnesses are
  deterministic, and compiled harnesses are cached by content hash in `build/`.
