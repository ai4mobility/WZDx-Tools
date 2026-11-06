# The answers: 3 questions x 3 setups

Written by contrib/ablation.py. Model Qwen/Qwen3-1.7B, thinking off, seed 1, on cpu. Data: WZDx snapshot snapshots/2026-11-05.

Read each answer against the right answer, then grade it in the table in ABLATION.md: right, partly or wrong, and why in a few words. The table to copy:

| Question | A. Without your tools | B. Your tools, plain | C. Your tools as written |
|---|---|---|---|
| busch_lanes | ? | ? | ? |
| thirtieth_works | ? | ? | ? |
| thirtieth_lanes | ? | ? | ? |

## busch_lanes

**Question:** Is any work reported on Busch Blvd near USF (28.0587, -82.4139) right now, and which lanes are closed?

**Right answer (tasks.json):** Yes: one work by the City of Tampa on East Busch Boulevard, about 2 mi from the point, reported as 2 records, until Thu Nov 5 at 4:00 pm. Eastbound, the right lane of 3 travel lanes is closed (the feed lists it as lane 4 of 5, because it counts the shoulders). The other record gives no direction and no lane impact. Checked in snapshots/2026-11-05/fldot.json, work 4577091647.

### A. Without your tools

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='FL', road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`. 2 turns, 58 s. Run: `ablation/runs/without__busch_lanes.json`

> The work zone on East Busch Boulevard is reported by the City of Tampa, Florida. The work zone is active from November 3rd to November 5th, 2023, and the lane impact is unknown. No specific lanes are closed, but the work zone is reported as "lane impact unknown." The position of the work zone is not verified, and the dates are not verified.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=0.5)`, `get_work_zones(feed='FL', road='Busch Blvd', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`. 3 turns, 76 s. Run: `ablation/runs/plain__busch_lanes.json`

> The work zone on East Busch Boulevard is reported by the City of Tampa, Florida. The work zone is active from November 3, 2023, to November 5, 2023, and is located 2.1 miles away. The lane impact is unknown, as indicated by the "lane impact unknown" status. No closed lanes or reduced speed limits are reported.

### C. Your tools as written

Tools called: `street_work_report(feed='FL', street='Busch Blvd', near_lat=28.0587, near_lon=-82.4139)`. 2 turns, 87 s. Run: `ablation/runs/full__busch_lanes.json`

> Yes, there is a work reported on Busch Blvd near USF (28.0587, -82.4139) right now. The work is reported by the City of Tampa, Florida, and it is 2.1 miles away. The work involves some lanes closed on the eastbound direction. The work is reported until Thursday, November 5, 16:00 EST. The lane impact is not reported for one of the records, but it is reported for the eastbound direction. The work is reported as follows:
>
> - East Busch Boulevard, Tampa
> - Eastbound: some lanes closed, right lane of 3 closed
>
> The work is reported as 1 active work on the street, from 2 record(s). The work is not findable by name, and there are 5 active record(s) within 5 mi that have no street name. To see them, call get_work_zones with near_lat, near_lon and radius_mi.

## thirtieth_works

**Question:** How many separate works (permits or projects) are reported on 30th St near USF (28.0587, -82.4139) right now?

**Right answer (tasks.json):** Two: a new sewer main (permit ROW-25-0001919, reported as 3 records, until Dec 15) and a wastewater repair (CWS-27-0000027, 1 record, until Nov 6 at 5:00 pm). The feed has 4 records, not 4 works. Checked in snapshots/2026-11-05/fldot.json, works 4233451340 and 4519480375.

### A. Without your tools

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='FL', road='30th St', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`. 2 turns, 95 s. Run: `ablation/runs/without__thirtieth_works.json`

> The work zones reported near 30th St (28.0587, -82.4139) are:
>
> 1. **North 30th Street (Northbound)** - 0.8 mi away, lane impact unknown (not reported), closed lanes, reduced speed limit, and reported by the City of Tampa, Florida.
> 2. **North 30th Street (Southbound)** - 0.8 mi away, lane impact unknown (not reported), closed lanes, reduced speed limit, and reported by the City of Tampa, Florida.
> 3. **North 30th Street (Southbound)** - 0.9 mi away, lane impact unknown (not reported), CWS-27-0000027 repairing wastewater asset, and reported by the City of Tampa, Florida.
> 4. **North 30th Street (Direction not reported)** - 0.9 mi away, lane impact unknown (not reported), ROW-25-0001919, installing new sewer main, and reported by the City of Tampa, Florida.
>
> There are **4** separate work zones reported near 30th St.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=0.5)`, `list_feeds(state='az')`. 3 turns, 55 s. Run: `ablation/runs/plain__thirtieth_works.json`

> No active work zone is reported within 0.5 mi of (28.05870, -82.41390) in the az feed. That is not proof there is none: if the camera sees cones, barrels or workers, trust the camera.

