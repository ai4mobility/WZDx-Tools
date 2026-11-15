"""Tests for contrib/alinahagen/tools.py – one test per KNOWLEDGE.md rule."""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from contrib.alinahagen.tools import (
    GENERAL_LANE_TYPES, SUPPLEMENTAL_LANE_TYPES,
    lane_closure_traffic_impact,
    work_zones_during_hours,
)

PASS = 0; FAIL = 0

def check(label, cond):
    global PASS, FAIL
    if cond:
        print(f'PASS {label}'); PASS += 1
    else:
        print(f'FAIL {label}'); FAIL += 1

# Rule 1: WZDx uses a LaneType field to distinguish travel lanes (general) from non-travel lanes 
# (shoulder, parking, median, sidewalk, bike-lane). Closing a non-travel lane does not reduce vehicle 
# throughput. Tools must check LaneType before assigning impact severity. 
# 
# Source: WZDx spec, spec-content/enumerated-types/LaneType.md 
# github.com/usdot-jpo-ode/wzdx/blob/develop/spec-content/enumerated-types/LaneType.md

def test_general_vs_nontravellane_types():
    check('test_general_in_general_set',   'general'  in GENERAL_LANE_TYPES)
    check('test_shoulder_not_general',     'shoulder' not in GENERAL_LANE_TYPES)
    check('test_parking_not_general',      'parking'  not in GENERAL_LANE_TYPES)
    check('test_median_not_general',       'median'   not in GENERAL_LANE_TYPES)
    check('test_bike_lane_not_general',    'bike-lane' not in GENERAL_LANE_TYPES)
    check('test_shoulder_in_supplemental', 'shoulder' in SUPPLEMENTAL_LANE_TYPES)

# Rule 2: WZDx treats each work zone record independently with no reference to nearby concurrent 
# closures. A corridor with multiple simultaneous closures deserves more scrutiny than any single 
# record indicates. This tool groups records by proximity and time window and flags when more than 
# one closure is active in the same area.
# 
# Source: Nov 5 2026 FDOT snapshot — 7 simultaneous active work zone records observed within 0.5 mi 
# of Kennedy Blvd between Armenia Ave and Howard Ave, Tampa.

def test_multiple_closures_flagged():
    # Downtown Tampa (Kennedy/Armenia/Howard) has 7 known simultaneous works
    result = lane_closure_traffic_impact('FL', 27.9472, -82.4677, radius_mi=0.5)
    check('test_corridor_tool_returns_string', isinstance(result, str) and len(result) > 0)
    import re
    m = re.search(r'Works:\s*(\d+)', result)
    n = int(m.group(1)) if m else 0
    if n >= 2:
        check('test_multiple_works_flagged_in_output', 'MULTIPLE' in result)
    else:
        check('test_single_work_no_false_multiple_flag', 'MULTIPLE' not in result)

# Rule 3: LaneStatus reports whether each lane is open, closed, or shifting, but contains no 
# traffic volume or speed data. Tools must count closed lanes by type (using LaneType), report how 
# many general travel lanes remain open, and state that severity is estimated from lane 
# configuration alone, not measured traffic conditions.
# 
# Source: WZDx spec, spec-content/enumerated-types/LaneStatus.md 
# and spec-content/enumerated-types/LaneType.md
def test_lane_count_reported_by_type():
    result = lane_closure_traffic_impact('FL', 27.9472, -82.4677, radius_mi=0.5)
    # Output must report general and shoulder/other counts separately
    check('test_general_lanes_reported', 'Reported closed general-lane entries:' in result)
    check('test_shoulder_lanes_reported', 'Reported closed supplemental-lane entries:' in result)
    check('test_conflicts_line_present', 'SCREENING INTERPRETATION' in result)

# Rule 4: A WZDx record’s EventStatus field distinguishes between planned (estimated, early design), 
# pending (scheduled 2–3 weeks out, >90% certainty), active (work zone in place and active), and 
# completed/cancelled. A record being present in the feed does not mean work is actively disrupting 
# traffic. Tools must report this status explicitly rather than treating all records as active 
# closures. 
# 
# Source: WZDx spec, spec-content/enumerated-types/EventStatus.md  
# github.com/usdot-jpo-ode/wzdx/blob/develop/spec-content/enumerated-types/EventStatus.md. 

def test_event_status_filtering():
    # A street with no active/pending work should return a clear result,
    # not a list of planned or cancelled records
    result = work_zones_during_hours('FL', 'Busch Blvd', 28.0587, -82.4139,
                                     radius_mi=1.0, start_hour=11, end_hour=14)
    check('test_status_filter_returns_string', isinstance(result, str))
    # Planned records should not appear as active conflicts
    check('test_no_planned_label_in_output', '[PLANNED]' not in result)

if __name__ == '__main__':
    test_general_vs_nontravellane_types()
    test_multiple_closures_flagged()
    test_lane_count_reported_by_type()
    test_event_status_filtering()
    print(f'\n{PASS} of {PASS+FAIL} pass')