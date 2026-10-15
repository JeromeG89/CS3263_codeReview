# Generated results tables

_Produced by `scripts/analyze.py`; do not edit by hand._

## Main results

| Model            | Approach               | Accuracy [95% CI]      | Recall (UNSAFE)   | Specificity (SAFE)   | Pair acc.   |   False alarms |   Missed bugs |   Unknown | Witness confirmed   |
|:-----------------|:-----------------------|:-----------------------|:------------------|:---------------------|:------------|---------------:|--------------:|----------:|:--------------------|
| llama3.2:3b      | Direct                 | 54.2% [45.3%, 62.8%]   | 10.0%             | 98.3%                | 8.3%        |              1 |            54 |         0 | 28.6%               |
| llama3.2:3b      | Direct + CoT           | 46.7% [38.0%, 55.6%]   | 33.3%             | 60.0%                | 18.3%       |             24 |            40 |         0 | 15.9%               |
| llama3.2:3b      | LLM→Z3                 | 0.0% [0.0%, 3.1%]      | 0.0%              | 0.0%                 | 0.0%        |              0 |             0 |       120 | –                   |
| llama3.2:3b      | LLM→Z3 guided          | 0.0% [0.0%, 24.3%]     | 0.0%              | 0.0%                 | 0.0%        |              0 |             0 |        12 | –                   |
| qwen2.5-coder:7b | Direct                 | 55.8% [46.9%, 64.4%]   | 25.0%             | 86.7%                | 13.3%       |              8 |            45 |         0 | 47.8%               |
| qwen2.5-coder:7b | Direct + CoT           | 56.7% [47.7%, 65.2%]   | 20.0%             | 93.3%                | 16.7%       |              4 |            48 |         0 | 62.5%               |
| qwen2.5-coder:7b | LLM→Z3                 | 40.0% [31.7%, 48.9%]   | 45.0%             | 35.0%                | 21.7%       |             15 |             9 |        48 | 38.1%               |
| qwen2.5-coder:7b | LLM→Z3 guided          | 23.3% [16.7%, 31.7%]   | 28.3%             | 18.3%                | 10.0%       |              9 |            11 |        72 | 42.3%               |
| qwen2.5-coder:7b | LLM→Z3 guided + repair | 27.5% [20.3%, 36.1%]   | 33.3%             | 21.7%                | 13.3%       |             14 |            12 |        61 | 35.3%               |
| —                | Gold Z3 (Claude)       | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | 100.0%              |
| —                | CBMC                   | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | –                   |
| —                | Fuzz (dictionary)      | 98.3% [94.1%, 99.5%]   | 96.7%             | 100.0%               | 96.7%       |              0 |             2 |         0 | 100.0%              |
| —                | Fuzz (random)          | 85.0% [77.5%, 90.3%]   | 70.0%             | 100.0%               | 70.0%       |              0 |            18 |         0 | 100.0%              |

## Derived policies (post hoc, no extra model calls)

| Model            | Approach                     | Accuracy [95% CI]    | Recall (UNSAFE)   | Specificity (SAFE)   | Pair acc.   |   False alarms |   Missed bugs |   Unknown | Witness confirmed   |
|:-----------------|:-----------------------------|:---------------------|:------------------|:---------------------|:------------|---------------:|--------------:|----------:|:--------------------|
| llama3.2:3b      | Hybrid: LLM→Z3, else CoT     | 46.7% [38.0%, 55.6%] | 33.3%             | 60.0%                | 18.3%       |             24 |            40 |         0 | –                   |
| llama3.2:3b      | CoT, witness-validated       | 55.8% [46.9%, 64.4%] | 11.7%             | 100.0%               | 11.7%       |              0 |            53 |         0 | 100.0%              |
| llama3.2:3b      | Direct, witness-validated    | 51.7% [42.8%, 60.4%] | 3.3%              | 100.0%               | 3.3%        |              0 |            58 |         0 | 100.0%              |
| llama3.2:3b      | LLM→Z3, witness-validated    | 0.0% [0.0%, 3.1%]    | 0.0%              | 0.0%                 | 0.0%        |              0 |             0 |       120 | –                   |
| llama3.2:3b      | Z3 guided, witness-validated | 0.0% [0.0%, 24.3%]   | 0.0%              | 0.0%                 | 0.0%        |              0 |             0 |        12 | –                   |
| qwen2.5-coder:7b | Hybrid: LLM→Z3, else CoT     | 63.3% [54.4%, 71.4%] | 53.3%             | 73.3%                | 35.0%       |             16 |            28 |         0 | 33.3%               |
| qwen2.5-coder:7b | Hybrid: Z3+repair, else CoT  | 56.7% [47.7%, 65.2%] | 40.0%             | 73.3%                | 26.7%       |             16 |            36 |         0 | 30.0%               |
| qwen2.5-coder:7b | CoT, witness-validated       | 58.3% [49.4%, 66.8%] | 16.7%             | 100.0%               | 16.7%       |              0 |            50 |         0 | 100.0%              |
| qwen2.5-coder:7b | Z3+repair, witness-validated | 32.5% [24.8%, 41.3%] | 20.0%             | 45.0%                | 16.7%       |              0 |            20 |        61 | 100.0%              |
| qwen2.5-coder:7b | Direct, witness-validated    | 59.2% [50.2%, 67.5%] | 18.3%             | 100.0%               | 18.3%       |              0 |            49 |         0 | 100.0%              |
| qwen2.5-coder:7b | LLM→Z3, witness-validated    | 43.3% [34.8%, 52.3%] | 26.7%             | 60.0%                | 23.3%       |              0 |            20 |        48 | 100.0%              |
| qwen2.5-coder:7b | Z3 guided, witness-validated | 25.8% [18.8%, 34.3%] | 18.3%             | 33.3%                | 13.3%       |              0 |            17 |        72 | 100.0%              |

