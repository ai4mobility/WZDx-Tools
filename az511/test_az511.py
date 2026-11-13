"""Checks for the Arizona 511 tools. Offline by default: it reads fixtures/ (the sample responses printed on
az511.com/help/endpoint/*, plus the first 400 work zones of a saved WZDx response).

    python test_az511.py            # tool checks
    python test_az511.py mcp        # also start az511_mcp_server.py over stdio and call it as a client would
    python test_az511.py live       # also call the real API with a fake key: the error must not show the key
"""
import os, sys, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['AZ511_SNAPSHOT'] = os.path.join(HERE, 'fixtures')
os.environ['AZ511_NOW'] = '1762354800'            # 2025-11-05 08:00 MST, a fixed clock for repeatable output
sys.path.insert(0, HERE)
import az511_tools as T

fails = 0
def check(name, ok, got=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'\n     got: {got!r}'))
    fails += not ok

# 1. road names people and feeds write differently
for q, field, want in [('I-10', 'I-10 / MP 320', True), ('Interstate 10', 'I-10 Eastbound', True), ('I 10', 'i-10', True),
                       ('I-10', 'I-100', False), ('I-10', 'SR-101', False), ('L-101', '101-LOOP', True),
                       ('Loop 202', 'L-202 EB @ 52nd St', True), ('SR 87', 'SR-87', True), ('US-60', 'I-60', False)]:
    check(f'road {q!r} vs {field!r} -> {want}', T._road_match(q, field) == want)

# 2. time: Unix -> Arizona time, which is UTC-7 all year (no daylight saving)
check('Unix 1711350000 -> Mon Mar 25 2024 00:00 MST (another year: the year is shown)',
      T._t(1711350000) == 'Mon Mar 25 2024 00:00 MST', T._t(1711350000))
check('July time is still MST (no DST)', T._t(1752253380).endswith('MST') and '10:03' in T._t(1752253380), T._t(1752253380))
check('a date in this year (2025 on the test clock) is shown without the year', '2025' not in T._t(1752253380), T._t(1752253380))
now = float(os.environ['AZ511_NOW'])
check('an expected end in the past is marked "(already passed)"', T._end(now - 86400).endswith('(already passed)'), T._end(now - 86400))
check('an expected end in the future is not marked', 'passed' not in T._end(now + 86400), T._end(now + 86400))

# 3. each tool on the documented samples
out = T.get_road_events(road='AJO')
check('events: "No Data" lanes become "lanes not reported"', 'lanes not reported' in out, out)
check('events: missing direction is said, not guessed', 'direction not reported' in out, out)
check('events: the 2024 start and 2027 end show their years; the future end is not marked passed',
      'started Mon Mar 25 2024' in out and 'Dec 31 2027' in out and 'passed' not in out, out)
out = T.get_road_events(event_type='crash')
check('events: a bad event_type is an error the model can read', out.startswith('Error: event_type'), out)
out = T.get_alerts()
check('alerts: the 2020 sample alert is not active now', '0 match of 1' in out, out)
out = T.get_message_signs(road='Loop 202')
check('signs: pages joined, line breaks kept as " / "', 'MINUTES TO / L-101 6 / L-101/US-60 9' in out, out)
out = T.get_road_weather(34.58, -113.49)
check('weather: °F written, wind unit flagged', '°F' in out and 'unit not stated' in out, out)
out = T.get_rest_areas(road='Interstate 10')
check('rest areas: truck spaces "8 of 22"', 'truck spaces 8 of 22 available' in out, out)
out = T.get_cameras(near_lat=35.17, near_lon=-114.57)
check('cameras: link to the image, distance in miles', 'az511.com/map/Cctv/960' in out and 'mi away' in out, out)
out = T.get_work_zones(active_now=False, max_results=3)
check('work zones: unknown impact said as unknown', 'Lane impact unknown for' in out and 'not verified' in out, out)
out = T.get_work_zones(road='I-10', near_lat=33.45, near_lon=-112.07, radius_mi=15, active_now=False)
check('work zones: road + radius filter runs', out.startswith('AZ511 work zones'), out)
out = T.get_work_zones(road='E Ajo Way', active_now=False)
check("work zones: WZDx lane order turned into 'right 2 lanes of 3 closed'", 'right 2 lanes of 3 closed' in out, out)
out = T.get_work_zones(active_now=False, max_results=400)
check("work zones: direction 'undefined' is written 'direction not reported'", ' undefined ' not in out and 'direction not reported' in out)
out = T.get_work_zones(max_results=0)
check('work zones: those past their planned end are counted and left out, not called finished',
      'Not shown: ' in out and 'past the planned end date' in out and 'may still be underway' in out, out)

