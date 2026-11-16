"""Read reported sidewalk closures and pedestrian notices from WZDx feeds."""
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import wzdx_tools as T

# Street-name matching from the course template.
SUFFIX = {'AVENUE': 'AVE', 'AV': 'AVE', 'BOULEVARD': 'BLVD', 'STREET': 'ST', 'ROAD': 'RD', 'DRIVE': 'DR',
          'LANE': 'LN', 'COURT': 'CT', 'CIRCLE': 'CIR', 'PLACE': 'PL', 'PARKWAY': 'PKWY', 'HIGHWAY': 'HWY',
          'TERRACE': 'TER', 'TRAIL': 'TRL', 'EXPRESSWAY': 'EXPY', 'CAUSEWAY': 'CSWY', 'PLAZA': 'PLZ'}
ABBREVIATED = set(SUFFIX.values()) | {'WAY', 'LOOP', 'RUN', 'PATH', 'PASS', 'ROW', 'WALK'}
DIRECTION = {'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W', 'NORTHEAST': 'NE', 'NORTHWEST': 'NW',
             'SOUTHEAST': 'SE', 'SOUTHWEST': 'SW'}
# Rule 2. A road-name field can end in ', City, State' and can hold several streets separated by commas.
CITY_STATE = re.compile(r'(^|,)\s*[A-Za-z .\'-]+,\s*(Florida|FL|Arizona|AZ)\s*$', re.I)


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


# Match explicit closure language. General sidewalk construction is insufficient.
PATH_WORD = r"(?:sidewalk|footway|walkway)s?"
CLOSED = re.compile(
    rf"\b{PATH_WORD}\s+(?:(?:is|are)\s+)?(?:temporarily\s+)?(?:closed|closures?)\b"
    rf"|\b(?:closure of|closing|closed)\s+(?:the\s+)?{PATH_WORD}\b", re.I)
NEGATED = re.compile(r"\b(?:no|without|avoid(?:ing)?|prevent(?:ing)?|possible|potential|proposed|planned)\s+(?:a\s+|any\s+|the\s+)?$", re.I)
PEDESTRIAN = re.compile(r"\b(?:pedestrians?|sidewalks?|footways?|walkways?|on foot|crosswalks?)\b", re.I)
GUIDANCE = re.compile(r"\b(?:use|follow|cross at|take|via|use the opposite side|do not enter)\b", re.I)
HAZARD = re.compile(r"\b(?:uneven|unprotected|fall hazard|trip(?:ping)? hazard|unmarked crossing|exposed|watch for|beware of|hazardous|slippery)\b", re.I)


def _closure(text):
    return any(not NEGATED.search(text[:m.start()]) for m in CLOSED.finditer(text))


def _search(feed, street, near_lat, near_lon, radius_mi):
    if not _street_parts(street):
        raise ValueError("Give a street name.")
    if not (-90 <= near_lat <= 90 and -180 <= near_lon <= 180):
        raise ValueError("Give latitude and longitude in decimal degrees.")
    if not math.isfinite(radius_mi) or radius_mi <= 0:
        raise ValueError("Give a positive search radius in miles.")
    data = T._load(feed)
    records = []
    now = T._now()
    for feature in data["wz"]:
        props = feature["properties"]
        details = props.get("core_details", {})
        if T._status(props, now) != "active" or not _closure(details.get("description") or ""):
            continue
        if not any(_matches(street, name) for name in details.get("road_names") or []):
            continue
        if not (feature.get("geometry") or {}).get("coordinates"):
            continue
        distance = T._dist(feature, near_lat, near_lon)
        if distance is not None and distance <= radius_mi:
            records.append((distance, feature))
    records.sort(key=lambda item: (item[0], str(item[1]["id"])))
    return data, records


@T._errors_as_text
def find_sidewalk_closures_plain(feed: str, street: str, near_lat: float, near_lon: float,
                                radius_mi: float = 5.0) -> str:
    """Read the fields from matching records without interpreting them."""
    data, records = _search(feed, street, near_lat, near_lon, radius_mi)
    return json.dumps({"feed": data["name"], "updated": data["info"].get("update_date"),
                       "records": [{"id": f["id"], **f["properties"]} for _, f in records]})


