"""Combined training-load / academic-deadline overlay (spec item 16): one
weekly timeline, flagging weeks where BOTH are elevated - the burnout /
overtraining window, rather than either signal alone.

Documented decisions (heuristics, not facts from the spec):

Training signal, in one unit for every week: intervals.icu training load, or
Strava Relative Effort when USE_ICU_PMC is off (the flag switches actual load,
projection rates and CTL together, so the two scales never mix):
  - past weeks: actual weekly load (sum of daily load).
  - current week: actual so far + the projected load of the planned sessions
    still to come this week.
  - future weeks: projected load = each planned session's calendar duration
    x Chris's own median load-per-hour for that discipline (load /
    moving hours per activity over the last RATE_WINDOW_DAYS, races and
    no-HR activities excluded; the same filters over all history if a
    discipline has < RATE_MIN_SAMPLES such activities; the all-sport median
    if it has < 3 at all). Derived from his data, not a constant - an
    easy trainer ride and a run of the same length score very differently.
    Calendar blocks include changing/transition time, so this over- rather
    than under-states planned load.
  "Usual week" = chronic weekly load (7 x CTL at the start of the week). For
  future weeks CTL is projected forward day by day through the planned load
  (same 42-day EWMA). Weeks with CTL < 5 have no meaningful base.

  A week is flagged (training_elevated) for one of two reasons - see
  training_flags(). The earlier "load >= 1.3 x usual week" rule flagged
  nearly every planned week, because a ramp from a quiet patch is >1.3x
  against a low chronic base for months; that says "the plan is a big jump",
  not which weeks are the problem.
    step_up:   load >= 1.3 x the previous week's load (and >= 0.6 x the usual
               week - relative, so it holds on either load scale).
    no_deload: the 4th+ consecutive week at/above the usual week with no
               deload week (a deload = <= 75% of the prior 3 weeks' peak).
  The 1.3 / 4-week / 75% numbers are common coaching rules of thumb,
  directional, not validated for either load unit.

Deadline signal: deadlines due in that Mon-Sun week (any status - a
submitted assignment still represented work that week). Elevated when >= 2
are due, or any exam. Known limitation: deadline *pressure* also lands in the
run-up week, which this simple count doesn't spread backwards.
"""

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

from sqlalchemy.orm import Session

from ..config import settings
from ..models.academic_tracking import AcademicDeadline
from ..models.activity import Activity
from ..models.intervals import IntervalsActivity
from ..models.performance import PlannedSession
from .compliance import _merge_slots, _slot_hours
from .training_load import load_pmc

ACWR_THRESHOLD = 1.3  # week-over-week step-up factor (name kept for the API field)
MIN_CTL = 5.0
DEADLINE_COUNT_THRESHOLD = 2
MIN_FLAG_FACTOR = 0.6  # a step-up only counts at >= this x the usual week
DELOAD_FACTOR = 0.75
HARD_RUN_WEEKS = 4
RATE_WINDOW_DAYS = 28
RATE_MIN_SAMPLES = 4
# Race = intervals.icu's own race flag where the row has one (IntervalsActivity);
# the name match is the fallback, and all there is for Strava rows.
_RACE_NAME = re.compile(r"marathon|half|race|10k|parkrun|time trial", re.I)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def training_flags(totals: list[float], hard: list[bool], usual: list[float]) -> list[tuple[bool, bool, bool]]:
    """Per week: (step_up, no_deload, deload). `totals` = weekly load (0 when
    unknown), `hard` = week is at/above the usual week, `usual` = the usual
    week's load (0 when there is no meaningful base - never a step-up)."""
    out = []
    run = 0
    for i, t in enumerate(totals):
        prev = totals[i - 1] if i else 0.0
        peak = max(totals[max(0, i - 3):i], default=0.0)
        deload = peak > 0 and t <= DELOAD_FACTOR * peak
        step_up = prev > 0 and usual[i] > 0 and t >= MIN_FLAG_FACTOR * usual[i] and t >= ACWR_THRESHOLD * prev
        run = run + 1 if hard[i] and not deload else 0
        out.append((step_up, run >= HARD_RUN_WEEKS, deload))
    return out


