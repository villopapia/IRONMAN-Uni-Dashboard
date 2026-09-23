from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.performance import PlannedSession
from ..schemas.compliance import ComplianceRange, ManualStatusUpdate, WeekCompliance
from ..services.compliance import COMPLIANCE_FLAG_PCT, compliance_range, week_compliance
from ..services.plan_sync import sync_plan

router = APIRouter()

NOTE = (
    f"Planned = emoji-tagged training events in Google Calendar (recurring events "
    f"expanded by Google). Completed = a Strava activity of the same sport on the "
    f"same day, or elsewhere in the same week (\"moved\"). Future sessions are "
    f"pending and excluded from the %. Flagged below {COMPLIANCE_FLAG_PCT:.0f}%. "
    f"Gym sessions only count if recorded on Strava - mark them done by hand otherwise."
)


@router.post("/sync")
def trigger_plan_sync(db: Session = Depends(get_db)):
    try:
        return sync_plan(db)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/weeks", response_model=ComplianceRange)
def weeks(weeks_back: int = 6, weeks_ahead: int = 1, db: Session = Depends(get_db)):
    weeks_back = max(0, min(weeks_back, 52))
    weeks_ahead = max(0, min(weeks_ahead, 26))
    synced = db.query(func.max(PlannedSession.synced_at)).scalar()
    return ComplianceRange(
        weeks=compliance_range(db, weeks_back, weeks_ahead),
        plan_synced_at=synced,
        note=NOTE,
    )


@router.get("/week", response_model=WeekCompliance)
def week(week_start_date: date, db: Session = Depends(get_db)):
    return week_compliance(db, week_start_date)


@router.patch("/sessions")
def set_manual_status(payload: ManualStatusUpdate, db: Session = Depends(get_db)):
    rows = db.query(PlannedSession).filter(PlannedSession.id.in_(payload.ids)).all()
    if not rows:
        raise HTTPException(404, "No matching planned sessions")
    for row in rows:
        row.manual_status = payload.manual_status
    db.commit()
    return {"updated": len(rows)}
