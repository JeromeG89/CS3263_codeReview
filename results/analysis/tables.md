# Generated results tables

_Produced by `scripts/analyze.py`; do not edit by hand._

## Main results

| Model                 | Approach               | Accuracy [95% CI]      | Recall (UNSAFE)   | Specificity (SAFE)   | Pair acc.   |   False alarms |   Missed bugs |   Unknown | Witness confirmed   |
|:----------------------|:-----------------------|:-----------------------|:------------------|:---------------------|:------------|---------------:|--------------:|----------:|:--------------------|
| gemini-3.5-flash-lite | Direct                 | 76.7% [68.3%, 83.3%]   | 78.3%             | 75.0%                | 55.0%       |             15 |            13 |         0 | 67.7%               |
| gemini-3.5-flash-lite | Direct + CoT           | 98.3% [94.1%, 99.5%]   | 96.7%             | 100.0%               | 96.7%       |              0 |             2 |         0 | 100.0%              |
| gemini-3.5-flash-lite | LLM→Z3                 | 78.3% [70.1%, 84.8%]   | 78.3%             | 78.3%                | 65.0%       |              1 |             2 |        23 | 97.9%               |
| gemini-3.5-flash-lite | LLM→Z3 guided          | 82.5% [74.7%, 88.3%]   | 83.3%             | 81.7%                | 70.0%       |              2 |             0 |        19 | 96.2%               |
| gemini-3.5-flash-lite | LLM→Z3 guided + repair | 97.5% [92.9%, 99.1%]   | 98.3%             | 96.7%                | 95.0%       |              0 |             1 |         2 | 100.0%              |
| gemini-3.8-flash      | Direct                 | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | 98.3%               |
| gemini-3.8-flash      | Direct + CoT           | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | 98.3%               |
| gemini-3.8-flash      | LLM→Z3                 | 80.8% [72.9%, 86.9%]   | 85.0%             | 76.7%                | 70.0%       |              0 |             2 |        21 | 100.0%              |
| gemini-3.8-flash      | LLM→Z3 guided          | 95.8% [90.6%, 98.2%]   | 98.3%             | 93.3%                | 93.3%       |              0 |             0 |         5 | 100.0%              |
| gemini-3.8-flash      | LLM→Z3 guided + repair | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | 100.0%              |
| llama3.2:3b           | Direct                 | 54.2% [45.3%, 62.8%]   | 10.0%             | 98.3%                | 8.3%        |              1 |            54 |         0 | 28.6%               |
| llama3.2:3b           | Direct + CoT           | 46.7% [38.0%, 55.6%]   | 33.3%             | 60.0%                | 18.3%       |             24 |            40 |         0 | 15.9%               |
| llama3.2:3b           | LLM→Z3                 | 0.0% [0.0%, 3.1%]      | 0.0%              | 0.0%                 | 0.0%        |              0 |             0 |       120 | –                   |
| llama3.2:3b           | LLM→Z3 guided          | 1.7% [0.5%, 5.9%]      | 3.3%              | 0.0%                 | 0.0%        |              1 |             0 |       117 | 0.0%                |
| qwen2.5-coder:7b      | Direct                 | 55.8% [46.9%, 64.4%]   | 25.0%             | 86.7%                | 13.3%       |              8 |            45 |         0 | 47.8%               |
| qwen2.5-coder:7b      | Direct + CoT           | 56.7% [47.7%, 65.2%]   | 20.0%             | 93.3%                | 16.7%       |              4 |            48 |         0 | 62.5%               |
| qwen2.5-coder:7b      | LLM→Z3                 | 40.0% [31.7%, 48.9%]   | 45.0%             | 35.0%                | 21.7%       |             15 |             9 |        48 | 38.1%               |
| qwen2.5-coder:7b      | LLM→Z3 guided          | 23.3% [16.7%, 31.7%]   | 28.3%             | 18.3%                | 10.0%       |              9 |            11 |        72 | 42.3%               |
| qwen2.5-coder:7b      | LLM→Z3 guided + repair | 27.5% [20.3%, 36.1%]   | 33.3%             | 21.7%                | 13.3%       |             14 |            12 |        61 | 35.3%               |
| —                     | Gold Z3 (Claude)       | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | 100.0%              |
| —                     | CBMC                   | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | –                   |
| —                     | Fuzz (dictionary)      | 98.3% [94.1%, 99.5%]   | 96.7%             | 100.0%               | 96.7%       |              0 |             2 |         0 | 100.0%              |
| —                     | Fuzz (random)          | 85.0% [77.5%, 90.3%]   | 70.0%             | 100.0%               | 70.0%       |              0 |            18 |         0 | 100.0%              |

