"""Road-work screening tools for a permit office using WZDx feeds.

Two registered read-only tools:
  1. work_zones_during_hours: street-specific, date/time conflict screening.
  2. lane_closure_traffic_impact: nearby active works and reported lane restrictions.

Each has a simple plain baseline and a JSON raw-result counterpart. The raw
counterparts return underlying feed records plus screening metadata.

Limitations: WZDx records may be incomplete. These are screening tools, not
proof of roadway clearance or calculated traffic capacity/delay.
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import wzdx_tools as T

# Use actual time zones, including daylight-saving rules (not longitude / 15).
FEED_TIME_ZONES = {'FL': 'America/New_York', 'FLDOT': 'America/New_York',
                   'AZ': 'America/Phoenix'}
GENERAL_LANE_TYPES = {
    'general', 'center-left-turn', 'exit-ramp', 'entrance-ramp',
    'hov', 'alternating-flow',
}
SUPPLEMENTAL_LANE_TYPES = {
    'shoulder', 'median', 'parking', 'bike-lane', 'sidewalk',
    'two-way-center-turn-lane', 'exit-lane', 'entrance-lane',
}
STREET_WORDS = {
    'blvd': 'boulevard', 'boul': 'boulevard', 'ave': 'avenue',
    'av': 'avenue', 'st': 'street', 'rd': 'road', 'dr': 'drive',
    'ln': 'lane', 'hwy': 'highway', 'pkwy': 'parkway', 'pl': 'place',
    'ct': 'court', 'n': 'north', 's': 'south', 'e': 'east', 'w': 'west',
    'ne': 'northeast', 'nw': 'northwest', 'se': 'southeast',
    'sw': 'southwest',
}
DIRECTIONS = {'north', 'south', 'east', 'west', 'northeast', 'northwest',
              'southeast', 'southwest'}


def _zone(feed):
    key = feed.strip().upper()
    if key not in FEED_TIME_ZONES:
        raise ValueError(f'Unknown feed time zone for {feed!r}; configure FEED_TIME_ZONES')
    return ZoneInfo(FEED_TIME_ZONES[key])


def _parse_date(value):
    """Parse ISO timestamp as UTC if naive; return aware UTC datetime or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _target_window(start_hour, end_hour, check_date, tz, now):
    if not (isinstance(start_hour, int) and isinstance(end_hour, int)
            and 0 <= start_hour <= 23 and 0 <= end_hour <= 24
            and start_hour != end_hour):
        raise ValueError('start_hour must be 0–23, end_hour 0–24, and they must differ')
    if check_date is None:
        day = now.astimezone(tz).date()
    else:
        day = date.fromisoformat(check_date)
    begin = datetime.combine(day, time(start_hour), tzinfo=tz)
    end_day = day + timedelta(days=int(end_hour <= start_hour))
    finish = datetime.combine(end_day, time(end_hour % 24), tzinfo=tz)
    return begin, finish


def _record_time_status(p, window_start, window_end):
    """Return ('overlap'|'outside'|'uncertain', explanation).

    Compare full calendar timestamps in UTC. Missing end means open-ended;
    missing or unparseable start means temporal status cannot be confirmed.
    """
    raw_start, raw_end = p.get('start_date'), p.get('end_date')
    start = _parse_date(raw_start)
    end = _parse_date(raw_end)
    if start is None:
        return 'uncertain', 'start date missing or invalid'
    if raw_end and end is None:
        return 'uncertain', 'end date invalid'
    if end is not None and end < start:
        return 'uncertain', 'end date precedes start date'
    # Intervals are [start,end), so touching boundaries is not overlap.
    overlap = (start < window_end.astimezone(timezone.utc)
               and (end is None or end > window_start.astimezone(timezone.utc)))
    return ('overlap' if overlap else 'outside',
            'open-ended record' if end is None else 'dated record')


def _road_tokens(s):
    words = re.findall(r'[a-z0-9]+', str(s).lower())
    words = [STREET_WORDS.get(x, x) for x in words]
    # Ignore leading road direction (West Kennedy vs Kennedy), but not other
    # distinctive words. Avoid arbitrary substring matching.
    while words and words[0] in DIRECTIONS:
        words.pop(0)
    return words


