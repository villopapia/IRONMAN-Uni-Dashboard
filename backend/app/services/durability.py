"""Per-sport fitness and durability progression (Training tab).

Per-sport CTL: the same exponentially weighted average intervals.icu uses for
its own CTL - CTL_d = CTL_(d-1) + (load_d - CTL_(d-1)) * (1 - exp(-1/42)) -
run separately on each sport's icu_training_load. That decay reproduces their
total CTL exactly when fed every sport (checked against intervals_wellness
2026-10-11); 1/42, which compute_pmc uses, drifts by about 0.5%. Each line
starts from 0 on the first cached day, so the first ~6 weeks read low. Swim +
bike + run is a little under their CTL because gym and walk load is left out;
ctl_check() reports by how much.

Durability: per week, the longest swim (m), ride (min - rides are indoor, so
there is no distance) and run (km), each against the race-distance target.
From Strava activities, like the run guard, so a session counts as soon as it
is recorded.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..models.activity import Activity
from ..models.intervals import IntervalsActivity, IntervalsWellness
from .intensity import _week_of, _week_starts
from .training_load import ICU_CTL_K as CTL_K

CTL_SPORTS = ("swim", "bike", "run")
CTL_CHECK_DAYS = 30
DURABILITY_WEEKS = 12
# Race targets: (target, unit, how one activity is measured).
TARGETS = {
    "swim": (1900.0, "m", lambda a: (a.distance_km or 0.0) * 1000),
    "bike": (165.0, "min", lambda a: a.duration_min or 0.0),
    "run": (21.1, "km", lambda a: a.distance_km or 0.0),
}


def sport_ctl(daily: dict[date, dict[str, float]], start: date, end: date) -> list[dict]:
    """One row per day from start to end: {"date", "swim", "bike", "run"}, each
    sport's CTL from 0 at `start`. `daily` = load per day per sport."""
    ctl = dict.fromkeys(CTL_SPORTS, 0.0)
    out = []
    day = start
    while day <= end:
        loads = daily.get(day, {})
        for s in CTL_SPORTS:
            ctl[s] += (loads.get(s, 0.0) - ctl[s]) * CTL_K
        out.append({"date": day, **ctl})
        day += timedelta(days=1)
    return out


def longest_by_week(activities: list, weeks: list[date]) -> list[dict]:
    """Per week and sport: the longest single session ({"value", "pct"} of the
    race target), or None when there was none. Never a weekly total."""
    best: dict[tuple[date, str], float] = {}
    for a in activities:
        if a.sport not in TARGETS:
            continue
        value = TARGETS[a.sport][2](a)
        key = (_week_of(a.date.date()), a.sport)
        if value > best.get(key, 0.0):
            best[key] = value
    return [
        {
            "week_start": w,
            **{
                s: {"value": round(best[(w, s)], 1), "pct": round(100 * best[(w, s)] / target)} if (w, s) in best else None
                for s, (target, _, _) in TARGETS.items()
            },
        }
        for w in weeks
    ]


def _daily_loads(db: Session) -> dict[date, dict[str, float]]:
    daily: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for a in db.query(IntervalsActivity).filter(IntervalsActivity.icu_training_load.isnot(None)):
        daily[a.date.date()][a.sport] += a.icu_training_load
    return daily


def ctl_check(db: Session, today: date | None = None) -> dict | None:
    """Swim + bike + run CTL against intervals.icu's own CTL over the last
    CTL_CHECK_DAYS: the largest relative gap. None without data."""
    today = today or date.today()
    daily = _daily_loads(db)
    theirs = {w.date: w.ctl for w in db.query(IntervalsWellness) if w.ctl}
    if not daily or not theirs:
        return None
    since = today - timedelta(days=CTL_CHECK_DAYS)
    gaps = [
        (abs(sum(p[s] for s in CTL_SPORTS) - theirs[p["date"]]) / theirs[p["date"]], p["date"])
        for p in sport_ctl(daily, min(daily), today)
        if p["date"] > since and p["date"] in theirs
    ]
    if not gaps:
        return None
    worst, worst_date = max(gaps)
    return {"max_deviation_pct": round(100 * worst, 1), "worst_date": worst_date, "days": len(gaps)}


def sport_ctl_series(db: Session, days: int = 180, today: date | None = None) -> dict:
    today = today or date.today()
    daily = _daily_loads(db)
    if not daily:
        return {"series": [], "starts_on": None, "check": None}
    start = min(daily)
    since = today - timedelta(days=days)
    return {
        "series": [
            {"date": p["date"], **{s: round(p[s], 1) for s in CTL_SPORTS}}
            for p in sport_ctl(daily, start, today)
            if p["date"] > since
        ],
        "starts_on": start,
        "check": ctl_check(db, today),
    }


def durability(db: Session, today: date | None = None) -> dict:
    weeks = _week_starts(today or date.today(), DURABILITY_WEEKS)
    activities = (
        db.query(Activity)
        .filter(Activity.sport.in_(TARGETS), Activity.date >= datetime.combine(weeks[0], datetime.min.time()))
        .all()
    )
    return {
        "targets": {s: {"target": target, "unit": unit} for s, (target, unit, _) in TARGETS.items()},
        "weeks": longest_by_week(activities, weeks),
    }