@T._errors_as_text
def find_sidewalk_closures(feed: str, street: str, near_lat: float, near_lon: float,
                          radius_mi: float = 5.0) -> str:
    """Find active work-zone records that explicitly describe a closed sidewalk or footway on a named
    street near a point. Give the feed (for example FL), street, latitude, longitude and radius in miles.
    A footway closure can affect walkers even when vehicle impact is unknown. Use the exact record ID
    with get_pedestrian_detour_info for reported walking directions. The reported end may be an estimate. Read-only."""
    data, records = _search(feed, street, near_lat, near_lon, radius_mi)
    updated = T._local(data["info"].get("update_date"), data["name"], near_lon)
    lines = [f"{street} within {radius_mi:g} mi of ({near_lat}, {near_lon}). "
             f"{data['name']} feed updated {updated}. Matching active closure records: {len(records)}."]
    for distance, feature in records:
        props = feature["properties"]
        details = props["core_details"]
        reported = T._ts(props.get("end_date"))
        end = "not reported"
        if reported is not None:
            zone, _ = T._tz(data["name"], T._pts(feature)[0][0])
            end = reported.astimezone(zone).strftime("%Y-%m-%d %H:%M %Z")
        if props.get("end_date") and props.get("end_date_accuracy") == "estimated":
            end += " (estimated)"
        elif props.get("end_date") and props.get("is_end_date_verified") is False:
            end += " (unverified)"
        lines.append(f"ID {feature['id']} | {details.get('direction') or 'direction not reported'} | "
                     f"{distance:.1f} mi | Reported end: {end} | {details['description']}")
    if records:
        lines.append("A reported end time does not confirm that the sidewalk has reopened.")
        lines.append("Northbound and southbound describe the closure records. Walking directions have not been checked. For a detour question, call get_pedestrian_detour_info for each relevant ID before answering. Do not infer a walking route from a closure direction.")
    else:
        lines.append("No matching closure was identified in the reports. Sidewalk access is unconfirmed.")
    return "\n".join(lines)


def _lookup(feed, work_zone_id):
    data = T._load(feed)
    key = work_zone_id.strip()
    for feature in data["wz"]:
        if str(feature["id"]) == key:
            return feature["properties"], data["detours"].get(key, [])
    raise ValueError(f"No work zone with ID {key!r} found in {data['name']}.")


@T._errors_as_text
def get_pedestrian_detour_info_raw(feed: str, work_zone_id: str) -> str:
    props, linked = _lookup(feed, work_zone_id)
    return json.dumps({"id": work_zone_id, "work_zone": props, "linked_detours": linked})


@T._errors_as_text
def get_pedestrian_detour_info(feed: str, work_zone_id: str) -> str:
    """Check one exact work-zone ID for pedestrian notices in its report and linked detours. Supply the
    same feed and ID returned by find_sidewalk_closures. Quote the reported wording and preserve restrictions.
    A linked vehicle detour alone gives no walking directions. Missing hazard information leaves conditions
    unknown. The tool cannot estimate walking time or confirm a safe alternate path. Read-only."""
    props, linked = _lookup(feed, work_zone_id)
    lines = [f"Work zone {work_zone_id} | Linked detour records: {len(linked)}"]
    directions = []
    hazards = []
    other = []
    for index, item in enumerate([props, *linked]):
        details = item.get("core_details", {})
        source = f"Linked detour {index}" if index else "Work zone"
        label = details.get("name") or ""
        description = (details.get("description") or "").strip()
        # Preserve the whole notice so conditions and negations stay with any instructions.
        notice = " | ".join(dict.fromkeys(s for s in [label, description] if s))
        if not notice:
            continue
        if not PEDESTRIAN.search(notice):
            continue
        quote = f'{source}: "{notice}"'
        if GUIDANCE.search(notice):
            directions.append(quote)
        if HAZARD.search(notice):
            hazards.append(quote)
        if quote not in directions and quote not in hazards:
            other.append(quote)
    lines.extend(other)
    lines.append("Reported text to check for walking directions:" if directions else
                 "No explicit walking directions identified in the checked text.")
    lines.extend(directions)
    lines.append("Reported text mentioning possible hazards:" if hazards else
                 "No additional pedestrian hazard identified in the checked text.")
    lines.extend(hazards)
    lines.append("Conditions on an alternate walking route are unconfirmed.")
    return "\n".join(lines)


TOOLS = [find_sidewalk_closures, get_pedestrian_detour_info]
READ_ONLY = {fn.__name__ for fn in TOOLS}
PLAIN_DESCRIPTIONS = {
    "find_sidewalk_closures": "Look up matching records by feed, street, coordinates and radius in miles.",
    "get_pedestrian_detour_info": "Look up one record and its linked entries by feed and ID.",
}
RAW_RESULTS = {
    "find_sidewalk_closures": find_sidewalk_closures_plain,
    "get_pedestrian_detour_info": get_pedestrian_detour_info_raw,
}
