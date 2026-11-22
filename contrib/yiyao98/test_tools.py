"""Unit tests for assess_record_trust, estimate_closure_capacity, and plain baseline (24 reviewed cases)."""
import math
import os
import sys
import copy
import json
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
os.environ.setdefault('WZDX_SNAPSHOT', os.path.join(REPO_ROOT, 'snapshots', '2026-11-05'))
os.environ.setdefault('WZDX_NOW', '1793888460')

sys.path.insert(0, HERE)
sys.path.insert(0, REPO_ROOT)
import tools as M

TOL = 1e-6
EXP_2_TO_1_RANGE = (1562.3556581986143, 2185.9122401847576)
EXP_2_TO_1_DISPLAY = [1560, 2190]


# ---- Tool 1: assess_record_trust (13 cases) ----

def test_trust_time_conflict_first():
    res = M._evaluate_record_trust('AZ', 'mEbzIYe+/rhIYgmaYk3Il2vM6ro=')
    assert res['final_tier'] == 'Low'
    assert res['final_tier'] != 'Scheduled'
    assert 'time_conflict' in res['reasons']
    text = M.assess_record_trust('AZ', 'mEbzIYe+/rhIYgmaYk3Il2vM6ro=')
    assert 'Trust Tier: Low' in text


def test_trust_completed_before_missing_evidence():
    res = M._evaluate_record_trust('FL', '4480061970/278730952/13254264/0')
    assert res['final_tier'] == 'Completed'
    assert 'Trust Tier: Completed' in M.assess_record_trust('FL', '4480061970/278730952/13254264/0')


def test_trust_pending_separate():
    res = M._evaluate_record_trust('FL', '4583116574')
    assert res['final_tier'] == 'Scheduled'


def test_trust_active_future_start_flag():
    res = M._evaluate_record_trust('FL', '4577079040')
    assert res['final_tier'] == 'Medium'
    assert res['event_status'] == 'active'
    assert 'active_with_future_start' in res['flags']


def test_trust_update_after_end_cap_then_and_rule():
    res = M._evaluate_record_trust('AZ', 'AZTech.Buckeye-buckeyeaz-l-100')
    assert res['time_component_cap'] == 'Medium'
    assert res['final_tier'] == 'Low'
    assert 'unknown_and_no_lanes_and_unverified' in res['reasons']


def test_trust_update_before_end_low():
    res = M._evaluate_record_trust('AZ', 'p/oWv21wtxKFU6pd1JhhnSxfAjA=')
    assert res['final_tier'] == 'Low'
    assert 'past_end_without_post_end_update' in res['reasons']


def test_trust_unknown_missing_lanes_unverified_low():
    res = M._evaluate_record_trust('AZ', '427111')
    assert res['final_tier'] == 'Low'
    assert res['lane_component']['lanes_presence'] == 'missing'


def test_trust_unknown_with_lane_evidence_medium():
    res = M._evaluate_record_trust('AZ', '364343')
    assert res['final_tier'] == 'Medium'
    assert res['lane_component']['consistency'] == 'no_confirmed_conflict'


def test_trust_open_impact_shoulder_closed_consistent():
    res = M._evaluate_record_trust('AZ', '351676')
    assert res['lane_component']['consistency'] == 'consistent'
    assert res['final_tier'] == 'Medium'


def test_trust_some_closed_only_shoulder_conflict():
    res = M._evaluate_record_trust('FL', '4586525408/293379759')
    assert res['lane_component']['consistency'] == 'conflict'
    assert res['final_tier'] == 'Low'
    assert res['lane_component']['general_total'] == 3
    assert res['lane_component']['general_closed'] == 0


def test_trust_exit_lane_component():
    res = M._evaluate_record_trust('AZ', 'pwBAluPBP/0qbRpIalbTSzTZCK0=')
    assert res['final_tier'] == 'Scheduled'
    lc = res['lane_component']
    assert lc['consistency'] == 'consistent'
    assert lc['general_total'] == 0
    assert lc['exit_lane_closed'] == 1


def test_trust_alternating_flow_compatible_component():
    res = M._evaluate_record_trust('AZ', 'L4AeTAPVfsxTcVm4yyxniniUboo=')
    assert res['final_tier'] == 'Medium'
    assert res['lane_component']['consistency'] == 'compatible_alternating_flow'


