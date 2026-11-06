# An example ablation

A real run of `contrib/ablation.py` on a demonstration folder made from the template. Its two tools are
`street_work_report` (the template's `work_zones_on_street`, renamed) and `street_work_count`, which returns the
first line of the report. The folder itself is not in `contrib/`. Its `tools.py` is here as `demo_tools.py`, with
`PLAIN_DESCRIPTIONS` and `RAW_RESULTS` at the end.

    python contrib/ablation.py contrib/<the demo folder>        # 3 questions x 3 setups = 9 runs

Qwen3-1.7B, thinking off, seed 1, on a 2-core cloud CPU with no GPU: 14 minutes in all.

| Setup | Right answers (graded by hand) |
|---|---|
| A. Without the new tools (the toolkit only) | 1 of 3 |
| B. The new tools, plain description and raw result | 0 of 3 |
| C. The new tools as written | 2 of 3, and 1 partly |

The files, as they were in the demo folder (its `ablation/runs/` is `runs/` here):
- `tasks.json`: the three questions and their right answers, written before the run
- `answers.md`: every answer, with the tools each run called (written by `ablation.py`)
- `ABLATION.md`: the grades and the two comparisons, written as a student would
- `runs/`: one file per run: the descriptions the model saw, its calls with their results, and its answer

Two things are worth noticing. In B the model never called the new tools, so the raw results were never read: the
plain description is what made the difference. And C's "partly" on `thirtieth_lanes` is the misreading the tool's
description warns against ("not reported" turned into "no lane impact"). A phrase score would have counted it right;
reading the answer did not.
