"""Template: one work-zone tool written the way a transportation engineer would write it, and the plain version it
is measured against. Copy this folder to contrib/<your-github-username>/ and replace the example with your own
tools (at least two). Keep the shape:

  * each tool is a function with type hints, '-> str', and a docstring: the description the model reads
  * TOOLS lists the tools the model may call; READ_ONLY names the ones that only read (all of them, for WZDx)
  * a *_plain function is the baseline: the same question answered without your knowledge. It is not in TOOLS, so
    the model never sees it; test_plain_vs_... uses it to show what your knowledge changes
  * the toolkit (wzdx_tools.py, imported as T) does the plumbing: loading feeds, local time, distances, lanes
  * PLAIN_DESCRIPTIONS and RAW_RESULTS (at the end) are for the ablation: the same tools, with the transportation
    knowledge taken out of what the model reads

The example: "What work is on this street?" The toolkit's get_work_zones(road=...) matches street names as plain
text. For 'Busch Blvd' it finds only the record whose name field happens to say 'E Busch Blvd', and misses the
record that says 'East Busch Boulevard': the one with the lane closure. work_zones_on_street adds what an engineer
knows about street names and about how a work is reported. KNOWLEDGE.md lists each rule with its source and its
test.
"""
import os, sys, re, json
from typing import Optional
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
import wzdx_tools as T

# Rule 1. USPS Publication 28: standard street suffix abbreviations (Appendix C1) and directionals.
SUFFIX = {'AVENUE': 'AVE', 'AV': 'AVE', 'BOULEVARD': 'BLVD', 'STREET': 'ST', 'ROAD': 'RD', 'DRIVE': 'DR',
          'LANE': 'LN', 'COURT': 'CT', 'CIRCLE': 'CIR', 'PLACE': 'PL', 'PARKWAY': 'PKWY', 'HIGHWAY': 'HWY',
          'TERRACE': 'TER', 'TRAIL': 'TRL', 'EXPRESSWAY': 'EXPY', 'CAUSEWAY': 'CSWY', 'PLAZA': 'PLZ'}
ABBREVIATED = set(SUFFIX.values()) | {'WAY', 'LOOP', 'RUN', 'PATH', 'PASS', 'ROW', 'WALK'}
DIRECTION = {'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W', 'NORTHEAST': 'NE', 'NORTHWEST': 'NW',
             'SOUTHEAST': 'SE', 'SOUTHWEST': 'SW'}
# Rule 2. A road-name field can end in ', City, State' and can hold several streets separated by commas.
CITY_STATE = re.compile(r'(^|,)\s*[A-Za-z .\'-]+,\s*(Florida|FL|Arizona|AZ)\s*$', re.I)
ROUTE = re.compile(r'^\s*(I|US|SR|CR|FL|State Road|Interstate|Loop|L)[\s-]*\d', re.I)


def _street_parts(name):
    """'East Busch Boulevard, Tampa, Florida' -> [('E', 'BUSCH', 'BLVD')]; 'North Orleans Avenue,West Hamilton
    Avenue' -> two streets; 'Tampa, Florida' -> [] (a city is not a street)."""
    out = []
    for s in re.split(r'[,;]', CITY_STATE.sub('', name or '')):
        w = re.sub(r'^\s*ON\s+', '', s.upper().replace('.', '')).split()      # 'on Pompano Dr'
        if not w:
            continue
        d = DIRECTION.get(w[0], w[0]) if w[0] in DIRECTION or w[0] in DIRECTION.values() else ''
        w = w[1:] if d and len(w) > 1 else w
        if not d and len(w) > 1 and (w[0] in DIRECTION or w[0] in DIRECTION.values()):
            d = DIRECTION.get(w[0], w[0])
        suf = SUFFIX.get(w[-1], w[-1]) if len(w) > 1 and (w[-1] in SUFFIX or w[-1] in ABBREVIATED) else ''
        core = ' '.join(w[:-1] if suf else w)
        out.append((d, core, suf))
    return out


