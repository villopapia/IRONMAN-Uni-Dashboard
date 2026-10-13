from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.overlay import load_vs_deadlines
from ..services.plan_volume import current_volume_status

router = APIRouter()


class OverlayDeadline(BaseModel):
    title: str
    kind: str
    due_at: datetime
    module_name: str | None
    status: str


class OverlayWeek(BaseModel):
    week_start: date
    state: str  # past / current / future
    actual_load: float
    projected_load: float | None
    total_load: float | None
    chronic_weekly_load: float
    elevated_above: float | None
    load_ratio: float | None
    planned_load: float
    planned_to_date: float
    planned_sessions: int
    planned_hours: float
    training_elevated: bool
    step_up: bool
    no_deload: bool
    deload: bool
    deadlines: list[OverlayDeadline]
    deadline_count: int
    exam_count: int
    deadline_elevated: bool
    risk: bool


class Overlay(BaseModel):
    weeks: list[OverlayWeek]
    load_source: str
    any_deadlines: bool
    load_per_hour_by_discipline: dict[str, float]
    load_per_hour_fallback: list[str]
    current_ctl: float
    acwr_threshold: float
    deadline_count_threshold: int
    risk_weeks: list[date]
    note: str


class VolumeSport(BaseModel):
    sport: str
    unit: str  # m for swim, min for bike and run
    done: float
    due: float
    week_total: float
    pct_of_due: float | None
    status: str | None  # None while a due session has no plan value
    line: str  # done vs due so far, ready to display
    week_line: str  # done vs the full week's prescription


class VolumeStatus(BaseModel):
    as_of: datetime  # Europe/London wall-clock
    week_start: date
    sports: list[VolumeSport]


@router.get("/volume-status", response_model=VolumeStatus)
def volume(db: Session = Depends(get_db)):
    """This week's swim / bike / run volume done vs due so far (plan/prescribed_sessions.json vs intervals.icu)."""
    return current_volume_status(db)


@router.get("/load-vs-deadlines", response_model=Overlay)
def overlay(weeks_back: int = 6, weeks_ahead: int = 10, db: Session = Depends(get_db)):
    return load_vs_deadlines(db, max(0, min(weeks_back, 26)), max(0, min(weeks_ahead, 40)))
