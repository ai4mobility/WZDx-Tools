# Ablation: what my tools and my transportation knowledge change

*Codex assisted with grading and drafting the comparisons. The judgments use the nine
[recorded answers](ablation/answers.md) and the [snapshot reference answers](ablation/tasks.json).*

The three setups:
- **A. Without your tools:** the toolkit's tools only.
- **B. Your tools, plain:** your tools find the same data, but the description is the plain one
  (`PLAIN_DESCRIPTIONS`), the result is raw (`RAW_RESULTS`), and your server instructions are left out.
- **C. Your tools as written.**

## Results

<!-- Copy the table that ablation.py printed. In each cell write right, partly or wrong, then why in a few words
(for example: "wrong: says the lanes are open"). The right answers are in ablation/tasks.json. -->

| Question | A. Without your tools | B. Your tools, plain | C. Your tools as written |
|---|---|---|---|
| busch_eastbound | Wrong: misses the closed travel lane and denies a missing direction. | Partly: notices the missing direction but misses the rightmost-lane closure. | Right: identifies the rightmost of three travel lanes and separates the unknown-direction record. |
| miami_detour | Partly: lists both directions and the correct end time but claims it was verified. | Wrong: an unrelated road lookup leads to a false claim that no detours were linked. | Partly: the northbound ID, end time, and unverified status are correct, but the southbound entry is omitted. |
| busch_unknown_impact | Partly: reports unknown lane impact but gives no clear dispatch recommendation or directional distinction. | Partly: advises against asserting open lanes but incorrectly says there are no nearby work zones. | Wrong: explicitly tells dispatch the westbound lanes are clear despite the unknown lane impact. |

## What my tools changed

<!-- A vs. C, at least 60 words, naming a question by its id. Without your tools, what did the model call and what
did it get wrong? What did your tool change? -->

For `busch_eastbound`, setup A used `get_work_zones` and missed the reported closure of the rightmost
travel lane. Setup C used the crash-area tool and returned the correct lane position together with
the separate unknown-direction feature. For `miami_detour`, C recovered the northbound feature's
unverified end, but A was more complete in listing both directions. On `busch_unknown_impact`, C
used the same toolkit calls as A and made a stronger, unsupported claim about open westbound lanes.
The benefit depended on whether the model chose the specialized tool and interpreted its response
correctly. In this run the full setup improved the eastbound answer, while the westbound result
shows why the agent cannot independently clear a diversion.

## What the transportation knowledge changed

<!-- B vs. C, at least 60 words, naming a question by its id. Your tool found the same data in both. Which sentence
of your description, or which part of your result, made the difference? Quote it. If B did as well as C, why? -->

For `busch_eastbound`, setup B had the crash-area tool available but used the general lookup instead.
Setup C selected the specialized tool, whose output stated “right lane of 3 closed” and labeled the
other feature “direction unknown; this record is not assigned to eastbound.” The full answer preserved
that distinction. For `miami_detour`, B looked up an unrelated road, while C used the supplied feature
ID and reported the end as unverified. B never called either contributed tool in these three runs,
so this comparison cannot isolate the effect of reading enriched results versus raw results from
the same tool. The descriptions, instructions, and result text changed together. In
`busch_unknown_impact`, neither setup used the specialized tool and C inferred that the lanes were
clear. The full wording did not prevent that error.