### C. Your tools as written

Tools called: `street_work_count(feed='FL', street='30th St', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0)`. 2 turns, 48 s. Run: `ablation/runs/full__thirtieth_works.json`

> The street_work_count function returned 2 active works on 30th St near USF (28.0587, -82.4139) right now. These works are reported as 4 records, with lane impact not reported for 4 of the 4 records.

## thirtieth_lanes

**Question:** Does the sewer work on 30th St near USF (28.0587, -82.4139) close any lanes?

**Right answer (tasks.json):** The feed does not say: every record of the 30th St works reports its lane impact as unknown. That is not the same as no lanes closed. Checked in snapshots/2026-11-05/fldot.json: vehicle_impact is 'unknown' on all 4 records.

### A. Without your tools

Tools called: `list_feeds(state='florida')`, `get_work_zones(feed='FL', road='30th St', near_lat='28.0587', near_lon='-82.4139', radius_mi=5.0, status='active')` (refused by the harness: Error: "near_lat" must be number or null, not "28.0587".), `check_location(feed='FL', lat='28.0587', lon='-82.4139', radius_mi=0.5)` (refused by the harness: Error: "lat" must be number, not "28.0587".), `list_feeds(state='florida')`, `get_work_zones(feed='FL', road='30th St', near_lat='28.0587', near_lon='-82.4139', radius_mi=5.0, status='active')` (refused by the harness: Error: "near_lat" must be number or null, not "28.0587".), `list_feeds(state='arizona')`, `get_work_zones(feed='AZ511', road='30th St', near_lat='28.0587', near_lon='-82.4139', radius_mi=5.0, status='active')` (refused by the harness: Error: "near_lat" must be number or null, not "28.0587".), `get_work_zones(feed='MCODT', road='30th St', near_lat='28.0587', near_lon='-82.4139', radius_mi=5.0, status='active')` (refused by the harness: Error: "near_lat" must be number or null, not "28.0587".), `get_work_zones(feed='FL', road='30th St', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0, status='active')`. 8 turns, 250 s. Run: `ablation/runs/without__thirtieth_lanes.json`

> The work zones near 30th Street (28.0587, -82.4139) are as follows:
>
> 1. **North 30th Street (Northbound)** - 0.8 mi away: Lane impact unknown (not reported). Footway closure. Active from Sep 8 to Dec 15. Reported by City of Tampa, Florida. Position and dates not verified.
> 2. **North 30th Street (Southbound)** - 0.8 mi away: Lane impact unknown (not reported). Footway closure. Active from Sep 8 to Dec 15. Reported by City of Tampa, Florida. Position and dates not verified.
> 3. **North 30th Street (Southbound)** - 0.9 mi away: Lane impact unknown (not reported). CWS-27-0000027 repairing wastewater asset. Active from Oct 27 to Nov 6. Reported by City of Tampa, Florida. Position and dates not verified.
> 4. **North 30th Street (Direction not reported)** - 0.9 mi away: Lane impact unknown (not reported). ROW-25-0001919, Installing new sewer main. Active from Sep 8 to Dec 15. Reported by City of Tampa, Florida. Position and dates not verified.
>
> None of the work zones have a verified position or dates. The lane impact is reported as "unknown" for all entries.

### B. Your tools, plain

Tools called: `list_feeds(state='florida')`, `check_location(feed='FL', lat=28.0587, lon=-82.4139, radius_mi=0.5)`. 2 turns, 45 s. Run: `ablation/runs/plain__thirtieth_lanes.json`

> No active work zone is reported within 0.5 mi of (28.05870, -82.41390) in the fldot feed. That is not proof there is none: if the camera sees cones, barrels or workers, trust the camera.

### C. Your tools as written

Tools called: `street_work_report(feed='FL', street='N 30th St', near_lat=28.0587, near_lon=-82.4139, radius_mi=5.0)`. 2 turns, 108 s. Run: `ablation/runs/full__thirtieth_lanes.json`

> The sewer work on N 30th St near USF (28.0587, -82.4139) is reported to be active. There are two active work zones on the street, with the following details:
>
> 1. **Work Zone 4233451340**:
>    - **Direction**: Not reported.
>    - **Lane Impact**: Not reported.
>    - **End Time**: Until Tue Dec 15 16:00 EST.
>    - **Description**: Installing new sewer main.
>
> 2. **Work Zone 4519480375**:
>    - **Direction**: Southbound.
>    - **Lane Impact**: Not reported.
>    - **End Time**: Until Fri Nov 6 17:00 EST.
>    - **Description**: Repairing wastewater asset.
>
> Both work zones are reported as **not having any lane impact**. The work zones are **not reported to close any lanes**, as the feed does not indicate any lane impact. The work zones are **active** and **reported**. 
>
> If you need more detailed information about the work zones, you can call `get_work_zones` with the coordinates (28.0587, -82.4139) and a radius of 5 miles.
