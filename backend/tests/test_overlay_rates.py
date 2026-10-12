"""Run from backend/: python -m tests.test_overlay_rates (also pytest-compatible)."""

from datetime import date, datetime

from app.models.activity import Activity
from app.models.intervals import IntervalsActivity
from app.services.overlay import rates_from

TODAY = date(2026, 10, 11)


def _act(day, name, minutes, re_, sport="run"):
    return Activity(name=name, date=datetime(2026, 10, day, 9), sport=sport, duration_min=minutes, relative_effort=re_)


def test_median_ignores_race_and_zero_re():
    acts = [
        _act(1, "Evening Run", 60, 30),  # 30 RE/h
        _act(2, "Morning Run", 60, 36),  # 36
        _act(3, "Morning Run", 60, 40),  # 40
        _act(4, "Evening Run", 30, 25),  # 50
        _act(5, "Winchester Half Marathon", 120, 276),  # race
        _act(6, "Evening Run", 60, 0),  # no HR
        _act(7, "Evening Run", 60, None),
        _act(8, "Shakeout", 5, 20),  # < 600 s
    ]
    rates, fallback = rates_from(acts, TODAY)
    assert rates["run"] == 38.0  # median(30, 36, 40, 50)
    assert fallback == []


def test_falls_back_below_min_samples():
    # 3 qualifying rides (< 4): all-history median, same filters - zero-RE ride excluded
    acts = [_act(d, "Ride", 60, r, "bike") for d, r in [(1, 0), (2, 40), (3, 50), (4, 60)]]
    rates, fallback = rates_from(acts, TODAY)
    assert rates["bike"] == 50.0  # median(40, 50, 60)
    assert fallback == ["bike"]


def test_icu_training_load_field():
    loads = [(1, 40), (2, 50), (3, 60), (4, 70), (5, 0)]  # zero-load ride excluded
    acts = [
        IntervalsActivity(name="Ride", date=datetime(2026, 10, d, 9), sport="bike", duration_min=60, icu_training_load=tl)
        for d, tl in loads
    ]
    rates, fallback = rates_from(acts, TODAY, load_field="icu_training_load")
    assert rates["bike"] == 55.0  # median(40, 50, 60, 70)
    assert fallback == []


if __name__ == "__main__":
    test_median_ignores_race_and_zero_re()
    test_falls_back_below_min_samples()
    test_icu_training_load_field()
    print("ok")