## Accuracy by tier

| model            | approach               |   T1 |     T2 |     T3 |     T4 |
|:-----------------|:-----------------------|-----:|-------:|-------:|-------:|
| llama3.2:3b      | Direct                 | 0.55 |   0.55 |   0.54 |   0.50 |
| llama3.2:3b      | Direct + CoT           | 0.47 |   0.45 |   0.50 |   0.44 |
| llama3.2:3b      | LLM→Z3                 | 0.00 |   0.00 |   0.00 |   0.00 |
| llama3.2:3b      | LLM→Z3 guided          | 0.00 | nan    | nan    | nan    |
| qwen2.5-coder:7b | Direct                 | 0.57 |   0.53 |   0.58 |   0.56 |
| qwen2.5-coder:7b | Direct + CoT           | 0.55 |   0.58 |   0.62 |   0.50 |
| qwen2.5-coder:7b | LLM→Z3                 | 0.68 |   0.39 |   0.19 |   0.06 |
| qwen2.5-coder:7b | LLM→Z3 guided          | 0.42 |   0.24 |   0.08 |   0.00 |
| qwen2.5-coder:7b | LLM→Z3 guided + repair | 0.47 |   0.32 |   0.08 |   0.00 |

## Accuracy by bug class

| model            | approach               |   bounds |   div_zero |   overflow |   shift |
|:-----------------|:-----------------------|---------:|-----------:|-----------:|--------:|
| llama3.2:3b      | Direct                 |     0.55 |       0.58 |       0.53 |    0.50 |
| llama3.2:3b      | Direct + CoT           |     0.47 |       0.35 |       0.50 |    0.55 |
| llama3.2:3b      | LLM→Z3                 |     0.00 |       0.00 |       0.00 |    0.00 |
| llama3.2:3b      | LLM→Z3 guided          |     0.00 |       0.00 |     nan    |  nan    |
| qwen2.5-coder:7b | Direct                 |     0.55 |       0.62 |       0.56 |    0.50 |
| qwen2.5-coder:7b | Direct + CoT           |     0.55 |       0.62 |       0.61 |    0.45 |
| qwen2.5-coder:7b | LLM→Z3                 |     0.45 |       0.42 |       0.31 |    0.45 |
| qwen2.5-coder:7b | LLM→Z3 guided          |     0.24 |       0.15 |       0.22 |    0.35 |
| qwen2.5-coder:7b | LLM→Z3 guided + repair |     0.24 |       0.19 |       0.33 |    0.35 |
| —                | Gold Z3 (Claude)       |     1.00 |       1.00 |       1.00 |    1.00 |
| —                | CBMC                   |     1.00 |       1.00 |       1.00 |    1.00 |
| —                | Fuzz (dictionary)      |     1.00 |       1.00 |       0.94 |    1.00 |
| —                | Fuzz (random)          |     1.00 |       0.92 |       0.72 |    0.70 |

## Pair accuracy by twin type (code fix vs precondition change)

