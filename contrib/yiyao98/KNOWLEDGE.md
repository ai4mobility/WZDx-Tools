# Knowledge card: assess_record_trust, estimate_closure_capacity

## Rules

The operational tiers and conservative implementation scope below are project rules confirmed in the working discussion. WZDx defines the input fields; it does not prescribe these High/Medium/Low tiers. The dated rule history and review materials are kept outside the repository. All listed tests exist in `test_tools.py`.

| # | Rule: what a transportation engineer knows | Source | Where in tools.py | Test |
|---|---|---|---|---|
| 1 | Check `start_date > end_date` before lifecycle grading. For valid input, respect reported completed/pending status; an active record with a future start stays active, carries a mismatch flag, and is capped at Medium. | User-confirmed project rule; [fixed snapshot clock](../../snapshots/README.md); lifecycle precedent in `wzdx_tools._status` | `_ref_time_utc`; `_evaluate_record_trust` date-order and status-first branches | `test_trust_time_conflict_first`; `test_trust_completed_before_missing_evidence`; `test_trust_pending_separate`; `test_trust_active_future_start_flag` |
| 2 | With no explicit status, separate future work from grading. After those exclusions, compare a past planned end with the reported update: update at/after end caps the time component at Medium; update before end triggers Low. Other Low conditions still take priority. | User-confirmed update-versus-end rule; Nov 5 snapshots. This is a project screening rule, not a fixed freshness threshold or proof of ongoing work. | `_evaluate_record_trust` no-status lifecycle branch and Low-trigger aggregation | `test_trust_update_after_end_cap_then_and_rule`; `test_trust_update_before_end_low` |
| 3 | Treat missing closure evidence as Low only for the conjunction unknown impact AND missing/empty lanes AND no verification flag True. Nonempty lane evidence with unknown impact and no positive verification is Medium unless another Low condition applies. High requires at least one actual True, usable lanes, and no Low trigger or Medium cap. | User-confirmed tier rule; [WZDx verification fields][WZ]; record-level snapshot checks | `_evaluate_record_trust` `verification_evidence`, Low triggers, and Medium caps | `test_trust_unknown_missing_lanes_unverified_low`; `test_trust_unknown_with_lane_evidence_medium`; `test_trust_partial_verification_high` |
| 4 | A shoulder-only closure is compatible with all-lanes-open. A some-lanes-closed claim with all listed general lanes open and only shoulders closed is a conflict under this project's consistency rule. | [WZDx LaneType][LT] and [VehicleImpact][VI]; user-confirmed conflict rule; AZ `351676` and FL `4586525408/293379759` | `_evaluate_lane_component` all-open and closure-claim branches | `test_trust_open_impact_shoulder_closed_consistent`; `test_trust_some_closed_only_shoulder_conflict` |
| 5 | Count general and exit-lane as vehicular lanes for consistency, but count only general for mainline capacity. Match alternating-one-way to alternating-flow rather than requiring a literal closed status. Keep lifecycle and independent lane checks separate. | [WZDx LaneType][LT], [LaneStatus][LS], and [VehicleImpact][VI]; user-confirmed checks | `VEHICULAR_LANE_TYPES`; `_evaluate_lane_component`; `_evaluate_closure_capacity` | `test_trust_exit_lane_component`; `test_capacity_exit_lane_not_general`; `test_trust_alternating_flow_compatible_component` |
| 6 | Invalid evidence must produce an error rather than a confident tier: do not coerce strings to verified booleans or silently discard damaged lane entries. Preserve unreported verification separately from False. | [WZDx field types][WZ]; implementation validation agreed during review | `_parse_time`; `_evaluate_record_trust` input validation; `_evaluate_lane_component`; `assess_record_trust` | `test_invalid_record_evidence_returns_error_not_trust_tier`; `test_unreported_verification_distinct_from_false`; `test_invalid_fractional_timestamp_not_silently_repaired` |
| 7 | Establish the event's facility before applying a freeway mainline model. Explicit ramp events are not mainline closures; an Interstate name alone is insufficient. Reject missing lanes, no general lanes, unsupported states/configurations, and zero open general lanes. Shoulder and exit-lane entries remain separate. | [Maryland SHA freeway/expressway context][M]; user-confirmed conservative scope; raw description of AZ `388321` | `_scope_evidence`; `ALLOWED_LANE_CONFIGS`; `_evaluate_closure_capacity` independent scope/input checks | `test_capacity_reject_explicit_exit_ramp`; `test_capacity_scope_unconfirmed`; `test_capacity_requires_lane_list`; `test_scope_does_not_reject_ramp_location_reference` |
| 8 | Model capacity rather than equating it to the open-lane fraction: use LCSI and the Appendix A equation, report pc/h per open lane and same-direction total, and expose a parameter-scenario envelope. Fixed alpha=13.4% is an explicit modeling assumption. | [Maryland SHA Appendix A, pp. 12–13][M]; user-confirmed endpoint-scan assumption | `_maryland_capacity_envelope`; `_evaluate_closure_capacity`; `ALPHA_PERCENT` | `test_capacity_two_to_one_speed_55_south`; `test_capacity_two_to_one_speed_55_north`; `test_per_open_lane_and_total_quantities` |
| 9 | Separate speed-input quality from capacity: distinguish positive, nonpositive, and missing values. The selected capacity equation does not use speed. Report work_zone_type as context; static/moving does not supply an HCM duration category. | [Maryland SHA Appendix A][M]; [WZDx WorkZoneType][WT]; user-confirmed input handling | `_inspect_speed`; `_evaluate_closure_capacity`; `estimate_closure_capacity` | `test_capacity_zero_speed_invalid_not_missing`; `test_capacity_speed_missing`; `test_moving_field_is_not_duration` |
| 10 | A remaining/loss percentage needs a finite positive non-work-zone baseline and its source. Without them, keep absolute capacity available when otherwise supported, but leave percentages unknown. A raw listed-lane fraction is not a capacity ratio. | User-confirmed baseline contract; [Maryland SHA capacity-ratio definition][M]; dimensional check | `_evaluate_closure_capacity` `percentage_issues`; `_evaluate_capacity_plain`; `estimate_closure_capacity` | `test_capacity_explicit_baseline_arithmetic`; `test_baseline_source_required_without_losing_absolute_capacity`; `test_invalid_baseline_does_not_block_absolute_capacity`; `test_plain_vs_capacity_exit_ramp_scope` |

