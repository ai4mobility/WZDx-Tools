"""Work-zone tools for AI agents over any WZDx feed (Work Zone Data Exchange, the USDOT format).

AI for Mobility, Part II (AI agents). Five read-only tools; each docstring is the description the model reads.
wzdx_mcp_server.py serves them over MCP, so Claude Desktop or Claude Code can call them.

Feeds are found in USDOT's public WZDx feed registry (datahub.transportation.gov, dataset 69qe-yiui), so no feed
address or key is written in this code. 'FL' is FDOT's feed (hosted by One.network, WZDx 4.2); 'AZ' is ADOT's
AZ511 feed (WZDx 4.1, documented at az511.com/developers/doc, not in the registry).

What the tools do that the raw feed does not:
  * keep only what was asked for: a road, or a point and a radius in miles, and active work zones by default
    (Florida's feed is 106 MB, 94% of it detour geometry; the model never sees it)
  * speak US units: WZDx stores reduced speed limits in km/h; the tools give mph
  * give local time: Florida is Eastern time except the panhandle west of the Apalachicola River (Central;
    approximated here by longitude < -85.0); Arizona is MST all year (the Navajo Nation's DST is not handled)
  * say 'lane impact unknown' and 'position not verified' instead of letting a model read silence as 'open'
  * link each Florida work zone to its posted detour routes

Offline: WZDX_SNAPSHOT=<folder> reads <feed>.json or <feed>.json.gz and registry.json from that folder.

    python wzdx_tools.py demo FL
"""
import os, sys, json, math, re, time, gzip, datetime, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_URL = 'https://datahub.transportation.gov/resource/69qe-yiui.json?$limit=500'
EXTRA = {'az511': {'state': 'arizona', 'issuingorganization': 'Arizona DOT (AZ511)', 'feedname': 'az511',
                   'url': 'https://az511.com/api/wzdx', 'version': '4.1', 'needapikey': False, 'active': True}}
ALIAS = {'FL': 'fldot', 'FLORIDA': 'fldot', 'AZ': 'az511', 'ARIZONA': 'az511'}
CACHE_S = 300
UA = 'AI4Mobility course tools (USF CGN 6933)'
_cache = {}


# ------------------------------------------------------------------ plumbing the model never sees
def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json', 'Accept-Encoding': 'gzip'})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            b = r.read()
    except urllib.error.HTTPError as e:                    # never echo the URL: some carry a key
        raise RuntimeError(f'the feed answered HTTP {e.code}') from None
    return json.loads(gzip.decompress(b) if b[:2] == b'\x1f\x8b' else b)


def _registry():
    snap = os.environ.get('WZDX_SNAPSHOT')
    if snap:
        rows = json.load(open(os.path.join(snap, 'registry.json'), encoding='utf-8'))
    else:
        hit = _cache.get('_registry')
        rows = hit[1] if hit and time.time() - hit[0] < 86400 else _get(REGISTRY_URL)
        _cache['_registry'] = (time.time(), rows)
    out = {r['feedname']: r for r in rows if r.get('feedname')}
    out.update(EXTRA)
    return out


def _url(r):
    u = r.get('url')
    return u.get('url') if isinstance(u, dict) else u


def _feed_name(feed):
    f = (feed or '').strip()
    return ALIAS.get(f.upper(), f.lower())