# 4. a trip along one highway (fixtures_trip/ holds SYNTHETIC data: a made-up I-17 trip, Phoenix to Flagstaff)
os.environ['AZ511_SNAPSHOT'] = os.path.join(HERE, 'fixtures_trip')
check('direction: I-10 Phoenix to Tucson is eastbound (even-numbered), though it heads southeast',
      T._signed_dir('I-10', 33.4484, -112.0740, 32.2226, -110.9747)[0] == 'E')
check('direction: I-17 Flagstaff to Phoenix is southbound (odd-numbered)', T._signed_dir('I-17', 35.1983, -111.6513, 33.4484, -112.0740)[0] == 'S')
check('direction: a loop takes the trip heading', T._signed_dir('Loop 202', 33.43, -111.94, 33.40, -111.68)[0] == 'E')
check('direction words: NB, North Bound, Both Directions, None',
      [T._dir_code(x) for x in ('NB', 'North Bound', 'Both Directions', 'None', '')] == ['N', 'N', 'both', None, None])
out = T.get_trip_briefing('I-17', 33.4484, -112.0740, 35.1983, -111.6513)
check('trip: northbound, explained by the route number', 'I-17 northbound' in out and 'odd-numbered' in out, out)
check('trip: the full closure and the ice lead, in a "Most important" line',
      'Most important: ALL LANES CLOSED at mi 50' in out and 'ice possible at mi 105' in out, out)
check('trip: in order: the sign (mi 17), then the Anthem roadwork (mi 27), then the closure (mi 50)',
      (lambda w: w.index('Happy Valley') < w.index('near Anthem') < w.index('closed both ways'))(out.split('On your way')[1]), out)
check('trip: the southbound crash, the stale project and the closure not yet started are left out and counted',
      'Camp Verde' not in out and 'Old project' not in out and 'Overnight closure' not in out and
      '2 event(s) in the other direction (southbound), 1 whose planned end has passed' in out and '1 not started yet' in out, out)
check('trip: an event with no direction is listed apart, as possibly on your side',
      'Direction not reported (1)' in out and 'Cordes Junction' in out.split('Direction not reported')[1], out)
check('trip: blank and other-direction signs are not shown', 'PHOENIX 25 MIN' not in out and '1 sign(s) facing the other way' in out, out)
check('trip: weather only near the road itself (Munds Park yes; off-road and Yuma no)', 'station W1' in out and 'W2' not in out and 'W3' not in out, out)
check('trip: rest area with truck parking; other roads left out', 'truck spaces 8 of 22 available' in out and 'Sacaton' not in out, out)
check('trip: only alerts naming the road', 'expect delays at Sunset Point' in out and 'SR 89A' not in out, out)
check('trip: events on other roads, or before the start, are left out', 'downtown Phoenix' not in out and 'South of the trip start' not in out, out)
check('trip: direction read from the road name when the field is empty ("I-17 Southbound" left out; "I-17 Northbound" kept)',
      'to SR-69' not in out and 'to Anthem Way' in out and 'northbound (from the road name or description)' in out, out)