[WZ]: https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/objects/WorkZoneRoadEvent.md
[LT]: https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/enumerated-types/LaneType.md
[LS]: https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/enumerated-types/LaneStatus.md
[VI]: https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/enumerated-types/VehicleImpact.md
[WT]: https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/enumerated-types/WorkZoneType.md
[M]: https://www.roads.maryland.gov/OOTS/13LaneClosureGuidelinesrev1.pdf#page=12

### Reference Time & Edge-Case Definitions

- **Reference time:** Unified on `WZDX_NOW` (`2026-11-05T14:21:00Z`) to stay consistent with `wzdx_tools.py` and the course test suite, avoiding boundary drift from the 28-minute gap between the FDOT and AZ511 feed timestamps.
- **Date-order check before lifecycle handling:** If `start_date > end_date`, assign **`Low (Time Conflict)`** before checking `event_status`, `Scheduled`, or the planned-end branches. This applies to 92 AZ511 records and 0 FDOT records in the Nov 5 snapshots.
- **Status-first lifecycle handling after the date-order check:**
  - **When `event_status` is present (FDOT):**
    - `completed` (1,056 records) → **`Completed (Inactive)`**. The feed marks these records completed; the tool excludes them from active-action grading rather than treating their presence as a low-trust error.
    - `pending` (719 records) → **`Scheduled (Not Yet Active)`**.
    - `active` (1,334 records) → Evaluated for `High` / `Medium` / `Low`. For the 4 records marked `active` whose `start_date` is still after `WZDX_NOW`, the tool flags a schedule-status mismatch and caps trust at **`Medium`** (verify via CCTV whether work started early).
  - **When `event_status` is absent (AZ511):**
    - After excluding time conflicts, `start_date > WZDX_NOW` (1,190 records) → **`Scheduled (Not Yet Active)`**.
    - After excluding time conflicts and scheduled records, `end_date < WZDX_NOW` applies to 523 records. The raw count before excluding time conflicts is 553; it is not the count entering this branch.
    - **Planned-end split without a fixed freshness threshold:** For these 523 records, `update_date >= end_date` (486 records) is capped at **`Medium`** with a verification note; `update_date < end_date` (37 records) is assigned **`Low`**. The repository's warning that a past planned end does not prove work has finished is separate from this plan's update-versus-end rule. The comparison describes the reported timestamps; it does not confirm that work is still underway. These are time-condition counts, not final trust-tier totals; other checks may also require `Low`.
    - The remaining 1,638 AZ511 records proceed to the other trust checks.