def _load(feed):
    """A feed as {'info', 'wz': [work-zone features], 'detours': {parent id: [detour properties]}}, cached 5 min.
    Detour geometry is dropped after parsing: it is most of Florida's feed and no tool returns it."""
    name = _feed_name(feed)
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < CACHE_S: return hit[1]
    snap = os.environ.get('WZDX_SNAPSHOT')
    if snap:
        p = os.path.join(snap, name + '.json')
        if not (os.path.exists(p) or os.path.exists(p + '.gz')):
            raise RuntimeError(f"no feed named '{feed}' in this snapshot. Call list_feeds to see the published feeds.")
        d = json.load(gzip.open(p + '.gz', 'rt', encoding='utf-8') if os.path.exists(p + '.gz') else open(p, encoding='utf-8'))
    else:
        reg = _registry()
        if name not in reg:
            raise RuntimeError(f"no feed named '{feed}'. Call list_feeds to see the published feeds.")
        r = reg[name]
        if str(r.get('needapikey')).lower() == 'true':
            raise RuntimeError(f"the {r.get('issuingorganization')} feed needs its own API key; this server only reads open feeds.")
        d = _get(_url(r))
    wz, det = [], {}
    for f in d.get('features', []):
        p = f.get('properties', {}); et = p.get('core_details', {}).get('event_type')
        if et == 'detour':
            for par in (p['core_details'].get('relationship') or {}).get('parents', []):
                det.setdefault(str(par), []).append(p)
        elif et == 'work-zone':
            wz.append(f)
    out = {'name': name, 'info': d.get('feed_info', {}), 'wz': wz, 'detours': det, 'n_features': len(d.get('features', []))}
    _cache[name] = (time.time(), out)
    return out


def _errors_as_text(fn):
    import functools
    @functools.wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:
            return f'Error: {e}'
    return wrapper


# ------------------------------------------------------------------ helpers: time, place, roads, units
def _now():
    t = os.environ.get('WZDX_NOW')
    return datetime.datetime.fromtimestamp(float(t), datetime.timezone.utc) if t else datetime.datetime.now(datetime.timezone.utc)


def _ts(s):
    """ISO 8601 -> datetime. Python 3.10 accepts only 3 or 6 fractional digits; Arizona's feed sends 5."""
    if not s: return None
    s = re.sub(r'\.(\d+)', lambda m: '.' + (m.group(1) + '000000')[:6], s.replace('Z', '+00:00'))
    return datetime.datetime.fromisoformat(s)


def _tz(feed, lon):
    if feed == 'az511': return ZoneInfo('America/Phoenix'), 'MST'
    if feed == 'fldot':
        z = ZoneInfo('America/Chicago') if lon is not None and lon < -85.0 else ZoneInfo('America/New_York')
        return z, None
    return datetime.timezone.utc, 'UTC'


def _local(s, feed, lon):
    d = _ts(s)
    if not d: return 'not reported'
    z, label = _tz(feed, lon); d = d.astimezone(z)
    yr = f' {d.year}' if d.year != _now().astimezone(z).year else ''
    return f"{d:%a %b} {d.day}{yr} {d:%H:%M} {label or d.tzname()}"