## Derived policies (post hoc, no extra model calls)

| Model                 | Approach                     | Accuracy [95% CI]      | Recall (UNSAFE)   | Specificity (SAFE)   | Pair acc.   |   False alarms |   Missed bugs |   Unknown | Witness confirmed   |
|:----------------------|:-----------------------------|:-----------------------|:------------------|:---------------------|:------------|---------------:|--------------:|----------:|:--------------------|
| gemini-3.5-flash-lite | Hybrid: LLM→Z3, else CoT     | 96.7% [91.7%, 98.7%]   | 95.0%             | 98.3%                | 93.3%       |              1 |             3 |         0 | 81.0%               |
| gemini-3.5-flash-lite | Hybrid: Z3+repair, else CoT  | 99.2% [95.4%, 99.9%]   | 98.3%             | 100.0%               | 98.3%       |              0 |             1 |         0 | 100.0%              |
| gemini-3.5-flash-lite | CoT, witness-validated       | 98.3% [94.1%, 99.5%]   | 96.7%             | 100.0%               | 96.7%       |              0 |             2 |         0 | 100.0%              |
| gemini-3.5-flash-lite | Z3+repair, witness-validated | 97.5% [92.9%, 99.1%]   | 98.3%             | 96.7%                | 95.0%       |              0 |             1 |         2 | 100.0%              |
| gemini-3.5-flash-lite | Direct, witness-validated    | 85.0% [77.5%, 90.3%]   | 70.0%             | 100.0%               | 70.0%       |              0 |            18 |         0 | 100.0%              |
| gemini-3.5-flash-lite | LLM→Z3, witness-validated    | 79.2% [71.1%, 85.5%]   | 78.3%             | 80.0%                | 66.7%       |              0 |             2 |        23 | 100.0%              |
| gemini-3.5-flash-lite | Z3 guided, witness-validated | 84.2% [76.6%, 89.6%]   | 83.3%             | 85.0%                | 73.3%       |              0 |             0 |        19 | 100.0%              |
| gemini-3.8-flash      | Hybrid: LLM→Z3, else CoT     | 98.3% [94.1%, 99.5%]   | 96.7%             | 100.0%               | 96.7%       |              0 |             2 |         0 | 87.9%               |
| gemini-3.8-flash      | Hybrid: Z3+repair, else CoT  | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | 100.0%              |
| gemini-3.8-flash      | CoT, witness-validated       | 99.2% [95.4%, 99.9%]   | 98.3%             | 100.0%               | 98.3%       |              0 |             1 |         0 | 100.0%              |
| gemini-3.8-flash      | Z3+repair, witness-validated | 100.0% [96.9%, 100.0%] | 100.0%            | 100.0%               | 100.0%      |              0 |             0 |         0 | 100.0%              |
| gemini-3.8-flash      | Direct, witness-validated    | 99.2% [95.4%, 99.9%]   | 98.3%             | 100.0%               | 98.3%       |              0 |             1 |         0 | 100.0%              |
| gemini-3.8-flash      | LLM→Z3, witness-validated    | 80.8% [72.9%, 86.9%]   | 85.0%             | 76.7%                | 70.0%       |              0 |             2 |        21 | 100.0%              |
| gemini-3.8-flash      | Z3 guided, witness-validated | 95.8% [90.6%, 98.2%]   | 98.3%             | 93.3%                | 93.3%       |              0 |             0 |         5 | 100.0%              |
| llama3.2:3b           | Hybrid: LLM→Z3, else CoT     | 46.7% [38.0%, 55.6%]   | 33.3%             | 60.0%                | 18.3%       |             24 |            40 |         0 | –                   |
| llama3.2:3b           | CoT, witness-validated       | 55.8% [46.9%, 64.4%]   | 11.7%             | 100.0%               | 11.7%       |              0 |            53 |         0 | 100.0%              |
| llama3.2:3b           | Direct, witness-validated    | 51.7% [42.8%, 60.4%]   | 3.3%              | 100.0%               | 3.3%        |              0 |            58 |         0 | 100.0%              |
| llama3.2:3b           | LLM→Z3, witness-validated    | 0.0% [0.0%, 3.1%]      | 0.0%              | 0.0%                 | 0.0%        |              0 |             0 |       120 | –                   |
| llama3.2:3b           | Z3 guided, witness-validated | 0.8% [0.1%, 4.6%]      | 0.0%              | 1.7%                 | 0.0%        |              0 |             2 |       117 | –                   |
| qwen2.5-coder:7b      | Hybrid: LLM→Z3, else CoT     | 63.3% [54.4%, 71.4%]   | 53.3%             | 73.3%                | 35.0%       |             16 |            28 |         0 | 33.3%               |
| qwen2.5-coder:7b      | Hybrid: Z3+repair, else CoT  | 56.7% [47.7%, 65.2%]   | 40.0%             | 73.3%                | 26.7%       |             16 |            36 |         0 | 30.0%               |
| qwen2.5-coder:7b      | CoT, witness-validated       | 58.3% [49.4%, 66.8%]   | 16.7%             | 100.0%               | 16.7%       |              0 |            50 |         0 | 100.0%              |
| qwen2.5-coder:7b      | Z3+repair, witness-validated | 32.5% [24.8%, 41.3%]   | 20.0%             | 45.0%                | 16.7%       |              0 |            20 |        61 | 100.0%              |
| qwen2.5-coder:7b      | Direct, witness-validated    | 59.2% [50.2%, 67.5%]   | 18.3%             | 100.0%               | 18.3%       |              0 |            49 |         0 | 100.0%              |
| qwen2.5-coder:7b      | LLM→Z3, witness-validated    | 43.3% [34.8%, 52.3%]   | 26.7%             | 60.0%                | 23.3%       |              0 |            20 |        48 | 100.0%              |
| qwen2.5-coder:7b      | Z3 guided, witness-validated | 25.8% [18.8%, 34.3%]   | 18.3%             | 33.3%                | 13.3%       |              0 |            17 |        72 | 100.0%              |