def test_trust_partial_verification_high():
    res = M._evaluate_record_trust('FL', '4586540208/293383742')
    assert res['final_tier'] == 'High'
    assert res['verification'] == [True, True, False, False]


# ---- Tool 2: estimate_closure_capacity (11 cases) ----

def _assert_two_to_one_envelope(res):
    assert res['estimate_available'] is True
    assert res['general_total'] == 2
    assert res['general_closed'] == 1
    assert res['general_open'] == 1
    assert math.isclose(res['LCSI'], 2.0, rel_tol=0.0, abs_tol=TOL)
    assert math.isclose(res['capacity_pcph_range'][0], EXP_2_TO_1_RANGE[0], rel_tol=0.0, abs_tol=TOL)
    assert math.isclose(res['capacity_pcph_range'][1], EXP_2_TO_1_RANGE[1], rel_tol=0.0, abs_tol=TOL)
    assert res['capacity_pcph_display_range'] == EXP_2_TO_1_DISPLAY
    assert res['capacity_drop_percent'] is None
    assert res['missing_for_percent'] == 'nonworkzone_baseline_capacity'
    assert res['speed_used_in_capacity_equation'] is False


def test_capacity_two_to_one_speed_55_south():
    res = M._evaluate_closure_capacity('AZ', 'lmsaCxKAd/C/B4u3LIJ7zNUM0E8=')
    _assert_two_to_one_envelope(res)
    assert res['speed_status'] == 'reported'
    assert res['speed_mph_display'] == 55.0
    text = M.estimate_closure_capacity('AZ', 'lmsaCxKAd/C/B4u3LIJ7zNUM0E8=')
    assert '1560–2190 pc/h' in text
    assert '55.0 mph' in text


def test_capacity_two_to_one_speed_55_north():
    res = M._evaluate_closure_capacity('AZ', 'ZdtaXBdb//ZWXk20qY/1fyTrPrk=')
    _assert_two_to_one_envelope(res)
    assert res['speed_status'] == 'reported'
    assert res['speed_mph_display'] == 55.0


def test_capacity_zero_speed_invalid_not_missing():
    res = M._evaluate_closure_capacity('AZ', '404506')
    _assert_two_to_one_envelope(res)
    assert res['speed_status'] == 'invalid_nonpositive'
    assert res['speed_mph_display'] is None


def test_capacity_speed_missing():
    res = M._evaluate_closure_capacity('AZ', 'G/c+aF7jDf9BiELBBXYH3XwrZGA=')
    _assert_two_to_one_envelope(res)
    assert res['speed_status'] == 'missing'
    assert res['speed_mph_display'] is None


def test_capacity_reject_explicit_exit_ramp():
    res = M._evaluate_closure_capacity('AZ', '388321')
    assert res['estimate_available'] is False
    assert 'non_mainline_exit_ramp' in res['refusal_reasons']
    assert res['capacity_pcph_range'] is None
    assert res['capacity_drop_percent'] is None


def test_refused_ramp_briefing_does_not_label_mainline_inventory():
    # The first local-model run turned a refused ramp estimate into zero mainline
    # capacity. The briefing must carry the scope refusal through the lane labels.
    text = M.estimate_closure_capacity('AZ', '388321')
    assert 'Mainline Capacity: unknown (no value estimated)' in text
    assert 'not a mainline inventory' in text
    assert 'Mainline general lanes (assumed complete as listed)' not in text
    assert 'No capacity equation or parameter scenarios were evaluated' in text


def test_capacity_requires_lane_list():
    res = M._evaluate_closure_capacity('AZ', '427111')
    assert res['estimate_available'] is False
    assert 'missing_lanes' in res['refusal_reasons']


def test_capacity_exit_lane_not_general():
    res = M._evaluate_closure_capacity('AZ', 'pwBAluPBP/0qbRpIalbTSzTZCK0=')
    assert res['estimate_available'] is False
    assert res['general_total'] == 0
    assert res['exit_lane_closed'] == 1