def _self_check() -> None:
    hard = [False, False, True, True, True, True, True, False]
    f = training_flags([100, 100, 300, 300, 300, 300, 300, 200], hard, [250.0] * 8)
    assert [x[0] for x in f] == [False, False, True, False, False, False, False, False]  # one step-up
    assert [x[1] for x in f] == [False] * 5 + [True, True, False]  # 4th+ hard week
    assert f[7][2]  # 200 <= 75% of 300 -> deload
    quiet = [False, False]
    assert not any(training_flags([50, 140], quiet, [250.0] * 2)[1][:2])  # 140 < 0.6 x usual 250
    assert training_flags([50, 140], quiet, [100.0] * 2)[1][0]  # same jump on a smaller scale: flagged
    assert not training_flags([50, 140], quiet, [0.0] * 2)[1][0]  # no base


def rates_from(
    activities: list, today: date, load_field: str = "relative_effort"
) -> tuple[dict[str, float], list[str]]:
    """(rates, fallback sports). Median load (`load_field`: relative_effort on
    Activity, icu_training_load on IntervalsActivity) per moving hour, per
    sport, over scored (load > 0), >= 10 min, non-race activities in the last
    RATE_WINDOW_DAYS. A sport with < RATE_MIN_SAMPLES of those uses the same
    filters over all history instead, and is listed in the fallback sports."""
    since = today - timedelta(days=RATE_WINDOW_DAYS)
    per: dict[str, list[float]] = defaultdict(list)  # all history (fallback)
    recent: dict[str, list[float]] = defaultdict(list)
    for a in activities:
        load = getattr(a, load_field)
        if not load or a.duration_min < 10 or getattr(a, "race", False) or _RACE_NAME.search(a.name):
            continue
        rate = load / (a.duration_min / 60)
        per[a.sport].append(rate)
        if a.date.date() >= since:
            recent[a.sport].append(rate)
    everything = [r for rs in per.values() for r in rs]
    overall = median(everything) if everything else None
    rates = {s: round(median(rs), 1) for s, rs in per.items() if len(rs) >= 3}
    windowed = {s: round(median(rs), 1) for s, rs in recent.items() if len(rs) >= RATE_MIN_SAMPLES}
    fallback = sorted(set(rates) - set(windowed))
    rates.update(windowed)
    if overall is not None:
        rates["_overall"] = round(overall, 1)
    return rates, fallback


def discipline_rates(db: Session, today: date) -> tuple[dict[str, float], list[str]]:
    if settings.use_icu_pmc:
        return rates_from(db.query(IntervalsActivity).all(), today, load_field="icu_training_load")
    return rates_from(db.query(Activity).all(), today)


