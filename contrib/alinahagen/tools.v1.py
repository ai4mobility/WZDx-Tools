"""
Alina Hagen – contrib/alinahagen/tools.py

Two designed tools for a city permit office evaluating traffic impact
of road closures near commercial districts during meal hours.

Tool 1: work_zones_during_hours
  Checks whether active/pending work zones on a street overlap a chosen
  time window (e.g. lunch 11–14, dinner 18–21). WZDx stores dates as UTC;
  this tool converts to local time before comparing, and treats a missing
  end_date as an indefinite closure.

Tool 2: lane_closure_traffic_impact
  Reports the lane-closure burden in a corridor, distinguishing general
  (mainline travel) lanes from shoulder/parking, and flagging when
  multiple simultaneous zones compound capacity loss.
"""
# AI Use Disclourse: This tool code was generated with Claude 
# I have gone through the code and added comments to keep track of my understanding
# of functions. 

import os, sys, re, json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import wzdx_tools as T

# WZDx LaneType values that represent mainline travel lanes (source: WZDx
# spec LaneType enumerated type, usdot-jpo-ode/wzdx).
GENERAL_LANE_TYPES = {
    'general', 'center-left-turn', 'exit-ramp', 'entrance-ramp',
    'hov', 'alternating-flow',
}
# Supplemental lane types that do not carry through traffic.
SUPPLEMENTAL_LANE_TYPES = {
    'shoulder', 'median', 'parking', 'bike-lane', 'sidewalk',
    'two-way-center-turn-lane', 'exit-lane', 'entrance-lane',
}


def _work_id(f):
    # Personal Comments
    # Extracts the records for a work zone or project
    """Group records that belong to one work (permit/project)."""
    return str(f.get('id', '')).split('/')[0].removesuffix('-R')


def _utc_hour_to_local(dt_str: str, lon: float):
    """
    Parse a UTC ISO-8601 datetime string and return the local hour (0–23).
    Uses longitude to approximate UTC offset: round(lon / 15).
    Returns None if the string is missing or cannot be parsed.
    """
    # Personal Comments
        # WZDx stores all datetimes in UTC ISO-8601
        # This function helps convert it to local time. It uses longitude to estimate the 
        # local timezone, which is an approximation but works for this tool's purpose.

    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        offset_h = round(lon / 15)   # e.g. lon=-82 → -5 (Florida EST)
        local_dt = dt.astimezone(timezone(timedelta(hours=offset_h)))
        return local_dt.hour
    except Exception:
        return None


def _overlaps(sh, eh, start_hour, end_hour) -> bool:
    """
    True when zone's local [sh, eh) overlaps target [start_hour, end_hour).
    None on either boundary means unknown → assume overlap (conservative).
    """
    # Personal Comments
    # This function checks if the work zone's active hours overlap with the target time window.
    # Some closures in the feed have no end_date at all. The spec allows this — it means 
    # the work has no defined end. This tool treats those as active through any window you check. 
    # This is a conservative design choice: rather flag a maybe-conflict than miss a real one. 

    left_ok  = (sh is None) or (sh < end_hour)
    right_ok = (eh is None) or (start_hour < eh)
    return left_ok and right_ok


# ── TOOL 1: "Are there already other closures around this area for the requested time"

def work_zones_during_hours_plain(
    feed: str, street: str, near_lat: float, near_lon: float,
    radius_mi: float = 1.0, start_hour: int = 11, end_hour: int = 14,
) -> str:
    """Plain baseline: list work zones on the street by text search, without time filtering."""
    # Personal Comments
    # This function provides a simple text-based search for work zones on a given street
    # It does not filter by time, just lists all records that match the street name.
    F = T._load(feed)
    hits = [
        f for f in F['wz']
        if any(street.lower() in n.lower()
               for n in f['properties']['core_details'].get('road_names') or [])
    ]
    lines = [f"{len(hits)} record(s) on '{street}' in {F['name']} feed (no time filter):"]
    for f in hits:
        p = f['properties']
        lines.append(
            f"  {f['id']}: {p.get('start_date','?')} → {p.get('end_date','no end date')}, "
            f"impact={p.get('vehicle_impact','?')}"
        )
    return '\n'.join(lines)