## Accuracy by tier

| model                 | approach               |   T1 |   T2 |   T3 |   T4 |
|:----------------------|:-----------------------|-----:|-----:|-----:|-----:|
| gemini-3.5-flash-lite | Direct                 | 0.80 | 0.76 | 0.81 | 0.62 |
| gemini-3.5-flash-lite | Direct + CoT           | 0.97 | 1.00 | 1.00 | 0.94 |
| gemini-3.5-flash-lite | LLM→Z3                 | 0.80 | 0.92 | 0.65 | 0.62 |
| gemini-3.5-flash-lite | LLM→Z3 guided          | 0.90 | 0.87 | 0.69 | 0.75 |
| gemini-3.5-flash-lite | LLM→Z3 guided + repair | 1.00 | 1.00 | 0.92 | 0.94 |
| gemini-3.8-flash      | Direct                 | 1.00 | 1.00 | 1.00 | 1.00 |
| gemini-3.8-flash      | Direct + CoT           | 1.00 | 1.00 | 1.00 | 1.00 |
| gemini-3.8-flash      | LLM→Z3                 | 0.90 | 0.89 | 0.65 | 0.62 |
| gemini-3.8-flash      | LLM→Z3 guided          | 1.00 | 1.00 | 0.85 | 0.94 |
| gemini-3.8-flash      | LLM→Z3 guided + repair | 1.00 | 1.00 | 1.00 | 1.00 |
| llama3.2:3b           | Direct                 | 0.55 | 0.55 | 0.54 | 0.50 |
| llama3.2:3b           | Direct + CoT           | 0.47 | 0.45 | 0.50 | 0.44 |
| llama3.2:3b           | LLM→Z3                 | 0.00 | 0.00 | 0.00 | 0.00 |
| llama3.2:3b           | LLM→Z3 guided          | 0.00 | 0.03 | 0.04 | 0.00 |
| qwen2.5-coder:7b      | Direct                 | 0.57 | 0.53 | 0.58 | 0.56 |
| qwen2.5-coder:7b      | Direct + CoT           | 0.55 | 0.58 | 0.62 | 0.50 |
| qwen2.5-coder:7b      | LLM→Z3                 | 0.68 | 0.39 | 0.19 | 0.06 |
| qwen2.5-coder:7b      | LLM→Z3 guided          | 0.42 | 0.24 | 0.08 | 0.00 |
| qwen2.5-coder:7b      | LLM→Z3 guided + repair | 0.47 | 0.32 | 0.08 | 0.00 |

## Accuracy by bug class

