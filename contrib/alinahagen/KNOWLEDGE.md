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