@T._errors_as_text
def work_zones_during_hours(
    feed: str, street: str, near_lat: float, near_lon: float,
    radius_mi: float = 1.0, start_hour: int = 11, end_hour: int = 14,
) -> str:
    """
    Active and pending work zones on a street that overlap a local-time window.

    Use this to flag road-work conflicts during meal-hour traffic peaks near
    commercial districts. For lunch set start_hour=11, end_hour=14; for dinner
    set start_hour=18, end_hour=21.

    WZDx start_date and end_date are stored as UTC ISO-8601. This tool converts
    them to local time using the longitude before comparing against your window,
    so a closure active at 8 PM in Tampa is not missed because it is stored as
    01:00 UTC the next day. A missing end_date means the closure has no defined
    end; it is counted as active through any window (the work is set up
    indefinitely). Zones with event_status 'active' are affecting traffic right
    now; 'pending' means equipment is in place but traffic control has not yet
    started — both are flagged, because a pending zone can flip to active during
    your window. Cancelled and completed zones are excluded.

    feed        : 'FL' or 'AZ'
    street      : Street name ('Busch Blvd', 'Fletcher Ave')
    near_lat    : Latitude of corridor point of interest
    near_lon    : Longitude of corridor point of interest
    radius_mi   : Search radius in miles (default 1.0)
    start_hour  : Start of window, local 24-h, inclusive (default 11 = 11 AM)
    end_hour    : End of window, local 24-h, exclusive (default 14 = 2 PM)

    Read-only.
    """

    #Personal Comments
    # This function checks for active or pending work zones on a specified street
    # that overlap with a given local time window. It filters the work zones based on
    # their status, distance from a point, and whether they match the street name.

    F = T._load(feed)
    now = T._now()

    active_during, pending_during, outside_window = [], [], []

    for f in F['wz']:
        p = f['properties']; cd = p['core_details']
        st = T._status(p, now)
        if st not in ('active', 'pending'):
            continue
        d = T._dist(f, near_lat, near_lon)
        if d is None or d > radius_mi:
            continue
        if not any(street.lower() in n.lower() for n in cd.get('road_names') or []):
            continue

        lon = (T._pts(f) or [[near_lon]])[0][0]
        sh = _utc_hour_to_local(p.get('start_date'), lon)
        # eh is None when end_date is missing (indefinite closure)
        eh = _utc_hour_to_local(p.get('end_date'), lon) if p.get('end_date') else None

        if _overlaps(sh, eh, start_hour, end_hour):
            (active_during if st == 'active' else pending_during).append((d, f, sh, eh))
        else:
            outside_window.append((d, f))

    win = f"{start_hour:02d}:00–{end_hour:02d}:00 local"
    total = len(active_during) + len(pending_during)

    lines = [
        f"Time-window check · {street} · {win} · "
        f"{F['name']} feed · {radius_mi:g} mi of ({near_lat:.4f},{near_lon:.4f})",
        f"Conflicts: {len(active_during)} active  |  {len(pending_during)} pending  |  "
        f"{len(outside_window)} outside window",
    ]

    for d, f, sh, eh in sorted(active_during, key=lambda x: x[0]):
        p = f['properties']; cd = p['core_details']
        road = (cd.get('road_names') or ['?'])[0]
        imp  = (p.get('vehicle_impact') or 'unknown').replace('-', ' ')
        lanes = T._lanes_text(p.get('lanes'))
        eh_str = f"hour {eh:02d}" if eh is not None else "no end date"
        lines.append(
            f"  [ACTIVE]  {road} · {d:.1f} mi · {imp}"
            f"{', ' + lanes if lanes else ''} · local {sh:02d}h → {eh_str}"
        )

    for d, f, sh, eh in sorted(pending_during, key=lambda x: x[0]):
        p = f['properties']; cd = p['core_details']
        road = (cd.get('road_names') or ['?'])[0]
        imp  = (p.get('vehicle_impact') or 'unknown').replace('-', ' ')
        eh_str = f"hour {eh:02d}" if eh is not None else "no end date"
        lines.append(
            f"  [PENDING] {road} · {d:.1f} mi · {imp} · local {sh:02d}h → {eh_str}"
        )

    if total == 0:
        lines.append(
            f"  → No conflicts with {win}. "
            f"Street appears clear for new permits during this window."
        )
    elif total >= 2:
        lines.append(
            f"\n  ⚠ {total} zone(s) conflict with {win}. "
            f"Permit issuance not recommended without review."
        )
    else:
        lines.append(f"\n  ⚡ 1 zone conflicts with {win}. Review before issuing permit.")

    return '\n'.join(lines)


# ── TOOL 2 "How severe would the impact be if this closure happened?"

