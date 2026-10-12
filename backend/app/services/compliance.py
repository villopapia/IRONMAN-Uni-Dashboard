"""Planned (Google Calendar) vs. completed (Strava) session compliance, per
week and per discipline (spec items 4-6).

Matching rules - documented decisions, not facts from the spec:
 1. Slots. Planned sessions of the same discipline on the same day whose
    times overlap are merged into one slot (the Phase 2 calendar has e.g. two
    06:00 Wednesday swims - one real session can't satisfy both, and neither
    can be done alongside the other). Different disciplines never merge.
 2. Pass 1 - same day: each slot takes the unused Strava activity of the same
    sport on the same day, nearest start time first -> "done".
 3. Pass 2 - moved: any slot still unmatched takes an unused activity of the
    same sport elsewhere in the same Mon-Sun week -> "moved" (counts as done).
 4. Unmatched slots are "missed" once their day is over, "pending" until then
    (pending slots are excluded from the % so a half-finished week isn't
    scored as failing).
 5. Chris's manual override on a slot wins: "done" (e.g. a gym session he
    didn't record on Strava) or "skipped" (counted as not completed).
 6. Leftover activities are reported as unplanned extras; they never push a
    discipline above 100%.
 7. Walks and "other" activities never match anything.

Bricks (spec item 5) are judged per day: a day is a brick day if any planned
slot on it is a brick leg. It's "done" when a Strava run starts after a Strava
bike that day and no later than 60 min after the bike's moving time ends
(moving time <= elapsed time, so this is lenient on long transitions).
"""

import re
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..models.activity import Activity
from ..models.performance import PlannedSession

DISCIPLINES = ["swim", "bike", "run", "gym"]
COMPLIANCE_FLAG_PCT = 80.0
BRICK_MAX_GAP_MIN = 60
STRENGTH_LABELS = {
    "upper_a": "Upper A (push)",
    "upper_b": "Upper B (pull)",
    "mobility": "Mobility / endurance",
    "other": "Other strength",
}
DONE_STATUSES = {"done", "moved", "manual_done"}
# The week's key sessions for the "This week" panel: (weekday, discipline,
# calendar-title pattern, label).
KEY_SESSIONS = [
    (1, "run", re.compile(r"threshold|tempo", re.I), "Tue threshold / tempo run"),
    (2, "bike", re.compile(r".", re.I), "Wed key bike"),  # any Wednesday bike
    (5, "bike", re.compile(r"long", re.I), "Sat long bike"),
    (5, "run", re.compile(r"brick", re.I), "Sat brick run"),
    (6, "run", re.compile(r"long", re.I), "Sun long run"),
]


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _slot_hours(slot: dict) -> float:
    if slot["start_at"] and slot["end_at"] and slot["end_at"] > slot["start_at"]:
        return (slot["end_at"] - slot["start_at"]).total_seconds() / 3600
    return 0.0


def _merge_slots(planned: list[PlannedSession]) -> list[dict]:
    planned = sorted(
        planned, key=lambda p: (p.date, p.discipline or "", p.start_at or datetime.min)
    )
    slots: list[dict] = []
    for p in planned:
        last = slots[-1] if slots else None
        if (
            last
            and last["date"] == p.date
            and last["discipline"] == p.discipline
            and p.start_at is not None
            and last["end_at"] is not None
            and p.start_at < last["end_at"]
        ):
            last["ids"].append(p.id)
            last["titles"].append(p.title)
            last["end_at"] = max(last["end_at"], p.end_at or last["end_at"])
            last["is_brick"] = last["is_brick"] or p.is_brick
            last["manual_statuses"].append(p.manual_status)
            continue
        slots.append(
            {
                "ids": [p.id],
                "date": p.date,
                "discipline": p.discipline,
                "start_at": p.start_at,
                "end_at": p.end_at,
                "titles": [p.title],
                "is_brick": p.is_brick,
                "strength_type": p.strength_type,
                "manual_statuses": [p.manual_status],
            }
        )
    for s in slots:
        ms = s.pop("manual_statuses")
        s["manual_status"] = "done" if "done" in ms else ("skipped" if "skipped" in ms else None)
    return slots


def _is_back_to_back(bike: Activity, run: Activity) -> bool:
    bike_end = bike.date + timedelta(minutes=bike.duration_min)
    return bike.date <= run.date <= bike_end + timedelta(minutes=BRICK_MAX_GAP_MIN)


