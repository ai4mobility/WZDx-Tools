"""Verify the crash diversion tools against the recorded FDOT snapshot."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import tools

SNAPSHOT = Path(__file__).resolve().parents[2] / 'snapshots' / '2026-11-05'
SNAPSHOT_ENV = {'WZDX_SNAPSHOT': str(SNAPSHOT), 'WZDX_NOW': '1793888460'}
BUSCH = ('Busch Blvd', 28.0587, -82.4139, 'EB')
MIAMI_WORK = '4571671574'
BUSCH_WORK = '4577091647'
BUSCH_EAST = '4577091647/292055206'
MIAMI_NORTH = '4571671574/291384760'


def _screen():
    with patch.dict(os.environ, SNAPSHOT_ENV):
        return tools.crash_area_work_zone_constraints(*BUSCH)


def _detours(work_zone_id=MIAMI_WORK, direction='NB', **environment):
    with patch.dict(os.environ, {**SNAPSHOT_ENV, **environment}):
        return tools.linked_work_zone_detours_for_direction(work_zone_id, direction)


def test_crash_screen_partitions_reported_directions():
    result = _screen()
    matching, unknown = result.split('Separate records with unknown direction: 1.')
    assert f'- {BUSCH_EAST} · FDOT reports eastbound' in matching, result
    assert f'- {BUSCH_WORK} · direction unknown; this record is not assigned to eastbound' in unknown, result
    assert f'- {BUSCH_WORK} ·' not in matching, result


def test_detour_uses_direction_field():
    north = _detours()
    south = _detours(direction='SB')
    assert f'- {MIAMI_NORTH} ·' in north and f'- {MIAMI_NORTH}-R ·' not in north, north
    assert f'- {MIAMI_NORTH}-R ·' in south and f'- {MIAMI_NORTH} ·' not in south, south
    assert 'unknown direction' not in north and 'unknown direction' not in south


def test_crash_screen_counts_travel_lanes_without_shoulders():
    result = _screen()
    assert 'right lane of 3 closed' in result, result
    assert 'lane 4 of 5' not in result, result


def test_crash_screen_surfaces_unreported_lane_impact():
    result = _screen()
    line = next(line for line in result.splitlines() if line.startswith(f'- {BUSCH_WORK} ·'))
    assert 'lane impact not reported' in line and 'specific closed travel-lane position not established' in line, line
    assert 'open' not in line, line


def test_detour_requires_exact_work_zone_relationship():
    assert f'- {MIAMI_NORTH} ·' in _detours()
    result = _detours(BUSCH_WORK)
    assert 'No linked detour for this work-zone ID and direction' in result and MIAMI_NORTH not in result, result
    assert 'exact FDOT feature ID' in _detours('Miami Gardens Detour')


def test_reported_detour_end_does_not_confirm_reopening():
    result = _detours(WZDX_NOW='1796205600')
    assert '2026-11-30 10:00 UTC (end unverified)' in result, result


def test_plain_vs_crash_area_work_zone_constraints():
    with patch.dict(os.environ, SNAPSHOT_ENV):
        raw = tools.crash_area_work_zone_constraints_plain(*BUSCH)
    records = {record['id']: record for record in json.loads(raw)['records']}
    east = records[BUSCH_EAST]
    assert [lane['order'] for lane in east['lanes'] if lane['status'] == 'closed'] == [4], east
    assert records[BUSCH_WORK]['vehicle_impact'] == 'unknown'
    assert 'right lane of 3 closed' not in raw and 'right lane of 3 closed' in _screen()


def test_plain_vs_linked_work_zone_detours_for_direction():
    with patch.dict(os.environ, SNAPSHOT_ENV):
        raw = tools.linked_work_zone_detours_for_direction_plain(MIAMI_WORK, 'NB')
    detour, = json.loads(raw)['records']
    assert detour['id'] == MIAMI_NORTH and detour['is_end_date_verified'] is False, detour
    assert 'end unverified' not in raw and 'end unverified' in _detours()


def test_crash_screen_explains_scope_and_invalid_input():
    with patch.dict(os.environ, SNAPSHOT_ENV):
        result = tools.crash_area_work_zone_constraints(*BUSCH, radius_mi=0.5)
        invalid = tools.crash_area_work_zone_constraints(*BUSCH, radius_mi=0)
    assert 'Reported eastbound records: 0.' in result and 'proximity screen' in result, result
    assert 'greater than 0' in invalid, invalid


if __name__ == '__main__':
    suite = unittest.TestSuite(
        unittest.FunctionTestCase(test)
        for name, test in tuple(globals().items()) if name.startswith('test_')
    )
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