| model                 | approach               |   bounds |   div_zero |   overflow |   shift |
|:----------------------|:-----------------------|---------:|-----------:|-----------:|--------:|
| gemini-3.5-flash-lite | Direct                 |     0.89 |       0.81 |       0.61 |    0.75 |
| gemini-3.5-flash-lite | Direct + CoT           |     1.00 |       0.96 |       0.97 |    1.00 |
| gemini-3.5-flash-lite | LLM→Z3                 |     0.79 |       0.81 |       0.83 |    0.65 |
| gemini-3.5-flash-lite | LLM→Z3 guided          |     0.84 |       0.77 |       0.92 |    0.70 |
| gemini-3.5-flash-lite | LLM→Z3 guided + repair |     0.95 |       1.00 |       1.00 |    0.95 |
| gemini-3.8-flash      | Direct                 |     1.00 |       1.00 |       1.00 |    1.00 |
| gemini-3.8-flash      | Direct + CoT           |     1.00 |       1.00 |       1.00 |    1.00 |
| gemini-3.8-flash      | LLM→Z3                 |     0.71 |       0.92 |       0.81 |    0.85 |
| gemini-3.8-flash      | LLM→Z3 guided          |     0.95 |       1.00 |       0.92 |    1.00 |
| gemini-3.8-flash      | LLM→Z3 guided + repair |     1.00 |       1.00 |       1.00 |    1.00 |
| llama3.2:3b           | Direct                 |     0.55 |       0.58 |       0.53 |    0.50 |
| llama3.2:3b           | Direct + CoT           |     0.47 |       0.35 |       0.50 |    0.55 |
| llama3.2:3b           | LLM→Z3                 |     0.00 |       0.00 |       0.00 |    0.00 |
| llama3.2:3b           | LLM→Z3 guided          |     0.03 |       0.00 |       0.03 |    0.00 |
| qwen2.5-coder:7b      | Direct                 |     0.55 |       0.62 |       0.56 |    0.50 |
| qwen2.5-coder:7b      | Direct + CoT           |     0.55 |       0.62 |       0.61 |    0.45 |
| qwen2.5-coder:7b      | LLM→Z3                 |     0.45 |       0.42 |       0.31 |    0.45 |
| qwen2.5-coder:7b      | LLM→Z3 guided          |     0.24 |       0.15 |       0.22 |    0.35 |
| qwen2.5-coder:7b      | LLM→Z3 guided + repair |     0.24 |       0.19 |       0.33 |    0.35 |
| —                     | Gold Z3 (Claude)       |     1.00 |       1.00 |       1.00 |    1.00 |
| —                     | CBMC                   |     1.00 |       1.00 |       1.00 |    1.00 |
| —                     | Fuzz (dictionary)      |     1.00 |       1.00 |       0.94 |    1.00 |
| —                     | Fuzz (random)          |     1.00 |       0.92 |       0.72 |    0.70 |

## Pair accuracy by twin type (code fix vs precondition change)

| model                 | approach               |   code |   precondition |
|:----------------------|:-----------------------|-------:|---------------:|
| gemini-3.5-flash-lite | Direct                 |   0.54 |           0.57 |
| gemini-3.5-flash-lite | Direct + CoT           |   0.97 |           0.96 |
| gemini-3.5-flash-lite | LLM→Z3                 |   0.68 |           0.61 |
| gemini-3.5-flash-lite | LLM→Z3 guided          |   0.70 |           0.70 |
| gemini-3.5-flash-lite | LLM→Z3 guided + repair |   0.95 |           0.96 |
| gemini-3.8-flash      | Direct                 |   1.00 |           1.00 |
| gemini-3.8-flash      | Direct + CoT           |   1.00 |           1.00 |
| gemini-3.8-flash      | LLM→Z3                 |   0.70 |           0.70 |
| gemini-3.8-flash      | LLM→Z3 guided          |   0.95 |           0.91 |
| gemini-3.8-flash      | LLM→Z3 guided + repair |   1.00 |           1.00 |
| llama3.2:3b           | Direct                 |   0.14 |           0.00 |
| llama3.2:3b           | Direct + CoT           |   0.19 |           0.17 |
| llama3.2:3b           | LLM→Z3                 |   0.00 |           0.00 |
| llama3.2:3b           | LLM→Z3 guided          |   0.00 |           0.00 |
| qwen2.5-coder:7b      | Direct                 |   0.16 |           0.09 |
| qwen2.5-coder:7b      | Direct + CoT           |   0.22 |           0.09 |
| qwen2.5-coder:7b      | LLM→Z3                 |   0.14 |           0.35 |
| qwen2.5-coder:7b      | LLM→Z3 guided          |   0.05 |           0.17 |
| qwen2.5-coder:7b      | LLM→Z3 guided + repair |   0.05 |           0.26 |