check('trip: a "NO_MESSAGE" sign is blank, not a message', 'NO_MESSAGE' not in out and 'Daisy Mtn' not in out, out)
check('trip: travel-time-only signs are summarized in one line', 'Travel-time signs on your way: 1' in out and 'FLAGSTAFF 99' in out
      and 'Black Canyon City' not in out.split('Travel-time signs')[0], out)
check('trip: the rest area for the other side (SB) is left out; NB and SB/NB are kept',
      out.count('McGuireville') == 1 and 'McGuireville Rest Area (NB)' in out and '1 rest area(s) on the other side' in out, out)
check('trip: "No Data" truck spaces read as not reported', '20 truck spaces, availability not reported' in out and 'No Data of' not in out, out)
out = T.get_message_signs(road='I-17')
check('signs: "NO_MESSAGE" counts as blank', 'NO_MESSAGE' not in out and '2 signs are blank' in out, out)
out = T.get_rest_areas(road='I-17')
check('rest areas: "No Data" truck spaces read as not reported', 'No Data of' not in out and 'availability not reported' in out, out)

# 5. cameras around an event (same SYNTHETIC folder)
check("roads: Phoenix's loops are state routes (SR-202 = 202-LOOP = Loop 202)",
      T._norm_road('SR-202') == T._norm_road('202-LOOP') == T._norm_road('Loop 202') == 'L-202' and T._norm_road('SR 101') == 'L-101')
check('mileposts read from a description', T._mps('Crash ... Near 24th St (MP 150).') == [150.0] and T._mps('from X (MP 215) to Y (MP 217)') == [215.0, 217.0])
check('camera labels read: road, side, milepost, place',
      T._view({'Description': 'SR-64 WB  213.90 @Williams'}) == {'road': 'SR-64', 'label': 'WB', 'mp': 213.9, 'place': 'Williams'})
out = T.get_cameras(road='L-202')
check('cameras: "L-202" finds the cameras ADOT files under SR-202, with view ids', 'McQueen' in out and 'view 2001' in out, out)
out = T.get_road_events(road='I-10')
check('events: each shows its event id', 'event 11 ·' in out, out)
out = T.get_event_cameras(11)
up, down = out.split('Upstream')[1].split('At the event')[0], out.split('Downstream')[1].split('On other roads')[0]
check('event cameras: I-10 mileposts grow southeast here (past Sky Harbor), so westbound traffic comes from the higher ones',
      'increase going southeast' in out and 'heads the other way, so it comes from the higher mileposts' in out, out)
check('event cameras: 150.3 is at the event (MP 150 is rounded to the mile); 150.6 upstream; 149.0 downstream',
      'view 1419' in out.split('At the event')[1].split('Downstream')[0] and 'view 850' in up and '0.6 mi upstream' in up
      and 'view 1258' in down and '1.0 mi downstream' in down, out)
check('event cameras: labels compared with the event (WB same; EB maybe the other side; NA not stated)',
      'label WB, same as the event' in out and 'label EB: maybe the other side' in out and 'label not stated' in out, out)
check('event cameras: a camera on another road is listed apart', 'view 895' in out.split('On other roads')[1], out)
out = T.get_event_cameras(12)
up, down = out.split('Upstream')[1].split('At the event')[0], out.split('Downstream')[1]
check('compass: 16 points (I-10 through Tucson runs south-southeast; mileposts grow east and north by default)',
      [T._compass(v) for v in [(0, 1), (1, 0), (0.34, -0.94), (-0.71, -0.71), (-0.92, 0.38)]] ==
      ['north', 'east', 'south-southeast', 'southwest', 'west-northwest'])
check('event cameras: on Loop 202 the mileposts grow WEST, so westbound traffic comes from the lower ones (Gilbert Rd)',
      'increase going west' in out and 'view 2002' in up and 'view 2003' in down and 'view 2001' in out.split('At the event')[1], out)
check('cross streets: "Near 5th Ave HOV (MP 144)." -> 5TH AVE; "N 7th Ave" -> 7TH AVE',
      T._cross_street('Crash blocking the HOV lane on I-10 Eastbound Near 5th Ave HOV (MP 144).') == '5TH AVE' and T._street('N 7th Ave') == '7TH AVE')
