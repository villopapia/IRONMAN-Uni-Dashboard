"""Academic trajectory: weighted-average history, deadlines, study-hours
compliance and exam-prep coverage (spec items 12-15)."""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..models.academic import AcademicModule
from ..models.academic_tracking import StudyLog, StudyTarget, WeightedAverageSnapshot
from ..models.performance import PlannedSession
from .classification import classify

STUDY_FLAG_PCT = 80.0  # same threshold as training compliance, for consistency


def snapshot_weighted_average(db: Session, academic_year: str) -> WeightedAverageSnapshot | None:
    """Record today's weighted average for the year (one row per day, latest
    recompute wins). Called whenever a mark / level / credit value changes,
    so the series only moves when the number actually does. Nothing is
    stored while there's no graded work - a null isn't a data point."""
    modules = (
        db.query(AcademicModule)
        .options(joinedload(AcademicModule.assessments))
        .filter(AcademicModule.academic_year == academic_year)
        .all()
    )
    result = classify(modules)
    if result["weighted_average_pct"] is None:
        return None
    counted = sum(
        1 for m in result["modules"] if m["mark_pct"] is not None and not m.get("needs_level_credits")
    )
    today = date.today()
    fields = dict(
        weighted_average_pct=round(result["weighted_average_pct"], 2),
        classification_estimate=result["classification_estimate"],
        modules_counted=counted,
    )
    row = (
        db.query(WeightedAverageSnapshot)
        .filter_by(academic_year=academic_year, recorded_on=today)
        .first()
    )
    if row is None:
        row = WeightedAverageSnapshot(academic_year=academic_year, recorded_on=today, **fields)
        db.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = (
            db.query(WeightedAverageSnapshot)
            .filter_by(academic_year=academic_year, recorded_on=today)
            .first()
        )
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
    return row


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _target_for_week(targets: list[StudyTarget], week_start: date) -> StudyTarget | None:
    applicable = [t for t in targets if t.effective_from <= week_start + timedelta(days=6)]
    return max(applicable, key=lambda t: (t.effective_from, t.id)) if applicable else None


def study_weeks(db: Session, weeks_back: int = 7, today: date | None = None) -> list[dict]:
    """Logged study hours per Mon-Sun week vs. a target. Target = Chris's own
    weekly target if set (effective-dated), otherwise the total length of the
    bracket-tagged study blocks ([LEC], [DEEP], [ASSIGN], [RECALL], [CONSOL],
    [REVIEW], [EXAM], [PP]) in his Google Calendar that week."""
    today = today or date.today()
    current = _monday(today)
    first = current - timedelta(days=7 * weeks_back)
    end = current + timedelta(days=7)

    logs = db.query(StudyLog).filter(StudyLog.date >= first, StudyLog.date < end).all()
    logged: dict[date, float] = defaultdict(float)
    for log in logs:
        logged[_monday(log.date)] += log.hours

    blocks = (
        db.query(PlannedSession)
        .filter(PlannedSession.kind == "study", PlannedSession.date >= first, PlannedSession.date < end)
        .all()
    )
    planned: dict[date, float] = defaultdict(float)
    for b in blocks:
        if b.start_at and b.end_at and b.end_at > b.start_at:
            planned[_monday(b.date)] += (b.end_at - b.start_at).total_seconds() / 3600

    targets = db.query(StudyTarget).all()
    out = []
    for i in range(weeks_back + 1):
        wk = first + timedelta(days=7 * i)
        manual = _target_for_week(targets, wk)
        if manual:
            target, source = manual.weekly_hours, "manual"
        elif planned.get(wk):
            target, source = round(planned[wk], 1), "calendar"
        else:
            target, source = None, None
        hours = round(logged.get(wk, 0.0), 1)
        # The current week is still in progress - pro-rate nothing, just don't flag it yet.
        in_progress = wk == current
        pct = round(hours / target * 100, 1) if target else None
        out.append(
            {
                "week_start": wk,
                "logged_hours": hours,
                "target_hours": target,
                "target_source": source,
                "calendar_planned_hours": round(planned.get(wk, 0.0), 1),
                "pct": pct,
                "in_progress": in_progress,
                "flag": pct is not None and pct < STUDY_FLAG_PCT and not in_progress,
            }
        )
    return out


def deadline_out(d, now: datetime) -> dict:
    weight = d.weight_pct
    if weight is None and d.assessment is not None:
        weight = d.assessment.weight_pct
    delta = d.due_at - now
    return {
        "id": d.id,
        "module_id": d.module_id,
        "module_name": d.module.name if d.module else None,
        "assessment_id": d.assessment_id,
        "assessment_name": d.assessment.name if d.assessment else None,
        "title": d.title,
        "due_at": d.due_at,
        "kind": d.kind,
        "weight_pct": weight,
        "status": d.status,
        "note": d.note,
        "days_until": round(delta.total_seconds() / 86400, 1),
        "overdue": delta.total_seconds() < 0 and d.status == "pending",
    }