def lane_closure_traffic_impact_plain(
    feed: str, near_lat: float, near_lon: float, radius_mi: float = 0.5,
) -> str:
    """Plain baseline: count all closed lanes without distinguishing general from shoulder/parking."""

# Personal Comments
# This function provides a simple count of closed lanes within a specified radius

    F = T._load(feed); now = T._now()
    hits = []
    for f in F['wz']:
        if T._status(f['properties'], now) != 'active':
            continue
        d = T._dist(f, near_lat, near_lon)
        if d is not None and d <= radius_mi:
            hits.append((d, f))
    if not hits:
        return f"No active work zones within {radius_mi} mi."
    lines = [f"{len(hits)} active record(s) within {radius_mi} mi:"]
    for d, f in hits:
        p = f['properties']
        lanes = p.get('lanes') or []
        closed = sum(1 for l in lanes if l.get('status') == 'closed')
        lines.append(
            f"  {f['id']}: {closed}/{len(lanes) or '?'} lanes closed, "
            f"impact={p.get('vehicle_impact','?')}"
        )
    return '\n'.join(lines)


@T._errors_as_text
def lane_closure_traffic_impact(
    feed: str, near_lat: float, near_lon: float, radius_mi: float = 0.5,
) -> str:
    """
    Corridor lane-closure burden, broken down by lane type, with multiple-closure flagging.

    WZDx LaneType distinguishes 'general' lanes — the mainline travel lanes
    that carry through traffic — from 'shoulder', 'parking', 'bike-lane',
    'median' and other supplemental lane types. Closing a general lane reduces
    throughput capacity; closing a shoulder typically does not. This tool reports
    the two categories separately so a permit office can judge whether a new
    closure would drop corridor throughput below an acceptable threshold, rather
    than counting all closed lanes as equivalent.

    When two or more active works appear in the same short corridor, their
    capacity reductions combine — a 2-lane road with one general lane closed by
    Work A and another general lane closed by Work B has effectively zero
    throughput. The WZDx feed reports each zone independently with no cross-zone
    aggregation; this tool surfaces that gap by grouping all active works within
    the radius into one corridor summary and flagging when multiple are present.

    feed      : 'FL' or 'AZ'
    near_lat  : Latitude of corridor centre
    near_lon  : Longitude of corridor centre
    radius_mi : Corridor radius in miles (default 0.5)

    Read-only.
    """

    # Personal Comments
    # This function analyzes the lane closure impact within a specified corridor.
    # It counts the number of closed general lanes and supplemental lanes, and flags if 
    # multiple works are present in the corridor.

    # If FDOT closes a shoulder lane, that’s annoying but traffic still flows. If they 
    # close a general lane on a 2-lane road, capacity is cut in half.

    F = T._load(feed); now = T._now()
    hits = []
    for f in F['wz']:
        if T._status(f['properties'], now) != 'active':
            continue
        d = T._dist(f, near_lat, near_lon)
        if d is not None and d <= radius_mi:
            hits.append((d, f))

    if not hits:
        return (
            f"No active work zones within {radius_mi:g} mi of "
            f"({near_lat:.4f},{near_lon:.4f}) in {F['name']} feed. "
            f"Corridor appears clear."
        )

    org = T._orgs(F['info'])
    works = {}
    for d, f in hits:
        works.setdefault(_work_id(f), []).append((d, f))

    total_gen_closed = total_supp_closed = 0
    work_lines = []

    for wid, recs in sorted(works.items(), key=lambda kv: min(d for d, _ in kv[1])):
        f0 = recs[0][1]; cd0 = f0['properties']['core_details']
        road = (cd0.get('road_names') or ['unnamed road'])[0]
        src  = org.get(cd0.get('data_source_id'), '?')
        g_cl = g_tot = s_cl = s_tot = 0
        for _, f in recs:
            for lane in (f['properties'].get('lanes') or []):
                lt     = (lane.get('type') or 'general').lower()
                closed = lane.get('status') == 'closed'
                if lt in GENERAL_LANE_TYPES:
                    g_tot += 1
                    if closed:
                        g_cl += 1
                else:
                    s_tot += 1
                    if closed:
                        s_cl += 1
        total_gen_closed  += g_cl
        total_supp_closed += s_cl
        work_lines.append(
            f"  • {road} · {min(d for d, _ in recs):.1f} mi · {src}\n"
            f"    General lanes closed: {g_cl}/{g_tot or '?'}  |  "
            f"Shoulder/other closed: {s_cl}/{s_tot or '?'}"
        )

    n = len(works)
    lines = [
        f"Corridor impact · {radius_mi:g} mi of ({near_lat:.4f},{near_lon:.4f}) · {F['name']} feed",
        f"Works: {n}  |  General lanes closed: {total_gen_closed}  |  "
        f"Shoulder/other closed: {total_supp_closed}",
    ] + work_lines

    if n >= 2:
        lines.append(
            f"\n  ⚠ MULTIPLE WORKS IN CORRIDOR: {n} simultaneous closures.\n"
            f"  WZDx reports each zone independently — no cross-zone aggregation.\n"
            f"  Combined: {total_gen_closed} general lane(s) removed from this corridor.\n"
            f"  A new permit here adds to existing capacity reductions; "
            f"off-peak scheduling strongly advised."
        )
    elif total_gen_closed > 0:
        word = "lane" if total_gen_closed == 1 else "lanes"
        lines.append(
            f"\n  ⚡ {total_gen_closed} general {word} closed in corridor. "
            f"Review before issuing a new permit."
        )
    else:
        note = "some shoulder/other closures noted" if total_supp_closed else "corridor clear"
        lines.append(f"\n  ✓ No general lanes closed in corridor ({note}).")

    return '\n'.join(lines)