These counts use only work-zone records: 3,109 FDOT and 3,443 AZ511, excluding FDOT's detour events. In the 486-record post-end-update branch, every record also has unknown impact, no lane list, and all four verification flags False. Consequently the time component is capped at Medium but the final AND-rule outcome is Low. The existing real-record test preserves that distinction.

Input validation occurs before domain grading. Unparseable/missing start or end timestamps, an unrecognized nonempty status, nonboolean reported verification values, and damaged lane inputs return an Error without a trust tier. On valid inputs, date-order conflict remains the first grading rule. A missing update timestamp cannot support the update-versus-end comparison.

### Edge-Case Definitions (from the Nov 5 FDOT & AZ511 Snapshots)

- **Not-yet-started records without an explicit `event_status` (after the date-order check, `start_date` after `WZDX_NOW`):** Assigned a separate status, **`Scheduled (Not Yet Active)`**, rather than forcing them into `High` / `Medium` / `Low`. Records with an explicit `event_status` follow the status-first handling above, including the FDOT active/future-start exception.
- **Missing lane evidence uses AND:** Assign `Low` for missing lane-level evidence only when `vehicle_impact = unknown` **and** `lanes` is missing or empty **and** none of the four date/position verification fields is `True`. If `vehicle_impact = unknown` but a nonempty `lanes` list is present and the four verification fields are all `False`, assign **`Medium`**, unless a higher-priority conflict requires `Low`. A nonempty list provides the reported lane entries; it does not independently establish that every physical lane is represented.
- **Vehicular travel lanes for consistency checks:** Both `general` and `exit-lane` count as vehicular travel lanes, while `shoulder` does not. An `all-lanes-closed` record listing only a closed `exit-lane` is treated as consistent (in capacity estimation, however, `exit-lane` closures are reported separately and excluded from mainline `general` lane counts).
- **Closure/restriction claims:** `some-lanes-closed`, `all-lanes-closed`, and `alternating-one-way` enter the vehicular consistency checks. For alternating one-way operation, a listed `alternating-flow` status is compatible; a literal `closed` entry is not required for that compatibility result.
- **Shoulder-only closures coded differently:**
  - `all-lanes-open` + only `shoulder` closed (18 AZ511 records) → **Consistent**, because shoulders are not travel lanes and the summary will not mislead an operator into thinking a travel lane is blocked.
  - `some-lanes-closed` + all `general` lanes open + only `shoulder` closed (1 FDOT record) → **Conflict (`Low`)**, because the summary field overstates the closure and could trigger a false travel-lane closure alert if taken at face value.

### Capacity method and source boundary

The checked capacity source is the [public Maryland SHA guideline][M], revised November 6, 2024. Its Appendix A reproduces an HCM-based procedure; the Table 1 footnote attributes its calculation to HCM 7th edition equations 10-8 and 10-9. This work does not claim direct consultation of the HCM book.

The implementation uses the published indicator alternatives and lateral-distance domain to form a scenario envelope, with alpha fixed at the reported mean of 13.4%. Selecting that mean and combining the domain endpoints are project assumptions, not universal site defaults or validated physical bounds. The admitted lane configurations are a conservative subset taken from Maryland Table 1. Applying this procedure outside Maryland is a screening assumption, not Arizona calibration.

The four checked Interstate partial-closure records all list 2 general lanes, 1 open. Their displayed total is about 1560–2190 pc/h under the same parameter scenarios. Each result states the assumption that listed general entries represent the event's normal mainline lanes. There is no checked mainline full-closure case in this group; AZ `388321` is an exit-ramp event and cannot fill that gap.

## Plain vs. yours

This section records expected implementation differences, not observed model performance or ablation grades. In `server.py`, `ABLATION=plain` retains the two tool names but uses generic descriptions and `RAW_RESULTS`: original properties plus reference/feed times. Full mode returns the rule-based briefing. Whether a model interprets either representation correctly must be established from the saved runs.