def _matches(query, name):
    """Same street? The core must agree; a direction or a suffix left out of the query matches any."""
    q = _street_parts(query)
    if not q:
        return False
    qd, qc, qs = q[0]
    return any(c == qc and (not qd or d == qd) and (not qs or not s or s == qs) for d, c, s in _street_parts(name))


def _work_id(f):
    """One work (a permit or a project) is reported as several records: 'work/segment/...', and '-R' for the
    reverse direction. Records that share the first part of the id are one work."""
    return str(f.get('id', '')).split('/')[0].removesuffix('-R')


def _pretty(d, c, s):
    word = lambda x: x.lower() if x[:1].isdigit() else x.capitalize()          # '30TH' -> '30th', 'BUSCH' -> 'Busch'
    return ' '.join(x for x in (d, ' '.join(map(word, c.split())), s.capitalize()) if x)


def _find(feed, street, near_lat, near_lon, radius_mi):
    """The search, shared by the tool and its raw version: active records on the street within the radius, grouped
    by work, and the count of active records nearby that have no street name."""
    F = T._load(feed); now = T._now()
    works, unnamed = {}, 0
    for f in F['wz']:
        p = f['properties']; cd = p.get('core_details', {})
        if T._status(p, now) != 'active':
            continue
        d = T._dist(f, near_lat, near_lon)
        if d is None or d > radius_mi:
            continue
        names = cd.get('road_names') or []
        if not names:
            unnamed += 1
            continue
        if any(_matches(street, n) for n in names):
            works.setdefault(_work_id(f), []).append((d, f))
    return F, works, unnamed


@T._errors_as_text
def work_zones_on_street(feed: str, street: str, near_lat: float, near_lon: float, radius_mi: float = 5.0) -> str:
    """Active work on one street near a place, counted as works rather than records. feed: 'FL', 'AZ' or a name
    from list_feeds. street: a street name as people say it ('Busch Blvd', 'N 30th St', 'Fowler Avenue'); suffixes
    and directions may be spelled out or abbreviated, and a name without N/S/E/W matches every direction prefix.
    near_lat, near_lon and radius_mi (default 5 mi) give the place, because street names repeat across a state
    (Florida's feed has a 109th Avenue in Tampa and another 200 mi away). One work (a permit or a project) is often reported as several records,
    one per segment and direction: the result lists each work with its records' directions, lane impact, closed
    lanes, end time in local time and reporting organization. 'Lane impact not reported' means the feed does not
    say; it does not mean the lanes are open. The result also says how many active records near the place have no
    street name, which a search by name cannot find. For route numbers (I-75, SR 580, US 41) use get_work_zones.
    Read-only."""
    if ROUTE.match(street or ''):
        return (f"'{street}' is a route number, not a street name: call get_work_zones with road='{street}' and the "
                f"same point and radius.")
    if not _street_parts(street):
        return f"Error: '{street}' is not a street name. Give one such as 'Busch Blvd' or 'N 30th St'."
    F, works, unnamed = _find(feed, street, near_lat, near_lon, radius_mi)
    org = T._orgs(F['info'])
    n_rec = sum(len(v) for v in works.values())
    unk = sum(1 for v in works.values() for _, f in v if (f['properties'].get('vehicle_impact') or 'unknown') == 'unknown')
    head = (f"{street} within {radius_mi:g} mi of ({near_lat:.4f}, {near_lon:.4f}), {F['name']} feed updated "
            f"{T._local(F['info'].get('update_date'), F['name'], near_lon)}: {len(works)} active work(s) on the street, "
            f"from {n_rec} record(s). Lane impact not reported for {unk} of {n_rec} records.")
    lines = [head]
    for wid, recs in sorted(works.items(), key=lambda kv: min(d for d, _ in kv[1])):
        f0 = recs[0][1]; cd0 = f0['properties']['core_details']
        names = [_pretty(*s) for n in cd0.get('road_names', []) for s in _street_parts(n) if _matches(street, _pretty(*s))]
        src = org.get(cd0.get('data_source_id'), cd0.get('data_source_id'))
        lines.append(f"- work {wid} · {names[0] if names else street} · {min(d for d, _ in recs):.1f} mi away · "
                     f"reported by {src} · {len(recs)} record(s)")
        for d, f in sorted(recs, key=lambda x: str(x[1].get('id'))):
            p = f['properties']; cd = p['core_details']
            dirn = cd.get('direction') if cd.get('direction') not in (None, '', 'unknown', 'undefined') else 'direction not reported'
            imp = p.get('vehicle_impact') or 'unknown'
            imp = 'lane impact not reported' if imp == 'unknown' else imp.replace('-', ' ')
            lanes = T._lanes_text(p.get('lanes'))
            lon = T._pts(f)[0][0] if T._pts(f) else near_lon
            lines.append(f"    {dirn}: {imp}{', ' + lanes if lanes else ''} · until "
                         f"{T._local(p.get('end_date'), F['name'], lon)}")
        desc = re.sub(r'\s+', ' ', cd0.get('description') or '').strip()
        if desc:
            lines.append('    ' + (desc if len(desc) <= 160 else desc[:159] + '…'))
    lines.append(f"Not findable by name: {unnamed} active record(s) within {radius_mi:g} mi have no street name. "
                 f"To see them, call get_work_zones with near_lat, near_lon and radius_mi.")
    return '\n'.join(lines)


