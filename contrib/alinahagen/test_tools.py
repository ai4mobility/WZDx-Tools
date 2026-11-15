"""Tests for the template tool: one test per rule in KNOWLEDGE.md, and one that compares the plain version with
the engineer's. They run on the saved snapshot, so everyone gets the same answers:

    python contrib/<you>/test_tools.py          # or: python contrib/check.py contrib/<you>

Each test is a function whose name starts with test_. A test passes when it runs without an AssertionError.
Write each assert with a message (after the comma) that shows what the tool returned, so a failure explains itself.
"""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
os.environ['WZDX_SNAPSHOT'] = os.path.join(ROOT, 'snapshots', '2026-11-05')
os.environ['WZDX_NOW'] = '1793888460'      # Thu Nov 5 2026 14:21 UTC = 09:21 EST, when the Florida feed was saved
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import tools as M
import wzdx_tools as T

USF = (28.0587, -82.4139)                  # USF Tampa campus


def test_suffix_and_direction_forms():
    # FDOT's record says 'East Busch Boulevard'; people say 'Busch Blvd'
    assert M._street_parts('East Busch Boulevard, Tampa, Florida') == [('E', 'BUSCH', 'BLVD')]
    out = M.work_zones_on_street('FL', 'Busch Blvd', *USF)
    assert '1 active work(s)' in out and 'right lane of 3 closed' in out, out
    # a direction in the query must agree; a query without one matches any
    assert M._matches('N 30th St', 'North 30th Street') and M._matches('30th St', 'North 30th Street')
    assert not M._matches('S 30th St', 'North 30th Street')
    # whole words, not text: '50th St' is not 'Northeast 150th Street' (Miami), which a text search takes
    assert '150th Street' in M.work_zones_on_street_plain('FL', '50th St')
    assert not M._matches('50th St', 'Northeast 150th Street')
    out = M.work_zones_on_street('FL', '50th St', *USF)
    assert '1 active work(s)' in out and 'N 50th St' in out and '150th' not in out, out
    a = M.work_zones_on_street('FL', '30th St', *USF).split('\n', 1)[1]
    b = M.work_zones_on_street('FL', 'North 30th Street', *USF).split('\n', 1)[1]
    assert a == b, (a, b)


def test_several_streets_and_city_tails():
    assert M._street_parts('North Orleans Avenue,West Hamilton Avenue') == [('N', 'ORLEANS', 'AVE'), ('W', 'HAMILTON', 'AVE')]
    assert M._street_parts('Tampa, Florida') == [], 'a city is not a street'
    out = M.work_zones_on_street('FL', 'Hamilton Ave', *USF)
    assert '2 active work(s)' in out and 'all lanes closed' in out, out
    assert '0 active work(s)' in M.work_zones_on_street('FL', 'Tampa', *USF)


def test_same_name_elsewhere():
    # FDOT's feed has an East 109th Avenue in Tampa and a Southwest 109th Avenue 200 mi away
    F = T._load('FL')
    same = [f for f in F['wz'] if any('109th ave' in n.lower() for n in f['properties']['core_details'].get('road_names') or [])]
    far = [f for f in same if T._dist(f, *USF) > 100]
    assert len(same) == 6 and len(far) == 3, (len(same), len(far))
    assert M.work_zones_on_street_plain('FL', '109th Ave').startswith('6 work zones found.')
    out = M.work_zones_on_street('FL', '109th Ave', *USF)
    assert '1 active work(s) on the street, from 3 record(s)' in out and 'E 109th Ave' in out and 'Sw' not in out, out


def test_records_grouped_into_works():
    out = M.work_zones_on_street('FL', '30th St', *USF)
    assert '2 active work(s) on the street, from 4 record(s)' in out, out
    block = out.split('- work 4233451340')[1].split('- work')[0]
    assert '3 record(s)' in block and 'northbound' in block and 'southbound' in block, block


def test_unknown_impact_is_not_open():
    out = M.work_zones_on_street('FL', '30th St', *USF)
    records = [l for l in out.split('\n') if l.startswith('    ') and ' · until ' in l]
    assert len(records) == 4, records
    assert all('lane impact not reported' in l for l in records), records
    assert not any(re.search(r'\bopen\b', l) for l in records), records


def test_unnamed_records_counted():
    F = T._load('FL'); now = T._now()
    want = sum(1 for f in F['wz'] if T._status(f['properties'], now) == 'active'
               and not f['properties']['core_details'].get('road_names')
               and (T._dist(f, *USF) or 99) <= 5.0)
    out = M.work_zones_on_street('FL', 'Busch Blvd', *USF)
    assert f'Not findable by name: {want} active record(s) within 5 mi' in out, (want, out.split('\n')[-1])
    assert 'get_work_zones' in out.split('\n')[-1]


def test_route_numbers_go_to_get_work_zones():
    out = M.work_zones_on_street('FL', 'I-275', *USF)
    assert 'route number' in out and "get_work_zones with road='I-275'" in out, out


def test_plain_vs_work_zones_on_street():
    # Busch Blvd: the plain search finds nothing; the right lane of 3 is closed eastbound until 4 pm
    plain = M.work_zones_on_street_plain('FL', 'Busch Blvd')
    mine = M.work_zones_on_street('FL', 'Busch Blvd', *USF)
    assert plain == '0 work zones found.', plain
    assert 'eastbound: some lanes closed, right lane of 3 closed · until Thu Nov 5 16:00 EST' in mine, mine
    # 30th St: the plain search reports 4 'work zones'; they are 2 works
    assert M.work_zones_on_street_plain('FL', '30th St').startswith('4 work zones found.')
    assert '2 active work(s)' in M.work_zones_on_street('FL', '30th St', *USF)


if __name__ == '__main__':
    tests = [(n, f) for n, f in list(globals().items()) if n.startswith('test_') and callable(f)]
    bad = 0
    for n, f in tests:
        try:
            f(); print('PASS', n)
        except Exception as e:
            bad += 1; print('FAIL', n, '\n    ', type(e).__name__, str(e)[:400])
    print(f'{len(tests) - bad} of {len(tests)} pass')
    sys.exit(1 if bad else 0)
