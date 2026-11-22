# The answers: 3 questions x 3 setups

Written by contrib/ablation.py. Model qwen3:0.6b (Ollama GGUF; Qwen/Qwen3-0.6B tokenizer), thinking off, seed 1, on cpu (Ollama). Data: WZDx snapshot snapshots/2026-11-05.

Read each answer against the right answer, then grade it in the table in ABLATION.md: right, partly or wrong, and why in a few words. The table to copy:

| Question | A. Without your tools | B. Your tools, plain | C. Your tools as written |
|---|---|---|---|
| shoulder_record_trust | ? | ? | ? |
| mainline_trust_and_capacity | ? | ? | ? |
| exit_ramp_scope_limit | ? | ? | ? |

## shoulder_record_trust

**Question:** At the saved reference time, AZ511 record 351676 says all-lanes-open but lists a closed shoulder. Is that a contradiction, and how much confidence should I place in this record before posting a major alert?

**Right answer (tasks.json):** The reported fields are consistent: the list contains one general lane open and one shoulder closed. A shoulder closure does not contradict the vehicle impact all-lanes-open. assess_record_trust returns Medium because all four verification flags are False. Confirm field status before a major DMS or detour action. Do not claim that the entire I-10 mainline is confirmed open: the description concerns a ramp from I-10 Eastbound to SR-387. Checked in snapshots/2026-11-05/az511.json.gz, record 351676, properties.vehicle_impact, lanes, is_*_verified and core_details.description.

### A. Without your tools

Tools called: none. 1 turns, 17 s. Run: `ablation/runs/without__shoulder_record_trust.json`

> The provided record from AZ511 record 351676 indicates that all-lanes-open, but it does not list a closed shoulder. This could be a contradiction, as it contradicts the assumption that a closed shoulder is part of the open-lane condition. There is a lack of information about the closed shoulder's status. Therefore, you should place **low confidence** in this record before posting a major alert.

### B. Your tools, plain

Tools called: none. 1 turns, 19 s. Run: `ablation/runs/plain__shoulder_record_trust.json`

> None of the tools can be used to determine if the record is contradictory or the confidence level for the alert. The tools provided do not include a function to assess the consistency of a work zone record or evaluate the confidence level in its use for a major alert. Therefore, I cannot answer this question with the information provided.

### C. Your tools as written

Tools called: none. 1 turns, 8 s. Run: `ablation/runs/full__shoulder_record_trust.json`

> None of the tools can be used to determine if the record is a contradiction. The question does not provide the necessary information to assess the record's validity or confidence level.

## mainline_trust_and_capacity

**Question:** For AZ511 record lmsaCxKAd/C/B4u3LIJ7zNUM0E8= on I-17 southbound, first assess the record's reliability and then estimate its freeway mainline capacity. What can you report without a non-work-zone baseline, and can I call it a 50% capacity loss?

**Right answer (tasks.json):** Use both assess_record_trust and estimate_closure_capacity. The record is Medium and unverified, with some-lanes-closed and two listed general lanes, one closed and one open. The reported scope is I-17 southbound, Munds Park MP328 to Kachina Blvd MP327, left lane closed. LCSI is 2. The fixed-alpha parameter-scenario sensitivity envelope is approximately 1560 to 2190 pc/h; one open lane makes the per-open-lane and directional total values numerically equal. Without a caller-supplied non-work-zone baseline and its source, capacity loss percentage is unknown. A 50% listed-lane closure fraction is not evidence of a 50% capacity loss. The 88.514 km/h speed limit displays as 55.0 mph but is not used in this capacity equation. The envelope assumes the list represents the event's normal general lanes and is not a field confidence interval. Checked in the AZ snapshot record, reviewed capacity arithmetic, and Maryland SHA 2024 Appendix A.

### A. Without your tools

Tools called: none. 1 turns, 3 s. Run: `ablation/runs/without__mainline_trust_and_capacity.json`

> None reported.

### B. Your tools, plain

Tools called: `assess_record_trust(feed='AZ511', record_id='lmsaCxKAd/C/B4u3LIJ7zNUM0E8=')`. 2 turns, 26 s. Run: `ablation/runs/plain__mainline_trust_and_capacity.json`

> The record's reliability is assessed as "unknown" due to the lack of verified positions. For the estimated freeway mainline capacity, a non-work-zone baseline is not provided, so we cannot confirm the exact capacity loss. Therefore, we can report the available data without a non-work-zone baseline as follows:
>
> - **Record Reliability**: Unknown
> - **Estimated Capacity**: Cannot confirm a 50% capacity loss without a non-work-zone baseline.

### C. Your tools as written

Tools called: `assess_record_trust(feed='AZ', record_id='C/B4u3LIJ7zNUM0E8')`, `estimate_closure_capacity(feed='AZ', record_id='C/B4u3LIJ7zNUM0E8', baseline_pcphpl=None, baseline_source='None')`. 2 turns, 18 s. Run: `ablation/runs/full__mainline_trust_and_capacity.json`

> The requested record "C/B4u3LIJ7zNUM0E8" is not found in the feed 'AZ511'. Please verify the record ID or feed name.

## exit_ramp_scope_limit

**Question:** AZ511 record 388321 names I-10 Eastbound and lists one general lane, closed. Does that mean the I-10 mainline has zero capacity? Check the scope of this record and explain what the feed cannot establish.

**Right answer (tasks.json):** No. The description explicitly says Exit ramp closed from I-10 Eastbound to S Palo Verde Blvd. The original listed lane type is general, with one closed entry and zero open entries; do not relabel the raw type as exit-lane. Those entries describe this reported ramp event and do not establish I-10 mainline closure or zero mainline capacity. estimate_closure_capacity refuses a mainline estimate, with non_mainline_exit_ramp among the reasons, and does not provide a mainline capacity or loss percentage. Check the event scope or obtain additional agency/field evidence. Checked in snapshots/2026-11-05/az511.json.gz, record 388321, core_details.description, road_names, vehicle_impact and lanes.

### A. Without your tools

Tools called: none. 1 turns, 7 s. Run: `ablation/runs/without__exit_ramp_scope_limit.json`

> The provided record contains the names of I-10 Eastbound and lists one general lane, closed. It does not provide information about the I-10 mainline's capacity, so we cannot establish that it has zero capacity based on this record. The feed does not establish the scope of this record and explains that it lists a specific lane, not the mainline.

### B. Your tools, plain

Tools called: `assess_record_trust(feed='AZ511 record 388321', record_id='388321')`. 2 turns, 14 s. Run: `ablation/runs/plain__exit_ramp_scope_limit.json`

> The tool returned an error indicating that no feed named 'AZ511 record 388321' was found in the current snapshot. Let me check the list of published feeds to identify the correct feed. I'll call the `list_feeds` function to see which feeds are available for reference.

### C. Your tools as written

Tools called: none. 1 turns, 6 s. Run: `ablation/runs/full__exit_ramp_scope_limit.json`

> None of the functions provided can be used to determine the capacity of the I-10 mainline. The question requires checking the scope of the record and explaining what the feed cannot establish, which is outside the scope of the provided tools.