## McNemar exact tests (paired by instance, Holm-corrected)

| model                 | A          | B                  |   n |   acc_A |   acc_B |   A_only_correct |   B_only_correct |     p |   p_holm |
|:----------------------|:-----------|:-------------------|----:|--------:|--------:|-----------------:|-----------------:|------:|---------:|
| gemini-3.5-flash-lite | direct     | direct_cot         | 120 |   0.767 |   0.983 |                0 |               26 | 0.000 |    0.000 |
| gemini-3.5-flash-lite | direct     | z3                 | 120 |   0.767 |   0.783 |               17 |               19 | 0.868 |    1.000 |
| gemini-3.5-flash-lite | direct_cot | z3_repair          | 120 |   0.983 |   0.975 |                3 |                2 | 1.000 |    1.000 |
| gemini-3.5-flash-lite | z3         | z3_guided          | 120 |   0.783 |   0.825 |               14 |               19 | 0.487 |    1.000 |
| gemini-3.5-flash-lite | z3_guided  | z3_repair          | 120 |   0.825 |   0.975 |                0 |               18 | 0.000 |    0.000 |
| gemini-3.5-flash-lite | direct     | z3_repair          | 120 |   0.767 |   0.975 |                2 |               27 | 0.000 |    0.000 |
| gemini-3.5-flash-lite | direct     | hybrid_z3_else_cot | 120 |   0.767 |   0.967 |                2 |               26 | 0.000 |    0.000 |
| gemini-3.5-flash-lite | direct_cot | hybrid_z3_else_cot | 120 |   0.983 |   0.967 |                3 |                1 | 0.625 |    1.000 |
| gemini-3.8-flash      | direct     | direct_cot         | 120 |   1.000 |   1.000 |                0 |                0 | 1.000 |    1.000 |
| gemini-3.8-flash      | direct     | z3                 | 120 |   1.000 |   0.808 |               23 |                0 | 0.000 |    0.000 |
| gemini-3.8-flash      | direct_cot | z3_repair          | 120 |   1.000 |   1.000 |                0 |                0 | 1.000 |    1.000 |
| gemini-3.8-flash      | z3         | z3_guided          | 120 |   0.808 |   0.958 |                2 |               20 | 0.000 |    0.003 |
| gemini-3.8-flash      | z3_guided  | z3_repair          | 120 |   0.958 |   1.000 |                0 |                5 | 0.062 |    1.000 |
| gemini-3.8-flash      | direct     | z3_repair          | 120 |   1.000 |   1.000 |                0 |                0 | 1.000 |    1.000 |
| gemini-3.8-flash      | direct     | hybrid_z3_else_cot | 120 |   1.000 |   0.983 |                2 |                0 | 0.500 |    1.000 |
| gemini-3.8-flash      | direct_cot | hybrid_z3_else_cot | 120 |   1.000 |   0.983 |                2 |                0 | 0.500 |    1.000 |
| llama3.2:3b           | direct     | direct_cot         | 120 |   0.542 |   0.467 |               27 |               18 | 0.233 |    1.000 |
| llama3.2:3b           | direct     | z3                 | 120 |   0.542 |   0.000 |               65 |                0 | 0.000 |    0.000 |
| llama3.2:3b           | z3         | z3_guided          | 120 |   0.000 |   0.017 |                0 |                2 | 0.500 |    1.000 |
| llama3.2:3b           | direct     | hybrid_z3_else_cot | 120 |   0.542 |   0.467 |               27 |               18 | 0.233 |    1.000 |
| llama3.2:3b           | direct_cot | hybrid_z3_else_cot | 120 |   0.467 |   0.467 |                0 |                0 | 1.000 |    1.000 |
| qwen2.5-coder:7b      | direct     | direct_cot         | 120 |   0.558 |   0.567 |               14 |               15 | 1.000 |    1.000 |
| qwen2.5-coder:7b      | direct     | z3                 | 120 |   0.558 |   0.400 |               40 |               21 | 0.020 |    0.388 |
| qwen2.5-coder:7b      | direct_cot | z3_repair          | 120 |   0.567 |   0.275 |               49 |               14 | 0.000 |    0.000 |
| qwen2.5-coder:7b      | z3         | z3_guided          | 120 |   0.400 |   0.233 |               28 |                8 | 0.001 |    0.024 |
| qwen2.5-coder:7b      | z3_guided  | z3_repair          | 120 |   0.233 |   0.275 |                0 |                5 | 0.062 |    1.000 |
| qwen2.5-coder:7b      | direct     | z3_repair          | 120 |   0.558 |   0.275 |               50 |               16 | 0.000 |    0.001 |
| qwen2.5-coder:7b      | direct     | hybrid_z3_else_cot | 120 |   0.558 |   0.633 |               17 |               26 | 0.222 |    1.000 |
| qwen2.5-coder:7b      | direct_cot | hybrid_z3_else_cot | 120 |   0.567 |   0.633 |               16 |               24 | 0.268 |    1.000 |