def _street_match(query, names):
    q = _road_tokens(query)
    if not q:
        return False
    for name in names or []:
        # A few WZDx producers combine several road names in one string.
        for subname in str(name).split(','):
            tokens = _road_tokens(subname)
            if tokens == q:
                return True
    return False


def _road_names(f):
    cd = (f.get('properties') or {}).get('core_details') or {}
    names = cd.get('road_names') or []
    if isinstance(names, str):
        names = [names]
    unique = []
    for name in names:
        for part in str(name).split(','):
            clean = part.strip()
            if clean and clean.lower() not in {x.lower() for x in unique}:
                unique.append(clean)
    return unique


def _work_id(f):
    value = str(f.get('id') or '').strip()
    if not value:
        return None
    return value.split('/')[0].removesuffix('-R')


def _record_key(f, index):
    return _work_id(f) or f'no-id-record-{index}'


def _nearby(F, now, lat, lon, radius, statuses):
    if radius <= 0:
        raise ValueError('radius_mi must be positive')
    hits = []
    for i, f in enumerate(F['wz']):
        p = f.get('properties') or {}
        status = T._status(p, now)
        if status not in statuses:
            continue
        d = T._dist(f, lat, lon)
        if d is None or d > radius:
            continue
        hits.append((d, i, f, status))
    return sorted(hits, key=lambda x: x[0])


def _classify_lanes(records):
    """Counts reported lane entries, not distinct physical corridor lanes."""
    counts = {'general_total': 0, 'general_closed': 0,
              'other_total': 0, 'other_closed': 0,
              'unknown_total': 0, 'unknown_closed': 0,
              'records_no_lane_data': 0}
    for _, _, f, _ in records:
        lanes = (f.get('properties') or {}).get('lanes') or []
        if not lanes:
            counts['records_no_lane_data'] += 1
            continue
        for lane in lanes:
            typ = str(lane.get('type') or '').lower()
            category = ('general' if typ in GENERAL_LANE_TYPES else
                        'other' if typ in SUPPLEMENTAL_LANE_TYPES else 'unknown')
            counts[f'{category}_total'] += 1
            if str(lane.get('status') or '').lower() == 'closed':
                counts[f'{category}_closed'] += 1
    return counts


def _lane_text(c):
    def fmt(k):
        total, closed = c[f'{k}_total'], c[f'{k}_closed']
        return f'{closed}/{total} reported' if total else 'not reported'
    return (f"general={fmt('general')}; supplemental={fmt('other')}; "
            f"unclassified={fmt('unknown')}; "
            f"records missing lanes={c['records_no_lane_data']}")


def _record_json(d, i, f, status, **extra):
    return {'id': f.get('id'), 'distance_mi': round(d, 3),
            'status_at_query_time': status, 'road_names': _road_names(f),
            'properties': f.get('properties') or {}, **extra}


def _workzone_results(feed, street, near_lat, near_lon, radius_mi,
                      start_hour, end_hour, check_date):
    F = T._load(feed)
    now = T._now()
    tz = _zone(feed)
    start, end = _target_window(start_hour, end_hour, check_date, tz, now)
    nearby = _nearby(F, now, near_lat, near_lon, radius_mi, {'active', 'pending'})
    matching = [item for item in nearby if _street_match(street, _road_names(item[2]))]
    rows = []
    for d, i, f, status in matching:
        timing, reason = _record_time_status(f.get('properties') or {}, start, end)
        rows.append((d, i, f, status, timing, reason))
    return F, start, end, nearby, rows


