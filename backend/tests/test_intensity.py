"""Run from backend/: python -m tests.test_intensity (also pytest-compatible)."""

from app.services.intensity import distribution, ramp_flags, zone_split


def test_zone_split():
    assert zone_split([10, 20, 30, 40, 50, 60, 70]) == (30, 70, 180)  # Z1-Z2 / Z3-Z4 / Z5-Z7
    assert zone_split([100, None, 5]) == (100, 5, 0)  # short list, a null zone
    assert zone_split(None) == (0, 0, 0)
    assert zone_split([]) == (0, 0, 0)


def test_distribution_pct_low():
    assert distribution([(750, 150, 100)]) == {"low": 75.0, "mid": 15.0, "high": 10.0}
    # pooled by time, not an average of per-activity percentages
    assert distribution([(900, 100, 0), (100, 0, 900)]) == {"low": 50.0, "mid": 5.0, "high": 45.0}
    assert distribution([(1, 1, 1)]) == {"low": 33.3, "mid": 33.3, "high": 33.4}  # always sums to 100
    assert distribution([(600, 0, 0)])["low"] == 100.0
    assert distribution([]) is None  # no activities
    assert distribution([(0, 0, 0)]) is None  # activities without zone time: no data, not 0% low


def _flag(previous4, km):
    return ramp_flags([*previous4, km])[0]


def test_ramp_flags():
    steady = [10, 10, 10, 10]
    assert _flag(steady, 12) == {"baseline_km": 10.0, "change_pct": 20.0, "status": "pass"}  # exactly +20% is not above it
    assert _flag(steady, 12.01)["status"] == "amber"
    assert _flag(steady, 13) == {"baseline_km": 10.0, "change_pct": 30.0, "status": "amber"}  # exactly +30% is still amber
    assert _flag(steady, 13.01)["status"] == "red"
    assert _flag([20, 20, 20, 20], 10) == {"baseline_km": 20.0, "change_pct": -50.0, "status": "pass"}  # a drop never flags
    assert _flag(steady, 0)["status"] == "pass"


def test_ramp_baseline_is_the_4_week_average():
    # +160% on the week before (5 km), but only +30% on the 4-week average (10 km)
    assert _flag([15, 10, 10, 5], 13) == {"baseline_km": 10.0, "change_pct": 30.0, "status": "amber"}
    # a big week before does not hide a jump on the average
    assert _flag([5, 5, 10, 20], 14)["status"] == "red"  # baseline 10 -> +40%
    assert _flag([9, 10, 10, 10], 30) == {"baseline_km": 9.8, "change_pct": None, "status": "no_data"}  # average under 10 km
    assert _flag([0, 0, 0, 0], 15)["status"] == "no_data"


def test_ramp_flags_series():
    flags = ramp_flags([10, 10, 10, 10, 12, 20, 5])
    assert [f["baseline_km"] for f in flags] == [10.0, 10.5, 13.0]  # the window rolls forward
    assert [f["status"] for f in flags] == ["pass", "red", "pass"]
    assert ramp_flags([10, 10, 10, 10]) == []  # baseline weeks only: nothing to judge
    assert ramp_flags([12]) == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