## Model comparison per approach (McNemar)

| approach   | A                     | B                |   n |   acc_A |   acc_B |     p |
|:-----------|:----------------------|:-----------------|----:|--------:|--------:|------:|
| direct     | gemini-3.5-flash-lite | gemini-3.8-flash | 120 |   0.767 |   1.000 | 0.000 |
| direct     | gemini-3.5-flash-lite | llama3.2:3b      | 120 |   0.767 |   0.542 | 0.001 |
| direct     | gemini-3.5-flash-lite | qwen2.5-coder:7b | 120 |   0.767 |   0.558 | 0.001 |
| direct     | gemini-3.8-flash      | llama3.2:3b      | 120 |   1.000 |   0.542 | 0.000 |
| direct     | gemini-3.8-flash      | qwen2.5-coder:7b | 120 |   1.000 |   0.558 | 0.000 |
| direct     | llama3.2:3b           | qwen2.5-coder:7b | 120 |   0.542 |   0.558 | 0.832 |
| direct_cot | gemini-3.5-flash-lite | gemini-3.8-flash | 120 |   0.983 |   1.000 | 0.500 |
| direct_cot | gemini-3.5-flash-lite | llama3.2:3b      | 120 |   0.983 |   0.467 | 0.000 |
| direct_cot | gemini-3.5-flash-lite | qwen2.5-coder:7b | 120 |   0.983 |   0.567 | 0.000 |
| direct_cot | gemini-3.8-flash      | llama3.2:3b      | 120 |   1.000 |   0.467 | 0.000 |
| direct_cot | gemini-3.8-flash      | qwen2.5-coder:7b | 120 |   1.000 |   0.567 | 0.000 |
| direct_cot | llama3.2:3b           | qwen2.5-coder:7b | 120 |   0.467 |   0.567 | 0.119 |
| z3         | gemini-3.5-flash-lite | gemini-3.8-flash | 120 |   0.783 |   0.808 | 0.736 |
| z3         | gemini-3.5-flash-lite | llama3.2:3b      | 120 |   0.783 |   0.000 | 0.000 |
| z3         | gemini-3.5-flash-lite | qwen2.5-coder:7b | 120 |   0.783 |   0.400 | 0.000 |
| z3         | gemini-3.8-flash      | llama3.2:3b      | 120 |   0.808 |   0.000 | 0.000 |
| z3         | gemini-3.8-flash      | qwen2.5-coder:7b | 120 |   0.808 |   0.400 | 0.000 |
| z3         | llama3.2:3b           | qwen2.5-coder:7b | 120 |   0.000 |   0.400 | 0.000 |
| z3_guided  | gemini-3.5-flash-lite | gemini-3.8-flash | 120 |   0.825 |   0.958 | 0.001 |
| z3_guided  | gemini-3.5-flash-lite | llama3.2:3b      | 120 |   0.825 |   0.017 | 0.000 |
| z3_guided  | gemini-3.5-flash-lite | qwen2.5-coder:7b | 120 |   0.825 |   0.233 | 0.000 |
| z3_guided  | gemini-3.8-flash      | llama3.2:3b      | 120 |   0.958 |   0.017 | 0.000 |
| z3_guided  | gemini-3.8-flash      | qwen2.5-coder:7b | 120 |   0.958 |   0.233 | 0.000 |
| z3_guided  | llama3.2:3b           | qwen2.5-coder:7b | 120 |   0.017 |   0.233 | 0.000 |
| z3_repair  | gemini-3.5-flash-lite | gemini-3.8-flash | 120 |   0.975 |   1.000 | 0.250 |
| z3_repair  | gemini-3.5-flash-lite | qwen2.5-coder:7b | 120 |   0.975 |   0.275 | 0.000 |
| z3_repair  | gemini-3.8-flash      | qwen2.5-coder:7b | 120 |   1.000 |   0.275 | 0.000 |

## Z3 pipeline outcomes (final attempt)