def work_zones_during_hours_plain(
    feed: str, street: str, near_lat: float, near_lon: float,
    radius_mi: float = 1.0, start_hour: int = 11, end_hour: int = 14,
    check_date: str = None,
) -> str:
    """Plain baseline: text-only street-name matching (no temporal/geographic filter)."""
    F = T._load(feed)
    hits = [f for f in F['wz'] if _street_match(street, _road_names(f))]
    lines = [f"PLAIN BASELINE / TOOL 1 | feed={F['name']} | street={street}",
             f'Matching records anywhere in feed: {len(hits)}',
             'No status, location, or proposed time-window filtering is applied.']
    for f in hits:
        p = f.get('properties') or {}
        lines.append(f"  {f.get('id','?')} | roads={', '.join(_road_names(f)) or 'not provided'}"
                     f" | start={p.get('start_date') or 'unknown'}"
                     f" | end={p.get('end_date') or 'open-ended/unknown'}"
                     f" | impact={p.get('vehicle_impact') or 'unknown'}")
    return '\n'.join(lines)


@T._errors_as_text
def work_zones_during_hours(
    feed: str, street: str, near_lat: float, near_lon: float,
    radius_mi: float = 1.0, start_hour: int = 11, end_hour: int = 14,
    check_date: str = None,
) -> str:
    """
    Identify existing work-zone conflicts when a user is planning to issue a road-closure permit 
    for a specified street, location, and time window.

    USE THIS TOOL when the user asks if there are  road closures, construction 
    projects, or work zones that might conflict with a proposed closure. 

    PREFER THIS TOOL over general toolkit functions such as get_work_zones
    when the question concerns scheduling conflicts or permit evaluation.
    Unlike tools from the general toolkit, this tool evaluates reported
    work-zone dates and times against the requested window and identifies
    potential conflicts. Use general toolkit functions when the user needs
    raw work-zone records rather than a conflict assessment.

    REQUIRED INPUTS:
        feed:       WZDx feed identifier, such as 'FL' for Florida.
        street:     Street name provided by the user, such as 'Kennedy Blvd'.
        near_lat:   Verified latitude in decimal degrees.
        near_lon:   Verified longitude in decimal degrees.
        radius_mi:  Search radius in miles (default 1.0).
        start_hour: Beginning of requested local-time window, 24-hour
                    format (default 11).
        end_hour:   End of requested local-time window, 24-hour
                    format (default 14).
        check_date: Date in YYYY-MM-DD format. Defaults to local today.

    GEOGRAPHIC VALIDATION:
        Use latitude and longitude when supplied by the user or
        verified through an appropriate geocoding or location tool.
        NEVER invent, estimate, or assume geographic coordinates.
        If coordinates cannot be reliably established, ask the user
        to provide them rather than evaluating a potentially wrong
        location. It is better to ask a clarifying question than guess

    INTERPRETING RESULTS:
        The tool screens active and pending work-zone records for
        geographic and temporal overlap. It does not establish
        whether a road is free of construction. A result with zero 
        matches just means that are no matching conflicts, NOT that a
        permit is automatically safe to approve.

    LIMITATIONS:
        This tool does NOT approve or deny permits.
        It does NOT calculate traffic delay, travel-time increases,
        queue lengths, or roadway capacity reductions.
        For questions about the number or types of lanes currently
        closed nearby, use lane_closure_traffic_impact.
        No tools in the toolkit can anwser travel times questions

    Read-only.
    """

    F, start, end, nearby, rows = _workzone_results(
        feed, street, near_lat, near_lon, radius_mi, start_hour, end_hour, check_date)
    overlapping = [r for r in rows if r[4] == 'overlap']
    uncertain = [r for r in rows if r[4] == 'uncertain']
    outside = [r for r in rows if r[4] == 'outside']
    lines = [
        'TOOL 1 | WORK-ZONE DATE/TIME CONFLICT SCREEN',
        f"Feed: {F['name']} | Road searched: {street}",
        f'Center: ({near_lat:.4f}, {near_lon:.4f}) | Radius: {radius_mi:g} mi',
        f'Window: {start:%Y-%m-%d %H:%M %Z} to {end:%Y-%m-%d %H:%M %Z}',
        'Scope: feed records active/pending NOW, matching road name and radius.',
        '',
        'FILTER RESULTS',
        f'  Active/pending records within radius (any road): {len(nearby)}',
        f'  Matching requested road: {len(rows)}',
        f'  Confirmed time-window overlaps: {len(overlapping)}',
        f'  Cannot determine temporal overlap: {len(uncertain)}',
        f'  Outside requested date/time: {len(outside)}',
    ]
    if not rows:
        nearby_roads = []
        for _, _, f, _ in nearby:
            for name in _road_names(f):
                if name not in nearby_roads:
                    nearby_roads.append(name)
        lines += ['', 'MATCHING RECORDS', '  None.',
                  f'  Nearby named roads: {", ".join(nearby_roads[:12]) or "none reported"}']
    else:
        lines += ['', 'MATCHING RECORDS']
        rank = {'overlap': 0, 'uncertain': 1, 'outside': 2}
        for d, i, f, status, timing, reason in sorted(rows, key=lambda x: (rank[x[4]], x[0])):
            p = f.get('properties') or {}
            ts = _parse_date(p.get('start_date'))
            te = _parse_date(p.get('end_date'))
            tz = start.tzinfo
            start_str = ts.astimezone(tz).strftime('%Y-%m-%d %H:%M %Z') if ts else 'unknown'
            end_str = te.astimezone(tz).strftime('%Y-%m-%d %H:%M %Z') if te else ('open-ended' if not p.get('end_date') else 'invalid')
            lines.append(f'  [{timing.upper()}] ID={f.get("id", "?")} | status now={status} | {d:.2f} mi')
            lines.append(f'    Roads: {", ".join(_road_names(f)) or "not provided"}')
            lines.append(f'    Recorded interval: {start_str} -> {end_str}')
            lines.append(f'    Vehicle impact: {p.get("vehicle_impact") or "not reported"}; note: {reason}')
    lines += ['', 'SCREENING INTERPRETATION']
    if overlapping:
        lines.append(f'  REVIEW: {len(overlapping)} matching record(s) overlap the requested date/time window.')
        lines.append('  Conflict detected. Consider shifting the requested window or date.')
    elif uncertain:
        lines.append('  INDETERMINATE: matching record dates are incomplete; review source data.')
    else:
        nearby_work_count = len(set(_work_id(f) for _, _, f, _ in nearby))
        if nearby_work_count >= 3:
            lines.append('  No confirmed conflicts on this street, but high concurrent activity nearby.')
            lines.append('  Consider field verification before permit issue, or depending on work need severity, postpone.')
        else:
            nearby_work_count = len(set(_work_id(f) for _, _, f, _ in nearby))
            if nearby_work_count >= 3:
                lines.append('  No confirmed conflicts on this street, but high concurrent activity nearby.')
                lines.append('  Consider field verification before permit issue, or depending on work need severity, postpone.')
            else:
                lines.append('  Based on current information, permit can proceed as planned.')
    if uncertain and overlapping:
        lines.append(f'  Also review {len(uncertain)} matching record(s) with uncertain timing.')
    lines.append('  Verify coverage, lane restrictions, and field conditions before permit approval.')
    return '\n'.join(lines)


