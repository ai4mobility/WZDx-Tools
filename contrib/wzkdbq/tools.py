"""Read-only FDOT work-zone screening for crash diversion decisions."""

import gzip
import json
import os
import re
import sys
import time
from datetime import timezone
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import wzdx_tools as T

Direction = Literal['NB', 'SB', 'EB', 'WB', 'northbound', 'southbound', 'eastbound', 'westbound']
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Radius = Annotated[float, Field(gt=0, le=25)]
DIRECTIONS = {'NB': 'northbound', 'SB': 'southbound', 'EB': 'eastbound', 'WB': 'westbound'}
UNREPORTED = {None, '', 'unknown', 'undefined', 'not-reported'}
STREET_WORDS = {
    'BOULEVARD': 'BLVD', 'AVENUE': 'AVE', 'STREET': 'ST', 'ROAD': 'RD',
    'DRIVE': 'DR', 'COURT': 'CT', 'LANE': 'LN', 'PARKWAY': 'PKWY',
    'EAST': 'E', 'WEST': 'W', 'NORTH': 'N', 'SOUTH': 'S',
}


def _direction(value):
    value = value.strip()
    normalized = DIRECTIONS.get(value.upper(), value.lower())
    if normalized not in DIRECTIONS.values():
        raise ValueError('Give a direction such as EB, WB, NB or SB.')
    return normalized


def _road_parts(value):
    words = re.findall(r'[A-Z0-9]+', value.upper())
    return tuple(STREET_WORDS.get(word, word) for word in words)


def _same_road(query, names):
    route = T._norm_road(query)
    if re.match(r'^(I|US|SR|CR|L)-\d', route):
        return T._road_match(query, *names)
    wanted = _road_parts(query)
    for name in names:
        for segment in re.split(r'[,;]', name):
            candidate = _road_parts(segment)
            if candidate == wanted or (
                candidate and candidate[0] in {'N', 'S', 'E', 'W'} and candidate[1:] == wanted
            ):
                return True
    return False


def _nearby(road, near_lat, near_lon, radius_mi):
    if not _road_parts(road):
        raise ValueError('Give a road name or route number, such as Busch Blvd or I-95.')
    if not (-90 <= near_lat <= 90 and -180 <= near_lon <= 180 and 0 < radius_mi <= 25):
        raise ValueError('Give valid latitude and longitude and a radius greater than 0 and at most 25 miles.')
    feed = T._load('FL')
    now = T._now()
    records = []
    unnamed = 0
    for feature in feed['wz']:
        props = feature['properties']
        if T._status(props, now) != 'active':
            continue
        points = T._pts(feature)
        if not points or not points[0]:
            continue
        distance = T._dist(feature, near_lat, near_lon)
        if distance is None or distance > radius_mi:
            continue
        names = props['core_details'].get('road_names') or []
        if not any(_road_parts(name) for name in names):
            unnamed += 1
        elif _same_road(road, names):
            records.append((distance, str(feature['id']), props))
    return feed['info'].get('update_date'), sorted(records, key=lambda item: item[:2]), unnamed


@lru_cache(maxsize=1)
def _detour_index(snapshot, refresh_bucket):
    if snapshot:
        path = Path(snapshot) / 'fldot.json'
        compressed = path.with_suffix('.json.gz')
        if compressed.exists():
            with gzip.open(compressed, 'rt', encoding='utf-8') as stream:
                feed = json.load(stream)
        else:
            with path.open(encoding='utf-8') as stream:
                feed = json.load(stream)
    else:
        feed = T._get(T._url(T._registry()['fldot']))
    work_zones = {}
    detours = {}
    for feature in feed['features']:
        props = feature['properties']
        core = props['core_details']
        feature_id = str(feature['id'])
        if core['event_type'] == 'work-zone':
            work_zones[feature_id] = _related(core, 'related-detour', 'children')
        elif core['event_type'] == 'detour':
            detours[feature_id] = props
    return feed['feed_info'].get('update_date'), work_zones, detours


