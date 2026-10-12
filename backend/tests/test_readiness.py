"""Run from backend/: python -m tests.test_readiness (also pytest-compatible)."""

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - registers every table on Base
from app.database import Base
from app.models.intervals import IntervalsWellness
from app.services.readiness import (
    ACTIONS,
    average,
    hrv_band,
    hrv_status,
    hrv_windows,
    overall_action,
    readiness,
    recovery_trend,
    rhr_status,
    sleep_status,
    weight_status,
)


def test_average_needs_four_readings():
    assert average([50, None, 52, None, 54, None, None]) is None  # 3 of 7
    assert average([50, None, 52, None, 54, 56, None]) == 53
    assert average([None] * 7) is None


def test_rhr_bands():
    assert rhr_status(54.0) == "pass"
    assert rhr_status(54.99) == "pass"
    assert rhr_status(55.0) == "amber"
    assert rhr_status(57.99) == "amber"
    assert rhr_status(58.0) == "red"
    assert rhr_status(None) == "no_data"


def test_sleep_bands():
    assert sleep_status(7.5) == "pass"
    assert sleep_status(7.49) == "amber"
    assert sleep_status(7.0) == "amber"
    assert sleep_status(6.99) == "red"
    assert sleep_status(None) == "no_data"


def test_hrv_band_coverage():
    assert hrv_band([40.0, 50.0] * 15) is not None
    assert hrv_band([45.0] * 15 + [None] * 15) is not None  # exactly 50% missing still counts
    assert hrv_band([45.0] * 14 + [None] * 16) is None  # more than 50% missing
    assert hrv_band([None] * 30) is None
    low, high = hrv_band([40.0, 50.0] * 15)
    assert abs((low + high) / 2 - 45) < 1e-9 and abs((high - low) / 2 - 5.0855) < 1e-3  # mean 45 +/- sample SD


def test_hrv_baseline_excludes_the_days_judged():
    # 2 older days (ignored), 30 baseline days, then the 3 days being judged
    daily = [99.0, 99.0] + [40.0, 50.0] * 15 + [20.0, 20.0, 20.0]
    baseline, recent = hrv_windows(daily)
    assert baseline == [40.0, 50.0] * 15 and recent == [20.0, 20.0, 20.0]
    low, high = hrv_band(baseline)
    assert abs((low + high) / 2 - 45) < 1e-9  # the three 20s did not drag the band down
    assert hrv_status(recent, (low, high)) == "red"
    assert hrv_band(hrv_windows([45.0] * 14 + [None] * 16 + [45.0] * 3)[0]) is None  # recent days don't count as coverage


def test_hrv_status():
    band = (40.0, 50.0)
    assert hrv_status([40.0, 45.0, 60.0], band) == "pass"  # on the lower edge, inside, above
    assert hrv_status([39.9, 45.0, 45.0], band) == "amber"  # 1 below
    assert hrv_status([39.9, 39.0, 45.0], band) == "amber"  # 2 below
    assert hrv_status([39.9, 39.0, 30.0], band) == "red"  # all 3 below
    assert hrv_status([45.0, None, 45.0], band) == "no_data"  # a missing day is never a pass
    assert hrv_status([30.0, 30.0, None], band) == "no_data"  # ...and never a red
    assert hrv_status([45.0, 45.0, 45.0], None) == "no_data"  # no baseline


def test_weight():
    few = [None] * 11 + [61.0, 61.0, 61.0]
    assert weight_status(few) is None  # 3 readings: row hidden
    enough = [None] * 10 + [70.0, 61.0, 61.0]
    assert weight_status(enough + [62.5]) == "pass"  # upper edge
    assert weight_status(enough + [59.5]) == "pass"  # lower edge
    assert weight_status(enough + [62.6]) == "amber"
    assert weight_status(enough + [59.4]) == "amber"


def test_overall_action():
    go, fix_one, recover = ACTIONS
    assert overall_action(["pass", "pass", "pass"]) == go
    assert overall_action(["pass", "amber", "amber"]) == go  # amber alone changes nothing
    assert overall_action(["red", "amber", "pass"]) == fix_one
    assert overall_action(["red", "red", "pass"]) == recover
    assert overall_action(["red", "red", "red", "amber"]) == recover
    assert overall_action(["no_data", "pass", "pass"]) == go  # missing data is not a red
    assert overall_action(["red", "no_data", "no_data"]) == fix_one
    assert overall_action(["no_data", "no_data", "no_data"]) == "No data"  # ...and never a pass


def test_recovery_trend_reports_the_readiness_statuses():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    today = date(2026, 10, 12)
    for i in range(45):  # last 7 days at 60 bpm, last 3 days of HRV far under a 45/55 baseline
        hrv = 30.0 if i < 3 else 45.0 + 10 * (i % 2)
        db.add(IntervalsWellness(date=today - timedelta(days=i), resting_hr=60.0 if i < 7 else 50.0, hrv=hrv, sleep_secs=8 * 3600))
    db.commit()
    ready = {m["key"]: m for m in readiness(db, today)["metrics"]}
    trend = recovery_trend(db, 42, today)
    assert trend["rhr"]["status"] == ready["rhr"]["status"] == "red"
    assert trend["hrv"]["status"] == ready["hrv"]["status"] == "red"
    assert trend["hrv"]["band"] == ready["hrv"]["band"] and trend["rhr"]["value"] == ready["rhr"]["value"] == 60.0
    assert len(trend["series"]) == 42
    assert trend["series"][-1] == {"date": today, "hrv": 30.0, "rhr": 60.0, "rhr_7d": 60.0}
    assert trend["series"][-8]["rhr_7d"] == 50.0  # the day before the jump: its own trailing 7 days


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