def work_zones_on_street_plain(feed: str, street: str) -> str:
    """The baseline: every work-zone record whose road name contains the text, as the feed gives it."""
    F = T._load(feed)
    hits = [f for f in F['wz'] if any(street.lower() in n.lower() for n in f['properties']['core_details'].get('road_names') or [])]
    lines = [f'{len(hits)} work zones found.']
    for f in hits:
        p = f['properties']
        lines.append(f"{f['id']}: {p['core_details'].get('road_names')}, vehicle_impact={p.get('vehicle_impact')}, "
                     f"{p.get('start_date')} to {p.get('end_date')}")
    return '\n'.join(lines)


TOOLS = [work_zones_on_street]
READ_ONLY = {'work_zones_on_street'}

# For the ablation's plain setup (contrib/ablation.py): your tools with the transportation knowledge taken out of
# what the model reads. The search stays the same; only the words change.
#   PLAIN_DESCRIPTIONS: each tool's description as any programmer would write it from the function signature alone
#     (what it returns, its inputs, read-only), without what only a transportation engineer would add.
#   RAW_RESULTS: for each tool, a function with the same inputs that returns the same data raw (here, the records as
#     the feed gives them, in JSON), without the wording you designed (DESIGN.md, section 4).
PLAIN_DESCRIPTIONS = {
    'work_zones_on_street': 'Active work zones on a street. feed: feed name. street: street name. near_lat, near_lon: '
                            'a point. radius_mi: search radius in miles. Read-only.',
}


@T._errors_as_text
def work_zones_on_street_raw(feed: str, street: str, near_lat: float, near_lon: float, radius_mi: float = 5.0) -> str:
    """The same search as work_zones_on_street, returned raw: the records as the feed gives them."""
    F, works, unnamed = _find(feed, street, near_lat, near_lon, radius_mi) if _street_parts(street) else (T._load(feed), {}, 0)
    records = [{'id': f.get('id'), **f['properties']} for recs in works.values() for _, f in recs]
    return json.dumps({'feed': F['name'], 'update_date': F['info'].get('update_date'), 'records': records,
                       'records_without_road_name': unnamed}, default=str)


RAW_RESULTS = {'work_zones_on_street': work_zones_on_street_raw}

if __name__ == '__main__':
    print(work_zones_on_street(*(sys.argv[1:3] or ['FL', 'Busch Blvd']), 28.0587, -82.4139))