def lane_closure_traffic_impact_plain(
    feed: str, near_lat: float, near_lon: float, radius_mi: float = 0.5,
) -> str:
    """Plain baseline: raw lane counts by active record; no lane-type distinctions."""
    F = T._load(feed)
    hits = _nearby(F, T._now(), near_lat, near_lon, radius_mi, {'active'})
    lines = [f"PLAIN BASELINE / TOOL 2 | feed={F['name']} | radius={radius_mi:g} mi",
             f'Active records in radius: {len(hits)}']
    for d, i, f, _ in hits:
        p = f.get('properties') or {}
        lanes = p.get('lanes') or []
        lane_txt = (f"{sum(l.get('status') == 'closed' for l in lanes)}/{len(lanes)}"
                    if lanes else 'not reported')
        lines.append(f'  ID={f.get("id", "?")} | {d:.2f} mi | closed/total={lane_txt}'
                     f' | impact={p.get("vehicle_impact") or "unknown"}')
    return '\n'.join(lines)


def _impact_results(feed, near_lat, near_lon, radius_mi):
    F = T._load(feed)
    now = T._now()
    hits = _nearby(F, now, near_lat, near_lon, radius_mi, {'active'})
    projects = defaultdict(list)
    for d, i, f, status in hits:
        projects[_record_key(f, i)].append((d, i, f, status))
    ordered = sorted(projects.items(), key=lambda kv: min(r[0] for r in kv[1]))
    return F, hits, ordered


