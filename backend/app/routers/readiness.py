from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.readiness import readiness, recovery_trend

router = APIRouter()


class SparkPoint(BaseModel):
    date: date
    value: float | None


class ReadinessMetric(BaseModel):
    key: str
    label: str
    status: str  # pass / amber / red / no_data
    value: float | None
    unit: str
    basis: str  # what `value` is, or why there is no status
    series: list[SparkPoint]  # last 28 days, daily
    band: tuple[float, float] | None  # HRV baseline band (low, high)


class Readiness(BaseModel):
    date: date
    action: str
    red: list[str]
    amber: list[str]
    no_data: list[str]
    metrics: list[ReadinessMetric]
    note: str


class TrendPoint(BaseModel):
    date: date
    hrv: float | None
    rhr: float | None
    rhr_7d: float | None  # same 7-day average the readiness status uses


class TrendMetric(BaseModel):
    status: str  # the readiness status, verbatim
    value: float | None
    unit: str
    basis: str
    band: tuple[float, float] | None


class RecoveryTrend(BaseModel):
    series: list[TrendPoint]
    hrv: TrendMetric
    rhr: TrendMetric
    rhr_amber_from: float
    rhr_red_from: float
    note: str


@router.get("", response_model=Readiness)
def get_readiness(db: Session = Depends(get_db)):
    return readiness(db)


@router.get("/trend", response_model=RecoveryTrend)
def trend(days: int = 42, db: Session = Depends(get_db)):
    return recovery_trend(db, max(14, min(days, 180)))
