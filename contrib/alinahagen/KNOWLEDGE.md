# Domain Knowledge

## Rule 1: General travel lane closures are different from non-travel lanes

WZDx uses a LaneType field to distinguish travel lanes (general) from non-travel lanes
(shoulder, parking, median, sidewalk, bike-lane). Closing a non-travel lane does not
reduce vehicle throughput. Tools must check LaneType before assigning impact severity.

**Source:** WZDx spec, spec-content/enumerated-types/LaneType.md
github.com/usdot-jpo-ode/wzdx/blob/develop/spec-content/enumerated-types/LaneType.md

---

## Rule 2: WZDx records are independent and simultaneous closures should be noted

WZDx treats each work zone record independently with no reference to nearby concurrent
closures. A corridor with multiple simultaneous closures deserves more scrutiny than any
single record indicates. This tool groups records by proximity and time window and flags
when more than one closure is active in the same area. Tools must count how many distinct work identifiers are present in the corridor and flag when that count exceeds one.

**Source:** Nov 5 2026 FDOT snapshot — 7 simultaneous active work zone records observed
within 0.5 mi of Kennedy Blvd between Armenia Ave and Howard Ave, Tampa.

---

## Rule 3: Lane counts are the only severity proxy as WZDx does not have annual traffic data or historic traffic use for corriodors

LaneStatus reports whether each lane is open, closed, or shifting, but contains no
traffic volume or speed data. Tools must count closed lanes by type (using LaneType),
report how many general travel lanes remain open, and state that severity is estimated
from lane configuration alone, not measured traffic conditions. Do not infer traffic volume from road name or time of day.

**Source:** WZDx spec, spec-content/enumerated-types/LaneStatus.md and
spec-content/enumerated-types/LaneType.md

---

## Rule 4: EventStatus limits which records are relevant 

A WZDx record's EventStatus field distinguishes between planned (estimated, early
design), pending (scheduled 2–3 weeks out, >90% certainty), active (work zone in place
and active), and completed/cancelled. A record being present in the feed does not mean
work is actively disrupting traffic. A permit office needs only records that are currently affecting or are about to affect traffic — `active` and `pending`. Tools must report this status explicitly rather than
treating all records as active closures.

**Source:** WZDx spec, spec-content/enumerated-types/EventStatus.md
github.com/usdot-jpo-ode/wzdx/blob/develop/spec-content/enumerated-types/EventStatus.md
Note: deprecated as of WZDx v4.1.


### AI Use Diclousre
AI Use Disclosure 
1. I choose Track W - I originally wanted to use SUMO, and considered asking Claude to help me with setting it up, as I originally wanted to do something with a simulation. However, I will be honest, I misread the due date for this assignment, and had less time then I had hoped to complete this assignment. So, I choose to do Track W as that seemed more manageable and I would need less AI assistance in understanding it. My original idea was to try and simulate what traffic impacts would happen if you shut down certain corridors for "pedestrian hours" (the idea of walkable cities). I couldn’t do that with Track W, so I tried to do something similar with trying to estimate how bad it would be to close down roads based on what's already closed around it. (I specifically wanted to test closing things around meal times, like Lunch and Dinner)
  
2. I did use Claude to help me find where WZDx kept some of its data dictionaries. Once I found the enumerated-types tab on the Github, that got a lot easier.  Claude made suggestion for my tools based on a slight misunderstanding I had -- I originally wanted to have the tool take into account what time the permit requester was setting for the permit, and determine if that was a high volume traffic time. This is not possible with the data WZDx has, and that was one misunderstanding I had. 
	
3. I did use Claude to help with suggestions for some wording for some of the rules or tasks, but only after I had fully drafted the rules and knew what I wanted them to say. 

4. All git commands and coding adjustments were done with Claude. One issue i ran into was having to set up a virtual environment on my machine, as for some reason my Mac, despite having Python 3.13, did not want to run this assignment as was. The virtual environment worked great though, but it did take some set up.




