"""Arizona 511 tools for AI agents, written the way a traffic engineer would write them.

AI for Mobility, Part II (AI agents). Ten read-only tools over the Arizona 511 developer API run by ADOT
(https://az511.com/developers/doc). Each tool is a plain Python function; its docstring is the description the
model reads. az511_mcp_server.py serves the same functions over MCP, so Claude Desktop or Claude Code can call them.

What the tools do that the raw API does not:
  * filter by road and by distance from a point, so the model gets 10 events, not every event in the state
  * turn Unix timestamps into Arizona time (MST all year: Arizona does not observe daylight saving time; the
    Navajo Nation does, and these tools do not handle that)
  * write units (feet, tons, mph) and say "not reported" or "unit not stated" instead of guessing
  * keep the API key inside the tool, so the model never sees it
  * cache each endpoint for 60 s, which keeps a busy agent under AZ511's limit of 10 calls per 60 seconds

Key:      put your AZ511 developer key in the environment variable AZ511_KEY, or in a one-line file named by
          AZ511_KEY_FILE, or in .secrets/az511_key.txt in this folder or any folder above it (in the WZDx-Tools
          repository: the repository's own .secrets/, which git ignores). The work-zone feed (WZDx) needs no key.
Offline:  AZ511_SNAPSHOT=<folder> reads saved responses (<endpoint>.json) instead of calling the API.

    python az511_tools.py demo                        # a short tour
    python az511_tools.py trip                        # the trip briefing: I-17 north, Phoenix to Flagstaff
    python az511_tools.py snapshot live/20261105      # save one response per endpoint (7 calls), for offline use
"""
import os, sys, json, math, re, time, html, datetime, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://az511.com/api/v2/get/'
WZDX_URL = 'https://az511.com/api/wzdx'
ENDPOINTS = ('event', 'alerts', 'messagesigns', 'cameras', 'weatherstations', 'restareas', 'wzdx')
AZ = ZoneInfo('America/Phoenix')
CACHE_S = 60
RATE = (10, 60)                      # AZ511: "Throttling is enabled. Ten calls every 60 seconds."
UA = 'AI4Mobility course tools (USF CGN 6933)'
_cache, _calls = {}, []


# ------------------------------------------------------------------ plumbing the model never sees
def _key():
    k = os.environ.get('AZ511_KEY', '').strip()
    if k: return k
    path = os.environ.get('AZ511_KEY_FILE')
    if not path:                                    # the nearest .secrets/az511_key.txt, here or in a folder above
        d = HERE
        while True:
            if os.path.exists(os.path.join(d, '.secrets', 'az511_key.txt')):
                path = os.path.join(d, '.secrets', 'az511_key.txt'); break
            if os.path.dirname(d) == d: break
            d = os.path.dirname(d)
    if path and os.path.exists(path):
        return open(path, encoding='utf-8').read().strip()
    raise RuntimeError('No AZ511 developer key. Sign in at az511.com, open Developers, request a key, and put it in '
                       'the AZ511_KEY environment variable or in a file .secrets/az511_key.txt (one line).')


def _now():
    t = os.environ.get('AZ511_NOW')                 # tests pin the clock
    return float(t) if t else time.time()


def _fetch(name):
    """One endpoint as parsed JSON: from the snapshot folder, from the 60 s cache, or from the API."""
    snap = os.environ.get('AZ511_SNAPSHOT')
    if snap:
        return json.load(open(os.path.join(snap, name + '.json'), encoding='utf-8'))
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    recent = [t for t in _calls if time.time() - t < RATE[1]]
    if len(recent) >= RATE[0] - 1:                  # keep one call in reserve
        wait = int(RATE[1] - (time.time() - min(recent))) + 1
        raise RuntimeError(f'AZ511 allows {RATE[0]} calls per {RATE[1]} s. Try again in {wait} s.')
    url = WZDX_URL if name == 'wzdx' else BASE + name + '?' + urllib.parse.urlencode({'key': _key(), 'format': 'json'})
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    _calls.append(time.time())
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:              # never echo the URL: it carries the key
        raise RuntimeError(f'AZ511 answered HTTP {e.code} for "{name}".' +
                           (' Check the developer key: AZ511 answers 400 to a wrong key.' if e.code in (400, 401, 403) else '')) from None
    _cache[name] = (time.time(), data)
    return data


def _errors_as_text(fn):
    """A tool never raises: the model reads the error and can fix its call or tell the person."""
    import functools
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:
            return f'Error: {e}'
    return wrapper


# ------------------------------------------------------------------ helpers: time, place, roads
def _fmt(d, year=None):
    """A date in Arizona time. The year is shown when it is not this year (year=None) or always (year=True):
    the feeds keep some events for years, and 'Sun Nov 12' alone reads as this year."""
    if year is None:
        year = d.year != datetime.datetime.fromtimestamp(_now(), AZ).year
    return f"{d:%a %b} {d.day}{' ' + str(d.year) if year else ''} {d:%H:%M} MST"


def _t(unix):
    if not unix: return 'not reported'
    return _fmt(datetime.datetime.fromtimestamp(unix, AZ))


def _end(unix):
    """An expected end, marked when it is already past: ADOT keeps some events listed long after their planned end."""
    if not unix: return 'not reported'
    return _t(unix) + (' (already passed)' if unix < _now() else '')


def _iso(s):
    """ISO 8601 -> datetime. Python 3.10 accepts only 3 or 6 fractional digits; the WZDx feed sends 5."""
    s = re.sub(r'\.(\d+)', lambda m: '.' + (m.group(1) + '000000')[:6], s.replace('Z', '+00:00'))
    return datetime.datetime.fromisoformat(s)


def _iso_t(s):
    if not s: return 'not reported'
    return _fmt(_iso(s).astimezone(AZ), year=True)


def _ago(unix):
    if not unix: return 'update time not reported'
    m = (_now() - unix) / 60
    if m < 0: return 'updated just now'
    if m < 90: return f'updated {m:.0f} min ago'
    if m < 48 * 60: return f'updated {m / 60:.0f} h ago'
    return f'updated {m / 1440:.0f} days ago'