def load_vs_deadlines(db: Session, weeks_back: int = 6, weeks_ahead: int = 10, today: date | None = None) -> dict:
    today = today or date.today()
    current = _monday(today)
    first = current - timedelta(days=7 * weeks_back)
    end = current + timedelta(days=7 * (weeks_ahead + 1))

    pmc = load_pmc(db, end=today)
    by_day = {p["date"]: p for p in pmc["series"]}
    latest_ctl = pmc["series"][-1]["ctl"] if pmc["series"] else 0.0
    rates, rate_fallback = discipline_rates(db, today)
    overall_rate = rates.get("_overall")

    planned = (
        db.query(PlannedSession)
        .filter(PlannedSession.kind == "session", PlannedSession.date >= first, PlannedSession.date < end)
        .all()
    )
    slots_by_week: dict[date, list[dict]] = defaultdict(list)
    projected_by_day: dict[date, float] = defaultdict(float)
    for slot in _merge_slots(planned):
        slots_by_week[_monday(slot["date"])].append(slot)
        rate = rates.get(slot["discipline"], overall_rate)
        slot["projected_load"] = round(_slot_hours(slot) * rate, 1) if rate is not None else None
        if slot["date"] > today and slot["projected_load"]:
            projected_by_day[slot["date"]] += slot["projected_load"]

    # Project CTL forward from today through the planned load.
    projected_ctl: dict[date, float] = {today: latest_ctl}
    ctl = latest_ctl
    day = today + timedelta(days=1)
    while day < end:
        ctl += (projected_by_day.get(day, 0.0) - ctl) / 42
        projected_ctl[day] = ctl
        day += timedelta(days=1)
    can_project = overall_rate is not None

    deadlines = (
        db.query(AcademicDeadline)
        .filter(
            AcademicDeadline.due_at >= datetime.combine(first, datetime.min.time()),
            AcademicDeadline.due_at < datetime.combine(end, datetime.min.time()),
        )
        .all()
    )
    dl_by_week: dict[date, list[AcademicDeadline]] = defaultdict(list)
    for d in deadlines:
        dl_by_week[_monday(d.due_at.date())].append(d)

    weeks = []
    usual: list[float] = []
    for i in range(weeks_back + weeks_ahead + 1):
        wk = first + timedelta(days=7 * i)
        state = "past" if wk < current else ("current" if wk == current else "future")
        slots = slots_by_week.get(wk, [])
        planned_hours = sum(_slot_hours(s) for s in slots)

        actual = sum(
            by_day[wk + timedelta(days=d)]["load"]
            for d in range(7)
            if (wk + timedelta(days=d)) in by_day and (wk + timedelta(days=d)) <= today
        )
        projected = (
            round(sum(s["projected_load"] or 0.0 for s in slots if s["date"] > today), 1)
            if state != "past"
            else 0.0
        )
        total = actual + projected
        # What the calendar asked for, in the same load unit: the whole week,
        # and the part that should already be done (sessions before today).
        planned_load = round(sum(s["projected_load"] or 0.0 for s in slots), 1)
        planned_to_date = round(sum(s["projected_load"] or 0.0 for s in slots if s["date"] < today), 1)

        ctl_ref_day = wk - timedelta(days=1)
        if ctl_ref_day in by_day:
            ctl = by_day[ctl_ref_day]["ctl"]
        else:
            ctl = projected_ctl.get(ctl_ref_day, 0.0)
        chronic_weekly = round(7 * ctl, 1)
        usual.append(chronic_weekly if ctl >= MIN_CTL else 0.0)
        ratio = round(total / chronic_weekly, 2) if ctl >= MIN_CTL and chronic_weekly else None
        has_signal = state != "future" or (can_project and planned_hours > 0)

        dls = sorted(dl_by_week.get(wk, []), key=lambda d: d.due_at)
        exam_count = sum(1 for d in dls if d.kind == "exam")
        deadline_elevated = len(dls) >= DEADLINE_COUNT_THRESHOLD or exam_count > 0

        weeks.append(
            {
                "week_start": wk,
                "state": state,
                "actual_load": round(actual, 1),
                "projected_load": projected if has_signal else None,
                "total_load": round(total, 1) if has_signal else None,
                "chronic_weekly_load": chronic_weekly,
                "elevated_above": round(chronic_weekly * ACWR_THRESHOLD, 1) if ctl >= MIN_CTL else None,
                "load_ratio": ratio if has_signal else None,
                "planned_load": planned_load,
                "planned_to_date": planned_to_date,
                "planned_sessions": len(slots),
                "planned_hours": round(planned_hours, 1),
                "training_elevated": False,  # set by the flag pass below
                "step_up": False,
                "no_deload": False,
                "deload": False,
                "deadlines": [
                    {
                        "title": d.title,
                        "kind": d.kind,
                        "due_at": d.due_at,
                        "module_name": d.module.name if d.module else None,
                        "status": d.status,
                    }
                    for d in dls
                ],
                "deadline_count": len(dls),
                "exam_count": exam_count,
                "deadline_elevated": deadline_elevated,
                "risk": False,
            }
        )

    totals = [w["total_load"] or 0.0 for w in weeks]
    hard = [w["load_ratio"] is not None and w["load_ratio"] >= 1.0 for w in weeks]
    for w, (step_up, no_deload, deload) in zip(weeks, training_flags(totals, hard, usual)):
        w["step_up"], w["no_deload"], w["deload"] = step_up, no_deload, deload
        w["training_elevated"] = step_up or no_deload
        w["risk"] = w["training_elevated"] and w["deadline_elevated"]

    load_source = "intervals.icu training load" if settings.use_icu_pmc else "Strava Relative Effort"
    return {
        "weeks": weeks,
        "load_source": load_source,
        "load_per_hour_by_discipline": {k: v for k, v in rates.items() if not k.startswith("_")},
        "load_per_hour_fallback": rate_fallback,
        "current_ctl": latest_ctl,
        "acwr_threshold": ACWR_THRESHOLD,
        "deadline_count_threshold": DEADLINE_COUNT_THRESHOLD,
        "risk_weeks": [w["week_start"] for w in weeks if w["risk"]],
        "note": (
            f"Training: weekly {load_source}; future weeks are projected from calendar-planned "
            f"session length x your own load-per-hour for that discipline (median over last "
            f"{RATE_WINDOW_DAYS // 7} weeks, races excluded). Flagged when a week is >= "
            f"{ACWR_THRESHOLD}x the week before (step up), or is the {HARD_RUN_WEEKS}th+ week at/above your usual "
            f"week with no deload. Deadlines: elevated with {DEADLINE_COUNT_THRESHOLD}+ due, or any exam. "
            f"A risk week is both at once. Heuristics, not a diagnosis."
        ),
    }
