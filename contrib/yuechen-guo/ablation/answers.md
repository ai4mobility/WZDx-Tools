# The answers: 3 questions x 3 setups

Written by contrib/ablation.py. Model Qwen/Qwen3-1.7B, thinking off, seed 1, on mps. Data: WZDx snapshot snapshots/2026-11-05.

Read each answer against the right answer, then grade it in the table in ABLATION.md: right, partly or wrong, and why in a few words. The table to copy:

| Question | A. Without your tools | B. Your tools, plain | C. Your tools as written |
|---|---|---|---|
| sidewalk_end_time | wrong — The 0.5-mile search missed the closure and gave no end time. | partly — It gave the correct date but left out 4:00 PM EST. | right — It gave the full local time, called it an estimate, and explained that reopening still needs confirmation. |
| sidewalk_closure_and_detour | wrong — It used an empty 0.5-mile search to say there was no reported closure on the street. | partly — It found the closure and the correct date, but told me to walk southbound without a reported detour. | partly — It found both records and the estimated end time, but stopped before checking either ID for a linked detour. |
| southbound_extra_walking_time | wrong — It told me my walk would take two weeks by confusing the construction period with walking time. | partly — It correctly said the route and walking time were unknown, but checked the parent ID instead of the southbound record I asked about. | wrong — It searched coordinates I never gave, missed the reported closure, and confused the construction period with extra walking time. |

## sidewalk_end_time

**Question:** I walk to class on North 30th Street near USF (28.0587, -82.4139). When is the sidewalk closure expected to end, in local time?

**Right answer (tasks.json):** Both closure records give the same estimated end time of December 15, 2026, at 4:00 PM EST. I still need confirmation that the sidewalk has reopened. I checked the end_date and end_date_accuracy fields in snapshots/2026-11-05/fldot.json.gz for records 4233451340/245269615 and 4233451340/245269615-R.

### A. Without your tools

Tools called: `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=0.5)`. 2 turns, 48 s. Run: `ablation/runs/without__sidewalk_end_time.json`

> No active work zone is reported within 0.5 mi of (28.05870, -82.41390) in the FL feed. This indicates that there is no active work zone reported in the vicinity of your location. However, it is important to note that feeds may miss work zones, and positions are often estimated. If you are concerned about a sidewalk closure, you may want to check with local authorities or use a more detailed mapping service for accurate information.

### B. Your tools, plain

Tools called: `find_sidewalk_closures(feed='FL', street='North 30th Street', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0)`. 2 turns, 32 s. Run: `ablation/runs/plain__sidewalk_end_time.json`

> The sidewalk closure on North 30th Street is expected to end on December 15, 2026, in local time.

### C. Your tools as written

Tools called: `find_sidewalk_closures(feed='FL', street='North 30th Street', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0)`. 2 turns, 46 s. Run: `ablation/runs/full__sidewalk_end_time.json`

> The sidewalk closure on North 30th Street is reported to end on December 15, 2026, at 4:00 PM EST. The closure is reported to be active and has an estimated end time. The closure is described as a footway closure, and the reported end time does not confirm that the sidewalk has reopened. For any walking directions, you should call get_pedestrian_detour_info for each relevant ID.

## sidewalk_closure_and_detour

**Question:** I walk to class near USF at (28.0587, -82.4139). Is there a reported sidewalk closure on North 30th Street? When is it expected to end, and does the report tell me which way to walk around it?

**Right answer (tasks.json):** Yes. The snapshot reports a footway closure on North 30th Street in two records, one northbound and one southbound. Both give an estimated end of December 15, 2026, at 4:00 PM EST. Neither description gives walking directions, and neither record has a linked detour. The direction labels describe the closure records and give me no route to follow. I checked records 4233451340/245269615 and 4233451340/245269615-R in snapshots/2026-11-05/fldot.json.gz and checked the linked detours for both IDs.

### A. Without your tools

Tools called: `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=0.5)`. 2 turns, 40 s. Run: `ablation/runs/without__sidewalk_closure_and_detour.json`