def _related(core, event_type, fallback):
    standard = {str(event['id']) for event in core.get('related_road_events') or ()
                if event.get('type') == event_type and event.get('id') is not None}
    return standard or set(map(str, (core.get('relationship') or {}).get(fallback) or ()))


def _linked(work_zone_id):
    work_zone_id = work_zone_id.strip()
    snapshot = os.environ.get('WZDX_SNAPSHOT')
    update, work_zones, detours = _detour_index(snapshot, 0 if snapshot else int(time.time() // T.CACHE_S))
    if work_zone_id not in work_zones:
        raise ValueError('Work-zone ID not found. Use the exact FDOT feature ID from the work-zone lookup.')
    records = [
        (feature_id, props) for feature_id, props in detours.items()
        if feature_id in work_zones[work_zone_id]
        or work_zone_id in _related(props['core_details'], 'related-work-zone', 'parents')
    ]
    return update, sorted(records)


@T._errors_as_text
def crash_area_work_zone_constraints_plain(
    road: str, near_lat: Latitude, near_lon: Longitude, direction: Direction, radius_mi: Radius = 5.0,
) -> str:
    """Return matching FDOT records and their raw fields."""
    requested = _direction(direction)
    update, records, unnamed = _nearby(road, near_lat, near_lon, radius_mi)
    return json.dumps({
        'feed_updated': update,
        'records_without_road_name': unnamed,
        'records': [
            {'id': feature_id, 'distance_mi': round(distance, 2), **props}
            for distance, feature_id, props in records
            if props['core_details'].get('direction') in UNREPORTED | {requested}
        ],
    })


@T._errors_as_text
def linked_work_zone_detours_for_direction_plain(work_zone_id: str, direction: Direction) -> str:
    """Return linked detour records and their raw fields."""
    requested = _direction(direction)
    update, records = _linked(work_zone_id)
    return json.dumps({'feed_updated': update, 'records': [
        {'id': feature_id, **props} for feature_id, props in records
        if props['core_details'].get('direction') in UNREPORTED | {requested}
    ]})


def _utc(value):
    parsed = T._ts(value)
    return parsed.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if parsed else 'not reported'


def _end(props):
    value = props.get('end_date')
    if not T._ts(value):
        return 'end time not reported'
    status = 'feed reports end verified' if props.get('is_end_date_verified') is True else 'end unverified'
    return f'reported end {_utc(value)} ({status})'


def _feed_label(update):
    source = 'Saved FDOT snapshot' if os.environ.get('WZDX_SNAPSHOT') else 'FDOT feed'
    return f'{source}, published update {_utc(update)}.'


def _lane_summary(props):
    impact = props.get('vehicle_impact')
    summary = 'lane impact not reported' if impact in UNREPORTED else impact.replace('-', ' ')
    lanes = props.get('lanes') or []
    orders = [lane.get('order') for lane in lanes]
    complete = (
        lanes and all(isinstance(order, int) for order in orders)
        and sorted(orders) == list(range(1, len(lanes) + 1))
        and all(lane.get('type') not in UNREPORTED and lane.get('status') not in UNREPORTED for lane in lanes)
    )
    if complete:
        travel = [lane for lane in lanes if lane['type'] == 'general']
        closed = [lane for lane in lanes if 'shoulder' in lane['type'] and lane['status'] == 'closed']
        labels = [T._lanes_text(travel)] if travel else []
        labels.extend(f"shoulder at feed order {lane['order']} closed" for lane in closed)
        detail = ', '.join(filter(None, labels))
        if detail:
            return f'{summary}; {detail}'
    return f'{summary}; specific closed travel-lane position not established'


@T._errors_as_text
def crash_area_work_zone_constraints(
    road: str, near_lat: Latitude, near_lon: Longitude, direction: Direction, radius_mi: Radius = 5.0,
) -> str:
    """Screen FDOT work-zone records near a crash point or candidate bypass. Enter a road name or route number,
    latitude and longitude, EB/WB/NB/SB, and a radius in miles. Results count reported work-zone records and give
    distance in miles, evidence time in UTC, and closed general travel-lane positions when supported. Records
    with unknown direction are listed separately. Unknown lane impact does not establish that lanes are open.
    For a linked detour use its work-zone ID with linked_work_zone_detours_for_direction. This point-radius
    screen cannot verify the crash, route alignment, or actual lane availability. The TMC operator verifies
    conditions through dispatch, a camera, or field staff before using the result. Read-only."""
    requested = _direction(direction)
    update, records, unnamed = _nearby(road, near_lat, near_lon, radius_mi)
    matches = []
    unknown = []
    for distance, feature_id, props in records:
        reported = props['core_details'].get('direction')
        if reported == requested:
            group = matches
            evidence = f'FDOT reports {requested}'
        elif reported in UNREPORTED:
            group = unknown
            evidence = f'direction unknown; this record is not assigned to {requested}'
        else:
            continue
        group.append(f'- {feature_id} · {evidence} · {distance:.2f} mi · {_lane_summary(props)} · {_end(props)}')
    uncertain = [f'Separate records with unknown direction: {len(unknown)}.', *unknown] if unknown else []
    return '\n'.join([
        f'FDOT work-zone screen: {road}, {requested}, within {radius_mi:g} mi of ({near_lat:g}, {near_lon:g}). '
        f'{_feed_label(update)}',
        f'Reported {requested} records: {len(matches)}.', *matches,
        *uncertain,
        f'Nearby active records without a road name: {unnamed}. The name search cannot assign them to this road.',
        'This is a work-zone proximity screen. Verify crash conditions and route suitability independently.',
    ])


@T._errors_as_text
def linked_work_zone_detours_for_direction(work_zone_id: str, direction: Direction) -> str:
    """Look up published FDOT work-zone detour records for an exact work-zone feature ID and EB/WB/NB/SB.
    Returns linked detour IDs, their names, and reported dates in UTC. It separates unknown directions and
    excludes known opposite directions using the direction field. An unverified end time is a reported
    planning window, not evidence of reopening. For a road or point without an ID, first use
    crash_area_work_zone_constraints or the toolkit lookup. A feed relationship does not approve a crash
    diversion. The TMC operator checks current conditions and the incident response plan before use. Read-only."""
    requested = _direction(direction)
    update, records = _linked(work_zone_id)
    matches = []
    unknown = []
    for feature_id, props in records:
        core = props['core_details']
        reported = core.get('direction')
        if reported == requested:
            group = matches
            evidence = f'FDOT reports {requested}'
        elif reported in UNREPORTED:
            group = unknown
            evidence = f'direction unknown; this record is not assigned to {requested}'
        else:
            continue
        name = core.get('name') or 'name not reported'
        group.append(
            f'- {feature_id} · {evidence} · {name} · reported start {_utc(props.get("start_date"))} · {_end(props)}'
        )
    verdict = (
        f'Reported {requested} detour records: {len(matches)}.'
        if matches else f'No linked detour for this work-zone ID and direction ({requested}).'
    )
    uncertain = [f'Separate detours with unknown direction: {len(unknown)}.', *unknown] if unknown else []
    return '\n'.join([
        f'FDOT work-zone {work_zone_id.strip()}. {_feed_label(update)}',
        verdict, *matches, *uncertain,
        'These are published work-zone relationships. Verify conditions and approval for crash diversion.',
    ])


TOOLS = [crash_area_work_zone_constraints, linked_work_zone_detours_for_direction]
READ_ONLY = {tool.__name__ for tool in TOOLS}
PLAIN_DESCRIPTIONS = {
    'crash_area_work_zone_constraints': 'Return FDOT records for a road, coordinates, direction, and radius in miles. Read-only.',
    'linked_work_zone_detours_for_direction': 'Return FDOT detour records for a work-zone ID and direction. Read-only.',
}
RAW_RESULTS = {
    'crash_area_work_zone_constraints': crash_area_work_zone_constraints_plain,
    'linked_work_zone_detours_for_direction': linked_work_zone_detours_for_direction_plain,
}