def _mi(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def _norm_road(s):
    """'Interstate 10', 'I 10', 'i-10' -> 'I-10'; 'Loop 101', '101-LOOP', 'L101', 'SR-101' -> 'L-101'; 'SR 87' -> 'SR-87'."""
    s = ' ' + (s or '').upper() + ' '
    s = re.sub(r'\bINTERSTATE\s*', 'I-', s)
    s = re.sub(r'\b(\d{2,3})\s*-?\s*LOOP\b', r'L-\1', s)
    s = re.sub(r'\bLOOP\s*-?\s*(\d{2,3})\b', r'L-\1', s)
    s = re.sub(r'\b(I|US|SR|L)\s*-?\s*(\d{1,3})\b', r'\1-\2', s)
    s = re.sub(r'\bSTATE ROUTE\s*(\d{1,3})\b', r'SR-\1', s)
    s = re.sub(r'\bSR-(101|202|303)L?\b', r'L-\1', s)    # Phoenix's loops are state routes: cameras say SR-202
    return re.sub(r'\s+', ' ', s).strip()


def _road_match(query, *fields):
    if not query: return True
    q = _norm_road(query)
    text = ' ' + ' | '.join(_norm_road(f) for f in fields if f) + ' '
    return re.search(r'(?<![A-Z0-9-])' + re.escape(q) + r'(?![0-9])', text) is not None


def _place(items, lat_of, lon_of, near_lat, near_lon, radius_mi):
    """Keep items within radius_mi of the point, nearest first; attach the distance. No point: keep all."""
    if near_lat is None or near_lon is None:
        return [(None, it) for it in items]
    out = []
    for it in items:
        la, lo = lat_of(it), lon_of(it)
        if la is None or lo is None: continue
        d = _mi(near_lat, near_lon, la, lo)
        if d <= radius_mi: out.append((d, it))
    return sorted(out, key=lambda x: x[0])


def _where(d):
    return '' if d is None else f' · {d:.1f} mi away'


def _head(source, n_match, n_all, shown, extra=''):
    return (f'AZ511 {source} (ADOT), read {_t(_now())}: {n_match} match of {n_all}; showing {shown}.' +
            (' ' + extra if extra else ''))


def _clean(s, n=280):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


def _lanes_text(lanes):
    """WZDx numbers lanes from the left (order 1 = left-most) and lists shoulders as lanes. A driver needs 'right
    lane of 3 closed', not 'lane 4 of 5', so count travel lanes only and name the side. (Same as wzdx_tools.)"""
    if not lanes: return ''
    L = sorted(lanes, key=lambda l: l.get('order') or 0)
    travel = [l for l in L if 'shoulder' not in (l.get('type') or '')]
    n = len(travel); closed = [k + 1 for k, l in enumerate(travel) if l.get('status') == 'closed']
    out = []
    if closed:
        c = len(closed); what = 'lane' if c == 1 else f'{c} lanes'
        if n == 1 or c == n: out.append(f'all {n} travel lane(s) closed' if n > 1 else 'the only travel lane closed')
        elif closed == list(range(n - c + 1, n + 1)): out.append(f'right {what} of {n} closed')
        elif closed == list(range(1, c + 1)): out.append(f'left {what} of {n} closed')
        else: out.append(f"travel lane(s) {', '.join(map(str, closed))} of {n} closed, counted from the left")
    if travel:
        first = travel[0].get('order') or 0
        for l in L:
            if 'shoulder' in (l.get('type') or '') and l.get('status') == 'closed':
                out.append(('left' if (l.get('order') or 0) < first else 'right') + ' shoulder closed')
    return ', '.join(out)


def _pages(sign):
    """A sign's message pages, without blanks and without ADOT's placeholder 'NO_MESSAGE' (a blank sign)."""
    return [p for p in (sign.get('Messages') or []) if p and p.strip() and p.strip().upper() != 'NO_MESSAGE']


def _trucks(r):
    """'truck spaces 8 of 22 available'; ADOT sends 'No Data' where it does not count free spaces."""
    tot, av = r.get('TotalTruckSpaces'), r.get('AvailableTruckSpaces')
    has = lambda v: v not in (None, '', 'No Data')
    if has(tot) and str(tot) != '0' and has(av): return f'truck spaces {av} of {tot} available'
    if has(tot) and str(tot) != '0': return f'{tot} truck spaces, availability not reported'
    return 'truck parking not reported'


def _dir(d):
    return d if d and d not in ('None', 'Unknown') else 'direction not reported'


# ------------------------------------------------------------------ the tools
@_errors_as_text
def get_road_events(road: Optional[str] = None, near_lat: Optional[float] = None, near_lon: Optional[float] = None,
                    radius_mi: float = 10.0, event_type: Optional[str] = None, max_results: int = 10) -> str:
    """Current road events on Arizona highways from AZ511 (ADOT): crashes and incidents, roadwork, and closures.

    Filter by road (for example 'I-10', 'I-17', 'SR-87', 'L-202') and/or by a point (near_lat, near_lon) and a
    radius in miles. event_type is one of 'accidentsAndIncidents', 'roadwork', 'closures'. Returns at most
    max_results events, nearest first when a point is given, otherwise most recently updated first. Each event has
    its event_id (for get_event_cameras), road, direction, lanes affected, whether all lanes are closed, start and
    expected end in Arizona time (MST, no daylight saving), and restrictions with units. Read-only. Events are reported by ADOT and its partners and
    can lag the road by minutes: say "reported", not "confirmed". A date shows its year when it is not this year,
    and an expected end in the past is marked "(already passed)": ADOT keeps some events listed after their planned
    end, so say that the planned end has passed rather than reporting the work as current."""
    ev = _fetch('event')
    if event_type and event_type not in ('accidentsAndIncidents', 'roadwork', 'closures'):
        return "Error: event_type must be 'accidentsAndIncidents', 'roadwork' or 'closures'."
    m = [e for e in ev if (not event_type or e.get('EventType') == event_type)
         and _road_match(road, e.get('RoadwayName'), e.get('Description'))]
    m = _place(m, lambda e: e.get('Latitude'), lambda e: e.get('Longitude'), near_lat, near_lon, radius_mi)
    if near_lat is None: m.sort(key=lambda x: -(x[1].get('LastUpdated') or 0))
    lines = [_head('road events', len(m), len(ev), min(len(m), max_results))]
    for d, e in m[:max_results]:
        lanes = e.get('LanesAffected')
        lanes = 'lanes not reported' if not lanes or lanes == 'No Data' else 'lanes: ' + lanes
        r = e.get('Restrictions') or {}
        if isinstance(r, list): r = r[0] if r else {}
        units = {'Width': 'ft', 'Height': 'ft', 'Weight': 'tons', 'Speed': 'mph'}
        lim = ', '.join(f'{k.lower()} {v} {units.get(k, "(unit not stated)")}' for k, v in r.items() if v not in (None, '', 0))
        sub = e.get('EventSubType') or e.get('Subtype')
        lines.append(f"- event {e.get('ID')} · [{e.get('EventType')}{' / ' + sub if sub else ''}] {e.get('RoadwayName')} · {_dir(e.get('DirectionOfTravel'))}"
                     f" · {lanes} · all lanes closed: {'yes' if e.get('IsFullClosure') else 'no'}{_where(d)}")
        lines.append(f"  {_clean(e.get('Description'))}")
        lines.append(f"  started {_t(e.get('StartDate'))} · expected end {_end(e.get('PlannedEndDate'))} · {_ago(e.get('LastUpdated'))}"
                     + (f' · limits: {lim}' if lim else ''))
    return '\n'.join(lines)


@_errors_as_text
def get_alerts(region: Optional[str] = None, high_importance_only: bool = False) -> str:
    """Statewide traveler alerts from AZ511 (ADOT) that are active now: major closures, weather, special events.

    region is an Arizona county name (for example 'Maricopa', 'Pima', 'Coconino'). Returns each alert's message,
    the counties it covers, its start and end in Arizona time, and whether ADOT marked it high importance.
    Read-only."""
    al = _fetch('alerts'); now = _now()
    act = [a for a in al if (a.get('StartTime') or 0) <= now and (not a.get('EndTime') or a['EndTime'] >= now)]
    m = [a for a in act if (not high_importance_only or a.get('HighImportance'))
         and (not region or any(region.lower() == (g or '').lower() for g in (a.get('Regions') or [])))]
    lines = [_head('alerts', len(m), len(al), len(m), f'{len(act)} of {len(al)} are active now.')]
    for a in m:
        lines.append(f"- {'HIGH IMPORTANCE · ' if a.get('HighImportance') else ''}{_clean(a.get('Message'), 200)}")
        lines.append(f"  counties: {', '.join(a.get('Regions') or []) or 'not reported'} · {_t(a.get('StartTime'))} to "
                     f"{_t(a.get('EndTime'))} · {_ago(a.get('LastUpdated'))}")
        if a.get('Notes'): lines.append(f"  {_clean(a.get('Notes'))}")
    return '\n'.join(lines)


@_errors_as_text
def get_message_signs(road: Optional[str] = None, near_lat: Optional[float] = None, near_lon: Optional[float] = None,
                      radius_mi: float = 10.0, max_results: int = 10) -> str:
    """What Arizona's dynamic message signs (DMS) show right now, from AZ511 (ADOT).

    Filter by road ('I-17', 'L-202') and/or a point and a radius in miles. Each sign: name and location, road,
    direction, every message page it is rotating, and when it was last updated. Blank signs are left out.
    Read-only: these tools cannot change a sign."""
    sg = _fetch('messagesigns')
    lit = [s for s in sg if _pages(s)]
    m = [s for s in lit if _road_match(road, s.get('Roadway'), s.get('Name'))]
    m = _place(m, lambda s: s.get('Latitude'), lambda s: s.get('Longitude'), near_lat, near_lon, radius_mi)
    lines = [_head('message signs', len(m), len(sg), min(len(m), max_results), f'{len(sg) - len(lit)} signs are blank.')]
    for d, s in m[:max_results]:
        pages = ' || '.join(re.sub(r'[ \t]{2,}', ' ', re.sub(r'\s*[\r\n]+\s*', ' / ', p.strip()))
                            for p in _pages(s))
        lines.append(f"- {s.get('Name')} ({s.get('Roadway')}, {_dir(s.get('DirectionOfTravel'))}){_where(d)}: "
                     f"\"{pages}\" · {_ago(s.get('LastUpdated'))}")
    return '\n'.join(lines)


@_errors_as_text
def get_road_weather(near_lat: float, near_lon: float, radius_mi: float = 25.0, max_results: int = 5) -> str:
    """Road weather stations near a point, from AZ511 (ADOT): air and pavement temperature (°F), wind, humidity
    and the station's level of grip.

    Use it before advising on ice, heat or high wind (for example I-40 at Flagstaff, I-10 dust corridors).
    AZ511 does not state the wind-speed unit; this tool reports the number without one. Read-only."""
    ws = _fetch('weatherstations')
    m = _place(ws, lambda w: w.get('Latitude'), lambda w: w.get('Longitude'), near_lat, near_lon, radius_mi)
    lines = [_head('road weather stations', len(m), len(ws), min(len(m), max_results))]
    for d, w in m[:max_results]:
        lines.append(f"- station {w.get('Id')}{_where(d)}: air {w.get('AirTemperature') or '?'} °F · pavement "
                     f"{w.get('SurfaceTemperature') or '?'} °F · wind {w.get('WindSpeed') or '?'} from {w.get('WindDirection') or '?'}"
                     f" (gusts {w.get('MaxWindSpeed') or '?'}; unit not stated) · humidity {w.get('RelativeHumidity') or '?'}%"
                     f" · grip {w.get('LevelOfGrip') or 'not reported'} · {_ago(w.get('LastUpdated'))}")
    return '\n'.join(lines)


@_errors_as_text
def get_rest_areas(road: Optional[str] = None, near_lat: Optional[float] = None, near_lon: Optional[float] = None,
                   radius_mi: float = 50.0, max_results: int = 8) -> str:
    """Arizona rest areas from AZ511 (ADOT): open or closed, milepost, amenities, and truck parking (spaces
    available of total, where ADOT reports it).

    Filter by road ('I-10', 'I-40') and/or a point and a radius in miles. Read-only."""
    ra = _fetch('restareas')
    m = [r for r in ra if _road_match(road, r.get('Location'), r.get('Name'))]
    m = _place(m, lambda r: r.get('Latitude'), lambda r: r.get('Longitude'), near_lat, near_lon, radius_mi)
    lines = [_head('rest areas', len(m), len(ra), min(len(m), max_results))]
    for d, r in m[:max_results]:
        trucks = _trucks(r)
        am = [k for k in ('Restroom', 'Ramada', 'VisitorCenter', 'VendingMachine') if (r.get(k) or '').lower() == 'yes']
        lines.append(f"- {r.get('Name')} · {r.get('Status') or 'status not reported'} · {r.get('Location')} near "
                     f"{r.get('City')}{_where(d)} · {trucks} · has: {', '.join(am) or 'not reported'}")
    return '\n'.join(lines)


@_errors_as_text
def get_cameras(road: Optional[str] = None, near_lat: Optional[float] = None, near_lon: Optional[float] = None,
                radius_mi: float = 5.0, max_results: int = 5) -> str:
    """Arizona traffic cameras from AZ511 (ADOT) near a point or on a road, with the link to each live image.

    Each view has its view_id, ADOT's label (road, NB/SB/EB/WB or NA, milepost, place) and the link to its live
    picture. This tool does not look at the pictures: pass a view_id to look_at_camera for that. Read-only."""
    cams = _fetch('cameras')
    m = [c for c in cams if _road_match(road, c.get('Roadway'), c.get('Location'))]
    m = _place(m, lambda c: c.get('Latitude'), lambda c: c.get('Longitude'), near_lat, near_lon, radius_mi)
    lines = [_head('cameras', len(m), len(cams), min(len(m), max_results))]
    for d, c in m[:max_results]:
        views = [v for v in (c.get('Views') or []) if (v.get('Status') or '').lower() == 'enabled']
        shown = '; '.join(f"view {v.get('Id')} \"{v.get('Description')}\": {v.get('Url')}" for v in views) or 'no enabled view'
        lines.append(f"- {c.get('Location')} ({c.get('Roadway')}){_where(d)}: {shown}")
    return '\n'.join(lines)


@_errors_as_text
def get_work_zones(road: Optional[str] = None, near_lat: Optional[float] = None, near_lon: Optional[float] = None,
                   radius_mi: float = 10.0, active_now: bool = True, max_results: int = 10) -> str:
    """Arizona work zones from ADOT's public WZDx feed (the national Work Zone Data Exchange format, v4.1):
    road, direction, cross streets, lane impact, which lanes are closed, workers present, and dates.

    Filter by road and/or a point and a radius in miles; active_now keeps work zones whose dates include now. The
    feed sends no status, so a work zone past its planned end date is counted and left out, not called finished:
    many are still listed years later. Many entries say the lane impact is 'unknown' and none has a verified position: report those as unknown and
    unverified, never as open lanes. Read-only."""
    fz = _fetch('wzdx'); F = fz.get('features', []); now = _now()

    def ts(s): return _iso(s).timestamp() if s else None
    def pts(f):
        g = f.get('geometry') or {}; c = g.get('coordinates') or []
        return c if g.get('type') in ('LineString', 'MultiPoint') else [c]

    keep, late = [], 0
    for f in F:
        p = f['properties']; cd = p.get('core_details', {})
        a, b = ts(p.get('start_date')) or 0, ts(p.get('end_date'))
        if active_now and now < a: continue
        if not _road_match(road, *(cd.get('road_names') or []), cd.get('description')): continue
        if near_lat is not None and near_lon is not None:
            ds = [_mi(near_lat, near_lon, la, lo) for lo, la, *_ in pts(f) if la is not None]
            if not ds or min(ds) > radius_mi: continue
            d = min(ds)
        else:
            d = None
        if active_now and b is not None and now > b:
            late += 1; continue                     # past its planned end; the feed sends no status
        keep.append((d, f))
    m = sorted(keep, key=lambda x: x[0]) if near_lat is not None and near_lon is not None else keep
    unk = sum(1 for _, f in m if f['properties'].get('vehicle_impact') in (None, 'unknown'))
    lines = [_head('work zones (WZDx ' + str(fz.get('feed_info', {}).get('version', '?')) + ')', len(m), len(F),
                   min(len(m), max_results), f'Lane impact unknown for {unk} of the {len(m)}. Positions in this feed are not verified.'
                   + (f' Not shown: {late} past the planned end date; the feed sends no status, so '
                      + ('it' if late == 1 else 'they') + ' may still be underway (active_now=False lists '
                      + ('it' if late == 1 else 'them') + ').' if late else ''))]
    for d, f in m[:max_results]:
        p = f['properties']; cd = p.get('core_details', {})
        lt = _lanes_text(p.get('lanes'))
        imp = p.get('vehicle_impact') or 'unknown'
        imp = 'lane impact unknown (not reported)' if imp == 'unknown' else imp.replace('-', ' ')
        wk = p.get('worker_presence') or {}
        dirn = cd.get('direction') if cd.get('direction') not in (None, '', 'unknown', 'undefined') else 'direction not reported'
        lines.append(f"- {', '.join(cd.get('road_names') or ['road not named'])} · {dirn} · "
                     f"{(p.get('beginning_cross_street') or '').strip() or '?'} to {(p.get('ending_cross_street') or '').strip() or '?'}"
                     f"{_where(d)} · {imp}" + (f' · {lt}' if lt else '')
                     + (f" · workers present: {wk.get('are_workers_present')}" if 'are_workers_present' in wk else ''))
        lines.append(f"  {_clean(cd.get('description'), 220)}")
        lines.append(f"  {_iso_t(p.get('start_date'))} to {_iso_t(p.get('end_date'))} · source {cd.get('data_source_id')}")
    return '\n'.join(lines)


# ------------------------------------------------------------------ a trip along one highway
def _event_dir(e, road=None):
    """(direction code, note): an event's direction of travel. AZ511 fills the direction field for few events; many
    give it only in the road name ('I-17 Northbound') or the description ('on I-10 Westbound')."""
    c = _dir_code(e.get('DirectionOfTravel'))
    if c: return c, ''
    m = re.search(r'\b(north|south|east|west)\s*bound\b', e.get('RoadwayName') or '', re.I)
    r = _route(road) or _route(e.get('RoadwayName'))
    if not m and r:
        m = re.search(re.escape(r) + r'\s+(north|south|east|west)\s*bound\b', _norm_road(e.get('Description')), re.I)
    return (_dir_code(m.group(1)), ' (from the road name or description)') if m else (None, '')


def _route(text):
    """The route in a road name or description: '202-LOOP' -> 'L-202', 'I-17 Northbound' -> 'I-17'; else None."""
    m = re.search(r'\b(I|US|SR|L)-\d{1,3}\b', _norm_road(text))
    return m.group(0) if m else None


def _mps(text):
    """Mileposts written in a description: '(MP 150)', 'MP 215', 'milepost 387' -> [150.0, 215.0, 387.0]."""
    return [float(x) for x in re.findall(r'\b(?:MP|mile\s*post)\s*(\d{1,3}(?:\.\d+)?)\b', text or '', re.I)]


_VIEW = re.compile(r'^\s*(\S+)\s+(NB|SB|EB|WB|NA)\s+(\d{1,3}(?:\.\d+)?)\s*@\s*(.*)$', re.I)


def _view(v):
    """ADOT's label of a camera view, 'I-10 WB 150.30 @E of 24th St' -> road, label, milepost, place; else None."""
    m = _VIEW.match((v or {}).get('Description') or '')
    if not m: return None
    return {'road': _norm_road(m.group(1)), 'label': m.group(2).upper(), 'mp': float(m.group(3)), 'place': m.group(4).strip()}


def _street(s):
    """A cross street reduced to compare: 'N 7th Ave' -> '7TH AVE', '5th Ave HOV' -> '5TH AVE', '5th. Ave.' -> '5TH AVE'."""
    s = re.sub(r'[^A-Z0-9 ]', ' ', (s or '').upper())
    s = re.sub(r'\b(HOV|RAMP|EXIT|ENTRANCE)\b', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'^[NSEW] ', '', s)


def _cross_street(desc):
    """The cross street an event is reported 'Near': 'Crash ... Near 5th Ave HOV (MP 144).' -> '5TH AVE'."""
    m = re.search(r'\bnear\s+(.+?)\s*(?:\(MP|\.\s*$|$)', desc or '', re.I)
    return _street(m.group(1)) if m else None


_UNIT = {'N': (0, 1), 'S': (0, -1), 'E': (1, 0), 'W': (-1, 0)}


def _mp_increase(pts):
    """From points (lat, lon, milepost) on one road, the compass way its mileposts increase here, as a unit vector
    (east, north); None if the points cannot tell. Mileposts usually grow north and east, but not on the loops:
    on Loop 202's Santan Freeway they grow westward."""
    if len(pts) < 2: return None
    a = min(pts, key=lambda p: p[2]); b = max(pts, key=lambda p: p[2])
    if b[2] - a[2] < 0.3: return None
    x, y = (b[1] - a[1]) * math.cos(math.radians(a[0])), b[0] - a[0]
    n = math.hypot(x, y)
    return (x / n, y / n) if n else None


_POINTS = ['north', 'north-northeast', 'northeast', 'east-northeast', 'east', 'east-southeast', 'southeast',
           'south-southeast', 'south', 'south-southwest', 'southwest', 'west-southwest', 'west', 'west-northwest',
           'northwest', 'north-northwest']


def _compass(g):
    """A unit vector (east, north) as one of 16 compass points: I-10 through Tucson runs south-southeast."""
    bearing = math.degrees(math.atan2(g[0], g[1])) % 360
    return _POINTS[int((bearing + 11.25) // 22.5) % 16]


_WORDS = {'N': 'northbound', 'S': 'southbound', 'E': 'eastbound', 'W': 'westbound', 'both': 'both directions'}
_OPP = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


def _dir_code(s):
    """'Northbound', 'North Bound', 'NB', 'N' -> 'N'; 'Both Directions' -> 'both'; not reported -> None."""
    s = (s or '').strip().lower()
    if not s or s in ('none', 'unknown', 'n/a', 'no data'): return None
    if re.search(r'\b(both|all)\b', s): return 'both'
    for w, c in (('north', 'N'), ('south', 'S'), ('east', 'E'), ('west', 'W')):
        if w in s: return c
    m = re.fullmatch(r'([nsew])b?', s)
    return m.group(1).upper() if m else None


def _signed_dir(road, a_lat, a_lon, b_lat, b_lon):
    """The direction on the signs. U.S. route numbering: odd-numbered routes are signed north and south, even-numbered
    ones east and west, however the road bends (I-10 from Phoenix to Tucson heads southeast, signed eastbound).
    Loops (L-101, L-202, L-303) and unnumbered roads: the trip's main heading."""
    dy = b_lat - a_lat
    dx = (b_lon - a_lon) * math.cos(math.radians((a_lat + b_lat) / 2))
    r = _norm_road(road)
    m = re.match(r'(I|US|SR)[- ]?(\d{1,3})', r)
    if m:
        if int(m.group(2)) % 2:
            return ('N' if dy > 0 else 'S'), f'{r} is odd-numbered, so it is signed north and south'
        return ('E' if dx > 0 else 'W'), f'{r} is even-numbered, so it is signed east and west'
    if abs(dy) >= abs(dx):
        return ('N' if dy > 0 else 'S'), "taken from the trip's main heading"
    return ('E' if dx > 0 else 'W'), "taken from the trip's main heading"


def _frame(a_lat, a_lon, b_lat, b_lon):
    """A straight line from the start A to the end B. For a point: (miles along A->B, miles off the line)."""
    c = math.cos(math.radians((a_lat + b_lat) / 2))
    bx, by = (b_lon - a_lon) * c * 69.17, (b_lat - a_lat) * 69.05
    L = math.hypot(bx, by) or 1e-9
    def f(lat, lon):
        x, y = (lon - a_lon) * c * 69.17, (lat - a_lat) * 69.05
        return (x * bx + y * by) / L, abs(x * by - y * bx) / L
    return L, f


@_errors_as_text
def get_trip_briefing(road: str, from_lat: float, from_lon: float, to_lat: float, to_lon: float,
                      max_items: int = 25) -> str:
    """A briefing for one trip along one Arizona highway, from AZ511 (ADOT): what a driver will meet, in the order
    they meet it. Use it for "I'm driving I-17 from Phoenix to Flagstaff; what's on the way?" For one place, use
    get_road_events.

    road is the highway ('I-17', 'I-10', 'US-60', 'SR-87', 'L-202'). from_lat, from_lon, to_lat and to_lon are the
    start and end of the trip, in decimal degrees; for a city, its center is close enough. The briefing gives the
    direction of travel as the signs show it, then, in order from the start: road events in that direction or in
    both (AZ511 often gives the direction only in the road name, 'I-17 Northbound'), message signs facing that
    direction (signs showing only travel times are summarized in one line), road weather stations within 5 mi of the road (ice possible when
    the pavement is at or below 32 °F), and rest areas on the driver's side with truck parking; full closures and ice come first, in a
    "Most important" line. Then events whose direction is not
    reported, which may be on the driver's side, and active alerts that name the road. Left out and counted:
    events in the other direction, events whose planned end has passed, and events not started yet. Distances
    are straight-line miles from the start; road miles are longer. Read-only. It reads six AZ511 feeds, so leave a
    minute before many other AZ511 calls."""
    now = _now()
    L, frame = _frame(from_lat, from_lon, to_lat, to_lon)
    D, why = _signed_dir(road, from_lat, from_lon, to_lat, to_lon)
    ev, sg, ws, ra, al, cams = [_fetch(n) for n in ('event', 'messagesigns', 'weatherstations', 'restareas', 'alerts', 'cameras')]

    def on_trip(lat, lon):
        """Miles from the start, or None when the point is not between the start and the end."""
        if lat is None or lon is None: return None
        a, off = frame(lat, lon)
        return max(a, 0.0) if -2 <= a <= L + 2 and off <= 30 else None

    road_pts, way, unknown, alerts, urgent, times = [], [], [], [], [], []
    n = dict(other=0, ended=0, later=0, signs_other=0, rest_other=0)
    side_unknown = False

    for e in ev:
        if not _road_match(road, e.get('RoadwayName')): continue
        mi = on_trip(e.get('Latitude'), e.get('Longitude'))
        if mi is None: continue
        road_pts.append((e['Latitude'], e['Longitude']))
        if e.get('PlannedEndDate') and e['PlannedEndDate'] < now: n['ended'] += 1; continue
        if e.get('StartDate') and e['StartDate'] > now: n['later'] += 1; continue
        c, src = _event_dir(e, road)
        if c == _OPP[D]: n['other'] += 1; continue
        lanes = e.get('LanesAffected')
        lanes = 'lanes not reported' if not lanes or lanes == 'No Data' else 'lanes: ' + lanes
        sub = e.get('EventSubType') or e.get('Subtype')
        sev = e.get('Severity') if e.get('Severity') not in (None, '', 'None') else None
        dtext = _WORDS[c] + src if c in (D, 'both') else ('direction not reported' if c is None else
                f"{_WORDS[c]}, which is not a direction of {_norm_road(road)}: a crossing road or a ramp?")
        txt = (f"EVENT {e.get('ID')} {e.get('EventType')}{' / ' + sub if sub else ''} · {e.get('RoadwayName')} · {dtext}"
               f" · {'ALL LANES CLOSED' if e.get('IsFullClosure') else 'not a full closure'} · {lanes}"
               f"{' · severity ' + sev if sev else ''}\n    {_clean(e.get('Description'), 200)}\n"
               f"    expected end {_t(e.get('PlannedEndDate'))} · {_ago(e.get('LastUpdated'))}")
        (way if c in (D, 'both') else unknown).append((mi, txt))
        if e.get('IsFullClosure') and c in (D, 'both'):
            urgent.append((mi, f"ALL LANES CLOSED at mi {mi:.0f}: {_clean(e.get('Description'), 90)}"))

    for s_ in sg:
        if not _road_match(road, s_.get('Roadway'), s_.get('Name')): continue
        mi = on_trip(s_.get('Latitude'), s_.get('Longitude'))
        if mi is None: continue
        road_pts.append((s_['Latitude'], s_['Longitude']))
        pages = _pages(s_)
        if not pages: continue
        c = _dir_code(s_.get('DirectionOfTravel'))
        if c not in (D, 'both', None): n['signs_other'] += 1; continue
        shown = ' || '.join(re.sub(r'[ \t]{2,}', ' ', re.sub(r'\s*[\r\n]+\s*', ' / ', p.strip())) for p in pages)
        txt = f"SIGN {s_.get('Name')}{'' if c else ' (facing not reported)'}: \"{shown}\" · {_ago(s_.get('LastUpdated'))}"
        if all(p.strip().upper().startswith('MINUTES TO') for p in pages):
            times.append((mi, txt))          # routine travel times: summarized, so warnings stand out
        else:
            way.append((mi, txt))

    for c_ in cams:
        if _road_match(road, c_.get('Roadway'), c_.get('Location')) and on_trip(c_.get('Latitude'), c_.get('Longitude')) is not None:
            road_pts.append((c_['Latitude'], c_['Longitude']))

    n_weather = 0
    for w in ws:
        la, lo = w.get('Latitude'), w.get('Longitude')
        if la is None or lo is None: continue
        a, off = frame(la, lo)
        if not (-2 <= a <= L + 2): continue
        near = min((_mi(la, lo, p, q) for p, q in road_pts), default=off)   # the road's own points trace its bends
        if near > 5: continue
        n_weather += 1
        pave, air = w.get('SurfaceTemperature'), w.get('AirTemperature')
        t = pave if pave not in (None, '') else air
        try: ice = float(t) <= 32
        except (TypeError, ValueError): ice = False
        if ice: urgent.append((max(a, 0.0), f"ice possible at mi {max(a, 0.0):.0f} (pavement at or below 32 °F)"))
        way.append((max(a, 0.0), f"WEATHER station {w.get('Id')}, {near:.0f} mi from the road: air {air if air not in (None, '') else '?'} °F · "
                    f"pavement {pave if pave not in (None, '') else 'not reported'} °F · grip {w.get('LevelOfGrip') or 'not reported'} · "
                    f"wind {w.get('WindSpeed') or '?'}, gusts {w.get('MaxWindSpeed') or '?'} (unit not stated)"
                    f"{' · ICE POSSIBLE: at or below 32 °F' if ice else ''} · {_ago(w.get('LastUpdated'))}"))

    for r in ra:
        if not _road_match(road, r.get('Location'), r.get('Name')): continue
        mi = on_trip(r.get('Latitude'), r.get('Longitude'))
        if mi is None: continue
        sides = {_dir_code(x) for x in re.findall(r'\b([NSEW]B)\b', r.get('Name') or '')}   # 'McGuireville Rest Area (SB)'
        if sides and D not in sides: n['rest_other'] += 1; continue
        side_unknown |= not sides
        way.append((mi, f"REST AREA {r.get('Name')} ({r.get('Location')}) · {r.get('Status') or 'status not reported'}"
                        f"{'' if sides else ' · side of the road not stated'} · {_trucks(r)}"))

    for a_ in al:
        if (a_.get('StartTime') or 0) <= now and (not a_.get('EndTime') or a_['EndTime'] >= now) \
                and _road_match(road, a_.get('Message'), a_.get('Notes')):
            alerts.append(f"- {'HIGH IMPORTANCE · ' if a_.get('HighImportance') else ''}{_clean(a_.get('Message'), 200)} · "
                          f"until {_t(a_.get('EndTime'))}")

    way.sort(key=lambda x: x[0]); unknown.sort(key=lambda x: x[0])
    lines = [f"Trip briefing: {_norm_road(road)} {_WORDS[D]}, from ({from_lat:.3f}, {from_lon:.3f}) to ({to_lat:.3f}, "
             f"{to_lon:.3f}), {L:.0f} mi in a straight line. AZ511 (ADOT), read {_t(now)}.",
             f"Direction: {_WORDS[D]}; {why}.",
             'Most important: ' + ('; '.join(t for _, t in sorted(urgent)) if urgent else
                                   'no full closure and no freezing pavement reported on your way') + '.',
             'On your way, in order (miles from the start in a straight line; road miles are longer):']
    lines += [f'- mi {mi:.0f}: {txt}' for mi, txt in way[:max_items]] or ['- nothing reported on your side of the road']
    if len(way) > max_items: lines.append(f'- ... and {len(way) - max_items} more; raise max_items to see them')
    if unknown:
        lines.append(f'Direction not reported ({len(unknown)}); these may be on your side:')
        lines += [f'- mi {mi:.0f}: {txt}' for mi, txt in unknown[:max_items]]
    lines.append('Active alerts that name this road:' if alerts else 'Active alerts that name this road: none.')
    lines += alerts
    lines.append(f"Left out: {n['other']} event(s) in the other direction ({_WORDS[_OPP[D]]}), {n['ended']} whose planned "
                 f"end has passed (ADOT keeps some listed for years), {n['later']} not started yet, {n['signs_other']} "
                 f"sign(s) facing the other way, and {n['rest_other']} rest area(s) on the other side of the road.")
    if times:
        (m0, t0), (m1, t1) = times[0], times[-1]
        lines.append(f"Travel-time signs on your way: {len(times)}, not listed above. First, at mi {m0:.0f}: {t0[5:]}"
                     + (f". Last, at mi {m1:.0f}: {t1[5:]}" if len(times) > 1 else ''))
    if not n_weather:
        lines.append('No road weather station within 5 mi of this road between the start and the end: weather unknown.')
    if side_unknown:
        lines.append('A rest area marked "side of the road not stated" may serve only the other direction.')
    return '\n'.join(lines)


# ------------------------------------------------------------------ cameras around an event
@_errors_as_text
def get_event_cameras(event_id: int, radius_mi: float = 3.0, per_side: int = 3) -> str:
    """The traffic cameras around one reported road event (a crash, a closure, roadwork), from AZ511 (ADOT), split
    into upstream (where the traffic comes from) and downstream (where it goes), each with the view_id to pass to
    look_at_camera. Use it to check a report; get the event_id from get_road_events or get_trip_briefing.

    Upstream and downstream follow the mileposts, and the tool works out which way they increase near the event
    from the cameras' own positions (they usually increase going north and east, but not on Phoenix's loops).
    Events give whole-number mileposts, so the cross street they are reported near ('Near 5th Ave') locates them
    better: a camera named for that street is marked, and one at it is put at the event. Each view's label (NB,
    SB, EB, WB, or NA when not stated) is ADOT's: it may name the side of the road or the view, so check the picture
    (guide signs face the traffic that reads them). Cameras on other roads within radius_mi are listed last. A queue upstream with
    traffic moving downstream points to a bottleneck between those cameras; no picture can confirm a crash or that
    it has cleared. Read-only."""
    ev = _fetch('event'); cams = _fetch('cameras'); now = _now()
    e = next((x for x in ev if str(x.get('ID')) == str(event_id)), None)
    if e is None:
        return f'Error: AZ511 lists no event {event_id} now; it may have been cleared. Call get_road_events for current events.'
    road = _route(e.get('RoadwayName')) or _route(e.get('Description'))
    D, src = _event_dir(e, road)
    emps = _mps(e.get('Description'))
    lo, hi = (min(emps), max(emps)) if emps else (None, None)
    tol = 0.5 if emps and all(m.is_integer() for m in emps) else 0.05    # 'MP 47' is rounded to the mile
    xs = _cross_street(e.get('Description'))                             # 'Near 5th Ave' locates it better
    ela, elo = e.get('Latitude'), e.get('Longitude')
    rows, pts = [], ([(ela, elo, lo)] if emps and ela is not None else [])
    for c in cams:
        if c.get('Latitude') is None: continue
        d = _mi(ela, elo, c['Latitude'], c['Longitude'])
        for v in c.get('Views') or []:
            if (v.get('Status') or '').lower() != 'enabled': continue
            lab = _view(v)
            mine = bool(road) and ((lab and lab['road'] == road) or _road_match(road, c.get('Roadway')))
            if mine and lab and d <= max(radius_mi, 6): pts.append((c['Latitude'], c['Longitude'], lab['mp']))
            if d <= radius_mi: rows.append((d, c, v, lab, mine))
    g = _mp_increase(pts)
    how = "from the cameras' own positions"
    if g is None and road and not road.startswith('L-'):
        g, how = ({'N': (0, 1), 'S': (0, 1), 'E': (1, 0), 'W': (1, 0)}.get(D), 'by the usual rule (north and east)')
    up_is_higher = None
    if D in _UNIT and g:
        dot = g[0] * _UNIT[D][0] + g[1] * _UNIT[D][1]
        up_is_higher = True if dot < -0.3 else False if dot > 0.3 else None
    ups, downs, at, unsure, others = [], [], [], [], []
    for d, c, v, lab, mine in sorted(rows, key=lambda r: r[0]):
        name = f"view {v.get('Id')} · {v.get('Description')}"
        tag = '' if not lab else (' (label not stated)' if lab['label'] == 'NA' else
              f" (label {lab['label']}, same as the event)" if D and lab['label'][0] == D else
              f" (label {lab['label']}: maybe the other side of the road, or a view the other way)")
        link = f" · {v.get('Url')}"
        place = _street(lab['place']) if lab else ''
        same_x = bool(xs) and len(xs) > 3 and (place == xs or re.search(r'\b' + re.escape(xs) + r'\b', place) is not None)
        if same_x: tag += f" (named for the event's cross street, {' '.join(w.lower() if w[0].isdigit() else w.capitalize() for w in xs.split())})"
        if not mine:
            others.append(f'- {d:.1f} mi away · {name}{link}'); continue
        if lab and lo is not None and up_is_higher is not None:
            if lo - tol <= lab['mp'] <= hi + tol or (same_x and place == xs):
                at.append(f"- at the event{' (within the rounding of its milepost)' if tol > 0.1 else ''} · {name}{tag}{link}"); continue
            dm = lab['mp'] - hi if lab['mp'] > hi else lo - lab['mp']
            higher = lab['mp'] > hi
            (ups if higher == up_is_higher else downs).append((dm, f"- {dm:.1f} mi {'upstream' if higher == up_is_higher else 'downstream'} by milepost · {name}{tag}{link}"))
        else:
            unsure.append(f'- {d:.1f} mi away, upstream or downstream not known · {name}{tag}{link}')
    sub = e.get('EventSubType') or e.get('Subtype')
    mins = (now - e['Reported']) / 60 if e.get('Reported') else None
    lines = [f"Cameras around event {event_id} (AZ511, ADOT), read {_t(now)}.",
             f"Event: {e.get('EventType')}{' / ' + sub if sub else ''} · {road or e.get('RoadwayName')} · "
             f"{(_WORDS.get(D) or 'direction not reported') + src} · "
             f"{'milepost ' + (f'{lo:g}' if lo == hi else f'{lo:g} to {hi:g}') if emps else 'milepost not stated'} · "
             f"reported {_t(e.get('Reported'))}" + (f' ({mins:.0f} min ago)' if mins is not None and mins >= 0 else ''),
             f"  {_clean(e.get('Description'), 200)}"]
    if up_is_higher is not None:
        lines.append(f"Mileposts on {road} here increase going {_compass(g)} ({how}). {_WORDS[D].capitalize()} traffic "
                     f"heads {'the other way' if up_is_higher else 'that way'}, so it comes from the "
                     f"{'higher' if up_is_higher else 'lower'} mileposts.")
    elif rows:
        lines.append('Upstream and downstream cannot be told here: ' + ('the direction is not reported.' if D not in _UNIT
                     else 'the event or the cameras give no milepost, or the road runs across its signed direction here.'))
    lines.append('Upstream (where the traffic comes from), nearest first:')
    lines += [t for _, t in sorted(ups)[:per_side]] or ['- none on this road within the radius']
    if at: lines.append('At the event:'); lines += at[:per_side]
    lines.append('Downstream (where the traffic goes), nearest first:')
    lines += [t for _, t in sorted(downs)[:per_side]] or ['- none on this road within the radius']
    if unsure: lines.append('On this road, position not known:'); lines += unsure[:per_side]
    if others: lines.append(f'On other roads within {radius_mi:g} mi (ramps and spillover):'); lines += others[:2]
    lines.append('Next: look_at_camera(view_id) for a picture. Read the time stamp on each picture.')
    return '\n'.join(lines)


_img_cache = {}


def _camera_image(view_id):
    """(JPEG bytes, fetch time) for one camera view: from the snapshot folder (cctv_<view_id>.jpg) or from
    az511.com, which serves the pictures without a key. Cached 30 s, to be polite to ADOT's server."""
    vid = int(view_id)
    snap = os.environ.get('AZ511_SNAPSHOT')
    if snap:
        return open(os.path.join(snap, f'cctv_{vid}.jpg'), 'rb').read(), _now()
    hit = _img_cache.get(vid)
    if hit and time.time() - hit[1] < 30:
        return hit
    req = urllib.request.Request(f'https://az511.com/map/Cctv/{vid}', headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if 'image' not in (r.headers.get('Content-Type') or ''):
            raise RuntimeError(f'camera view {vid} did not return a picture')
        data = r.read()
    _img_cache[vid] = (data, time.time())
    return _img_cache[vid]


@_errors_as_text
def look_at_camera(view_id: int) -> str:
    """The current picture from one Arizona traffic camera view (AZ511, ADOT), for a model that can see images. Get
    view_id from get_event_cameras or get_cameras. Over MCP the picture comes back with this text; called as plain
    Python, only the text and the picture's link do.

    Read the time stamp printed on the picture and compare it with the fetch time below: some camera clocks are an
    hour off, and a frozen camera keeps sending an old picture. A picture can show queues, stopped vehicles, blocked
    lanes, responders, weather and glare. It cannot show what is outside its view, or that a crash has cleared;
    operators may turn a camera during an incident, so the label may not name the view. Read-only."""
    vid = int(view_id)
    found = [(c, v) for c in _fetch('cameras') for v in (c.get('Views') or []) if str(v.get('Id')) == str(vid)]
    if not found:
        return f'Error: no camera view {vid} in AZ511. Get view ids from get_event_cameras or get_cameras.'
    c, v = found[0]
    data, t = _camera_image(vid)
    return (f"Camera view {vid}: \"{v.get('Description')}\" ({c.get('Location')}). Picture fetched {_t(t)} "
            f"({len(data) // 1024} KB JPEG): https://az511.com/map/Cctv/{vid}")


TOOLS = [get_road_events, get_alerts, get_message_signs, get_road_weather, get_rest_areas, get_cameras, get_work_zones,
         get_trip_briefing, get_event_cameras, look_at_camera]


# ------------------------------------------------------------------ command line
def snapshot(folder):
    """Save one raw response per endpoint (7 calls, under the 10-per-minute limit). The key is not saved."""
    os.makedirs(folder, exist_ok=True)
    meta = {'read_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'endpoints': {}}
    for name in ENDPOINTS:
        t0 = time.time()
        try:
            data = _fetch(name)
        except Exception as e:
            meta['endpoints'][name] = {'error': str(e)}; print(name, 'ERROR', e); continue
        raw = json.dumps(data, ensure_ascii=False)
        open(os.path.join(folder, name + '.json'), 'w', encoding='utf-8').write(raw)
        n = len(data['features']) if name == 'wzdx' else len(data)
        meta['endpoints'][name] = {'records': n, 'bytes': len(raw.encode('utf-8')), 'seconds': round(time.time() - t0, 2)}
        print(f'{name:16s} {n:6d} records {len(raw.encode()):>10,d} bytes')
    json.dump(meta, open(os.path.join(folder, '_meta.json'), 'w'), indent=1)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    if cmd == 'snapshot':
        snapshot(sys.argv[2])
    elif cmd == 'trip':
        print(get_trip_briefing('I-17', 33.4484, -112.0740, 35.1983, -111.6513))
    else:
        print(get_road_events(road='I-17', max_results=3)); print()
        print(get_message_signs(road='I-10', max_results=3)); print()
        print(get_rest_areas(road='I-10', max_results=3)); print()
        print(get_work_zones(road='I-40', max_results=3))
