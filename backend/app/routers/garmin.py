from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.garmin import GarminDailyMetric
from ..schemas.garmin import GarminDailyMetricOut
from ..services.garmin_sync import backfill_rhr, sync_estimates, sync_recent

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

