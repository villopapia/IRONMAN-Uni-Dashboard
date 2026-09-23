"""Academic trajectory endpoints, mounted under /api/academic alongside the
existing module / assessment / classification routes."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.academic import AcademicAssessment, AcademicModule
from ..models.academic_tracking import (
    AcademicDeadline,
    ExamPrepItem,
    StudyLog,
    StudyTarget,
    WeightedAverageSnapshot,
)
from ..schemas.academic_tracking import (
    DeadlineCreate,
    DeadlineOut,
    DeadlineUpdate,
    ModulePrep,
    PrepItemCreate,
    PrepItemOut,
    StudyLogCreate,
    StudyLogOut,
    StudySummary,
    StudyTargetCreate,
    WeightedHistory,
)
from ..services.academic_tracking import STUDY_FLAG_PCT, deadline_out, study_weeks
from ..services.classification import FIRST_THRESHOLD, classify

router = APIRouter()


# --- Weighted-average trajectory ---------------------------------------------


@router.get("/history", response_model=WeightedHistory)
def weighted_history(academic_year: str, db: Session = Depends(get_db)):
    snapshots = (
        db.query(WeightedAverageSnapshot)
        .filter(WeightedAverageSnapshot.academic_year == academic_year)
        .order_by(WeightedAverageSnapshot.recorded_on)
        .all()
    )
    modules = (
        db.query(AcademicModule)
        .options(joinedload(AcademicModule.assessments))
        .filter(AcademicModule.academic_year == academic_year)
        .all()
    )
    summary = classify(modules)
    return WeightedHistory(
        academic_year=academic_year,
        snapshots=snapshots,
        first_threshold_pct=FIRST_THRESHOLD,
        current_pct=summary["weighted_average_pct"],
        modules_missing_level_credits=[
            m["name"] for m in summary["modules"] if m.get("needs_level_credits")
        ],
        note=(
            "A point is recorded whenever a mark, FHEQ level or credit value changes "
            "(latest value per day). Modules without a confirmed level + credits are "
            "left out of the average rather than weighted by guesswork."
        ),
    )


# --- Deadlines ---------------------------------------------------------------


def _deadline_query(db: Session):
    return db.query(AcademicDeadline).options(
        joinedload(AcademicDeadline.module), joinedload(AcademicDeadline.assessment)
    )


@router.get("/deadlines", response_model=list[DeadlineOut])
def list_deadlines(include_done: bool = False, past_days: int = 14, db: Session = Depends(get_db)):
    """Sorted by proximity: overdue first, then soonest upcoming. Submitted
    items and anything more than `past_days` in the past are hidden unless
    include_done=true."""
    now = datetime.now()
    rows = _deadline_query(db).all()
    out = []
    for d in rows:
        if not include_done and d.status == "submitted":
            continue
        if not include_done and d.due_at < now - timedelta(days=past_days):
            continue
        out.append(deadline_out(d, now))
    out.sort(key=lambda d: (not d["overdue"], d["due_at"]))
    return out


def _validate_links(db: Session, module_id: int | None, assessment_id: int | None) -> None:
    if module_id is not None and not db.get(AcademicModule, module_id):
        raise HTTPException(404, "Module not found")
    if assessment_id is not None:
        a = db.get(AcademicAssessment, assessment_id)
        if not a:
            raise HTTPException(404, "Assessment not found")
        if module_id is not None and a.module_id != module_id:
            raise HTTPException(400, "Assessment belongs to a different module")


@router.post("/deadlines", response_model=DeadlineOut)
def create_deadline(payload: DeadlineCreate, db: Session = Depends(get_db)):
    _validate_links(db, payload.module_id, payload.assessment_id)
    data = payload.model_dump()
    if data["assessment_id"] and data["module_id"] is None:
        data["module_id"] = db.get(AcademicAssessment, data["assessment_id"]).module_id
    row = AcademicDeadline(**data)
    db.add(row)
    db.commit()
    row = _deadline_query(db).filter(AcademicDeadline.id == row.id).one()
    return deadline_out(row, datetime.now())


@router.patch("/deadlines/{deadline_id}", response_model=DeadlineOut)
def update_deadline(deadline_id: int, payload: DeadlineUpdate, db: Session = Depends(get_db)):
    row = db.get(AcademicDeadline, deadline_id)
    if not row:
        raise HTTPException(404, "Deadline not found")
    data = payload.model_dump(exclude_unset=True)
    _validate_links(db, data.get("module_id", row.module_id), data.get("assessment_id", row.assessment_id))
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    row = _deadline_query(db).filter(AcademicDeadline.id == deadline_id).one()
    return deadline_out(row, datetime.now())


@router.delete("/deadlines/{deadline_id}")
def delete_deadline(deadline_id: int, db: Session = Depends(get_db)):
    row = db.get(AcademicDeadline, deadline_id)
    if not row:
        raise HTTPException(404, "Deadline not found")
    db.delete(row)
    db.commit()
    return {"deleted": deadline_id}


# --- Study hours -------------------------------------------------------------


@router.get("/study", response_model=StudySummary)
def study_summary(weeks: int = 8, db: Session = Depends(get_db)):
    weeks = max(1, min(weeks, 26))
    today = date.today()
    recent = (
        db.query(StudyLog)
        .filter(StudyLog.date >= today - timedelta(days=21))
        .order_by(StudyLog.date.desc(), StudyLog.id.desc())
        .all()
    )
    target = (
        db.query(StudyTarget)
        .filter(StudyTarget.effective_from <= today)
        .order_by(StudyTarget.effective_from.desc(), StudyTarget.id.desc())
        .first()
    )
    return StudySummary(
        weeks=study_weeks(db, weeks - 1, today),
        recent_logs=recent,
        manual_target_hours=target.weekly_hours if target else None,
        flag_threshold_pct=STUDY_FLAG_PCT,
        note=(
            "Target = your weekly target if you've set one, otherwise the hours of "
            "study blocks ([LEC], [DEEP], [ASSIGN], [RECALL], [CONSOL], [REVIEW], "
            "[EXAM], [PP]) in your calendar that week. [APP]/[OUT] blocks don't count. "
            f"Completed weeks under {STUDY_FLAG_PCT:.0f}% are flagged, same as training."
        ),
    )


@router.post("/study/logs", response_model=StudyLogOut)
def log_study(payload: StudyLogCreate, db: Session = Depends(get_db)):
    if payload.module_id is not None and not db.get(AcademicModule, payload.module_id):
        raise HTTPException(404, "Module not found")
    row = StudyLog(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/study/logs/{log_id}")
def delete_study_log(log_id: int, db: Session = Depends(get_db)):
    row = db.get(StudyLog, log_id)
    if not row:
        raise HTTPException(404, "Log not found")
    db.delete(row)
    db.commit()
    return {"deleted": log_id}


@router.post("/study/target")
def set_study_target(payload: StudyTargetCreate, db: Session = Depends(get_db)):
    today = date.today()
    effective = payload.effective_from or (today - timedelta(days=today.weekday()))
    row = StudyTarget(weekly_hours=payload.weekly_hours, effective_from=effective, note=payload.note)
    db.add(row)
    db.commit()
    return {"weekly_hours": row.weekly_hours, "effective_from": row.effective_from}


@router.delete("/study/target")
def clear_study_target(db: Session = Depends(get_db)):
    """Back to calendar-planned hours as the target (all weeks)."""
    n = db.query(StudyTarget).delete()
    db.commit()
    return {"deleted": n}


# --- Exam-prep coverage --------------------------------------------------------


@router.get("/prep", response_model=list[ModulePrep])
def prep_coverage(academic_year: str, db: Session = Depends(get_db)):
    modules = (
        db.query(AcademicModule)
        .filter(AcademicModule.academic_year == academic_year)
        .order_by(AcademicModule.id)
        .all()
    )
    items = (
        db.query(ExamPrepItem)
        .filter(ExamPrepItem.module_id.in_([m.id for m in modules]))
        .order_by(ExamPrepItem.kind, ExamPrepItem.sort_order, ExamPrepItem.id)
        .all()
    )
    by_module: dict[int, list[ExamPrepItem]] = {m.id: [] for m in modules}
    for it in items:
        by_module[it.module_id].append(it)
    out = []
    for m in modules:
        its = by_module[m.id]
        topics = [i for i in its if i.kind == "topic"]
        papers = [i for i in its if i.kind == "past_paper"]
        done = sum(1 for i in its if i.done)
        out.append(
            ModulePrep(
                module_id=m.id,
                module_name=m.name,
                total=len(its),
                done=done,
                pct=round(done / len(its) * 100, 1) if its else None,
                topics_done=sum(1 for i in topics if i.done),
                topics_total=len(topics),
                papers_done=sum(1 for i in papers if i.done),
                papers_total=len(papers),
                items=its,
            )
        )
    return out


@router.post("/prep", response_model=PrepItemOut)
def add_prep_item(payload: PrepItemCreate, db: Session = Depends(get_db)):
    if not db.get(AcademicModule, payload.module_id):
        raise HTTPException(404, "Module not found")
    count = db.query(ExamPrepItem).filter(ExamPrepItem.module_id == payload.module_id).count()
    row = ExamPrepItem(**payload.model_dump(), sort_order=count)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/prep/{item_id}", response_model=PrepItemOut)
def toggle_prep_item(item_id: int, done: bool, db: Session = Depends(get_db)):
    row = db.get(ExamPrepItem, item_id)
    if not row:
        raise HTTPException(404, "Item not found")
    row.done = done
    row.done_on = date.today() if done else None
    db.commit()
    db.refresh(row)
    return row


@router.delete("/prep/{item_id}")
def delete_prep_item(item_id: int, db: Session = Depends(get_db)):
    row = db.get(ExamPrepItem, item_id)
    if not row:
        raise HTTPException(404, "Item not found")
    db.delete(row)
    db.commit()
    return {"deleted": item_id}
