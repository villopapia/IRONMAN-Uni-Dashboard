from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.training_load import compute_pmc, rebuild_daily_loads

router = APIRouter()


class PmcPoint(BaseModel):
    date: date
    load: float
    ctl: float
    atl: float
    tsb: float
    by_sport: dict[str, float]


class PmcResponse(BaseModel):
    series: list[PmcPoint]
    current: PmcPoint | None
    ctl_ramp_7d: float | None  # CTL change over the last 7 days (load units / week)
    first_load_date: date | None
    estimated_sessions: int
    total_sessions: int
    methodology_note: str


@router.get("/pmc", response_model=PmcResponse)
def pmc(days: int = 120, db: Session = Depends(get_db)):
    days = max(14, min(days, 730))
    today = date.today()
    result = compute_pmc(db, start=today - timedelta(days=days - 1), end=today)
    series = result["series"]
    current = series[-1] if series else None
    ramp = (
        round(series[-1]["ctl"] - series[-8]["ctl"], 1) if len(series) >= 8 else None
    )
    return PmcResponse(current=current, ctl_ramp_7d=ramp, **result)


@router.post("/rebuild")
def rebuild(db: Session = Depends(get_db)):
    return {"days_by_sport": rebuild_daily_loads(db)}