def _brick_days(slots: list[dict], acts_by_day: dict[date, list[Activity]], today: date) -> list[dict]:
    days = sorted({s["date"] for s in slots if s["is_brick"]})
    out = []
    for d in days:
        day_slots = [s for s in slots if s["date"] == d and s["discipline"] in ("bike", "run")]
        manual_done = day_slots and all(s["manual_status"] == "done" for s in day_slots)
        bikes = [a for a in acts_by_day.get(d, []) if a.sport == "bike"]
        runs = [a for a in acts_by_day.get(d, []) if a.sport == "run"]
        pair = next(
            ((b, r) for b in bikes for r in runs if _is_back_to_back(b, r)), None
        )
        if pair or manual_done:
            state = "done"
        elif bikes and runs:
            state = "split"  # both legs done, but not back-to-back
        elif bikes or runs:
            state = "partial" if d < today else "in_progress"
        else:
            state = "missed" if d < today else "pending"
        out.append(
            {
                "date": d,
                "status": state,
                "titles": [t for s in day_slots for t in s["titles"]],
                "bike_activity": pair[0].name if pair else (bikes[0].name if bikes else None),
                "run_activity": pair[1].name if pair else (runs[0].name if runs else None),
            }
        )
    return out


def week_compliance(db: Session, week_start: date, today: date | None = None) -> dict:
    today = today or date.today()
    week_start = _monday(week_start)
    week_end = week_start + timedelta(days=7)

    planned = (
        db.query(PlannedSession)
        .filter(
            PlannedSession.kind == "session",
            PlannedSession.date >= week_start,
            PlannedSession.date < week_end,
        )
        .all()
    )
    activities = (
        db.query(Activity)
        .filter(
            Activity.date >= datetime.combine(week_start, datetime.min.time()),
            Activity.date < datetime.combine(week_end, datetime.min.time()),
        )
        .order_by(Activity.date)
        .all()
    )
    matchable = [a for a in activities if a.sport in DISCIPLINES]
    acts_by_day: dict[date, list[Activity]] = defaultdict(list)
    for a in matchable:
        acts_by_day[a.date.date()].append(a)

    slots = _merge_slots(planned)
    used: set[int] = set()

    def _nearest(candidates: list[Activity], slot: dict) -> Activity | None:
        free = [a for a in candidates if a.id not in used]
        if not free:
            return None
        ref = slot["start_at"] or datetime.combine(slot["date"], datetime.min.time())
        return min(free, key=lambda a: abs((a.date - ref).total_seconds()))

    # Pass 1: same day.
    for slot in sorted(slots, key=lambda s: (s["date"], s["start_at"] or datetime.min)):
        slot["status"] = None
        slot["activity"] = None
        if slot["manual_status"]:
            continue
        cands = [a for a in acts_by_day.get(slot["date"], []) if a.sport == slot["discipline"]]
        match = _nearest(cands, slot)
        if match:
            used.add(match.id)
            slot["status"], slot["activity"] = "done", match

    # Pass 2: moved within the week.
    for slot in sorted(slots, key=lambda s: (s["date"], s["start_at"] or datetime.min)):
        if slot["status"] or slot["manual_status"]:
            continue
        cands = [a for a in matchable if a.sport == slot["discipline"]]
        match = _nearest(cands, slot)
        if match:
            used.add(match.id)
            slot["status"], slot["activity"] = "moved", match

    for slot in slots:
        if slot["manual_status"] == "done":
            slot["status"] = "manual_done"
        elif slot["manual_status"] == "skipped":
            slot["status"] = "skipped"
        elif slot["status"] is None:
            slot["status"] = "missed" if slot["date"] < today else "pending"

    def _rollup(group: list[dict]) -> dict:
        due = [s for s in group if s["status"] != "pending"]
        completed = sum(1 for s in due if s["status"] in DONE_STATUSES)
        pct = round(completed / len(due) * 100, 1) if due else None
        return {
            "planned": len(group),
            "due": len(due),
            "completed": completed,
            "pending": len(group) - len(due),
            "pct": pct,
            "flag": pct is not None and pct < COMPLIANCE_FLAG_PCT,
        }

    by_discipline = {}
    for d in DISCIPLINES:
        group = [s for s in slots if s["discipline"] == d]
        roll = _rollup(group)
        roll["extras"] = sum(
            1 for a in matchable if a.sport == d and a.id not in used
        )
        by_discipline[d] = roll

    strength = {}
    for st, label in STRENGTH_LABELS.items():
        group = [s for s in slots if s["discipline"] == "gym" and s["strength_type"] == st]
        if group:
            strength[st] = {"label": label, **_rollup(group)}

    bricks = _brick_days(slots, acts_by_day, today)
    brick_due = [b for b in bricks if b["status"] not in ("pending", "in_progress")]
    brick_done = sum(1 for b in brick_due if b["status"] == "done")

    overall = _rollup(slots)
    return {
        "week_start": week_start,
        "has_plan": bool(slots),
        "overall": overall,
        "by_discipline": by_discipline,
        "strength": strength,
        "bricks": {
            "days": bricks,
            "planned": len(bricks),
            "completed": brick_done,
            "pct": round(brick_done / len(brick_due) * 100, 1) if brick_due else None,
            "flag": bool(brick_due) and brick_done < len(brick_due),
        },
        "sessions": [
            {
                "ids": s["ids"],
                "date": s["date"],
                "start_at": s["start_at"],
                "discipline": s["discipline"],
                "titles": s["titles"],
                "is_brick": s["is_brick"],
                "strength_type": s["strength_type"],
                "status": s["status"],
                "manual_status": s["manual_status"],
                "activity_name": s["activity"].name if s["activity"] else None,
                "activity_date": s["activity"].date if s["activity"] else None,
            }
            for s in sorted(slots, key=lambda s: (s["date"], s["start_at"] or datetime.min))
        ],
        "extras": [
            {"name": a.name, "date": a.date, "sport": a.sport, "duration_min": round(a.duration_min, 1)}
            for a in matchable
            if a.id not in used
        ],
        "flag_threshold_pct": COMPLIANCE_FLAG_PCT,
    }