| model                 | approach   |   bug found (cex confirmed) |   bug found (cex not reproduced) |   error: Z3 sort/API misuse |   error: hallucinated API |   error: runaway output (token limit) |   error: runtime |   error: solver unknown |   error: syntax |   error: type/operator misuse |   false alarm (spurious cex) |   missed bug (unsat) |   proved safe |
|:----------------------|:-----------|----------------------------:|---------------------------------:|----------------------------:|--------------------------:|--------------------------------------:|-----------------:|------------------------:|----------------:|------------------------------:|-----------------------------:|---------------------:|--------------:|
| gemini-3.5-flash-lite | z3         |                          47 |                                0 |                           4 |                        11 |                                     0 |                3 |                       1 |               2 |                             2 |                            1 |                    2 |            47 |
| gemini-3.5-flash-lite | z3_guided  |                          50 |                                0 |                           0 |                         9 |                                     0 |                0 |                       3 |               2 |                             5 |                            2 |                    0 |            49 |
| gemini-3.5-flash-lite | z3_repair  |                          59 |                                0 |                           0 |                         0 |                                     0 |                0 |                       2 |               0 |                             0 |                            0 |                    1 |            58 |
| gemini-3.8-flash      | z3         |                          51 |                                0 |                           1 |                        10 |                                     0 |                0 |                       6 |               0 |                             4 |                            0 |                    2 |            46 |
| gemini-3.8-flash      | z3_guided  |                          59 |                                0 |                           0 |                         0 |                                     0 |                0 |                       5 |               0 |                             0 |                            0 |                    0 |            56 |
| gemini-3.8-flash      | z3_repair  |                          60 |                                0 |                           0 |                         0 |                                     0 |                0 |                       0 |               0 |                             0 |                            0 |                    0 |            60 |
| llama3.2:3b           | z3         |                           0 |                                0 |                           0 |                        31 |                                    84 |                0 |                       0 |               5 |                             0 |                            0 |                    0 |             0 |
| llama3.2:3b           | z3_guided  |                           0 |                                2 |                           4 |                         8 |                                    84 |                5 |                       0 |               6 |                            10 |                            1 |                    0 |             0 |
| qwen2.5-coder:7b      | z3         |                          16 |                               11 |                           9 |                        11 |                                     8 |                0 |                       0 |               3 |                            17 |                           15 |                    9 |            21 |
| qwen2.5-coder:7b      | z3_guided  |                          11 |                                6 |                           6 |                        30 |                                    12 |                1 |                       0 |               7 |                            16 |                            9 |                   11 |            11 |
| qwen2.5-coder:7b      | z3_repair  |                          12 |                                8 |                           8 |                        27 |                                    12 |                0 |                       0 |               3 |                            11 |                           14 |                   12 |            13 |

## Effect of repair rounds

| model                 |   k |   accuracy |   executable |
|:----------------------|----:|-----------:|-------------:|
| gemini-3.5-flash-lite |   0 |       0.82 |         0.84 |
| gemini-3.5-flash-lite |   1 |       0.94 |         0.94 |
| gemini-3.5-flash-lite |   2 |       0.97 |         0.97 |
| gemini-3.5-flash-lite |   3 |       0.97 |         0.98 |
| gemini-3.8-flash      |   0 |       0.96 |         0.96 |
| gemini-3.8-flash      |   1 |       0.98 |         0.98 |
| gemini-3.8-flash      |   2 |       0.99 |         0.99 |
| gemini-3.8-flash      |   3 |       1.00 |         1.00 |
| qwen2.5-coder:7b      |   0 |       0.23 |         0.40 |
| qwen2.5-coder:7b      |   1 |       0.27 |         0.48 |
| qwen2.5-coder:7b      |   2 |       0.27 |         0.48 |
| qwen2.5-coder:7b      |   3 |       0.28 |         0.49 |

## Static features of the generated Z3 code (final attempt)