def _mi(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def _pts(f):
    g = f.get('geometry') or {}; c = g.get('coordinates') or []
    return c if g.get('type') in ('LineString', 'MultiPoint') else [c]


def _dist(f, lat, lon):
    ds = [_mi(lat, lon, la, lo) for lo, la, *_ in _pts(f) if la is not None]
    return min(ds) if ds else None


def _norm_road(s):
    """'I 75' / 'Interstate 75' -> 'I-75'; 'FL 434' / 'SR 434' / 'State Road 434' -> 'SR-434'; 'Loop 101' -> 'L-101'."""
    s = ' ' + (s or '').upper().replace('’', "'") + ' '
    s = re.sub(r'\bINTERSTATE\s*', 'I-', s)
    s = re.sub(r'\bSTATE\s+ROAD\s*', 'SR ', s)
    s = re.sub(r'\bFL\s*-?\s*(\d{1,3})\b', r'SR-\1', s)
    s = re.sub(r'\b(\d{2,3})\s*-?\s*LOOP\b', r'L-\1', s)
    s = re.sub(r'\bLOOP\s*-?\s*(\d{2,3})\b', r'L-\1', s)
    s = re.sub(r'\b(I|US|SR|CR|L)\s*-?\s*(\d{1,3}[A-Z]?)\b', r'\1-\2', s)
    return re.sub(r'\s+', ' ', s).strip()


def _road_match(query, *fields):
    if not query: return True
    q = _norm_road(query)
    text = ' ' + ' | '.join(_norm_road(f) for f in fields if f) + ' '
    if re.match(r'^(I|US|SR|CR|L)-\d', q):
        return re.search(r'(?<![A-Z0-9-])' + re.escape(q) + r'(?![0-9A-Z])', text) is not None
    return q in text                                   # a street name: 'FOWLER', 'BUSCH BOULEVARD'


def _lanes_text(lanes):
    """WZDx numbers lanes from the left (order 1 = left-most) and lists shoulders as lanes. A driver needs 'right
    lane of 3 closed', not 'lane 4 of 5', so count travel lanes only and name the side."""
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
        first, last = travel[0].get('order') or 0, travel[-1].get('order') or 0
        for l in L:
            if 'shoulder' in (l.get('type') or '') and l.get('status') == 'closed':
                out.append(('left' if (l.get('order') or 0) < first else 'right') + ' shoulder closed')
    return ', '.join(out)


def _mph(kph):
    return round(kph / 1.609344) if kph is not None else None


def _status(p, now):
    s = p.get('event_status')                           # WZDx 4.2; older feeds: from the dates
    if s: return s
    a, b = _ts(p.get('start_date')), _ts(p.get('end_date'))
    if a and now < a: return 'pending'
    if b and now > b: return 'completed'
    return 'active'


def _orgs(info):
    return {s.get('data_source_id'): s.get('organization_name') for s in info.get('data_sources', [])}


def _describe(f, feed, org, detours, d=None):
    p = f['properties']; cd = p.get('core_details', {})
    lon = (_pts(f)[0][0] if _pts(f) else None)
    names = [', '.join(dict.fromkeys(x.strip() for x in re.split(r'[,;]', n) if x.strip()))   # 'A,A' -> 'A'
             for n in (cd.get('road_names') or [])]
    names = list(dict.fromkeys(n for n in names if n))
    names = [a for a in names if not any(a != b and a.startswith(b + ',') for b in names)]   # 'A' and 'A, Tampa'
    roads = ', '.join(names) or 'road not named'
    dirn = cd.get('direction') if cd.get('direction') not in (None, '', 'unknown') else 'direction not reported'
    imp = p.get('vehicle_impact') or 'unknown'
    imp = 'lane impact unknown (not reported)' if imp == 'unknown' else imp.replace('-', ' ')
    bits = [f"- {roads} · {dirn}" + ('' if d is None else f' · {d:.1f} mi away'), imp]
    lt = _lanes_text(p.get('lanes'))
    if lt: bits.append(lt)
    if p.get('reduced_speed_limit_kph'): bits.append(f"reduced limit {_mph(p['reduced_speed_limit_kph'])} mph")
    wk = p.get('worker_presence') or {}
    if 'are_workers_present' in wk: bits.append('workers present' if wk['are_workers_present'] else 'no workers reported')
    lines = [' · '.join(bits)]
    desc = re.sub(r'\s+', ' ', cd.get('description') or cd.get('name') or '').strip()
    if desc: lines.append('  ' + (desc if len(desc) <= 200 else desc[:199] + '…'))
    src = org.get(cd.get('data_source_id'), cd.get('data_source_id'))
    ver = 'position not verified' if not p.get('is_start_position_verified') else 'position verified'
    dv = 'dates verified' if p.get('is_start_date_verified') else 'dates not verified'
    lines.append(f"  {_local(p.get('start_date'), feed, lon)} to {_local(p.get('end_date'), feed, lon)} · "
                 f"reported by {src} · {ver}, {dv} · id {f.get('id', '?')}")
    nd = len(detours.get(str(f.get('id')), []))
    if nd: lines.append(f'  {nd} posted detour route(s): call get_detours with this id')
    return lines


# ------------------------------------------------------------------ the five tools
@_errors_as_text
def list_feeds(state: Optional[str] = None) -> str:
    """Published WZDx work-zone feeds from USDOT's feed registry, with the state, the agency, the WZDx version
    and whether a key is needed. state is a full name ('florida', 'arizona') or empty for all. Use the feed name
    in the other tools; 'FL' and 'AZ' are shortcuts. Read-only."""
    reg = _registry()
    rows = [(k, r) for k, r in reg.items() if not state or (r.get('state') or '').lower() == state.lower()]
    lines = [f'{len(rows)} feed(s) in the USDOT WZDx registry' + (f' for {state}' if state else '') + ':']
    for k, r in sorted(rows, key=lambda x: (x[1].get('state') or '', x[0])):
        key = 'key needed' if str(r.get('needapikey')).lower() == 'true' else 'open'
        act = '' if str(r.get('active')).lower() == 'true' else ' · marked inactive'
        lines.append(f"- {k}: {r.get('issuingorganization')} ({r.get('state')}) · WZDx {r.get('version')} · {key}{act}")
    return '\n'.join(lines)


@_errors_as_text
def get_work_zones(feed: str, road: Optional[str] = None, near_lat: Optional[float] = None,
                   near_lon: Optional[float] = None, radius_mi: float = 5.0, status: str = 'active',
                   max_results: int = 10) -> str:
    """Work zones from a WZDx feed ('FL', 'AZ' or a name from list_feeds), filtered by road ('I-75', 'SR 434',
    'Fowler Avenue') and/or a point and a radius in miles. status: 'active' (default), 'pending', 'completed' or
    'all'. Each work zone: road, direction, distance, lane impact, closed lanes, reduced speed limit in mph,
    workers, the reporting organization, local start and end times, and whether its position and dates were
    verified. Most entries say lane impact unknown: report that as unknown, never as open lanes. Read-only."""
    F = _load(feed); now = _now(); org = _orgs(F['info'])
    if status not in ('active', 'pending', 'completed', 'all'):
        return "Error: status must be 'active', 'pending', 'completed' or 'all'."
    keep = []
    for f in F['wz']:
        p = f['properties']; cd = p.get('core_details', {})
        if status != 'all' and _status(p, now) != status: continue
        if not _road_match(road, *(cd.get('road_names') or []), cd.get('name'), cd.get('description')): continue
        d = None
        if near_lat is not None and near_lon is not None:
            d = _dist(f, near_lat, near_lon)
            if d is None or d > radius_mi: continue
        keep.append((d, f))
    keep.sort(key=lambda x: (x[0] if x[0] is not None else 0, x[1]['properties'].get('start_date') or ''))
    unk = sum(1 for _, f in keep if (f['properties'].get('vehicle_impact') or 'unknown') == 'unknown')
    head = (f"{len(keep)} {status if status != 'all' else ''} work zone(s) match in the {F['name']} feed "
            f"(WZDx {F['info'].get('version', '?')}, updated {_local(F['info'].get('update_date'), F['name'], -82.0)}); "
            f"showing {min(len(keep), max_results)}. Lane impact unknown for {unk} of {len(keep)}.")
    lines = [re.sub(r'\s+', ' ', head)]
    for d, f in keep[:max_results]:
        lines += _describe(f, F['name'], org, F['detours'], d)
    return '\n'.join(lines)


@_errors_as_text
def check_location(feed: str, lat: float, lon: float, radius_mi: float = 0.5) -> str:
    """Is this point in or near an active work zone? For a dashcam or vehicle agent: give the vehicle's GPS
    position. Returns the active work zones within radius_mi (default 0.5 mi), nearest first, or says that none
    is reported. 'None reported' does not mean none exists: feeds miss work zones, and positions are often
    estimated. Read-only."""
    F = _load(feed); now = _now(); org = _orgs(F['info'])
    near = []
    for f in F['wz']:
        if _status(f['properties'], now) != 'active': continue
        d = _dist(f, lat, lon)
        if d is not None and d <= radius_mi: near.append((d, f))
    near.sort(key=lambda x: x[0])
    if not near:
        return (f'No active work zone is reported within {radius_mi} mi of ({lat:.5f}, {lon:.5f}) in the {F["name"]} feed. '
                'That is not proof there is none: if the camera sees cones, barrels or workers, trust the camera.')
    lines = [f'{len(near)} active work zone(s) reported within {radius_mi} mi of ({lat:.5f}, {lon:.5f}):']
    for d, f in near[:5]:
        lines += _describe(f, F['name'], org, F['detours'], d)
    return '\n'.join(lines)


@_errors_as_text
def get_detours(feed: str, work_zone_id: str) -> str:
    """The detour routes posted for one work zone (Florida's feed links them), by the work zone's id as shown by
    get_work_zones or check_location: each detour's name, direction and dates. Read-only."""
    F = _load(feed); ds = F['detours'].get(str(work_zone_id), [])
    if not ds:
        return f'No detour route is linked to work zone {work_zone_id} in the {F["name"]} feed.'
    lines = [f'{len(ds)} detour route(s) for work zone {work_zone_id}:']
    for p in ds[:10]:
        cd = p.get('core_details', {})
        lines.append(f"- {cd.get('name') or cd.get('description') or 'unnamed'} · {cd.get('direction') or 'direction not reported'}"
                     f" · {_local(p.get('start_date'), F['name'], None)} to {_local(p.get('end_date'), F['name'], None)}")
    return '\n'.join(lines)


@_errors_as_text
def feed_quality(feed: str) -> str:
    """How complete a WZDx feed is right now: counts by status, the share of work zones with unknown lane impact,
    verified positions and dates, missing road names, workers and reduced speed reported, the reporting
    organizations, and when it was updated. Use it before trusting a feed for a study or a product. Read-only."""
    F = _load(feed); now = _now(); P = [f['properties'] for f in F['wz']]; n = len(P) or 1
    from collections import Counter
    st = Counter(_status(p, now) for p in P)
    org = _orgs(F['info']); src = Counter(org.get(p['core_details'].get('data_source_id'), p['core_details'].get('data_source_id')) for p in P)
    pct = lambda k: f'{k:,} ({100 * k / n:.0f}%)'
    lines = [f"{F['name']}: WZDx {F['info'].get('version', '?')}, published by {F['info'].get('publisher', '?')}, "
             f"updated {_local(F['info'].get('update_date'), F['name'], -82.0)}.",
             f"- {len(P):,} work zones ({', '.join(f'{k} {v:,}' for k, v in st.most_common())}) and "
             f"{sum(len(v) for v in F['detours'].values()):,} detour routes; {F['n_features']:,} features in all.",
             f"- lane impact unknown: {pct(sum(1 for p in P if (p.get('vehicle_impact') or 'unknown') == 'unknown'))}",
             f"- start position verified: {pct(sum(1 for p in P if p.get('is_start_position_verified')))}; "
             f"start date verified: {pct(sum(1 for p in P if p.get('is_start_date_verified')))}",
             f"- no road name: {pct(sum(1 for p in P if not p['core_details'].get('road_names')))}",
             f"- lane-by-lane detail: {pct(sum(1 for p in P if p.get('lanes')))}; workers reported: "
             f"{pct(sum(1 for p in P if p.get('worker_presence')))}; reduced speed limit: {pct(sum(1 for p in P if p.get('reduced_speed_limit_kph')))}",
             f"- top reporting organizations: {', '.join(f'{k} {v:,}' for k, v in src.most_common(5))}"]
    return '\n'.join(lines)


TOOLS = [list_feeds, get_work_zones, check_location, get_detours, feed_quality]


if __name__ == '__main__':
    feed = sys.argv[2] if len(sys.argv) > 2 else 'FL'
    print(feed_quality(feed)); print()
    print(get_work_zones(feed, near_lat=28.0587, near_lon=-82.4139, radius_mi=3, max_results=4)); print()
    print(check_location(feed, 28.0336, -82.4382))
