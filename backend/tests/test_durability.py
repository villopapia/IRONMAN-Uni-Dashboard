"""Run from backend/: python -m tests.test_durability (also pytest-compatible).
Run as a module it also prints the real-data check of per-sport CTL against
intervals.icu's own CTL."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app.services.durability import CTL_K, CTL_SPORTS, longest_by_week, sport_ctl

D0 = date(2026, 6, 1)  # a Monday


def _day(n):
    return D0 + timedelta(days=n)


def test_ctl_single_session_and_decay():
    rows = sport_ctl({_day(0): {"run": 100.0}}, _day(0), _day(2))
    assert abs(rows[0]["run"] - 100 * CTL_K) < 1e-12  # 2.35 after one 100-load day
    assert abs(rows[1]["run"] - 100 * CTL_K * (1 - CTL_K)) < 1e-12  # then decays by the same factor
    assert rows[0]["swim"] == rows[0]["bike"] == 0.0  # sports are independent
    assert [r["date"] for r in rows] == [_day(0), _day(1), _day(2)]  # one row per day, gaps included


def test_ctl_converges_to_a_constant_daily_load():
    daily = {_day(i): {"bike": 50.0} for i in range(400)}
    assert abs(sport_ctl(daily, _day(0), _day(399))[-1]["bike"] - 50.0) < 0.01
    assert 0.62 < sport_ctl(daily, _day(0), _day(41))[-1]["bike"] / 50.0 < 0.64  # 1 - 1/e after 42 days


def test_ctl_sports_sum_to_the_all_sport_ctl():
    daily = {_day(i): {"swim": 10.0 * (i % 3), "bike": 7.0 * (i % 5), "run": 13.0 * (i % 2), "gym": 99.0} for i in range(60)}
    total = 0.0
    for i in range(60):
        total += (sum(v for s, v in daily[_day(i)].items() if s in CTL_SPORTS) - total) * CTL_K
    last = sport_ctl(daily, _day(0), _day(59))[-1]
    assert abs(sum(last[s] for s in CTL_SPORTS) - total) < 1e-9  # linear: per-sport lines add up; gym is ignored


def _act(day, sport, km=0.0, minutes=0.0):
    return SimpleNamespace(date=datetime.combine(_day(day), datetime.min.time()), sport=sport, distance_km=km, duration_min=minutes)


def test_longest_by_week():
    acts = [
        _act(0, "swim", km=1.0, minutes=25),  # Monday
        _act(2, "swim", km=1.5, minutes=40),  # longest swim of week 1: 1500 m
        _act(3, "bike", minutes=60),
        _act(5, "bike", minutes=120),  # longest ride: by minutes, distance is 0 indoors
        _act(1, "run", km=8.0, minutes=45),
        _act(6, "run", km=16.0, minutes=95),  # Sunday still belongs to week 1
        _act(7, "run", km=21.1, minutes=120),  # next Monday: week 2
        _act(8, "gym", minutes=300),  # not a durability sport
        _act(9, "bike", km=40.0, minutes=0),  # nothing measurable: not a session
    ]
    w1, w2, w3 = longest_by_week(acts, [_day(0), _day(7), _day(14)])
    assert w1["swim"] == {"value": 1500.0, "pct": 79}  # the longest session, not the 2500 m total
    assert w1["bike"] == {"value": 120.0, "pct": 73}
    assert w1["run"] == {"value": 16.0, "pct": 76}
    assert w2["run"] == {"value": 21.1, "pct": 100} and w2["swim"] is None and w2["bike"] is None
    assert w3 == {"week_start": _day(14), "swim": None, "bike": None, "run": None}  # an empty week is no data, not 0%


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
    from app.database import SessionLocal
    from app.services.durability import ctl_check

    print("real data, swim + bike + run CTL vs intervals.icu CTL:", ctl_check(SessionLocal()))