| model            | approach               |   code |   precondition |
|:-----------------|:-----------------------|-------:|---------------:|
| llama3.2:3b      | Direct                 |   0.14 |           0.00 |
| llama3.2:3b      | Direct + CoT           |   0.19 |           0.17 |
| llama3.2:3b      | LLM→Z3                 |   0.00 |           0.00 |
| llama3.2:3b      | LLM→Z3 guided          |   0.00 |           0.00 |
| qwen2.5-coder:7b | Direct                 |   0.16 |           0.09 |
| qwen2.5-coder:7b | Direct + CoT           |   0.22 |           0.09 |
| qwen2.5-coder:7b | LLM→Z3                 |   0.14 |           0.35 |
| qwen2.5-coder:7b | LLM→Z3 guided          |   0.05 |           0.17 |
| qwen2.5-coder:7b | LLM→Z3 guided + repair |   0.05 |           0.26 |

## McNemar exact tests (paired by instance, Holm-corrected)

| model            | A          | B                  |   n |   acc_A |   acc_B |   A_only_correct |   B_only_correct |     p |   p_holm |
|:-----------------|:-----------|:-------------------|----:|--------:|--------:|-----------------:|-----------------:|------:|---------:|
| llama3.2:3b      | direct     | direct_cot         | 120 |   0.542 |   0.467 |               27 |               18 | 0.233 |    1.000 |
| llama3.2:3b      | direct     | z3                 | 120 |   0.542 |   0.000 |               65 |                0 | 0.000 |    0.000 |
| llama3.2:3b      | z3         | z3_guided          |  12 |   0.000 |   0.000 |                0 |                0 | 1.000 |    1.000 |
| llama3.2:3b      | direct     | hybrid_z3_else_cot | 120 |   0.542 |   0.467 |               27 |               18 | 0.233 |    1.000 |
| llama3.2:3b      | direct_cot | hybrid_z3_else_cot | 120 |   0.467 |   0.467 |                0 |                0 | 1.000 |    1.000 |
| qwen2.5-coder:7b | direct     | direct_cot         | 120 |   0.558 |   0.567 |               14 |               15 | 1.000 |    1.000 |
| qwen2.5-coder:7b | direct     | z3                 | 120 |   0.558 |   0.400 |               40 |               21 | 0.020 |    0.184 |
| qwen2.5-coder:7b | direct_cot | z3_repair          | 120 |   0.567 |   0.275 |               49 |               14 | 0.000 |    0.000 |
| qwen2.5-coder:7b | z3         | z3_guided          | 120 |   0.400 |   0.233 |               28 |                8 | 0.001 |    0.012 |
| qwen2.5-coder:7b | z3_guided  | z3_repair          | 120 |   0.233 |   0.275 |                0 |                5 | 0.062 |    0.500 |
| qwen2.5-coder:7b | direct     | z3_repair          | 120 |   0.558 |   0.275 |               50 |               16 | 0.000 |    0.000 |
| qwen2.5-coder:7b | direct     | hybrid_z3_else_cot | 120 |   0.558 |   0.633 |               17 |               26 | 0.222 |    1.000 |
| qwen2.5-coder:7b | direct_cot | hybrid_z3_else_cot | 120 |   0.567 |   0.633 |               16 |               24 | 0.268 |    1.000 |

## Model comparison per approach (McNemar)

| approach   | A           | B                |   n |   acc_A |   acc_B |     p |
|:-----------|:------------|:-----------------|----:|--------:|--------:|------:|
| direct     | llama3.2:3b | qwen2.5-coder:7b | 120 |   0.542 |   0.558 | 0.832 |
| direct_cot | llama3.2:3b | qwen2.5-coder:7b | 120 |   0.467 |   0.567 | 0.119 |
| z3         | llama3.2:3b | qwen2.5-coder:7b | 120 |   0.000 |   0.400 | 0.000 |
| z3_guided  | llama3.2:3b | qwen2.5-coder:7b |  12 |   0.000 |   0.667 | 0.008 |

## Z3 pipeline outcomes (final attempt)

