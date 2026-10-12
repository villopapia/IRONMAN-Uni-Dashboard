from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.durability import durability, sport_ctl_series
from ..services.intensity import intensity_distribution, run_ramp
from ..services.overlay import planned_load_by_day
from ..services.training_load import (
    RAMP_AMBER_ABOVE,
    RAMP_NORMAL_FROM,
    RAMP_RED_ABOVE,
    ctl_decay,
    load_pmc,
    project_ctl,
    ramp_status,
    rebuild_daily_loads,
)

router = APIRouter()


class PmcPoint(BaseModel):
    date: date
    load: float
    ctl: float
    atl: float
    tsb: float
    by_sport: dict[str, float]


class ProjectedCtl(BaseModel):
    date: date
    ctl: float


class PmcResponse(BaseModel):
    series: list[PmcPoint]
    current: PmcPoint | None
    ctl_ramp_7d: float | None  # CTL change over the last 7 days (load units / week)
    ramp_status: str | None  # low / normal / amber / red
    ramp_normal_from: float
    ramp_amber_above: float
    ramp_red_above: float
    projection: list[ProjectedCtl]  # CTL after today through the calendar plan; empty unless project_to is given
    first_load_date: date | None
    estimated_sessions: int
    total_sessions: int
    methodology_note: str


@router.get("/pmc", response_model=PmcResponse)
def pmc(days: int = 120, since: date | None = None, project_to: date | None = None, db: Session = Depends(get_db)):
    """`since` overrides `days` as the start of the series. `project_to` adds the
    projected CTL from tomorrow to that date."""
    days = max(14, min(days, 730))
    today = date.today()
    result = load_pmc(db, start=since or today - timedelta(days=days - 1), end=today)
    series = result["series"]
    current = series[-1] if series else None
    ramp = (
        round(series[-1]["ctl"] - series[-8]["ctl"], 1) if len(series) >= 8 else None
    )
    projection = []
    if project_to and current:
        planned = planned_load_by_day(db, today, project_to)
        projection = [
            {"date": p["date"], "ctl": round(p["ctl"], 1)}
            for p in project_ctl(current["ctl"], planned, today, project_to, ctl_decay())
        ]
    return PmcResponse(
        current=current,
        ctl_ramp_7d=ramp,
        ramp_status=ramp_status(ramp),
        ramp_normal_from=RAMP_NORMAL_FROM,
        ramp_amber_above=RAMP_AMBER_ABOVE,
        ramp_red_above=RAMP_RED_ABOVE,
        projection=projection,
        **result,
    )


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


class SportCtlPoint(BaseModel):
    date: date
    swim: float
    bike: float
    run: float


class CtlCheck(BaseModel):
    max_deviation_pct: float  # swim + bike + run vs intervals.icu's CTL
    worst_date: date
    days: int


class SportCtl(BaseModel):
    series: list[SportCtlPoint]
    starts_on: date | None  # every line starts from 0 here
    check: CtlCheck | None


class Longest(BaseModel):
    value: float
    pct: int  # of the race target; can exceed 100


class DurabilityWeek(BaseModel):
    week_start: date
    swim: Longest | None  # None = no session that week
    bike: Longest | None
    run: Longest | None


class DurabilityTarget(BaseModel):
    target: float
    unit: str


class Durability(BaseModel):
    targets: dict[str, DurabilityTarget]
    weeks: list[DurabilityWeek]


@router.get("/sport-ctl", response_model=SportCtl)
def sport_ctl(days: int = 180, db: Session = Depends(get_db)):
    return sport_ctl_series(db, max(28, min(days, 730)))


@router.get("/durability", response_model=Durability)
def get_durability(db: Session = Depends(get_db)):
    return durability(db)