@T._errors_as_text
def lane_closure_traffic_impact(
    feed: str, near_lat: float, near_lon: float, radius_mi: float = 0.5,
) -> str:
    """
    Identify existing lane closures near a proposed road-closure permit
    location and report the types of lanes currently affected.

    USE THIS TOOL when you need to answer how many lanes are currently closed
    near a given location, if multiple construction projects are active
    nearby, or if existing lane restrictions might make approving new permits
    in this area unwise. 

    PREFER THIS TOOL over general toolkit functions such as get_work_zones
    when the question concerns existing lane closures or the potential
    burden of additional construction. Unlike general work-zone lookup
    tools, this function groups records by work ID, distinguishes general
    travel lanes from supplemental lanes, and flags multiple nearby
    construction projects.

    REQUIRED INPUTS:
        feed:       WZDx feed identifier, such as 'FL' for Florida.
        near_lat:   Verified latitude in decimal degrees.
        near_lon:   Verified longitude in decimal degrees.
        radius_mi:  Search radius in miles (default 0.5).

    GEOGRAPHIC VALIDATION:
        Use latitude and longitude supplied by the user or verified
        through an appropriate geocoding or location tool.
        NEVER invent, estimate, or assume geographic coordinates.
        If coordinates cannot be reliably established, ask the user
        to provide them instead of guessing.

    INTERPRETING RESULTS:
        The tool reports active work-zone records within the specified
        radius and groups records belonging to the same work ID.
        General lanes are lanes used for vehicle travel, while
        supplemental lanes include shoulders, parking lanes, and
        other non-mainline lane types.
        Multiple active works within a radius indicate possible
        overlapping construction impacts, but do not prove that
        the projects affect the same road, direction, or segment.

    LIMITATIONS:
        This tool does NOT approve or deny permits.
        It does NOT calculate actual traffic capacity reductions,
        vehicle delays, queue lengths, or travel-time increases.
        For questions about whether existing work zones overlap
        a proposed closure's date and time, use
        work_zones_during_hours.
        No tools in the toolkit can anwser travel times questions

    Read-only.
    """

    F, hits, projects = _impact_results(feed, near_lat, near_lon, radius_mi)
    org = T._orgs(F['info'])
    total = _classify_lanes(hits)
    lines = [
        'TOOL 2 | NEARBY ACTIVE WORKS & LANE RESTRICTIONS',
        f"Feed: {F['name']} | Center: ({near_lat:.4f}, {near_lon:.4f}) | Radius: {radius_mi:g} mi",
        'Scope: all roads within radius; work status must be active NOW.',
        '', 'SUMMARY',
        f'  Active WZDx records: {len(hits)}',
        f'  Grouped work IDs (approx. projects): {len(projects)}',
        f"  Reported closed general-lane entries: {total['general_closed']}",
        f"  Reported closed supplemental-lane entries: {total['other_closed']}",
        f"  Reported closed unclassified-lane entries: {total['unknown_closed']}",
        f"  Records with no lane data: {total['records_no_lane_data']}",
        '', 'WORK DETAILS',
    ]
    if not projects:
        lines.append('  No active records were found inside the radius.')
    for wid, recs in projects:
        names = []
        agencies = []
        for _, _, f, _ in recs:
            for name in _road_names(f):
                if name not in names:
                    names.append(name)
            source = (f.get('properties') or {}).get('core_details') or {}
            agency = org.get(source.get('data_source_id'), 'not reported')
            if agency not in agencies:
                agencies.append(agency)
        c = _classify_lanes(recs)
        dist = min(r[0] for r in recs)
        lines.append(f'  Work ID: {wid} | nearest record {dist:.2f} mi | {len(recs)} record(s)')
        lines.append(f'    Roads: {", ".join(names) or "not reported"}')
        lines.append(f'    Source: {", ".join(agencies)}')
        lines.append(f'    Lane data: {_lane_text(c)}')
    lines += ['', 'SCREENING INTERPRETATION']
    if len(projects) >= 2:
        lines.append(f'  REVIEW: {len(projects)} active work IDs are located near the reference point.')
        lines.append('  Their restrictions may affect different roads, directions, and segments.')
    elif projects:
        lines.append('  One active work ID was identified near the reference point.')
    else:
        lines.append('  No active work records found; this does not establish that roads are clear.')
    if total['records_no_lane_data']:
        lines.append('  INCOMPLETE DATA: missing lane lists prevent a complete closure count.')
    lines.append('  Lane totals count feed entries, NOT unique blocked lanes or capacity reduction.')
    lines.append('  No delay, queue length, travel-time, or capacity estimate is calculated.')
    return '\n'.join(lines)