| model            | approach   |   bug found (cex confirmed) |   bug found (cex not reproduced) |   error: Z3 sort/API misuse |   error: hallucinated API |   error: runaway output (token limit) |   error: runtime |   error: syntax |   error: type/operator misuse |   false alarm (spurious cex) |   missed bug (unsat) |   proved safe |
|:-----------------|:-----------|----------------------------:|---------------------------------:|----------------------------:|--------------------------:|--------------------------------------:|-----------------:|----------------:|------------------------------:|-----------------------------:|---------------------:|--------------:|
| llama3.2:3b      | z3         |                           0 |                                0 |                           0 |                         0 |                                    84 |               31 |               5 |                             0 |                            0 |                    0 |             0 |
| llama3.2:3b      | z3_guided  |                           0 |                                0 |                           1 |                         2 |                                     8 |                0 |               0 |                             1 |                            0 |                    0 |             0 |
| qwen2.5-coder:7b | z3         |                          16 |                               11 |                           9 |                        11 |                                     8 |                0 |               3 |                            17 |                           15 |                    9 |            21 |
| qwen2.5-coder:7b | z3_guided  |                          11 |                                6 |                           6 |                        30 |                                    12 |                1 |               7 |                            16 |                            9 |                   11 |            11 |
| qwen2.5-coder:7b | z3_repair  |                          12 |                                8 |                           8 |                        27 |                                    12 |                0 |               3 |                            11 |                           14 |                   12 |            13 |

## Effect of repair rounds

| model            |   k |   accuracy |   executable |
|:-----------------|----:|-----------:|-------------:|
| qwen2.5-coder:7b |   0 |       0.23 |         0.40 |
| qwen2.5-coder:7b |   1 |       0.27 |         0.48 |
| qwen2.5-coder:7b |   2 |       0.27 |         0.48 |
| qwen2.5-coder:7b |   3 |       0.28 |         0.49 |

## Static features of the generated Z3 code (final attempt)

| model            | approach   |   n |   acc |   bitvec |   int_sort |   srem |   ovf_helpers |   push_pop |   lines |
|:-----------------|:-----------|----:|------:|---------:|-----------:|-------:|--------------:|-----------:|--------:|
| llama3.2:3b      | z3         | 120 |  0.00 |     0.69 |       1.00 |   0.00 |          0.00 |       0.01 |  122.00 |
| llama3.2:3b      | z3_guided  |  12 |  0.00 |     0.83 |       0.33 |   0.00 |          0.83 |       0.00 |   83.00 |
| qwen2.5-coder:7b | z3         | 120 |  0.40 |     0.07 |       0.95 |   0.00 |          0.00 |       0.00 |   31.00 |
| qwen2.5-coder:7b | z3_guided  | 120 |  0.23 |     1.00 |       0.00 |   0.00 |          0.62 |       0.00 |   25.00 |
| qwen2.5-coder:7b | z3_repair  | 120 |  0.28 |     1.00 |       0.00 |   0.00 |          0.62 |       0.00 |   25.00 |

### Accuracy conditioned on code features (all models, all Z3 approaches)

| feature               | present   |   n |   accuracy |
|:----------------------|:----------|----:|-----------:|
| uses_bitvec           | True      | 342 |       0.19 |
| uses_bitvec           | False     | 150 |       0.30 |
| uses_int_sort         | True      | 238 |       0.19 |
| uses_int_sort         | False     | 254 |       0.25 |
| uses_overflow_helpers | True      | 158 |       0.18 |
| uses_overflow_helpers | False     | 334 |       0.24 |
| uses_srem             | False     | 492 |       0.22 |

## Cost

| model            | approach               |   mean_llm_calls |   mean_out_tokens |   mean_wall_s |
|:-----------------|:-----------------------|-----------------:|------------------:|--------------:|
| llama3.2:3b      | Direct                 |             1.00 |             41.53 |          2.73 |
| llama3.2:3b      | Direct + CoT           |             1.00 |            598.71 |         11.07 |
| llama3.2:3b      | LLM→Z3                 |             1.00 |           2355.13 |         44.76 |
| llama3.2:3b      | LLM→Z3 guided          |             1.00 |           2251.08 |         46.89 |
| qwen2.5-coder:7b | Direct                 |             1.00 |             60.76 |          3.32 |
| qwen2.5-coder:7b | Direct + CoT           |             1.00 |            661.32 |         27.29 |
| qwen2.5-coder:7b | LLM→Z3                 |             1.00 |            537.83 |         21.28 |
| qwen2.5-coder:7b | LLM→Z3 guided          |             1.00 |            567.18 |         23.66 |
| qwen2.5-coder:7b | LLM→Z3 guided + repair |             3.11 |           2107.91 |         66.65 |

Tools (mean wall-clock seconds per instance):

| approach          |   mean_wall_s |
|:------------------|--------------:|
| Gold Z3 (Claude)  |          0.52 |
| CBMC              |          1.71 |
| Fuzz (dictionary) |          2.16 |
| Fuzz (random)     |          3.63 |
