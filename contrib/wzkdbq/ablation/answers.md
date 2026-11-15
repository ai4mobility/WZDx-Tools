# The answers: 3 questions x 3 setups

Written by contrib/ablation.py. Model Qwen/Qwen3-1.7B, thinking off, seed 1, on cpu. Data: WZDx snapshot snapshots\2026-11-05.

Read each answer against the right answer, then grade it in the table in ABLATION.md: right, partly or wrong, and why in a few words. The table to copy:

| Question | A. Without your tools | B. Your tools, plain | C. Your tools as written |
|---|---|---|---|
| busch_eastbound | ? | ? | ? |
| miami_detour | ? | ? | ? |
| busch_unknown_impact | ? | ? | ? |

## busch_eastbound

**Question:** Dispatch reported a crash near USF. In the FDOT snapshot, what eastbound work-zone lane closure is reported on Busch Blvd within 5 mi of 28.0587, -82.4139? Give the affected travel lane and flag any record whose direction is missing.

**Right answer (tasks.json):** FDOT reports an eastbound work-zone closure of the rightmost of three general travel lanes. Check snapshots/2026-11-05/fldot.json.gz feature 4577091647/292055206: lane order 4 is closed, orders 1 and 5 are shoulders, and orders 2 through 4 are general lanes. Feature 4577091647 has unknown direction and unknown impact; keep it separate from the eastbound match. This is work-zone evidence.

### A. Without your tools

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='FL', road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`. 3 turns, 56 s. Run: `ablation/runs/without__busch_eastbound.json`

> The reported work zone on East Busch Boulevard is eastbound, and the direction is not reported. The affected travel lane is the eastbound lane. The lane impact is unknown, as indicated by the "lane impact unknown" status. No record has a missing direction.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='FL', road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0)`. 3 turns, 60 s. Run: `ablation/runs/plain__busch_eastbound.json`

> The work zone reported on East Busch Boulevard is not directed (direction not reported). The affected travel lane is the eastbound lane. The lane impact is unknown, and the direction is missing.

### C. Your tools as written

Tools called: `crash_area_work_zone_constraints(road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, direction='eastbound', radius_mi=5.0)`. 2 turns, 111 s. Run: `ablation/runs/full__busch_eastbound.json`

> FDOT work-zone screen: Busch Blvd, eastbound, within 5 mi of (28.0587, -82.4139). Saved FDOT snapshot, published update 2026-11-05 14:21 UTC.
>
> Reported eastbound records: 1.
> - 4577091647/292055206 · FDOT reports eastbound · 2.08 mi · some lanes closed; right lane of 3 closed · reported end 2026-11-05 21:00 UTC (feed reports end verified)
>
> Separate records with unknown direction: 1.
> - 4577091647 · direction unknown; this record is not assigned to eastbound · 2.12 mi · lane impact not reported; specific closed travel-lane position not established · reported end 2026-11-05 21:00 UTC (end unverified)
>
> Nearby active records without a road name: 5. The name search cannot assign them to this road.
>
> This is a work-zone proximity screen. Verify crash conditions and route suitability independently.

## miami_detour

**Question:** For FDOT work-zone feature 4571671574, what published detours does the toolkit list, then which is northbound when checked by direction? Include its reported end time and whether the feed has verified the end.

**Right answer (tasks.json):** The snapshot links two Miami Gardens detour records to 4571671574. The northbound record is 4571671574/291384760, named '441 nb to I95 nb using Miami Gardens Detour'; reported end is 2026-11-30 10:00 UTC (05:00 EST), unverified. The other linked feature, 4571671574/291384760-R, is southbound despite the identical name. Check snapshots/2026-11-05/fldot.json.gz, those three IDs, core_details.related_road_events, direction, end_date and is_end_date_verified.

### A. Without your tools

Tools called: `get_work_zones(feed='FL', road='I-75', near_lat=None, near_lon=None, radius_mi=5.0, status='active', max_results=1)`, `get_detours(feed='FL', work_zone_id='4571671574')`. 2 turns, 71 s. Run: `ablation/runs/without__miami_detour.json`

> The published detours for work zone 4571671574 are as follows:
>
> 1. **441 nb to I95 nb using Miami Gardens Detour** - **Northbound** · **Mon Nov 2 22:00 EST to Mon Nov 30 05:00 EST**
> 2. **441 nb to I95 nb using Miami Gardens Detour** - **Southbound** · **Mon Nov 2 22:00 EST to Mon Nov 30 05:00 EST**
>
> The feed has verified the end time for both detours, and the reported end time is as specified. The lane impact for this work zone is unknown, and the position and dates were verified.

