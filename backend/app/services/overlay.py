"""Combined training-load / academic-deadline overlay (spec item 16): one
weekly timeline, flagging weeks where BOTH are elevated - the burnout /
overtraining window, rather than either signal alone.

Documented decisions (heuristics, not facts from the spec):

Training signal, in one unit (Strava Relative Effort load) for every week:
  - past weeks: actual weekly load (sum of daily load).
  - current week: actual so far + the projected load of the planned sessions
    still to come this week.
  - future weeks: projected load = each planned session's calendar duration
    x Chris's own median load-per-hour for that discipline (all history:
    Relative Effort / moving hours per activity; the all-sport median if a
    discipline has < 3 samples). Derived from his data, not a constant - an
    easy trainer ride and a run of the same length score very differently.
    Calendar blocks include changing/transition time, so this over- rather
    than under-states planned load.
  Elevated when the week's load >= 1.3 x the chronic weekly load (7 x CTL at
  the start of the week). For future weeks CTL is projected forward day by
  day through the planned load (same 42-day EWMA), so a week is compared with
  the fitness it will actually be built on, not today's. 1.3 is the
  acute:chronic "spike" threshold commonly cited from Gabbett (2016), applied
  here to Relative-Effort EWMAs - directional, not validated for this scale.
  Weeks with CTL < 5 (no meaningful chronic base) are never flagged.

Deadline signal: deadlines due in that Mon-Sun week (any status - a
submitted assignment still represented work that week). Elevated when >= 2
are due, or any exam. Known limitation: deadline *pressure* also lands in the
run-up week, which this simple count doesn't spread backwards.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..models.academic_tracking import AcademicDeadline
from ..models.activity import Activity
from ..models.performance import DailyTrainingLoad, PlannedSession
from .compliance import _merge_slots
from .training_load import compute_pmc

ACWR_THRESHOLD = 1.3
MIN_CTL = 5.0
DEADLINE_COUNT_THRESHOLD = 2


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _slot_hours(slot: dict) -> float:
    if slot["start_at"] and slot["end_at"] and slot["end_at"] > slot["start_at"]:
        return (slot["end_at"] - slot["start_at"]).total_seconds() / 3600
    return 0.0


def discipline_rates(db: Session) -> dict[str, float]:
    """Median Relative Effort per moving hour, per sport, from all history."""
    from statistics import median

    per: dict[str, list[float]] = defaultdict(list)
    for a in db.query(Activity).filter(Activity.relative_effort.isnot(None)).all():
        if a.duration_min >= 10:
            per[a.sport].append(a.relative_effort / (a.duration_min / 60))
    everything = [r for rs in per.values() for r in rs]
    overall = median(everything) if everything else None
    rates = {s: round(median(rs), 1) for s, rs in per.items() if len(rs) >= 3}
    if overall is not None:
        rates["_overall"] = round(overall, 1)
    return rates


def load_vs_deadlines(db: Session, weeks_back: int = 6, weeks_ahead: int = 10, today: date | None = None) -> dict:
    today = today or date.today()
    current = _monday(today)
    first = current - timedelta(days=7 * weeks_back)
    end = current + timedelta(days=7 * (weeks_ahead + 1))

    pmc = compute_pmc(db, end=today)
    by_day = {p["date"]: p for p in pmc["series"]}
    latest_ctl = pmc["series"][-1]["ctl"] if pmc["series"] else 0.0
    rates = discipline_rates(db)
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

        ctl_ref_day = wk - timedelta(days=1)
        if ctl_ref_day in by_day:
            ctl = by_day[ctl_ref_day]["ctl"]
        else:
            ctl = projected_ctl.get(ctl_ref_day, 0.0)
        chronic_weekly = round(7 * ctl, 1)
        ratio = round(total / chronic_weekly, 2) if ctl >= MIN_CTL and chronic_weekly else None
        has_signal = state != "future" or (can_project and planned_hours > 0)
        training_elevated = bool(ratio is not None and has_signal and ratio >= ACWR_THRESHOLD)

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
                "planned_sessions": len(slots),
                "planned_hours": round(planned_hours, 1),
                "training_elevated": training_elevated,
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
                "risk": training_elevated and deadline_elevated,
            }
        )

    return {
        "weeks": weeks,
        "load_per_hour_by_discipline": {k: v for k, v in rates.items() if not k.startswith("_")},
        "current_ctl": latest_ctl,
        "acwr_threshold": ACWR_THRESHOLD,
        "deadline_count_threshold": DEADLINE_COUNT_THRESHOLD,
        "risk_weeks": [w["week_start"] for w in weeks if w["risk"]],
        "note": (
            f"Training: weekly Relative-Effort load; future weeks are projected from calendar-planned "
            f"session length x your own load-per-hour for that discipline. Elevated at >= {ACWR_THRESHOLD}x "
            f"your chronic weekly load (7 x CTL, projected forward through the plan). Deadlines: elevated "
            f"with {DEADLINE_COUNT_THRESHOLD}+ due, or any exam. A risk week is both at once. "
            f"Heuristics, not a diagnosis."
        ),
    }
