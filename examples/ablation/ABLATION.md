# Ablation: what my tools and my transportation knowledge change

*Run `python contrib/ablation.py contrib/<you>`: your three questions, each asked in three setups, 9 runs. It
writes every answer to `ablation/answers.md`. Read them, then fill in this page yourself, in your own words.*

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
| busch_lanes | wrong: found only the record with no lane data, "No specific lanes are closed" | wrong: did not call my tools; "No closed lanes ... are reported" | right: eastbound, right lane of 3 closed, until 4 pm, 1 work from 2 records (one misread line at the end) |
| thirtieth_works | wrong: "4 separate work zones" (it counted records), and made up "closed lanes, reduced speed limit" | wrong: did not call my tools; answered about "the az feed": "No active work zone is reported" | right: "2 active works", reported as 4 records |
| thirtieth_lanes | right: lane impact unknown on all 4 records, never says open (after 5 calls refused) | wrong: did not call my tools; "No active work zone is reported within 0.5 mi" | partly: "Lane Impact: Not reported", then "not having any lane impact" |

Model Qwen3-1.7B, thinking off, seed 1, on the Nov 5 snapshot. Right answers: A 1 of 3, B 0 of 3, C 2 of 3 (and 1
partly).

## What my tools changed

<!-- A vs. C, at least 60 words, naming a question by its id. Without your tools, what did the model call and what
did it get wrong? What did your tool change? -->

Without my tools, the model used get_work_zones, which matches street names as plain text. On busch_lanes it found
only the record that has no lane data and answered "No specific lanes are closed". It missed the eastbound
closure, which is in the second record. On thirtieth_works it counted the 4 records as "4 separate work zones" and
added "closed lanes, reduced speed limit", which no record says. With my tools, both came back right: "1 active work
on the street, from 2 record(s)" with the right lane of 3 closed, and "2 active works" from 4 records. The one
question the toolkit alone got right, thirtieth_lanes, is my control: get_work_zones already says "lane impact
unknown", and the model repeated it. It needed 8 turns, because it sent the coordinates as text and five calls were refused.

## What the transportation knowledge changed

<!-- B vs. C, at least 60 words, naming a question by its id. Your tool found the same data in both. Which sentence
of your description, or which part of your result, made the difference? Quote it. If B did as well as C, why? -->

In B, my tools were there with plain descriptions, and the model never called them, on any of the three questions.
It called list_feeds and check_location, which found nothing within 0.5 mi of the USF point, and on thirtieth_works
it listed the Arizona feeds and answered about "the az feed". So the raw results were never seen, and the difference came from what the model read
before calling: the descriptions, and my server instructions, which B also leaves out. The plain description, "Active
work zones on a street", says what get_work_zones already says, so the model had no reason to pick my tool. Mine
says in its first sentence "counted as works rather than records" and gives "a street name as people say it", and in C the model
called my tool first every time.

The knowledge in the result helped only partly. On thirtieth_lanes, C read "Lane Impact: Not reported" correctly,
then wrote "not having any lane impact", the misreading my description warns against. The warning is in the
description, but the model read the result line, and that line has only "lane impact not reported". Next I would put
"(not reported: this does not mean open)" in that line.
