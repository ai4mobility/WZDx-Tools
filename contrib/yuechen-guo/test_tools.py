"""Check the pedestrian tools against the saved Florida feed."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["WZDX_SNAPSHOT"] = str(HERE.parents[1] / "snapshots" / "2026-11-05")
os.environ["WZDX_NOW"] = "1793888460"
sys.path.insert(0, str(HERE))
import tools as M

AREA = ("FL", "N 30th St", 28.0587, -82.4139, 5.0)
RECORD = "4233451340/245269615"


def _record_line():
    result = M.find_sidewalk_closures(*AREA)
    return next((line for line in result.splitlines() if line.startswith(f"ID {RECORD} |")), "")


def test_estimated_end_time():
    line = _record_line()
    assert "2026-12-15 16:00 EST (estimated)" in line, line


def test_footway_closure_with_unknown_vehicle_impact():
    records = json.loads(M.find_sidewalk_closures_plain(*AREA))["records"]
    record = next(r for r in records if str(r["id"]) == RECORD)
    assert record["vehicle_impact"] == "unknown", record
    assert "Footway closure" in _record_line(), _record_line()


def test_no_walking_directions_reported():
    text = M.get_pedestrian_detour_info("FL", RECORD)
    assert "Linked detour records: 0" in text and "No explicit walking directions" in text, text


def test_no_additional_hazard_described():
    text = M.get_pedestrian_detour_info("FL", RECORD)
    assert "No additional pedestrian hazard" in text and "unconfirmed" in text, text


def test_plain_vs_find_sidewalk_closures():
    plain = json.loads(M.find_sidewalk_closures_plain(*AREA))
    record = next(r for r in plain["records"] if str(r["id"]) == RECORD)
    assert record["end_date"] == "2026-12-15T21:00:00.000+00:00", record
    assert record["is_end_date_verified"] is False, record
    full = M.find_sidewalk_closures(*AREA)
    assert "16:00 EST (estimated)" in _record_line() and "does not confirm" in full, full


if __name__ == "__main__":
    tests = [fn for name, fn in list(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"{len(tests)} of {len(tests)} pass")
