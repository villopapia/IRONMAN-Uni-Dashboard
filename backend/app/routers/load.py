from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.intensity import intensity_distribution, run_ramp
from ..services.training_load import load_pmc, rebuild_daily_loads

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
    result = load_pmc(db, start=today - timedelta(days=days - 1), end=today)
    series = result["series"]
    current = series[-1] if series else None
    ramp = (
        round(series[-1]["ctl"] - series[-8]["ctl"], 1) if len(series) >= 8 else None
    )
    return PmcResponse(current=current, ctl_ramp_7d=ramp, **result)


@router.post("/rebuild")
def rebuild(db: Session = Depends(get_db)):
    return {"days_by_sport": rebuild_daily_loads(db)}


class ZoneShare(BaseModel):
    low: float  # % of HR-zone time
    mid: float
    high: float


class IntensityWeek(BaseModel):
    week_start: date
    bike: ZoneShare | None  # None = no zone time that week
    run: ZoneShare | None


class Intensity(BaseModel):
    weeks: list[IntensityWeek]
    aggregate: dict[str, ZoneShare | None]  # all / bike / run over the whole window
    target_note: str
    caveats: list[str]


class RampWeek(BaseModel):
    week_start: date
    km: float
    baseline_km: float  # average of the baseline_weeks weeks before this one
    change_pct: float | None  # vs baseline_km; None = baseline too small, or week in progress
    status: str  # pass / amber / red / no_data / in_progress (the current week)


class RunRamp(BaseModel):
    weeks: list[RampWeek]
    baseline_weeks: int
    amber_above_pct: float
    red_above_pct: float
    min_baseline_km: float


@router.get("/intensity", response_model=Intensity)
def intensity(db: Session = Depends(get_db)):
    return intensity_distribution(db)


@router.get("/run-ramp", response_model=RunRamp)
def get_run_ramp(db: Session = Depends(get_db)):
    return run_ramp(db)
