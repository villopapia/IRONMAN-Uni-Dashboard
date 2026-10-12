"""Run from backend/: python -m tests.test_season (also pytest-compatible)."""

from datetime import date, timedelta

from app.services.season import season_status
from app.services.training_load import ICU_CTL_K, project_ctl, ramp_status


def test_expected_values_on_2026_10_11():
    s = season_status(date(2026, 10, 11))
    assert s["race"] == {"name": "IRONMAN 70.3 Jönköping", "date": date(2027, 7, 11)}
    assert (s["days_to_race"], s["weeks_to_race"]) == (273, 39)
    assert s["phase"] == {"name": "Phase 1 Base", "week": 2, "weeks": 4}
    assert s["next_gate"] == {"name": "HM time trial", "date": date(2026, 10, 25), "days": 14}


def test_phase_weeks_count_from_the_monday_of_the_phase_start():
    assert season_status(date(2026, 9, 29))["phase"] is None  # same Mon-Sun week, but the phase starts tomorrow
    assert season_status(date(2026, 9, 30))["phase"]["week"] == 1  # the Wednesday it starts
    assert season_status(date(2026, 10, 4))["phase"]["week"] == 1  # Sunday of that week
    assert season_status(date(2026, 10, 5))["phase"]["week"] == 2  # Monday
    assert season_status(date(2026, 10, 25))["phase"] == {"name": "Phase 1 Base", "week": 4, "weeks": 4}  # last day
    assert season_status(date(2026, 10, 26))["phase"] is None  # no phase configured yet


def test_next_gate():
    assert season_status(date(2026, 10, 25))["next_gate"]["days"] == 0  # gate day itself still counts
    after = season_status(date(2026, 10, 26))["next_gate"]
    assert (after["name"], after["days"]) == ("Sheffield Half", (date(2027, 4, 4) - date(2026, 10, 26)).days)
    assert season_status(date(2027, 4, 5))["next_gate"] is None  # no gates left


def test_countdown_weeks_are_whole_weeks():
    assert [season_status(date(2027, 7, d))[k] for d in (4, 5, 11) for k in ("days_to_race", "weeks_to_race")] == [7, 1, 6, 0, 0, 0]
    assert season_status(date(2027, 7, 12))["weeks_to_race"] == 0  # after the race: never negative weeks


D0 = date(2026, 10, 11)


def _day(n):
    return D0 + timedelta(days=n)


def test_project_ctl():
    k = ICU_CTL_K
    out = project_ctl(40.0, {}, D0, _day(3), k)
    assert [p["date"] for p in out] == [_day(1), _day(2), _day(3)]  # starts the day after, includes the end
    assert abs(out[0]["ctl"] - 40 * (1 - k)) < 1e-12 and abs(out[2]["ctl"] - 40 * (1 - k) ** 3) < 1e-12  # no plan: pure decay
    flat = project_ctl(40.0, {_day(i): 40.0 for i in range(1, 31)}, D0, _day(30), k)
    assert all(abs(p["ctl"] - 40.0) < 1e-9 for p in flat)  # daily load equal to CTL holds it level
    one = project_ctl(0.0, {_day(2): 100.0}, D0, _day(3), k)
    assert one[0]["ctl"] == 0.0 and abs(one[1]["ctl"] - 100 * k) < 1e-12 and abs(one[2]["ctl"] - 100 * k * (1 - k)) < 1e-12
    # load on the start day (already in `ctl`) or after the end is ignored
    assert abs(project_ctl(10.0, {D0: 999.0, _day(2): 999.0}, D0, _day(1), k)[-1]["ctl"] - 10 * (1 - k)) < 1e-12
    assert project_ctl(10.0, {}, D0, D0, k) == []
    rising = [p["ctl"] for p in project_ctl(20.0, {_day(i): 80.0 for i in range(1, 400)}, D0, _day(399), k)]
    assert rising == sorted(rising) and 79.9 < rising[-1] < 80.0  # climbs towards the planned daily load, never past it


def test_ramp_status():
    assert [ramp_status(r) for r in (-3.0, 1.9, 2.0, 6.0, 6.1, 8.0, 8.1)] == ["low", "low", "normal", "normal", "amber", "amber", "red"]
    assert ramp_status(None) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
