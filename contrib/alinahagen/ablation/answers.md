# The answers: 3 questions x 3 setups

Written by contrib/ablation.py. Model Qwen/Qwen3-1.7B, thinking off, seed 1, on mps. Data: WZDx snapshot snapshots/2026-11-05.

Read each answer against the right answer, then grade it in the table in ABLATION.md: right, partly or wrong, and why in a few words. The table to copy:

| Question | A. Without your tools | B. Your tools, plain | C. Your tools as written |
|---|---|---|---|
| bayshore_blvd | F | D | C |
| north_oregon | D | F | C |
| south_village | F | F | F |

## bayshore_blvd

**Question:** I am planning utility work on Bayshore Boulevard (27.932268, -82.472911). How many active work zones are currently reported on this road?

**Right answer (tasks.json):** No active work zones are reported on Bay Boulevard. However, the absence of reported work zones does not necessarily indicate that the roadway is free of construction.

### A. Without your tools

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='fldot', road='Bayshore Boulevard', radius_mi=5.0, status='active')`. 3 turns, 22 s. Run: `ablation/runs/without__bayshore_blvd.json`

> The active work zone on Bayshore Boulevard is reported by the City of Tampa, Florida. The work zone is for concrete slab repairs and is scheduled to be active from Wednesday, October 14, 2023, at 08:30 EDT to Friday, November 6, 2023, at 15:30 EST. The lane impact is unknown, and the position and dates of the work zone have not been verified.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='fldot', road='Bayshore Boulevard', radius_mi=5.0)`. 3 turns, 22 s. Run: `ablation/runs/plain__bayshore_blvd.json`

> The active work zone on Bayshore Boulevard is reported as "lane impact unknown" and is not verified. There is 1 active work zone reported on Bayshore Boulevard.

### C. Your tools as written

Tools called: `check_location(feed='FL', lat=27.932268, lon=-82.472911)`. 2 turns, 29 s. Run: `ablation/runs/full__bayshore_blvd.json`

> 1 active work zone(s) reported within 0.5 mi of (27.93227, -82.47291):
> - Bayshore Boulevard · southbound · 0.0 mi away · lane impact unknown (not reported)
>   ROW-26-0002424 Concrete slab repairs
>   Wed Oct 14 08:30 EDT to Fri Nov 6 15:30 EST · reported by City of Tampa, Florida · position not verified, dates not verified · id 4475220461

## north_oregon

**Question:** We are considering a road closure on North Oregon Avenue (27.958576, -82.474650). Are there any nearby construction projects that might create traffic conflicts?

**Right answer (tasks.json):** The proposed closure warrants further review due to existing construction activity on North Rome Avenue and Chestnut Street. These nearby projects may contribute to traffic disruptions, so additional coordination is recommended before approving the permit.

### A. Without your tools

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='fldot', road='North Oregon Avenue', near_lat=27.958576, near_lon=-82.47465, radius_mi=5.0)`. 3 turns, 25 s. Run: `ablation/runs/without__north_oregon.json`

> The work zone on North Oregon Avenue is reported by the City of Tampa, Florida, and is active from September 17, 2023, to December 8, 2023. The work zone is located 0.8 miles away and has a lane impact that is unknown. The work zone is not verified in terms of its position and dates, so it is not confirmed to be active at the current time. Therefore, there may be traffic conflicts near this area.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='fldot', road='North Oregon Avenue', near_lat=27.958576, near_lon=-82.47465, radius_mi=0.5)`. 3 turns, 25 s. Run: `ablation/runs/plain__north_oregon.json`

> 0 active work zones were found near North Oregon Avenue (27.958576, -82.474650) in the fldot feed. The lane impact is unknown for 0 of 0 work zones.

### C. Your tools as written

Tools called: `work_zones_during_hours(feed='FL', street='North Oregon Avenue', near_lat=27.958576, near_lon=-82.47465, radius_mi=1.0, start_hour=11, end_hour=14, check_date='2023-10-05')`. 2 turns, 56 s. Run: `ablation/runs/full__north_oregon.json`

> The tool returned the following results:
>
> 1. **[OUTSIDE] ID=4336587447**:
>    - **Status**: Active
>    - **Distance**: 0.76 mi
>    - **Roads**: Fig Street, North Oregon Avenue
>    - **Recorded Interval**: 2026-09-17 09:00 EDT -> 2026-12-08 16:00 EST
>    - **Vehicle Impact**: Unknown (note: dated record)
>
> 2. **[OUTSIDE] ID=4499310675**:
>    - **Status**: Active
>    - **Distance**: 0.98 mi
>    - **Roads**: South Oregon Avenue
>    - **Recorded Interval**: 2026-11-05 06:00 EST -> 2026-11-20 23:59 EST
>    - **Vehicle Impact**: Unknown (note: dated record)
>
> ### Interpretation:
> - **No confirmed conflicts** on North Oregon Avenue during the requested time window (11:00 EDT to 14:00 EDT on 2023-10-05).
> - However, there is **high concurrent activity** nearby, particularly with the work zone on **Fig Street** and **South Oregon Avenue**.
> - **Recommendations**:
>   - **Field verification** is recommended before issuing the permit to confirm the presence and timing of the work zones.
>   - **Consider postponing** the permit issuance if the work zones are critical or if the impact is significant.
>   - **Verify coverage**, **lane restrictions**, and **field conditions** before finalizing the permit.
>
> If you need further details about the work zones or their impact, please provide additional information.

## south_village

**Question:** I am planning to schedule construction work on South Village Avenue (28.062669, -82.480072). Are there existing work zones nearby that might affect whether the permit should be approved?

**Right answer (tasks.json):** The proposed work should be reconsidered due to the substantial amount of existing construction activity in the surrounding area. Additional review and coordination are recommended before issuing another closure permit.

### A. Without your tools

Tools called: `list_feeds(state='florida')`, `check_location(feed='FL', lat=28.062669, lon=-82.480072, radius_mi=0.5)`. 2 turns, 24 s. Run: `ablation/runs/without__south_village.json`

> The check_location tool returned that there are no active work zones reported within 0.5 miles of the given coordinates (28.06267, -82.48007) in the fldot feed. This suggests that there are no active work zones reported in the vicinity. However, it is important to note that the feed may not capture all work zones, and the presence of cones, barrels, or workers could indicate a work zone that is not reported by the system. Therefore, while there are no reported active work zones in the immediate area, it is still advisable to consult with local authorities or use additional tools to confirm the presence of any work zones.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='fldot', road='South Village Avenue', near_lat=28.062669, near_lon=-82.480072, radius_mi=5.0)`. 3 turns, 26 s. Run: `ablation/runs/plain__south_village.json`

> 0 active work zones are reported near South Village Avenue (28.062669, -82.480072) in the fldot feed (WZDx 4.2, updated Thu Nov 5 09:21 EST). The lane impact is unknown for 0 of 0 work zones.

### C. Your tools as written

Tools called: `work_zones_during_hours(feed='FL', street='South Village Avenue', near_lat=28.062669, near_lon=-82.480072, radius_mi=1.0, start_hour=11, end_hour=14, check_date='2023-10-05')`. 2 turns, 33 s. Run: `ablation/runs/full__south_village.json`

> Based on the tool response, there are no active or pending work zones within the specified radius of South Village Avenue (28.0627, -82.4801) during the requested time window (11:00 EDT to 14:00 EDT). Therefore, there are no conflicts that would prevent the permit from being approved. However, it is recommended to verify the coverage, lane restrictions, and field conditions before finalizing the permit approval.