def test_capacity_scope_unconfirmed():
    res = M._evaluate_closure_capacity('FL', '4586540208/293383742')
    assert res['estimate_available'] is False
    assert 'freeway_mainline_scope_unconfirmed' in res['refusal_reasons']


def test_moving_field_is_not_duration():
    res = M._evaluate_closure_capacity('AZ', '337554')
    assert res['work_zone_type_reported'] == 'moving'
    assert res['hcm_duration_category'] is None
    assert res['estimate_available'] is False
    assert 'non_mainline_exit_ramp' in res['refusal_reasons']
    assert 'moving_automatically_forbidden_by_hcm' not in res['refusal_reasons']


def test_plain_vs_capacity_exit_ramp_scope():
    plain = M._evaluate_capacity_plain('AZ', '388321')
    domain = M._evaluate_closure_capacity('AZ', '388321')
    assert plain['plain_listed_lane_count'] == 1
    assert plain['plain_listed_closed_count'] == 1
    assert plain['plain_listed_open_fraction'] == 0.0
    assert plain['plain_fraction_is_not_capacity'] is True
    assert domain['estimate_available'] is False
    assert 'listed-lane fraction only' in M.estimate_closure_capacity_plain('AZ', '388321')
    assert 'No (refused)' in M.estimate_closure_capacity('AZ', '388321')


def test_capacity_explicit_baseline_arithmetic():
    res = M._evaluate_closure_capacity(
        'AZ',
        'lmsaCxKAd/C/B4u3LIJ7zNUM0E8=',
        baseline_pcphpl=2000.0,
        baseline_source='controlled arithmetic unit-test input; not a field observation',
    )
    assert math.isclose(res['capacity_pcph_range'][0], EXP_2_TO_1_RANGE[0], rel_tol=0.0, abs_tol=TOL)
    assert math.isclose(res['capacity_pcph_range'][1], EXP_2_TO_1_RANGE[1], rel_tol=0.0, abs_tol=TOL)
    assert math.isclose(res['remaining_percent_range'][0], 39.05889145496536, rel_tol=0.0, abs_tol=TOL)
    assert math.isclose(res['remaining_percent_range'][1], 54.64780600461894, rel_tol=0.0, abs_tol=TOL)
    assert math.isclose(res['loss_percent_range'][0], 45.35219399538106, rel_tol=0.0, abs_tol=TOL)
    assert math.isclose(res['loss_percent_range'][1], 60.94110854503464, rel_tol=0.0, abs_tol=TOL)


# Implementation regressions below use explicitly modified in-memory fixtures.
# They supplement, and do not replace, the 24 reviewed real-record cases above.
def _fixture():
    feed, feature = M._find_record('AZ', 'lmsaCxKAd/C/B4u3LIJ7zNUM0E8=')
    return feed, copy.deepcopy(feature)


def test_scope_uses_whole_route_and_work_evidence():
    feed, feature = _fixture()
    for description in ('I-170 mainline left lane closed', 'I-17',
                        'Construction work on I-170. I-17 mainline remains open.',
                        'Construction work on I-17. Exit ramp closed.',
                        'Construction work on I-17 exit ramp at Exit 123.'):
        feature['properties']['core_details']['description'] = description
        with patch.object(M, '_find_record', return_value=(feed, feature)):
            result = M._evaluate_closure_capacity('AZ', 'fixture')
        assert not result['estimate_available']
        assert any(reason in result['refusal_reasons'] for reason in
                   ('freeway_mainline_scope_unconfirmed', 'non_mainline_exit_ramp'))
    feature['properties']['core_details']['road_names'] = ['Interstate 17']
    feature['properties']['core_details']['description'] = 'I-17 mainline left lane closed'
    with patch.object(M, '_find_record', return_value=(feed, feature)):
        assert M._evaluate_closure_capacity('AZ', 'fixture')['estimate_available']


def test_scope_does_not_reject_ramp_location_reference():
    feed, feature = _fixture()
    feature['properties']['core_details']['description'] = (
        'I-17 mainline right lane closed between the on-ramp at Exit 123 and Exit 125.'
    )
    with patch.object(M, '_find_record', return_value=(feed, feature)):
        result = M._evaluate_closure_capacity('AZ', 'fixture')
    assert result['estimate_available']
    assert not result['refusal_reasons']


