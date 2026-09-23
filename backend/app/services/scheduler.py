import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..database import SessionLocal
from .garmin_sync import TOKEN_STORE as GARMIN_TOKEN_STORE
from .garmin_sync import sync_estimates as sync_garmin_estimates
from .garmin_sync import sync_recent as sync_garmin
from .plan_sync import sync_plan
from .strava_sync import sync_activities

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_strava_sync() -> None:
    db = SessionLocal()
    try:
        inserted = sync_activities(db)
        logger.info("Strava sync: %d new activities", inserted)
    except Exception:
        logger.exception("Strava sync failed")
    finally:
        db.close()


def _run_garmin_sync() -> None:
    db = SessionLocal()
    try:
        synced = sync_garmin(db)
        logger.info("Garmin sync: %d days updated", synced)
    except Exception:
        logger.exception("Garmin sync failed")
    try:
        # HM race-prediction change-points + profile FTP (2 extra requests).
        added = sync_garmin_estimates(db, history_days=14)
        logger.info("Garmin estimates: %d new", added)
    except Exception:
        db.rollback()
        logger.exception("Garmin estimates sync failed")
    finally:
        db.close()


def _run_plan_sync() -> None:
    db = SessionLocal()
    try:
        result = sync_plan(db)
        logger.info("Calendar plan sync: %s", result)
    except Exception:
        logger.exception("Calendar plan sync failed")
    finally:
        db.close()


def start_scheduler(
    strava_interval_minutes: int = 6,
    garmin_interval_minutes: int = 60,
    plan_interval_minutes: int = 30,
) -> None:
    if scheduler.running:
        return

    jobs_added = False

    if settings.strava_refresh_token:
        scheduler.add_job(
            _run_strava_sync,
            "interval",
            minutes=strava_interval_minutes,
            next_run_time=datetime.now(),
            id="strava_sync",
        )
        jobs_added = True
        logger.info("Scheduled Strava sync every %d minutes", strava_interval_minutes)
    else:
        logger.info("STRAVA_REFRESH_TOKEN not set - scheduled Strava sync disabled")

    if Path(GARMIN_TOKEN_STORE).exists():
        scheduler.add_job(
            _run_garmin_sync,
            "interval",
            minutes=garmin_interval_minutes,
            next_run_time=datetime.now(),
            id="garmin_sync",
        )
        jobs_added = True
        logger.info("Scheduled Garmin sync every %d minutes", garmin_interval_minutes)
    else:
        logger.info(
            "No cached Garmin session (%s) - run app.services.garmin_login first; "
            "scheduled Garmin sync disabled",
            GARMIN_TOKEN_STORE,
        )

    if settings.google_refresh_token:
        scheduler.add_job(
            _run_plan_sync,
            "interval",
            minutes=plan_interval_minutes,
            next_run_time=datetime.now(),
            id="plan_sync",
        )
        jobs_added = True
        logger.info("Scheduled calendar plan sync every %d minutes", plan_interval_minutes)
    else:
        logger.info("GOOGLE_REFRESH_TOKEN not set - scheduled calendar plan sync disabled")

    if jobs_added:
        scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
