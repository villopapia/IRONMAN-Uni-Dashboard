"""Run from backend/: python -m tests.test_this_week (also pytest-compatible)."""

from datetime import date, timedelta

from app.services.compliance import key_session_rows

MON = date(2026, 10, 5)


def _day(n):
    return MON + timedelta(days=n)


def _slot(day, discipline, title):
    return {"date": _day(day), "discipline": discipline, "titles": [title]}


def test_key_session_status():
    slots = [
        _slot(1, "run", "🏃 Tempo Run"),
        _slot(2, "swim", "🏊 Technique Swim"),  # not the Wednesday key bike
        _slot(2, "bike", "🚴 Z2 + Cadence"),  # any Wednesday bike is the key bike
        _slot(5, "bike", "🚴 Long Bike → Brick"),
        _slot(5, "run", "🔗 Brick Run"),
        _slot(6, "run", "🏃 Long Run"),
    ]
    done = {(_day(1), "run"), (_day(5), "bike"), (_day(5), "swim")}  # a swim doesn't cover the brick run
    rows = key_session_rows(slots, done, MON, today=_day(6))
    assert [r["status"] for r in rows] == ["done", "missed", "done", "missed", "pending"]
    assert rows[1]["title"] == "🚴 Z2 + Cadence"
    # no Wednesday bike in the calendar at all -> not_planned
    assert key_session_rows(slots[:2], done, MON, today=_day(6))[1]["status"] == "not_planned"


if __name__ == "__main__":
    test_key_session_status()
    print("ok")