| model                 | approach   |   n |   acc |   bitvec |   int_sort |   srem |   ovf_helpers |   push_pop |   lines |
|:----------------------|:-----------|----:|------:|---------:|-----------:|-------:|--------------:|-----------:|--------:|
| gemini-3.5-flash-lite | z3         | 120 |  0.78 |     0.97 |       0.03 |   0.02 |          0.03 |       0.00 |   54.50 |
| gemini-3.5-flash-lite | z3_guided  | 120 |  0.82 |     1.00 |       0.00 |   0.08 |          0.78 |       0.00 |   44.50 |
| gemini-3.5-flash-lite | z3_repair  | 120 |  0.97 |     1.00 |       0.00 |   0.08 |          0.78 |       0.00 |   42.00 |
| gemini-3.8-flash      | z3         | 120 |  0.81 |     1.00 |       0.00 |   0.01 |          0.17 |       0.00 |   34.00 |
| gemini-3.8-flash      | z3_guided  | 120 |  0.96 |     1.00 |       0.00 |   0.08 |          0.85 |       0.00 |   32.50 |
| gemini-3.8-flash      | z3_repair  | 120 |  1.00 |     0.97 |       0.03 |   0.07 |          0.82 |       0.00 |   32.50 |
| llama3.2:3b           | z3         | 120 |  0.00 |     0.69 |       1.00 |   0.00 |          0.00 |       0.01 |  122.00 |
| llama3.2:3b           | z3_guided  | 120 |  0.02 |     0.69 |       0.48 |   0.00 |          0.73 |       0.00 |  113.00 |
| qwen2.5-coder:7b      | z3         | 120 |  0.40 |     0.07 |       0.95 |   0.00 |          0.00 |       0.00 |   31.00 |
| qwen2.5-coder:7b      | z3_guided  | 120 |  0.23 |     1.00 |       0.00 |   0.00 |          0.62 |       0.00 |   25.00 |
| qwen2.5-coder:7b      | z3_repair  | 120 |  0.28 |     1.00 |       0.00 |   0.00 |          0.62 |       0.00 |   25.00 |

### Accuracy conditioned on code features (all models, all Z3 approaches)

| feature               | present   |    n |   accuracy |
|:----------------------|:----------|-----:|-----------:|
| uses_bitvec           | True      | 1129 |       0.62 |
| uses_bitvec           | False     |  191 |       0.27 |
| uses_int_sort         | True      |  299 |       0.17 |
| uses_int_sort         | False     | 1021 |       0.69 |
| uses_overflow_helpers | True      |  647 |       0.63 |
| uses_overflow_helpers | False     |  673 |       0.51 |
| uses_srem             | True      |   42 |       0.93 |
| uses_srem             | False     | 1278 |       0.56 |

## Cost

| model                 | approach               |   mean_llm_calls |   mean_out_tokens |   mean_wall_s |
|:----------------------|:-----------------------|-----------------:|------------------:|--------------:|
| gemini-3.5-flash-lite | Direct                 |             1.00 |             74.99 |         11.89 |
| gemini-3.5-flash-lite | Direct + CoT           |             1.00 |            562.14 |         12.02 |
| gemini-3.5-flash-lite | LLM→Z3                 |             1.00 |            824.48 |         12.04 |
| gemini-3.5-flash-lite | LLM→Z3 guided          |             1.00 |            570.89 |         12.32 |
| gemini-3.5-flash-lite | LLM→Z3 guided + repair |             1.27 |            717.91 |          5.37 |
| gemini-3.8-flash      | Direct                 |             1.00 |            169.32 |          8.59 |
| gemini-3.8-flash      | Direct + CoT           |             1.00 |            485.61 |          6.28 |
| gemini-3.8-flash      | LLM→Z3                 |             1.00 |            674.46 |         10.96 |
| gemini-3.8-flash      | LLM→Z3 guided          |             1.00 |            449.52 |          7.13 |
| gemini-3.8-flash      | LLM→Z3 guided + repair |             1.07 |            483.06 |          2.78 |
| llama3.2:3b           | Direct                 |             1.00 |             41.53 |          2.73 |
| llama3.2:3b           | Direct + CoT           |             1.00 |            598.71 |         11.07 |
| llama3.2:3b           | LLM→Z3                 |             1.00 |           2355.13 |         44.76 |
| llama3.2:3b           | LLM→Z3 guided          |             1.00 |           2481.22 |         51.12 |
| qwen2.5-coder:7b      | Direct                 |             1.00 |             60.76 |          3.32 |
| qwen2.5-coder:7b      | Direct + CoT           |             1.00 |            661.32 |         27.29 |
| qwen2.5-coder:7b      | LLM→Z3                 |             1.00 |            537.83 |         21.28 |
| qwen2.5-coder:7b      | LLM→Z3 guided          |             1.00 |            567.18 |         23.66 |
| qwen2.5-coder:7b      | LLM→Z3 guided + repair |             3.11 |           2107.91 |         66.65 |

Tools (mean wall-clock seconds per instance):

| approach          |   mean_wall_s |
|:------------------|--------------:|
| Gold Z3 (Claude)  |          0.52 |
| CBMC              |          1.71 |
| Fuzz (dictionary) |          2.16 |
| Fuzz (random)     |          3.63 |
