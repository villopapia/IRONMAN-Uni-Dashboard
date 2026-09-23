"""Pulls daily recovery metrics from Garmin Connect (unofficial API, resumes
the cached session from garmin_login.py - never touches the password after
first login).

NOTE: this is an unofficial, reverse-engineered API. Field paths below were
verified against a real account on 2026-09-23 (sleep score, sleep duration,
HRV, resting HR, body battery, VO2max all confirmed correct; training_status
was wrong on the first pass - it's keyed by a dynamic per-device ID, not a
fixed field - and has been fixed). Extraction stays defensive (falls back to
None rather than raising) since the library is unofficial and its response
shape could still drift on a future Garmin-side change.
"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from garminconnect import Garmin
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.garmin import GarminDailyMetric
from ..models.performance import ThresholdTest

logger = logging.getLogger(__name__)

TOKEN_STORE = str(Path(__file__).resolve().parent.parent.parent / ".garmin_tokens")


def _safe_get(d: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def _get_client() -> Garmin:
    if not Path(TOKEN_STORE).exists():
        raise RuntimeError(
            "No cached Garmin session found - run "
            "`python -m app.services.garmin_login` yourself first (interactive, "
            "handles MFA if needed)."
        )
    garmin = Garmin()
    garmin.login(TOKEN_STORE)
    return garmin


def _fetch_day(client: Garmin, day: date) -> dict:
    day_str = day.isoformat()

    sleep = client.get_sleep_data(day_str) or {}
    readiness = client.get_training_readiness(day_str) or []
    hrv = client.get_hrv_data(day_str) or {}
    stats = client.get_stats(day_str) or {}
    training_status = client.get_training_status(day_str) or {}

    readiness_score = readiness[0].get("score") if readiness else None

    # Keyed by a dynamic per-device ID (e.g. the watch's device ID) rather than
    # a fixed field name - verified against a real account on 2026-09-23; take
    # whichever device reported most recently rather than assuming a key.
    training_status_by_device = (
        _safe_get(training_status, "mostRecentTrainingStatus", "latestTrainingStatusData")
        or {}
    )
    device_status = next(iter(training_status_by_device.values()), {})

    return {
        "sleep_score": _safe_get(sleep, "dailySleepDTO", "sleepScores", "overall", "value"),
        "sleep_duration_min": (
            (_safe_get(sleep, "dailySleepDTO", "sleepTimeSeconds") or 0) / 60
            if _safe_get(sleep, "dailySleepDTO", "sleepTimeSeconds") is not None
            else None
        ),
        "body_battery_high": stats.get("bodyBatteryHighestValue"),
        "body_battery_low": stats.get("bodyBatteryLowestValue"),
        "training_readiness": readiness_score,
        "hrv_status": _safe_get(hrv, "hrvSummary", "status"),
        "hrv_value": _safe_get(hrv, "hrvSummary", "lastNightAvg"),
        "resting_hr": stats.get("restingHeartRate"),
        "vo2max_running": _safe_get(
            training_status, "mostRecentVO2Max", "generic", "vo2MaxPreciseValue"
        ),
        "training_status": device_status.get("trainingStatusFeedbackPhrase"),
    }


def _upsert_day(db: Session, day: date, fields: dict) -> None:
    metric = db.query(GarminDailyMetric).filter(GarminDailyMetric.date == day).first()
    if metric is None:
        metric = GarminDailyMetric(date=day)
        db.add(metric)
    for key, value in fields.items():
        if value is not None:
            setattr(metric, key, value)
    # `onupdate` on the column only fires when SQLAlchemy sees an attribute
    # actually change value - a day whose data is already fully settled
    # (nothing new to report) leaves the row un-dirtied, so onupdate never
    # fires and "last synced" goes stale even though the sync ran fine every
    # time. Set it explicitly so it means "last confirmed synced," not "last
    # time a value happened to change."
    metric.updated_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError:
        # A concurrent sync (e.g. the scheduled job firing right after a
        # manual /sync call) inserted this same day first between our SELECT
        # and INSERT - same race as the Strava pagination duplicate-key bug.
        # Roll back and update the row it just created instead of erroring.
        db.rollback()
        metric = db.query(GarminDailyMetric).filter(GarminDailyMetric.date == day).first()
        for key, value in fields.items():
            if value is not None:
                setattr(metric, key, value)
        metric.updated_at = datetime.utcnow()
        db.commit()


def backfill_rhr(db: Session, days: int = 90, _retried: bool = False) -> int:
    """Resting-HR history in ONE request (`get_rhr_daily` takes a range), for
    the 7-day rolling trend + baseline. Only fills days whose resting_hr is
    still empty - never overwrites what the full per-day sync wrote.

    HRV has no equivalent: `get_hrv_data_range` returned {} and per-day HRV
    for dates before 2026-09-22 is null on this account (verified
    2026-09-23), so HRV history only accumulates from the regular sync.
    """
    client = _get_client()
    end = date.today()
    start = end - timedelta(days=days - 1)
    rows = client.get_rhr_daily(start.isoformat(), end.isoformat()) or []
    existing = {
        m.date: m
        for m in db.query(GarminDailyMetric)
        .filter(GarminDailyMetric.date >= start, GarminDailyMetric.date <= end)
        .all()
    }
    seen: set[date] = set()
    filled = 0
    for row in rows:
        value = row.get("value")
        day_str = row.get("calendarDate")
        if value is None or not day_str:
            continue
        day = date.fromisoformat(day_str)
        if day in seen:
            continue
        seen.add(day)
        metric = existing.get(day)
        if metric is None:
            metric = GarminDailyMetric(date=day)
            db.add(metric)
        if metric.resting_hr is None:
            metric.resting_hr = int(round(value))
            filled += 1
    try:
        db.commit()
    except IntegrityError:
        # The hourly sync created one of these days concurrently - retry as
        # a pure update pass.
        db.rollback()
        if _retried:
            raise
        return backfill_rhr(db, days, _retried=True)
    return filled


def _upsert_estimate(db: Session, key: str, fields: dict) -> bool:
    row = db.query(ThresholdTest).filter(ThresholdTest.external_key == key).first()
    if row is None:
        db.add(ThresholdTest(external_key=key, source="garmin", **fields))
        return True
    for k, v in fields.items():
        setattr(row, k, v)
    return False


def sync_estimates(db: Session, history_days: int = 180, _retried: bool = False) -> int:
    """Device estimates into the threshold history, labelled source="garmin"
    so they're never confused with a real test:

    - Half-marathon race prediction from Garmin's daily prediction history,
      sampled to one row per week (that week's latest value).
    - Cycling FTP from the Garmin profile. On this account it's 172 W dated
      2026-05-09 with biometricSourceType CHANGE_LOG - there's no power
      meter yet, so it is NOT a measured FTP; stored with that caveat.

    Garmin's running lactate threshold (speed/HR) is null on this account, and
    the heart-rate-zone config's "LTHR" reads 47 bpm (clearly not real), so
    neither is imported.
    """
    client = _get_client()
    added = 0
    end = date.today()
    start = end - timedelta(days=min(history_days, 365))

    predictions = client.get_race_predictions(start.isoformat(), end.isoformat(), "daily") or []
    # One row per Mon-Sun week holding that week's latest prediction (updated
    # in place as the week goes on). Garmin's prediction drifts by seconds
    # nearly every day, so daily rows would be noise, not a trend.
    latest_by_week: dict[date, dict] = {}
    for p in predictions:
        value, day = p.get("timeHalfMarathon"), p.get("calendarDate")
        if value is None or not day:
            continue
        d = date.fromisoformat(day)
        wk = d - timedelta(days=d.weekday())
        if wk not in latest_by_week or d > latest_by_week[wk]["date"]:
            latest_by_week[wk] = {"date": d, "value": float(value)}
    for wk, p in latest_by_week.items():
        added += _upsert_estimate(
            db,
            f"garmin:hm_prediction:week:{wk.isoformat()}",
            dict(
                test_date=p["date"],
                discipline="run",
                metric="hm_prediction",
                value=p["value"],
                unit="s",
                protocol="Garmin race predictor (weekly)",
                note="Device estimate from recent runs - not a race result.",
            ),
        )

    ftp = client.get_cycling_ftp() or {}
    if isinstance(ftp, list):
        ftp = ftp[0] if ftp else {}
    ftp_value = ftp.get("functionalThresholdPower")
    ftp_date = (ftp.get("calendarDate") or "")[:10]
    if ftp_value and ftp_date:
        added += _upsert_estimate(
            db,
            f"garmin:ftp:{ftp_date}",
            dict(
                test_date=date.fromisoformat(ftp_date),
                discipline="bike",
                metric="ftp",
                value=float(ftp_value),
                unit="W",
                protocol=f"Garmin profile ({ftp.get('biometricSourceType') or 'unknown source'})",
                note="Garmin profile value, not a power-meter test - unconfirmed.",
            ),
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if _retried:
            raise
        return sync_estimates(db, history_days, _retried=True)
    return added


def sync_recent(db: Session, days: int = 3) -> int:
    client = _get_client()
    today = date.today()
    synced = 0

    for i in range(days):
        day = today - timedelta(days=i)
        try:
            fields = _fetch_day(client, day)
        except Exception:
            logger.exception("Garmin fetch failed for %s", day)
            continue

        _upsert_day(db, day, fields)
        synced += 1

    return synced
