from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.readiness import readiness

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


@router.get("", response_model=Readiness)
def get_readiness(db: Session = Depends(get_db)):
    return readiness(db)