out = T.get_event_cameras(13)
check('event cameras: the camera at the event\'s cross street is at the event, though its milepost (144.8) is past MP 144',
      'view 834' in out.split('At the event')[1].split('Downstream')[0] and "named for the event's cross street, 5th Ave" in out, out)
check('event cameras: the label E/W of a street is flagged as the same street but placed by milepost',
      'view 831' in out.split('At the event')[1].split('Downstream')[0], out)
check('event cameras: an event no longer listed is an error the model can read', T.get_event_cameras(99999).startswith('Error: AZ511 lists no event'))
out = T.look_at_camera(1419)
check('look_at_camera: the label, the fetch time and the link (the picture itself goes over MCP)',
      'I-10 WB 150.30 @E of 24th St' in out and 'KB JPEG' in out and 'Cctv/1419' in out, out)
check('look_at_camera: an unknown view is an error', T.look_at_camera(5).startswith('Error: no camera view'))
os.environ['AZ511_SNAPSHOT'] = os.path.join(HERE, 'fixtures')

# 6. the key is plumbing: it never reaches the model's text
os.environ.pop('AZ511_SNAPSHOT'); os.environ['AZ511_KEY_FILE'] = '/nonexistent'; os.environ.pop('AZ511_KEY', None)
out = T.get_alerts()
check('no key: the error says how to get one', out.startswith('Error: No AZ511 developer key'), out)

if 'live' in sys.argv:
    os.environ['AZ511_KEY'] = 'FAKE-KEY-12345'
    out = T.get_alerts()
    check('live with a fake key: an error, and the key is not in it', out.startswith('Error') and 'FAKE-KEY' not in out, out)
    print('     the model would read:', out)

if 'mcp' in sys.argv:
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = dict(os.environ, AZ511_SNAPSHOT=os.path.join(HERE, 'fixtures'))
    async def run():
        p = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, 'az511_mcp_server.py')], env=env)
        async with stdio_client(p) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = (await s.list_tools()).tools
                res = await s.call_tool('get_rest_areas', {'road': 'I-10'})
                return tools, res
    tools, res = asyncio.run(run())
    names = sorted(t.name for t in tools)
    check('mcp: ten tools listed', len(names) == 10, names)
    ro = lambda a: bool(a) and bool(getattr(a, 'read_only_hint', None) or getattr(a, 'readOnlyHint', None))  # mcp 2.x | 1.x
    check('mcp: every tool marked read-only', all(ro(t.annotations) for t in tools))
    txt = res.content[0].text
    check('mcp: a call returns the same text as the function', 'truck spaces 8 of 22 available' in txt, txt)
    async def picture():
        p = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, 'az511_mcp_server.py')],
                                  env=dict(os.environ, AZ511_SNAPSHOT=os.path.join(HERE, 'fixtures_trip')))
        async with stdio_client(p) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await s.call_tool('look_at_camera', {'view_id': 1419})
    pic = asyncio.run(picture())
    kinds = [getattr(c, 'type', None) for c in pic.content]
    img = next((c for c in pic.content if getattr(c, 'type', None) == 'image'), None)
    mime = img and (getattr(img, 'mime_type', None) or getattr(img, 'mimeType', None))
    check('mcp: look_at_camera returns the text and the picture (image/jpeg)', kinds == ['text', 'image'] and mime == 'image/jpeg', (kinds, mime))
    t0 = next(t for t in tools if t.name == 'get_road_events')
    schema = getattr(t0, 'input_schema', None) or getattr(t0, 'inputSchema')                     # mcp 2.x | 1.x
    check('mcp: the schema is read from the type hints', set(schema['properties']) >= {'road', 'near_lat', 'event_type'}, schema)

print('\n' + ('all checks pass' if not fails else f'{fails} check(s) FAILED'))
sys.exit(1 if fails else 0)