def compliance_range(db: Session, weeks_back: int, weeks_ahead: int, today: date | None = None) -> list[dict]:
    today = today or date.today()
    current = _monday(today)
    return [
        week_compliance(db, current + timedelta(days=7 * i), today)
        for i in range(-weeks_back, weeks_ahead + 1)
    ]


def key_session_rows(slots: list[dict], done: set[tuple[date, str]], week_start: date, today: date) -> list[dict]:
    """One row per KEY_SESSIONS entry. `done` = (day, sport) pairs with a recorded
    activity. done if a same-sport activity exists that day, missed once the day
    has passed without one, pending until then; not_planned when no calendar
    event that day matches the title pattern."""
    rows = []
    for weekday, discipline, pattern, label in KEY_SESSIONS:
        day = week_start + timedelta(days=weekday)
        slot = next(
            (
                s
                for s in slots
                if s["date"] == day
                and s["discipline"] == discipline
                and any(pattern.search(t) for t in s["titles"])
            ),
            None,
        )
        if slot is None:
            status = "not_planned"
        elif (day, discipline) in done:
            status = "done"
        else:
            status = "missed" if day < today else "pending"
        rows.append(
            {
                "label": label,
                "date": day,
                "title": slot["titles"][0] if slot else None,
                "discipline": discipline,
                "status": status,
            }
        )
    return rows


def this_week(db: Session, today: date | None = None) -> dict:
    """Current Mon-Sun week: key sessions, and minutes done vs planned per sport
    (planned = calendar event duration, done = moving time)."""
    today = today or date.today()
    week_start = _monday(today)
    week_end = week_start + timedelta(days=7)
    planned = (
        db.query(PlannedSession)
        .filter(PlannedSession.kind == "session", PlannedSession.date >= week_start, PlannedSession.date < week_end)
        .all()
    )
    activities = (
        db.query(Activity)
        .filter(
            Activity.date >= datetime.combine(week_start, datetime.min.time()),
            Activity.date < datetime.combine(week_end, datetime.min.time()),
        )
        .all()
    )
    slots = _merge_slots(planned)
    return {
        "week_start": week_start,
        "key_sessions": key_session_rows(slots, {(a.date.date(), a.sport) for a in activities}, week_start, today),
        "minutes": {
            sport: {
                "planned": round(sum(_slot_hours(s) for s in slots if s["discipline"] == sport) * 60),
                "done": round(sum(a.duration_min for a in activities if a.sport == sport)),
            }
            for sport in ("swim", "bike", "run")
        },
    }
