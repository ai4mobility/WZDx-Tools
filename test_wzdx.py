"""Checks for the work-zone tools. Offline: fixtures/ holds a Tampa-area slice of FDOT's WZDx feed (Nov 5 2026,
work zones within 8 mi of USF plus one Miami work zone and its detours, detour geometry trimmed), 400 Arizona
work zones, and USDOT's registry with every URL query string removed.

    python test_wzdx.py            # tool checks
    python test_wzdx.py mcp        # also start wzdx_mcp_server.py over stdio and call it as a client would
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['WZDX_SNAPSHOT'] = os.path.join(HERE, 'fixtures')
os.environ['WZDX_NOW'] = '1793888460'                    # 2026-11-05 14:21 UTC, when the Florida slice was read
sys.path.insert(0, HERE)
import wzdx_tools as T

fails = 0
def check(name, ok, got=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'\n     got: {got!r}'))
    fails += not ok

# 1. road names as Florida and Arizona feeds write them
for q, field, want in [('I-75', 'I 75', True), ('I-75', 'I-275', False), ('I 275', 'I-275', True),
                       ('SR 434', 'FL 419;FL 434', True), ('SR-43', 'FL 434', False), ('US-41', 'US 41', True),
                       ('Busch Boulevard', 'East Busch Boulevard, Tampa, Florida', True), ('L-101', '101-LOOP', True)]:
    check(f'road {q!r} vs {field!r} -> {want}', T._road_match(q, field) == want)

# 2. lanes: WZDx counts from the left and lists shoulders as lanes
S, G = 'shoulder', 'general'
busch = [{'order': 1, 'status': 'open', 'type': S}, {'order': 2, 'status': 'open', 'type': G},
         {'order': 3, 'status': 'open', 'type': G}, {'order': 4, 'status': 'closed', 'type': G}, {'order': 5, 'status': 'open', 'type': S}]
check("Busch Blvd 'lane 4 of 5' -> right lane of 3", T._lanes_text(busch) == 'right lane of 3 closed', T._lanes_text(busch))
two = [{'order': 1, 'status': 'open', 'type': G}, {'order': 2, 'status': 'closed', 'type': G}, {'order': 3, 'status': 'closed', 'type': G}]
check('right two of three', T._lanes_text(two) == 'right 2 lanes of 3 closed', T._lanes_text(two))
mid = [{'order': 1, 'status': 'open', 'type': G}, {'order': 2, 'status': 'closed', 'type': G}, {'order': 3, 'status': 'open', 'type': G}]
check('middle lane named by number', 'travel lane(s) 2 of 3 closed, counted from the left' in T._lanes_text(mid), T._lanes_text(mid))
sh = [{'order': 1, 'status': 'open', 'type': G}, {'order': 2, 'status': 'closed', 'type': S}]
check('right shoulder only', T._lanes_text(sh) == 'right shoulder closed', T._lanes_text(sh))

# 3. units and time
check('72.42 km/h -> 45 mph', T._mph(72.42) == 45)
check('Tampa: Eastern time', T._local('2026-11-05T14:21:00Z', 'fldot', -82.4).endswith('EST'))
check('Pensacola: Central time', T._local('2026-11-05T14:21:00Z', 'fldot', -87.2).endswith('CST'))
check('Arizona: MST in July', T._local('2026-07-01T12:00:00Z', 'az511', -112.0).endswith('MST'))
check('another year is shown', '2027' in T._local('2027-06-29T05:00:00Z', 'fldot', -82.4))

# 4. the tools
out = T.list_feeds('florida')
check('registry: Florida feed listed as open', 'fldot' in out and 'open' in out, out)
out = T.feed_quality('FL')
check('quality: WZDx version and unknown share reported', 'WZDx 4.2' in out and 'lane impact unknown' in out, out)
out = T.get_work_zones('FL', near_lat=28.0587, near_lon=-82.4139, radius_mi=3)
check('near USF: active work zones found, unknown impact said', 'active work zone(s) match' in out and 'unknown' in out, out)
out = T.get_work_zones('FL', road='Busch Boulevard')
check('road filter by street name, duplicate names collapsed', 'East Busch Boulevard ·' in out and 'Boulevard, East Busch' not in out, out)
out = T.check_location('FL', 28.0336, -82.4382)
check('dashcam point on Busch Blvd: the lane closure is found', 'some lanes closed' in out and 'right lane of 3 closed' in out, out)
out = T.check_location('FL', 27.0, -81.0, radius_mi=0.2)
check('no work zone: says it is not proof', out.startswith('No active work zone') and 'trust the camera' in out, out)
out = T.get_detours('FL', '4571671574')
check('detours linked to their work zone', 'Miami Gardens Detour' in out, out)
out = T.get_work_zones('FL', status='open')
check('bad status: an error the model can read', out.startswith("Error: status must be"), out)
out = T.get_work_zones('AZ', road='I-17', status='all', max_results=2)
check('Arizona feed through the same tool', 'az511 feed' in out and 'MST' in out, out)
out = T.get_work_zones('XX')
check('unknown feed: points to list_feeds', 'Error' in out and 'list_feeds' in out, out)

if 'mcp' in sys.argv:
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def run():
        p = StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, 'wzdx_mcp_server.py')], env=dict(os.environ))
        async with stdio_client(p) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return (await s.list_tools()).tools, await s.call_tool('check_location', {'feed': 'FL', 'lat': 28.0336, 'lon': -82.4382})
    tools, res = asyncio.run(run())
    check('mcp: five tools listed', len(tools) == 5, [t.name for t in tools])
    ro = lambda a: bool(a) and bool(getattr(a, 'read_only_hint', None) or getattr(a, 'readOnlyHint', None))
    check('mcp: every tool marked read-only', all(ro(t.annotations) for t in tools))
    check('mcp: a call returns the same text as the function', 'some lanes closed' in res.content[0].text, res.content[0].text)

print('\n' + ('all checks pass' if not fails else f'{fails} check(s) FAILED'))
sys.exit(1 if fails else 0)
