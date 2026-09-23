from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.garmin import GarminDailyMetric
from ..models.performance import RecoveryBaseline
from ..schemas.garmin import GarminDailyMetricOut
from ..services.garmin_sync import backfill_rhr, sync_estimates, sync_recent
from ..services.recovery_trend import recovery_trend

router = APIRouter()


@router.post("/sync")
def trigger_sync(db: Session = Depends(get_db)):
    try:
        synced = sync_recent(db)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"synced": synced}


@router.post("/backfill")
def backfill(db: Session = Depends(get_db)):
    """One-off history pull: 90 days of resting HR (one request) and up to a
    year of Garmin HM race predictions + the profile FTP. Safe to re-run."""
    try:
        return {"rhr_days_filled": backfill_rhr(db, 90), "estimates_added": sync_estimates(db, 365)}
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/today", response_model=GarminDailyMetricOut | None)
def today(db: Session = Depends(get_db)):
    """Returns the most recently synced day's metrics, not strictly today's -
    if a sync fails (API change, rate limit, expired session), the panel
    should keep showing the last good data with its own staleness rather
    than going blank just because today's row doesn't exist yet.

    Only rows the full daily sync wrote count here (sleep or body-battery
    present) - the resting-HR backfill creates HR-only rows for past days,
    which must never masquerade as "the latest sync".
    """
    return (
        db.query(GarminDailyMetric)
        .filter(
            (GarminDailyMetric.sleep_score.isnot(None))
            | (GarminDailyMetric.body_battery_high.isnot(None))
            | (GarminDailyMetric.sleep_duration_min.isnot(None))
        )
        .order_by(GarminDailyMetric.date.desc())
        .first()
    )


@router.get("/range", response_model=list[GarminDailyMetricOut])
def metric_range(start: date, end: date | None = None, db: Session = Depends(get_db)):
    end = end or date.today()
    return (
        db.query(GarminDailyMetric)
        .filter(GarminDailyMetric.date >= start, GarminDailyMetric.date <= end)
        .order_by(GarminDailyMetric.date)
        .all()
    )


# --- HRV / RHR rolling trend -------------------------------------------------


class TrendPoint(BaseModel):
    date: date
    hrv: float | None
    rhr: float | None
    hrv_7d: float | None
    rhr_7d: float | None


class Baseline(BaseModel):
    value: float | None
    method: str  # manual / snapshot_28d / auto_28d / insufficient_history
    effective_from: date | None
    sd: float | None
    n: int


class MetricTrend(BaseModel):
    unit: str
    rolling_7d: float | None
    baseline: Baseline
    deviation_pct: float | None
    flag: str | None  # normal / below_normal / above_normal / null (not enough data)
    readings: int
    first_reading: date | None


class RecoveryTrend(BaseModel):
    series: list[TrendPoint]
    metrics: dict[str, MetricTrend]


@router.get("/trend", response_model=RecoveryTrend)
def trend(days: int = 42, db: Session = Depends(get_db)):
    return recovery_trend(db, max(14, min(days, 180)))


class BaselineCreate(BaseModel):
    metric: str
    value: float | None = Field(default=None, gt=0)  # omitted -> snapshot the current auto baseline
    note: str | None = None

    @field_validator("metric")
    @classmethod
    def _m(cls, v: str) -> str:
        if v not in ("hrv", "rhr"):
            raise ValueError("metric must be hrv or rhr")
        return v


@router.post("/baselines")
def set_baseline(payload: BaselineCreate, db: Session = Depends(get_db)):
    value, method = payload.value, "manual"
    if value is None:
        auto = recovery_trend(db, 42)["metrics"][payload.metric]["baseline"]
        if auto["method"] != "auto_28d" or auto["value"] is None:
            raise HTTPException(
                400,
                "Not enough history for an automatic baseline yet (needs 14+ readings "
                "in the 28-day window) - enter a value instead.",
            )
        value, method = auto["value"], "snapshot_28d"
    row = RecoveryBaseline(
        metric=payload.metric, value=value, method=method, effective_from=date.today(), note=payload.note
    )
    db.add(row)
    db.commit()
    return {"metric": row.metric, "value": row.value, "method": row.method, "effective_from": row.effective_from}


@router.delete("/baselines/{metric}")
def clear_baselines(metric: str, db: Session = Depends(get_db)):
    """Back to the automatic 28-day baseline."""
    n = db.query(RecoveryBaseline).filter(RecoveryBaseline.metric == metric).delete()
    db.commit()
    return {"deleted": n}