> The check_location function indicates that there are no active work zones reported within 0.5 miles of your location (28.05870, -82.41390) in the Florida feed. This means that, based on the data from the Florida feed, there is no reported sidewalk closure on North 30th Street.
>
> However, it is important to note that the feed may not capture all work zones, and the reported data might not always be accurate. If you are concerned about a sidewalk closure, you might want to check with local authorities or use additional sources for confirmation. 
>
> If you need further details about the sidewalk closure, you might need to use the `get_work_zones` function with specific parameters to search for any work zones near North 30th Street.

### B. Your tools, plain

Tools called: `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=0.5)`, `find_sidewalk_closures(feed='FL', street='North 30th Street', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0)`. 3 turns, 90 s. Run: `ablation/runs/plain__sidewalk_closure_and_detour.json`

> The sidewalk closure on North 30th Street is reported as active and is expected to end on December 15, 2026. The report indicates a footway closure in the northbound direction. To avoid the closure, you should walk southbound. The report does not specify a detour route, so you may need to adjust your route accordingly.

### C. Your tools as written

Tools called: `find_sidewalk_closures(feed='FL', street='North 30th Street', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0)`. 2 turns, 38 s. Run: `ablation/runs/full__sidewalk_closure_and_detour.json`

> There are reported sidewalk closures on North 30th Street. The closure records are:
>
> 1. **Northbound**: 
>    - **Reported end**: 2026-12-15 16:00 EST (estimated)
>    - **Lane impact**: Unknown
>    - **Direction**: Northbound
>
> 2. **Southbound**: 
>    - **Reported end**: 2026-12-15 16:00 EST (estimated)
>    - **Lane impact**: Unknown
>    - **Direction**: Southbound
>
> The reported end times are estimates, and the sidewalk closures are not confirmed to have been reopened. The closure records do not provide specific walking directions, and the tool cannot estimate walking time or confirm a safe alternate path. For a detour question, call `get_pedestrian_detour_info` for each relevant ID before answering.

## southbound_extra_walking_time

**Question:** I walk to class on North 30th Street. For work zone 4233451340/245269615-R in Florida, does the report say which way I should walk around the closed sidewalk? How much longer will my walk take?

**Right answer (tasks.json):** The southbound record reports a footway closure. Its description gives no walking directions, and the record has no linked detour. I cannot tell from this record which way to walk or how many extra minutes the walk would take. The estimated construction end time does not tell me the length of my walk. I checked the description and linked detours for record 4233451340/245269615-R in snapshots/2026-11-05/fldot.json.gz.

### A. Without your tools

Tools called: `get_work_zones(feed='FL', road='North 30th Street', near_lat=None, near_lon=None, radius_mi=5.0, status='active', max_results=10)`. 2 turns, 74 s. Run: `ablation/runs/without__southbound_extra_walking_time.json`

> The work zone ID provided is 4233451340/245269615-R, which is for a work zone on North 30th Street in Florida. The report does not specify which way you should walk around the closed sidewalk, as the direction is not reported. 
>
> The work zone is active and has a duration of 2 weeks (from Tue Sep 8 07:00 EDT to Tue Dec 15 16:00 EST). The work zone is reported by the City of Tampa, Florida, and the position and dates are not verified. 
>
> Since the work zone is active and the direction is not reported, you should walk around the closed sidewalk in the direction you are going. The work zone is expected to last for approximately 2 weeks, so your walk will take about 2 weeks.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='fldot', road='North 30th Street', radius_mi=5.0)`, `check_location(feed='fldot', lat=33.4938, lon=-82.0162, radius_mi=0.5)`, `get_detours(feed='fldot', work_zone_id='4233451340')`. 5 turns, 126 s. Run: `ablation/runs/plain__southbound_extra_walking_time.json`

> The report does not indicate which way to walk around the closed sidewalk. Additionally, there is no information provided about how long the walk will take.

### C. Your tools as written

Tools called: `find_sidewalk_closures(feed='FL', street='North 30th Street', near_lat=39.7362, near_lon=-83.0053, radius_mi=5.0)`. 2 turns, 74 s. Run: `ablation/runs/full__southbound_extra_walking_time.json`

> The report does not indicate any closed sidewalks on North 30th Street. The work zone report does not confirm the presence of a closed sidewalk, and the sidewalk access is unconfirmed. Therefore, there are no specific walking directions provided for avoiding a closed sidewalk. The report also does not indicate how long the work zone will last, so it is difficult to estimate how much longer your walk will take.