| Frozen record | What the plain server exposes | What the full implementation adds |
|---|---|---|
| AZ `351676` | all-lanes-open, general/open and shoulder/closed entries, and four False verification fields | Explains shoulder compatibility and returns Medium for unverified evidence, rather than asserting field confirmation. Its description identifies ramp work; it does not establish I-10 mainline status. |
| AZ `lmsaCxKAd/C/B4u3LIJ7zNUM0E8=` | I-17 southbound left-lane closure, two general entries, dates, and 88.514 km/h | The trust tool returns Medium. The capacity tool gives the scoped 2-to-1 scenario envelope and keeps percentage loss unknown without a sourced baseline. |
| AZ `388321` | I-10 Eastbound road label, an exit-ramp description, and one general/closed entry | Refuses freeway mainline capacity estimation from this ramp event; does not turn its zero listed-open fraction into zero I-10 mainline capacity. |

The separate helper `estimate_closure_capacity_plain` is a unit-test baseline, not the function served in plain MCP mode. It reports counts and the explicitly labeled listed-lane open fraction. For `388321`, that fraction is 0/1. `test_plain_vs_capacity_exit_ramp_scope` compares those raw counts with the domain tool's refusal; it does not demonstrate that a model actually made a scope error.

The record facts and reference outcomes are fixed before viewing model answers. The [model-run report](AGENT_RUN.md) and [ablation report](ABLATION.md) record actual calls, preserved responses, and disagreements with these references. No success rate, grade, or claim of full-mode superiority is inferred from the unit tests or this table.

### Observed model comparison

The nine fixed-condition runs do not establish that the full tools outperform the other settings. In `mainline_trust_and_capacity`, the plain condition copied the complete ID and retrieved raw fields; full mode truncated it and retrieved no record. Neither delivered the requested numerical capacity envelope. In `exit_ramp_scope_limit`, the full condition did not call the scope tool, so its generic refusal is not evidence that it applied the ramp rule. The earlier baseline agent run actually read the refusal and still invented zero mainline capacity. These are model-use failures documented in the reports, rather than failures of the independently tested arithmetic.

The refused-ramp briefing was corrected after that observed error: its reported general entries are event-scoped, not labeled as a mainline inventory, and its mainline capacity remains explicitly unknown. `test_refused_ramp_briefing_does_not_label_mainline_inventory` preserves that real-record presentation regression.

## What the data cannot tell

- **`High` trust does not prove cones are on the road right now:** A static snapshot can only verify that the tool reads and applies the rules correctly. It cannot prove that a crew is actively blocking lanes at this minute or that they did not pack up early. Major detour or DMS decisions still need CCTV or field confirmation.
- **All-`False` verification fields do not mean a feed is fake:** None of AZ511's four verification fields is True in this snapshot. The snapshot does not establish why these flags are False or independently verify whether work is present.
- **Listed lanes do not prove a complete physical inventory:** A nonempty array supplies reported entries. Consecutive lane orders and an Interstate label alone do not verify the full roadway cross section or the event's mainline scope.
- **The capacity envelope does not predict queues, delay, or an alert threshold:** The selected records do not supply observed demand, a non-work-zone capacity baseline, or the site factors needed for local calibration. The tool reports modeled capacity in pc/h, not converted veh/h, measured throughput, or a percentage loss without a sourced baseline. It does not infer field barrier type, heavy-vehicle effects, terrain, or actual operational control from these records.

## AI use

- **Claude:** Helped create the initial `inspect_wzdx.py`, examine WZDx fields and existing tools, and organize the supplied rule notes and earlier Markdown materials.
- **Codex:** Helped inspect the snapshots and sources, check record fields and capacity arithmetic, implement and debug the tools/tests/MCP server, and automate the local-model runs and ablation. It also helped draft and format technical explanations, reference checks, ratings, and comparisons from the supplied task/rule decisions and preserved experimental evidence.
- **Local Qwen3 through Ollama:** Generated the model answers evaluated here. The saved API fields, prompts, tool calls, and natural-language replies are preserved; model responses were not rewritten.
- **Source scope:** The directly consulted capacity source is Maryland SHA's public Appendix A reproduction, with its HCM attribution reported as such. The analysis does not claim direct consultation of the original HCM chapters or field/CCTV confirmation. The operational tiers and modeling assumptions are the project decisions recorded in the working discussion.
