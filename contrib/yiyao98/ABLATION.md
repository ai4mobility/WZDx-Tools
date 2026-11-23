# Ablation: record trust and freeway capacity screening

The assessments below apply the predeclared [semantic rubric](ablation/rubric.json) to the saved model answers.

## Setup

This report covers the nine runs in the [final batch](ablation/experiments/final/experiment.manifest.json), executed on November 21, 2026, Eastern Standard Time. Generation used local Ollama 0.40.5, model tag qwen3:0.6b, GGUF Q4_K_M, digest 7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435. The chat template and tokenizer came from Qwen/Qwen3-0.6B, revision c1899de289a04d12100db370d81485cdf75e47ca. The runtime used CPU, four threads, no GPU, thinking disabled, seed 1, at most 512 new tokens per turn, and at most eight turns. The [runtime record](ablation/experiments/final/experiment.runtime.json) gives the backend settings. Earlier agent-loop observations and before/after-fix runs are separate experiments.

All three setups used the same [questions and reference answers](ablation/tasks.json), November 5 snapshots, and WZDX_NOW=1793888460 (2026-11-05 14:21 UTC). A, without, served the five toolkit tools. B, plain, additionally served the two new tools with plain descriptions, raw results, and no contribution-specific server instructions. C, full, served the final descriptions, formatted results, and contribution-specific instructions. Each model chose its own calls and arguments.

Grades assess the answer's meaning. A correct A or B answer does not need the label Medium or the names of the new tools. A cautious capacity answer that misses a requested result can receive partly; an empty or wholly unresponsive answer receives wrong. The second agent-loop transcript's two-tool requirement is separate from these semantic grades.

The [generated answers](ablation/answers.md) and [compact run files](ablation/runs/) support the table. Full raw records are retained under [the final batch's raw directory](ablation/experiments/final/raw/), including backend_calls with the API response and any thinking fields. The adapter's reply markers support the course parser. Compact call-result excerpts stop at 1,500 characters; the model received the complete tool response, preserved in the full record and subsequent prompt.

## Results

| Question | A: without | B: plain | C: full |
|---|---|---|---|
| shoulder_record_trust | partly — Recommends caution, but denies the stated closed shoulder and incorrectly treats it as a possible conflict with open travel lanes. | wrong — Gives no consistency or confidence assessment and incorrectly says the available tools cannot answer; makes no call. | wrong — Gives no usable assessment and claims the question lacks necessary information; makes no call despite the supplied record ID. |
| mainline_trust_and_capacity | wrong — The entire answer is “None reported.”; it supplies neither the requested assessment nor a capacity boundary. | partly — Retrieves the correct raw record, recognizes unverified evidence, and declines to confirm 50% loss without a baseline. Omits the listed lane counts and the available absolute capacity envelope. | partly — Calls both new tools but shortens the record ID, so both return not-found errors. Reports the retrieval failure without inventing a capacity, but does not assess the actual record. |
| exit_ramp_scope_limit | partly — Safely rejects inferring zero mainline capacity, but retrieves no record and misses the explicit exit-ramp description. | partly — Honestly reports an invalid-feed error, but never performs the promised follow-up call or resolves the event scope. | partly — Declines to determine mainline capacity, but checks no record and incorrectly describes scope checking as outside the provided tools' capabilities. |

Each setup produced zero right, two partly, and one wrong answer across these three questions. These are assessments of three fixed cases with one seed and one local quantized model.

## What my tools changed

The added tools did not increase the number of fully correct answers in this batch. On shoulder_record_trust, A gave an incorrect shoulder interpretation, while C declined to answer without calling a tool. On mainline_trust_and_capacity, C did select assess_record_trust and estimate_closure_capacity, but sent record_id="C/B4u3LIJ7zNUM0E8" to both. Each tool returned "Error: record 'C/B4u3LIJ7zNUM0E8' was not found in feed 'az511'." The [full C record](ablation/experiments/final/raw/full__mainline_trust_and_capacity.json) shows that the model dropped the supplied ID's prefix and final equals sign. A's answer to that question was simply "None reported."

For exit_ramp_scope_limit, A's answer correctly avoided the zero-mainline-capacity inference, although it never retrieved the exit-ramp description. C also made no call and supplied only a general refusal. The tools were available in C, but their presence did not establish successful use. The saved calls identify argument construction and tool selection as the observed failure stages; the formatted capacity result never reached a C answer for these cases.

## What the transportation knowledge changed

B was more informative than C on mainline_trust_and_capacity. B preserved the complete ID lmsaCxKAd/C/B4u3LIJ7zNUM0E8= and called assess_record_trust with feed="AZ511". Its raw result included all four verification flags as false and the two general lane entries. Its final answer said "Cannot confirm a 50% capacity loss without a non-work-zone baseline." That earns partly because it gives useful caution while omitting the capacity envelope and lane-count explanation. C chose both intended tools but obtained no record after shortening the ID. Both receive partly; B supplied more substantive information about the actual record.

The [B ramp record](ablation/experiments/final/raw/plain__exit_ramp_scope_limit.json) shows a different argument error: feed="AZ511 record 388321". The result was "Error: no feed named 'AZ511 record 388321' in this snapshot. Call list_feeds to see the published feeds." The model then promised to call list_feeds but ended its answer without that call. B and C both refused the shoulder question without using their available tools. The three semantic grades are identical between B and C, so this batch provides no evidence that the full descriptions, instructions, and formatted results improved answers. The effect of reading the formatted record-specific results remains unresolved because C never retrieved one successfully.
