"""Training load: one per-session load number, rolled up per day, and the
Coggan-style Performance Management Chart (CTL / ATL / TSB) computed on read.

== The load formula (settled once, used for every discipline) ==

Per-session load = Strava Relative Effort (the API's `suffer_score`).

Why not a hand-rolled Banister/Edwards TRIMP: both need Chris's max HR and
resting-HR baseline to compute %HRR zone weights, and there is no
Chris-confirmed max HR. The only numbers available are Garmin's configured
max HR (205, never confirmed by Chris) or 220-age - using either would bake
an unverified constant into every CTL/ATL value. Relative Effort is Strava's
own HR-zone-weighted duration score (conceptually a TRIMP), computed
server-side from the zones on Chris's Strava profile, and it's present on
100% of his activities (checked 2026-09-23: runs, rides, swims, walks, gym,
HIIT). Using it for *every* sport keeps swim/bike/run loads on one scale -
there are no separate per-discipline TSS variants to drift apart.

Known limitation: swim load inherits wrist-HR-in-water noise, and all sports
share one set of HR zones, so a swim and a run at the same HR score the same.

Fallback (only when an activity has no Relative Effort, e.g. a manual entry
with no HR): duration_min x Chris's own median Relative-Effort-per-minute for
that sport (activities >= 10 min with a real score; the all-sport median if
the sport has < 3 samples). It's derived from his own data rather than a
guessed constant, and every fallback session is counted and surfaced in the
API (`estimated_sessions`) so it's never silently mixed in.

== CTL / ATL / TSB ==

Standard exponentially-weighted moving averages, computed from the stored
daily loads on every read (never stored, so they can't drift):
    CTL_d = CTL_(d-1) + (load_d - CTL_(d-1)) / 42     (fitness)
    ATL_d = ATL_(d-1) + (load_d - ATL_(d-1)) / 7      (fatigue)
    TSB_d = CTL_(d-1) - ATL_(d-1)                     (form, prior-day convention)
Both start at 0 on the first day with any activity, so CTL reads low for
roughly the first six weeks of history - the response carries that date.
"""

from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.activity import Activity
from ..models.performance import DailyTrainingLoad

CTL_DAYS = 42
ATL_DAYS = 7
FALLBACK_MIN_DURATION = 10.0
FALLBACK_MIN_SAMPLES = 3

METHODOLOGY_NOTE = (
    "Load = Strava Relative Effort per session (Strava's own HR-zone-weighted "
    "score, the same scale for swim, bike, run and gym) - used instead of a "
    "hand-rolled TRIMP because that needs a confirmed max HR we don't have. "
    "CTL = 42-day and ATL = 7-day exponentially-weighted averages of daily "
    "load; TSB = yesterday's CTL - ATL. Sessions without a Relative Effort "
    "score use your own median effort-per-minute for that sport x duration, "
    "and are counted as estimated."
)


def _fallback_rates(activities: list[Activity]) -> tuple[dict[str, float], float | None]:
    per_sport: dict[str, list[float]] = defaultdict(list)
    for a in activities:
        if a.relative_effort is not None and a.duration_min >= FALLBACK_MIN_DURATION:
            per_sport[a.sport].append(a.relative_effort / a.duration_min)
    all_rates = [r for rates in per_sport.values() for r in rates]
    overall = median(all_rates) if all_rates else None
    return (
        {s: median(r) for s, r in per_sport.items() if len(r) >= FALLBACK_MIN_SAMPLES},
        overall,
    )


def session_load(a: Activity, rates: dict[str, float], overall: float | None) -> tuple[float | None, bool]:
    """(load, estimated)."""
    if a.relative_effort is not None:
        return float(a.relative_effort), False
    rate = rates.get(a.sport, overall)
    if rate is None:
        return None, True
    return a.duration_min * rate, True


def rebuild_daily_loads(db: Session) -> int:
    activities = db.query(Activity).all()
    rates, overall = _fallback_rates(activities)

    agg: dict[tuple[date, str], dict] = {}
    for a in activities:
        load, estimated = session_load(a, rates, overall)
        if load is None:
            continue
        key = (a.date.date(), a.sport)
        row = agg.setdefault(key, {"load": 0.0, "sessions": 0, "estimated_sessions": 0})
        row["load"] += load
        row["sessions"] += 1
        row["estimated_sessions"] += int(estimated)

    def _write() -> None:
        db.query(DailyTrainingLoad).delete()
        for (day, sport), row in agg.items():
            db.add(DailyTrainingLoad(date=day, sport=sport, **row))
        db.commit()

    try:
        _write()
    except IntegrityError:
        db.rollback()
        _write()
    return len(agg)


def compute_pmc(db: Session, start: date | None = None, end: date | None = None) -> dict:
    end = end or date.today()
    rows = db.query(DailyTrainingLoad).order_by(DailyTrainingLoad.date).all()
    if not rows:
        return {
            "series": [],
            "first_load_date": None,
            "estimated_sessions": 0,
            "total_sessions": 0,
            "methodology_note": METHODOLOGY_NOTE,
        }

    by_day: dict[date, dict[str, float]] = defaultdict(dict)
    for r in rows:
        by_day[r.date][r.sport] = by_day[r.date].get(r.sport, 0.0) + r.load
    first = rows[0].date

    series = []
    ctl = atl = 0.0
    day = first
    while day <= end:
        sports = by_day.get(day, {})
        load = sum(sports.values())
        tsb = ctl - atl  # prior-day values, before today's update
        ctl += (load - ctl) / CTL_DAYS
        atl += (load - atl) / ATL_DAYS
        if start is None or day >= start:
            series.append(
                {
                    "date": day,
                    "load": round(load, 1),
                    "ctl": round(ctl, 1),
                    "atl": round(atl, 1),
                    "tsb": round(tsb, 1),
                    "by_sport": {s: round(v, 1) for s, v in sports.items()},
                }
            )
        day += timedelta(days=1)

    return {
        "series": series,
        "first_load_date": first,
        "estimated_sessions": sum(r.estimated_sessions for r in rows),
        "total_sessions": sum(r.sessions for r in rows),
        "methodology_note": METHODOLOGY_NOTE,
    }
