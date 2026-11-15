## Setup

- Model: `Qwen/Qwen3-1.7B`, seed 1. Question 1 and its rerun used thinking. Questions 2 and 3 used `--no-think`.
- Date: November 15, 2026.
- Data: FDOT WZDx snapshot `snapshots/2026-11-05` with the clock pinned to the snapshot time.
- Computer: AMD Ryzen 5 7600X, CPU only. Model generation for the three runs took 185, 80, 109 seconds respectively.

## Questions

### Question 1: Directional lane closure

**Question:** Dispatch reported a crash near USF. In the FDOT snapshot, what eastbound work-zone lane closure is reported on Busch Blvd within 5 mi of 28.0587, -82.4139? Give the affected travel lane and flag any record whose direction is missing.

**Transcript:** [runs/crash_q1.md](runs/crash_q1.md)

**Tool calls:**

- `crash_area_work_zone_constraints(road="Busch Blvd", near_lat=28.0587, near_lon=-82.4139, direction="EB", radius_mi=5)` (ok)

**What the loop shows:** In [Step 1](runs/crash_q1.md#step-1), the tool description and input schema appear
in the prompt. The model considers the general work-zone lookup and then chooses the crash-area tool
because the question gives a road, coordinates, and a direction. Its `<tool_call>` sets `EB` and a
five-mile radius. The harness sends `tools/call` and records the response with one eastbound record
and a separate record with unknown direction. The [Step 2 prompt](runs/crash_q1.md#step-2) inserts that
response in `<tool_response>`. The final answer keeps the lane position but blurs the boundary
between the eastbound finding and the direction-unknown flag.

**Answer:**

> The FDOT snapshot indicates a reported eastbound work zone on Busch Blvd within 5 miles of the crash location (28.0587, -82.4139). Key details:
> - **Distance**: 2.08 miles.
> - **Lane Closure**: Some lanes closed (right lane of 3 closed).
> - **Direction**: Reported (eastbound), but the **direction not reported** flag indicates uncertainty.
> - **End Date**: Verified as 2026-11-05 21:00 UTC.
>
> **Flags**:
> 1. **Direction missing**: 1 record (4577091647) lacks direction.
> 2. **Lane impact unknown**: 1 record (4577091647) has unknown lane impact.
>
> **Recommendation**: Verify the crash conditions and route alignment independently, as the tool response does not confirm actual lane availability or direction.

**My grade:** Partly correct. The model gets the rightmost of three travel lanes and names feature
`4577091647` as the unknown record. Its eastbound bullet suggests uncertainty about the direction
of the closure itself, even though feature `4577091647/292055206` explicitly reports eastbound.

### Question 2: Toolkit inventory and directional detour

**Question:** For FDOT work-zone feature 4571671574, first call get_detours with feed FL to list all published detours, then call linked_work_zone_detours_for_direction with NB to verify the northbound feature ID, reported end time, and whether the end is verified.

**Transcript:** [runs/crash_q2_toolkit_and_direction.md](runs/crash_q2_toolkit_and_direction.md)

**Tool calls:**

- `get_detours(feed="FL", work_zone_id="4571671574")` (ok)
- `linked_work_zone_detours_for_direction(work_zone_id="4571671574", direction="NB")` (ok)

**What the loop shows:** The [first prompt](runs/crash_q2_toolkit_and_direction.md#step-1) includes
both tool descriptions. The model emits two `<tool_call>` blocks in the same turn, using the feature
ID from the question in both. The first MCP response lists two same-named detours in different
directions. The second returns the northbound feature ID and an unverified end at 10:00 UTC. The
[next prompt](runs/crash_q2_toolkit_and_direction.md#step-2) includes both tool responses. The answer
quotes the northbound result but omits the second detour and calls the detour verified.

**Answer:**

> FDOT work-zone 4571671574. Saved FDOT snapshot, published update 2026-11-05 14:21 UTC.
> Reported northbound detour records: 1.
> - 4571671574/291384760 · FDOT reports northbound · 441 nb to I95 nb using Miami Gardens Detour · reported start 2026-11-03 03:00 UTC · reported end 2026-11-30 10:00 UTC (end unverified)
>
> The detour is reported and verified. The TMC operator verifies conditions and the incident response plan before use.

**My grade:** Partly correct. The northbound ID and reported end time match the snapshot. The answer
omits the southbound feature and contradicts the raw northbound record's
`is_end_date_verified: false` field.

### Question 3: Unknown westbound availability

**Question:** Check westbound Busch Blvd within 5 mi of 28.0587, -82.4139 in the FDOT work-zone snapshot. Can I tell dispatch that all westbound lanes are open and clear for a crash diversion? What is missing?

**Transcript:** [runs/crash_q3.md](runs/crash_q3.md)

**Tool calls:**

- `check_location(feed="FDOT", lat=28.0587, lon=-82.4139, radius_mi=5)` (ok)
- `list_feeds(state="florida")` (ok)
- `get_work_zones(feed="fldot", road="Busch Blvd", near_lat=28.0587, near_lon=-82.4139, radius_mi=5, status="active")` (ok)
- `get_detours(feed="fldot", work_zone_id="4577091647")` (ok)

**What the loop shows:** The first `tools/call` reaches the server, but the returned text rejects
`FDOT` as a feed name. The model uses `list_feeds` to recover the registry name `fldot` and passes
that name to the next lookup. The work-zone response says direction and lane impact are both
unreported for the retrieved feature. After the detour lookup returns no link, the
[final prompt](runs/crash_q3.md#step-5) includes that result as another `<tool_response>`.
The assistant correctly refuses to clear the westbound lanes, although it never calls the
direction-specific work-zone tool.

**Answer:**

> The work zone at East Busch Boulevard does not have a linked detour route in the FDOT feed. Therefore, there are no published detours for this work zone.
>
> For the crash diversion, the TMC operator verifies the current conditions and the incident response plan before using the result. Based on the information provided, the work zone is reported as having an unknown lane impact, and the position and dates are not verified. Therefore, it is not possible to definitively tell dispatch that all westbound lanes are open and clear for a crash diversion without verification.
>
> What is missing is the verification of the position and dates of the work zone, as well as the actual lane availability. The work zone's lane impact is unknown, and the position is not verified.

**My grade:** Partly correct. The answer correctly says the operator cannot confirm open westbound
lanes from the feed. It leaves out the unknown direction and does not distinguish the lack of a
westbound match from the separate eastbound closure shown in the reference evidence.

## One fix I made

The first run attached the unknown-direction flag to the eastbound finding in its final answer.
The tool now labels direction on each result row, puts unknown records in an explicitly separate
group, and identifies saved snapshot evidence. The rerun used the same question, model, seed, and
thinking setting. It identified which record had unknown direction, but its answer still used
"Lane impact: Unknown" for the eastbound finding. The tool response reports a closure on that record.

**Before:** [runs/crash_q1.md](runs/crash_q1.md)
**After:** [runs/crash_q1_after_fix.md](runs/crash_q1_after_fix.md)
