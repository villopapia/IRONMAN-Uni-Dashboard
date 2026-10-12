"""Intensity distribution and the run injury guard (Training tab).

Intensity: share of HR-zone time that is Low / Mid / High, per week and sport,
from the zone times intervals.icu already computed with its own boundaries
(7 HR zones, set by the threshold HR there). Low = Z1-Z2, Mid = Z3-Z4, High =
Z5+. Shares only, never hours: zone time is recorded time and can exceed
moving time. Bike and run only - swim is left out because the HR zones are
run-derived and wrist HR is unreliable in water.

Run guard: weekly run km (Strava distance, so today's run counts as soon as it
is recorded). Each completed week is compared with the average of the 4 weeks
before it: AMBER above a 20% increase, RED above 30%; no comparison when that
average is under 10 km. The current week is in progress, so it gets km only -
no change and no status until it is complete.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean

from sqlalchemy.orm import Session

from ..models.activity import Activity
from ..models.intervals import IntervalsActivity

LOW_ZONES = 2  # Z1-Z2
MID_ZONES = 2  # Z3-Z4; everything above is High
INTENSITY_SPORTS = ("bike", "run")
WEEKS = 8
RAMP_BASELINE_WEEKS = 4  # a week is compared with the average of this many weeks before it
RAMP_AMBER_PCT = 20.0  # run km above the baseline by more than this = AMBER
RAMP_RED_PCT = 30.0
RAMP_MIN_BASELINE_KM = 10.0  # below this the baseline is no basis for a comparison


def zone_split(zone_secs: list[float | None] | None) -> tuple[float, float, float]:
    """(low, mid, high) seconds from per-zone seconds, Z1 first."""
    z = [s or 0.0 for s in zone_secs or []]
    return sum(z[:LOW_ZONES]), sum(z[LOW_ZONES : LOW_ZONES + MID_ZONES]), sum(z[LOW_ZONES + MID_ZONES :])


def distribution(splits: list[tuple[float, float, float]]) -> dict[str, float] | None:
    """% of total zone time that is low / mid / high; None when there is no zone time."""
    low, mid, high = (sum(s[i] for s in splits) for i in range(3))
    total = low + mid + high
    if not total:
        return None
    low_pct, mid_pct = round(100 * low / total, 1), round(100 * mid / total, 1)
    return {"low": low_pct, "mid": mid_pct, "high": max(0.0, round(100 - low_pct - mid_pct, 1))}


def ramp_flags(weekly_km: list[float]) -> list[dict]:
    """One entry per week from the (RAMP_BASELINE_WEEKS + 1)th on: the baseline
    (mean of the RAMP_BASELINE_WEEKS weeks before it), the % change against it,
    and its status. no_data (change None) when the baseline is under
    RAMP_MIN_BASELINE_KM."""
    out = []
    for i in range(RAMP_BASELINE_WEEKS, len(weekly_km)):
        baseline, km = mean(weekly_km[i - RAMP_BASELINE_WEEKS : i]), weekly_km[i]
        if baseline < RAMP_MIN_BASELINE_KM:
            out.append({"baseline_km": round(baseline, 1), "change_pct": None, "status": "no_data"})
            continue
        change = (km - baseline) * 100 / baseline
        status = "red" if change > RAMP_RED_PCT else "amber" if change > RAMP_AMBER_PCT else "pass"
        out.append({"baseline_km": round(baseline, 1), "change_pct": round(change, 1), "status": status})
    return out


def _week_starts(today: date, n: int) -> list[date]:
    monday = today - timedelta(days=today.weekday())
    return [monday - timedelta(days=7 * i) for i in range(n - 1, -1, -1)]


def _week_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def intensity_distribution(db: Session, today: date | None = None) -> dict:
    weeks = _week_starts(today or date.today(), WEEKS)
    activities = (
        db.query(IntervalsActivity)
        .filter(
            IntervalsActivity.date >= datetime.combine(weeks[0], datetime.min.time()),
            IntervalsActivity.sport.in_(INTENSITY_SPORTS),
        )
        .all()
    )
    splits: dict[tuple[date, str], list] = defaultdict(list)
    for a in activities:
        splits[(_week_of(a.date.date()), a.sport)].append(zone_split(a.hr_zone_secs))

    def over(sports: tuple[str, ...]) -> dict | None:
        return distribution([s for (_, sport), group in splits.items() if sport in sports for s in group])

    return {
        "weeks": [{"week_start": w, **{s: distribution(splits.get((w, s), [])) for s in INTENSITY_SPORTS}} for w in weeks],
        "aggregate": {"all": over(INTENSITY_SPORTS), **{s: over((s,)) for s in INTENSITY_SPORTS}},
        "target_note": "target approx. 75-80% low (Seiler 2010)",
        "caveats": [
            "Zones depend on threshold HR set in intervals.icu",
            "Swim excluded: HR zones are run-derived and wrist HR is unreliable in water",
        ],
    }


def run_ramp(db: Session, today: date | None = None) -> dict:
    # extra leading weeks so the first displayed week has its full baseline
    weeks = _week_starts(today or date.today(), WEEKS + RAMP_BASELINE_WEEKS)
    km: dict[date, float] = defaultdict(float)
    runs = db.query(Activity).filter(Activity.sport == "run", Activity.date >= datetime.combine(weeks[0], datetime.min.time()))
    for a in runs:
        km[_week_of(a.date.date())] += a.distance_km or 0.0
    weekly = [km[w] for w in weeks]
    shown = slice(RAMP_BASELINE_WEEKS, None)
    rows = [{"week_start": w, "km": round(k, 1), **flag} for w, k, flag in zip(weeks[shown], weekly[shown], ramp_flags(weekly))]
    # The last week is still in progress: km only, never a change or a status.
    rows[-1].update(change_pct=None, status="in_progress")
    return {
        "weeks": rows,
        "baseline_weeks": RAMP_BASELINE_WEEKS,
        "amber_above_pct": RAMP_AMBER_PCT,
        "red_above_pct": RAMP_RED_PCT,
        "min_baseline_km": RAMP_MIN_BASELINE_KM,
    }