def test_baseline_source_required_without_losing_absolute_capacity():
    result = M._evaluate_closure_capacity('AZ', 'lmsaCxKAd/C/B4u3LIJ7zNUM0E8=', 2000.0)
    assert result['estimate_available']
    assert result['capacity_pcph_range'] is not None
    assert result['loss_percent_range'] is None
    assert 'missing_baseline_source' in result['percentage_issues']
    assert result['missing_for_percent'] == 'baseline_source'


def test_invalid_baseline_does_not_block_absolute_capacity():
    for baseline in (-1, 0, float('nan'), float('inf'), True, '2000'):
        result = M._evaluate_closure_capacity(
            'AZ', 'lmsaCxKAd/C/B4u3LIJ7zNUM0E8=', baseline, 'controlled invalid input'
        )
        assert result['estimate_available']
        assert result['capacity_pcph_range'] is not None
        assert result['loss_percent_range'] is None
        assert 'invalid_baseline_pcphpl' in result['percentage_issues']


def test_per_open_lane_and_total_quantities():
    feed, feature = _fixture()
    feature['properties']['lanes'].append({'order': 3, 'type': 'general', 'status': 'open'})
    with patch.object(M, '_find_record', return_value=(feed, feature)):
        result = M._evaluate_closure_capacity('AZ', 'fixture')
    assert result['estimate_available']
    assert result['general_open'] == 2
    for total, per_lane in zip(result['capacity_pcph_range'], result['per_open_lane_pcph_range']):
        assert math.isclose(total, 2 * per_lane, rel_tol=0.0, abs_tol=TOL)


def test_invalid_record_evidence_returns_error_not_trust_tier():
    feed, original = _fixture()
    mutations = [
        lambda p: p.update(start_date='bad'),
        lambda p: p.pop('end_date'),
        lambda p: p.update(event_status='garbled'),
        lambda p: p.update(is_start_date_verified='false'),
        lambda p: p.update(lanes=[None]),
        lambda p: p.update(lanes='not a list'),
        lambda p: p.update(lanes=[{'order': 1, 'type': 'general'}]),
    ]
    for mutate in mutations:
        feature = copy.deepcopy(original)
        feature['properties']['is_start_date_verified'] = True
        mutate(feature['properties'])
        with patch.object(M, '_find_record', return_value=(feed, feature)):
            text = M.assess_record_trust('AZ', 'fixture')
        assert text.startswith('Error:'), text
        assert 'Trust Tier:' not in text


def test_unreported_verification_distinct_from_false():
    feed, feature = _fixture()
    feature['properties'].pop('is_start_date_verified')
    with patch.object(M, '_find_record', return_value=(feed, feature)):
        text = M.assess_record_trust('AZ', 'fixture')
    assert 'is_start_date_verified=not reported (field absent)' in text
    assert 'is_end_date_verified=False' in text


def test_raw_versions_preserve_reference_time():
    for raw_fn in (M.assess_record_trust_raw, M.estimate_closure_capacity_raw):
        result = json.loads(raw_fn('AZ', 'lmsaCxKAd/C/B4u3LIJ7zNUM0E8='))
        assert result['reference_time'] == '2026-11-05T14:21:00+00:00'
        assert result['feed_update_date']


def test_capacity_briefing_contains_context_and_scope_evidence():
    text = M.estimate_closure_capacity('AZ', 'lmsaCxKAd/C/B4u3LIJ7zNUM0E8=')
    for label in ('Reference Time (UTC):', 'Feed Update (as reported):',
                  'Scope Evidence (description):', 'Per Open General Lane:'):
        assert label in text
    assert 'Munds Park' in text


def test_invalid_fractional_timestamp_not_silently_repaired():
    assert M._parse_time('2026-11-05T14:21:00.Z') is None


if __name__ == '__main__':
    tests = [(name, fn) for name, fn in list(globals().items())
             if name.startswith('test_') and callable(fn)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print('PASS', name)
        except Exception as exc:
            failures += 1
            print('FAIL', name, '\n    ', type(exc).__name__, str(exc)[:400])
    print(f'{len(tests) - failures} of {len(tests)} pass')
    sys.exit(1 if failures else 0)