### B. Your tools, plain

Tools called: `get_work_zones(feed='FL', road='Fowler Avenue', near_lat=None, near_lon=None, radius_mi=5.0, status='active', max_results=10)`. 2 turns, 49 s. Run: `ablation/runs/plain__miami_detour.json`

> The toolkit does not list any active work zones for the specified feed (FL) with the given parameters. Therefore, there are no detours associated with the work zone feature 4571671574.

### C. Your tools as written

Tools called: `linked_work_zone_detours_for_direction(work_zone_id='4571671574', direction='northbound')`. 2 turns, 70 s. Run: `ablation/runs/full__miami_detour.json`

> FDOT work-zone 4571671574 has the following published detours:
>
> 1. **Northbound Detour**:
>    - **Detour ID**: 4571671574/291384760
>    - **Detour Name**: FDOT reports northbound
>    - **Direction**: Northbound
>    - **Detour Route**: 441 nb to I95 nb using Miami Gardens Detour
>    - **Reported Start Time**: 2026-11-03 03:00 UTC
>    - **Reported End Time**: 2026-11-30 10:00 UTC
>    - **End Time Verified**: Unverified
>
> The feed does not verify the end time of the detour. The TMC operator is responsible for verifying the current conditions and incident response plan before using the result.

## busch_unknown_impact

**Question:** Check westbound Busch Blvd within 5 mi of 28.0587, -82.4139 in the FDOT work-zone snapshot. Can I tell dispatch that all westbound lanes are open and clear for a crash diversion? What is missing?

**Right answer (tasks.json):** No. There is no explicitly westbound match on this road in the search, and the record with unknown direction also has unknown lane impact. FDOT feature 4577091647 has both fields unknown and no lane inventory. The lane closure in 4577091647/292055206 is eastbound, so do not transfer it westbound. Use dispatch, a camera or field staff to verify actual westbound availability and confirm diversion suitability. Check core_details.direction, vehicle_impact and lanes in snapshots/2026-11-05/fldot.json.gz.

### A. Without your tools

Tools called: `get_work_zones(feed='FL', road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`, `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=5.0)`, `get_detours(feed='FL', work_zone_id='4577091647')`. 3 turns, 62 s. Run: `ablation/runs/without__busch_unknown_impact.json`

> The work zone with ID 4577091647 does not have a detour route linked to it in the FDOT feed.
>
> What is missing? The work zone has a reported start and end time, but the position and dates were not verified. Additionally, the lane impact is unknown, and there is no detour route associated with it.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='FL', road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`, `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=5.0)`, `get_detours(feed='FL', work_zone_id='4577091647')`, `feed_quality(feed='FL')`. 5 turns, 126 s. Run: `ablation/runs/plain__busch_unknown_impact.json`

> The FDOT work-zone feed is comprehensive, but there are several things to note:
>
> 1. **Lane Impact**: Most work zones have an unknown lane impact, with 96% of them having this status.
> 2. **Position Verification**: Only 19% of start positions are verified, and 595 of the start dates are verified.
> 3. **Road Names**: 22% of work zones do not have a road name reported.
> 4. **Reporting Organizations**: The top reporting organizations include Plant City, FL, Florida DOT, and Hillsborough County, FL.
>
> Based on the information provided, there are no reported work zones within 5 miles of the given coordinates. However, it's important to note that feeds may miss work zones, and positions can be estimated. Therefore, it is not possible to definitively say that all westbound lanes are open and clear for a crash diversion. The information provided is limited and may not be fully accurate.

### C. Your tools as written

Tools called: `get_work_zones(feed='FL', road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`, `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=5.0)`, `get_detours(feed='FL', work_zone_id='4577091647')`. 3 turns, 94 s. Run: `ablation/runs/full__busch_unknown_impact.json`

> The work zone with ID 4577091647 does not have a linked detour route in the FDOT feed. Therefore, there is no published detour for this specific work zone.
>
> For the crash diversion, you can inform dispatch that all westbound lanes are open and clear based on the information provided. However, it is important to note that the work zone's lane impact is unknown, and the position and dates of the work zone are not verified. Therefore, the actual conditions may vary, and it is recommended to verify with the TMC operator or dispatch before making any decisions. 
>
> What is missing is the verification of the work zone's position and dates, as well as the lane impact status. The feed does not provide verified position and dates, which could affect the accuracy of the information provided.
