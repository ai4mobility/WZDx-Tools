# Design: assess_record_trust, estimate_closure_capacity

## 1. The task

<!-- What task are you asking the agent to do? Who asks, in what words, what decision depends on the answer, how
often, and how is it done today without AI? Give two or three questions exactly as that person would ask them. -->

**User:** A Traffic Management Center (TMC) operator on shift.

**Task:** Work zone feeds push thousands of WZDx records to the TMC, and an operator does not have time to inspect raw JSON fields one by one. Within a few minutes of seeing a record, the operator has to decide whether to post a Dynamic Message Sign (DMS) warning, push a 511 detour alert, or flag the signal timing team.

Typical questions an operator asks on shift:
- "Can I trust this closure record? Is a crew actually blocking lanes out there right now, or is this a stale permit from last week—do I need to pull up CCTV first?"
- "If those lanes really are closed, how much capacity are we losing? Is the drop severe enough to put up detour alerts right now?"

## 2. The tools

<!-- Which tools did you design for that task, and why these? For each tool: the question it answers, what it
returns, and why it is useful to the person in section 1: what transportation knowledge it carries that the raw
data or the toolkit lacks (point to your rules in KNOWLEDGE.md by number). Why did you split the work this way, and
what did you leave out? -->

- **`assess_record_trust` (Screen the record first):** Checks whether a record is active, verified, internally consistent, and detailed enough to act on. It flags expired records, conflicting fields, and missing lane breakdowns so the operator knows whether to use the record as-is or verify it via CCTV first.
- **`estimate_closure_capacity` (Gauge the traffic impact):** For a supported freeway mainline closure with a usable lane breakdown, estimates a capacity sensitivity envelope in passenger cars per hour using Maryland SHA Appendix A. It reports a percentage loss only when the caller supplies a non-work-zone baseline and its source. It refuses ramp events and unconfirmed freeway scope, and lists the missing inputs and modeling assumptions. Rules 6–10 in KNOWLEDGE.md define these boundaries.
- **Net-new value over existing `wzdx_tools.py`:** While `get_work_zones`, `check_location`, and `feed_quality` already surface individual flags (unknown impact, verification status, past-end-date warnings), `assess_record_trust` synthesizes them into an explicit operational tier (`High` / `Medium` / `Low` / `Scheduled` / `Completed`) and adds rules the base toolkit does not enforce: shoulder-only consistency checks, treating `alternating-one-way` as a travel-lane closure claim, and capping records without lane-level evidence at `Medium`.

The two functions separate the quality of a report from a conditional capacity calculation. A record can be internally consistent yet unverified; an unverified report can still support a clearly labeled scenario calculation. Neither function predicts demand, delay, queue length, or the benefit of signal retiming. The capacity tool adds a documented equation and scope guard beyond the existing lane-summary contributions; counting closed lanes alone is not its claimed contribution. The trust tiers are operational screening rules agreed for this project, rather than calibrated probabilities or WZDx-defined ratings.

## 3. The descriptions

<!-- How does each description help the model pick the right tool and fill in its inputs? Quote the sentences that
do the work and explain each one: the words a person would use, when to use it instead of a toolkit tool, input
names and units, what it refuses and where to go instead. Use your transcripts: which sentence did the model's
reasoning pick up, and what did you change? -->

The description of `assess_record_trust` says, "Use this tool instead of get_work_zones or check_location" when the operator asks about a specific report's reliability. Words such as stale, unverified, contradictory, DMS and CCTV connect the function to the operator's decision rather than asking the model to infer the purpose from a generic JSON lookup. The description defines feed aliases and an exact feature ID, and distinguishes operational screening from proof that cones are deployed. Its date-order priority and shoulder exception identify two cases in which reading a summary alone would be misleading.

For `estimate_closure_capacity`, "Output is a parameter-domain sensitivity envelope, not a field confidence interval." defines the meaning of the returned range. The input description gives pc/h/lane for the optional baseline and requires its source; it does not supply a default baseline for the model. The refusal conditions direct the model away from interpreting an Interstate road label as sufficient evidence of mainline scope. The phrase "marks percentage drop unknown when baseline_pcphpl or its source is omitted" makes the missing-baseline outcome part of the tool's contract. These descriptions communicate different decisions: report quality first, then a scoped conditional calculation. The saved run analysis below checks whether the model actually follows those distinctions.

In [baseline question 1](runs/baseline_q1.md), the model's reasoning says, "Then, the user needs to assess the record's trust level using assess_record_trust with the record_id." It selected the intended assessment, but also invented unsupported inputs for `list_feeds`. The server instructions were therefore revised to distinguish finding a feed from verifying a record and to preserve exact IDs. The [after-fix question 1](runs/after_fix_q1.md) made no tool call, so these instructions did not reliably solve tool selection for this small model.

## 4. The results

<!-- How is each result written so the model reads it correctly? Quote a real result and explain each part: units,
the verdict stated either way, definitions (a work vs. a record), unknowns said as unknown, warnings. Use your
transcripts: where did the model read it right, where did it read it wrong, and what would you change? -->

`assess_record_trust` states a tier, reference clock, reporting source and separate lifecycle, verification and lane checks. In [baseline question 1](runs/baseline_q1.md), the result recommends, "Usable for situational awareness, but verify via CCTV or field contact before posting major DMS or detour alerts." That sentence explains what Medium permits. The same result reports all four verification flags False. The model repeated Medium and the CCTV action, but invented a verified position. Thus a correct tier alone did not ensure a correct explanation; the revised server instructions require verification claims to refer to their actual field flags and distinguish rejected calls from evidence.

`estimate_closure_capacity` states units and scope before presenting lane inputs. The [baseline ramp result](runs/baseline_q3.md) said, "Mainline Estimate Available: No (refused)" and supplied the exit-ramp description. Nevertheless, its later heading called the listed entries mainline general lanes, and the model asserted zero mainline capacity. The revised result carries the refusal through every label: reported event entries are not a mainline inventory, mainline capacity and loss percentage remain unknown, and the equation was not evaluated. This addresses an observed contradiction in presentation without changing the refusal rule or calculating a new number.

For admitted mainline cases, capacity is pc/h, with per-open-lane and same-direction totals separated. A percentage needs an explicit sourced baseline. Scenario endpoints describe parameter sensitivity, not observed throughput or a confidence interval. Each result describes one WZDx feature, not every event on the named highway. The before/after transcripts and the three-condition ablation test how well the model preserves these distinctions; they do not establish that a result format guarantees correct interpretation.

The after-fix ramp run did not call the capacity tool, so it never read the revised result. Its avoidance of a zero-capacity assertion cannot be credited to that result formatting. The admitted-mainline question also failed retrieval in both agent batches; the model never consumed its numerical envelope there. The final ablation did not establish an advantage for the full condition. Implementation tests validate the arithmetic and scope rules, while these traces expose a separate failure in model tool use and evidence handling.