# ── registry 
# A registry of the tools in this file, for use by the WZDx-Tools framework. The
# framework uses this to discover the tools and their metadata, and to call them
# with the right arguments. The registry also marks which tools are read-only.

TOOLS     = [work_zones_during_hours, lane_closure_traffic_impact]
READ_ONLY = {'work_zones_during_hours', 'lane_closure_traffic_impact'}

PLAIN_DESCRIPTIONS = {
    'work_zones_during_hours':
        'Work zones on a street near a point within a time window. '
        'feed: feed name. street: street name. near_lat, near_lon: location. '
        'radius_mi: radius in miles. start_hour, end_hour: 24-h hour window. '
        'Read-only.',
    'lane_closure_traffic_impact':
        'Lane closures in a corridor. feed: feed name. '
        'near_lat, near_lon: corridor centre. radius_mi: radius in miles. '
        'Read-only.',
}


@T._errors_as_text
def work_zones_during_hours_raw(
    feed: str, street: str, near_lat: float, near_lon: float,
    radius_mi: float = 1.0, start_hour: int = 11, end_hour: int = 14,
) -> str:
    F = T._load(feed); now = T._now()
    records = []
    for f in F['wz']:
        p = f['properties']
        if T._status(p, now) not in ('active', 'pending'):
            continue
        d = T._dist(f, near_lat, near_lon)
        if d is None or d > radius_mi:
            continue
        if any(street.lower() in n.lower()
               for n in p['core_details'].get('road_names') or []):
            records.append({'id': f.get('id'), **p})
    return json.dumps({'feed': F['name'], 'records': records}, default=str)


@T._errors_as_text
def lane_closure_traffic_impact_raw(
    feed: str, near_lat: float, near_lon: float, radius_mi: float = 0.5,
) -> str:
    F = T._load(feed); now = T._now()
    records = []
    for f in F['wz']:
        if T._status(f['properties'], now) != 'active':
            continue
        d = T._dist(f, near_lat, near_lon)
        if d is not None and d <= radius_mi:
            records.append({'id': f.get('id'), **f['properties']})
    return json.dumps({'feed': F['name'], 'records': records}, default=str)


RAW_RESULTS = {
    'work_zones_during_hours':     work_zones_during_hours_raw,
    'lane_closure_traffic_impact': lane_closure_traffic_impact_raw,
}


if __name__ == '__main__':
    # Quick smoke-test: Busch Blvd near USF during lunch
    print(work_zones_during_hours('FL', 'Busch Blvd', 28.0587, -82.4139,
                                   start_hour=11, end_hour=14))
    print()
    print(lane_closure_traffic_impact('FL', 28.0587, -82.4139, radius_mi=1.0))
    print()
    # Personal Smoke test - this should return a work zine affecting the corridor 
    # I live here and its been closed for construction for awhile (over a year)
    print("--- Kennedy Blvd (Armenia to Howard), Tampa ---")
    print(work_zones_during_hours('FL', 'Kennedy Blvd', 27.9472, -82.4677,
                                   radius_mi=0.5, start_hour=11, end_hour=14))
    print()
    print(lane_closure_traffic_impact('FL', 27.9472, -82.4677, radius_mi=0.5))