# Registry retained for WZDx-Tools framework compatibility.
TOOLS = [work_zones_during_hours, lane_closure_traffic_impact]
READ_ONLY = {'work_zones_during_hours', 'lane_closure_traffic_impact'}
PLAIN_DESCRIPTIONS = {
    'work_zones_during_hours':
        'Screen active/pending work zones by street, radius and local date/time. '
        'feed, street, near_lat, near_lon, radius_mi, start_hour, end_hour, '
        'optional check_date (YYYY-MM-DD). Read-only.',
    'lane_closure_traffic_impact':
        'Report active nearby work IDs and lane-closure entries by type. '
        'feed, near_lat, near_lon, radius_mi. Read-only.',
}


@T._errors_as_text
def work_zones_during_hours_raw(
    feed: str, street: str, near_lat: float, near_lon: float,
    radius_mi: float = 1.0, start_hour: int = 11, end_hour: int = 14,
    check_date: str = None,
) -> str:
    """JSON: same matching records and temporal classification as designed Tool 1."""
    F, start, end, nearby, rows = _workzone_results(
        feed, street, near_lat, near_lon, radius_mi, start_hour, end_hour, check_date)
    records = [_record_json(d, i, f, st, time_classification=timing, time_note=reason)
               for d, i, f, st, timing, reason in rows]
    return json.dumps({'tool': 'work_zones_during_hours', 'feed': F['name'],
                       'requested_street': street, 'window_start_local': start.isoformat(),
                       'window_end_local': end.isoformat(),
                       'nearby_active_pending_records_all_roads': len(nearby),
                       'matching_records': records}, indent=2, default=str)


@T._errors_as_text
def lane_closure_traffic_impact_raw(
    feed: str, near_lat: float, near_lon: float, radius_mi: float = 0.5,
) -> str:
    """JSON: same active records and lane tallies as designed Tool 2."""
    F, hits, projects = _impact_results(feed, near_lat, near_lon, radius_mi)
    return json.dumps({'tool': 'lane_closure_traffic_impact', 'feed': F['name'],
                       'radius_mi': radius_mi, 'active_record_count': len(hits),
                       'work_id_count': len(projects),
                       'lane_entry_totals': _classify_lanes(hits),
                       'records': [_record_json(d, i, f, st) for d, i, f, st in hits]},
                      indent=2, default=str)


RAW_RESULTS = {
    'work_zones_during_hours': work_zones_during_hours_raw,
    'lane_closure_traffic_impact': lane_closure_traffic_impact_raw,
}


if __name__ == '__main__':
    print('=== TOOL 1: BUSCH BLVD ===')
    print(work_zones_during_hours('FL', 'Busch Blvd', 28.0587, -82.4139,
                                  start_hour=11, end_hour=14))
    print('\n=== TOOL 2: BUSCH BLVD AREA ===')
    print(lane_closure_traffic_impact('FL', 28.0587, -82.4139, radius_mi=1.0))
    print('\n=== TOOL 1: KENNEDY BLVD ===')
    print(work_zones_during_hours('FL', 'Kennedy Blvd', 27.9472, -82.4677,
                                  radius_mi=0.5, start_hour=11, end_hour=14))
    print('\n=== TOOL 2: KENNEDY BLVD AREA ===')
    print(lane_closure_traffic_impact('FL', 27.9472, -82.4677, radius_mi=0.5))
