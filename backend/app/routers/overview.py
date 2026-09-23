from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.overlay import load_vs_deadlines

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
    planned_sessions: int
    planned_hours: float
    training_elevated: bool
    deadlines: list[OverlayDeadline]
    deadline_count: int
    exam_count: int
    deadline_elevated: bool
    risk: bool


class Overlay(BaseModel):
    weeks: list[OverlayWeek]
    load_per_hour_by_discipline: dict[str, float]
    current_ctl: float
    acwr_threshold: float
    deadline_count_threshold: int
    risk_weeks: list[date]
    note: str


@router.get("/load-vs-deadlines", response_model=Overlay)
def overlay(weeks_back: int = 6, weeks_ahead: int = 10, db: Session = Depends(get_db)):
    return load_vs_deadlines(db, max(0, min(weeks_back, 26)), max(0, min(weeks_ahead, 40)))
