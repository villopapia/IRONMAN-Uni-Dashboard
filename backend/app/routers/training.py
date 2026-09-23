from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.activity import Activity
from ..models.performance import DailyTrainingLoad
from ..models.training import WeeklyTrainingTarget
from ..schemas.training import (
    DisciplineWeek,
    SportRollup,
    TargetCreate,
    TargetOut,
    WeekDisciplineRollup,
    WeekSummary,
)
from ..services.strava_sync import sync_activities

router = APIRouter()


@router.post("/sync")
def trigger_sync(full: bool = False, db: Session = Depends(get_db)):
    """`full=true` walks back through the whole Strava history (up to 1,000
    activities) instead of the scheduled job's most recent 100 - a one-off
    backfill, e.g. to give the CTL (42-day) average enough history."""
    try:
        inserted = (
            sync_activities(db, per_page=100, pages=10) if full else sync_activities(db)
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"inserted": inserted}


ROLLUP_SPORTS = ["swim", "bike", "run", "gym"]


@router.get("/weeks", response_model=list[WeekDisciplineRollup])
def weekly_discipline_rollup(weeks: int = 12, db: Session = Depends(get_db)):
    """Per-week minutes / km / sessions / load for swim, bike, run and gym
    (strength) separately, oldest first, ending with the current week.
    Walks and uncategorised activities are folded into `other`."""
    weeks = max(1, min(weeks, 52))
    today = date.today()
    current = today - timedelta(days=today.weekday())
    first = current - timedelta(days=7 * (weeks - 1))
    end = current + timedelta(days=7)

    activities = (
        db.query(Activity)
        .filter(Activity.date >= first, Activity.date < end)
        .all()
    )
    loads = (
        db.query(DailyTrainingLoad)
        .filter(DailyTrainingLoad.date >= first, DailyTrainingLoad.date < end)
        .all()
    )

    buckets = {
        first + timedelta(days=7 * i): {
            s: {"minutes": 0.0, "distance_km": 0.0, "sessions": 0, "load": 0.0}
            for s in ROLLUP_SPORTS + ["other"]
        }
        for i in range(weeks)
    }
    for a in activities:
        d = a.date.date()
        wk = d - timedelta(days=d.weekday())
        sport = a.sport if a.sport in ROLLUP_SPORTS else "other"
        b = buckets[wk][sport]
        b["minutes"] += a.duration_min
        b["distance_km"] += a.distance_km or 0.0
        b["sessions"] += 1
    for row in loads:
        wk = row.date - timedelta(days=row.date.weekday())
        sport = row.sport if row.sport in ROLLUP_SPORTS else "other"
        buckets[wk][sport]["load"] += row.load

    return [
        WeekDisciplineRollup(
            week_start=wk,
            sports={
                s: DisciplineWeek(
                    minutes=round(v["minutes"], 1),
                    distance_km=round(v["distance_km"], 1),
                    sessions=v["sessions"],
                    load=round(v["load"], 1),
                )
                for s, v in sports.items()
            },
        )
        for wk, sports in sorted(buckets.items())
    ]


@router.get("/week", response_model=WeekSummary)
def week_summary(week_start_date: date, db: Session = Depends(get_db)):
    week_end = week_start_date + timedelta(days=7)

    targets = (
        db.query(WeeklyTrainingTarget)
        .filter(WeeklyTrainingTarget.week_start_date == week_start_date)
        .all()
    )
    target_minutes_by_sport = {t.sport: t.target_minutes for t in targets}
    target_km_by_sport = {t.sport: t.target_distance_km for t in targets}

    activities = (
        db.query(Activity)
        .filter(Activity.date >= week_start_date, Activity.date < week_end)
        .all()
    )
    actual_minutes_by_sport: dict[str, float] = {}
    actual_km_by_sport: dict[str, float] = {}
    active_days: set[date] = set()
    for activity in activities:
        actual_minutes_by_sport[activity.sport] = (
            actual_minutes_by_sport.get(activity.sport, 0.0) + activity.duration_min
        )
        actual_km_by_sport[activity.sport] = actual_km_by_sport.get(
            activity.sport, 0.0
        ) + (activity.distance_km or 0.0)
        active_days.add(activity.date.date())

    sports = sorted(set(target_minutes_by_sport) | set(actual_minutes_by_sport))
    rollup = []
    for sport in sports:
        target_minutes = target_minutes_by_sport.get(sport)
        actual_minutes = round(actual_minutes_by_sport.get(sport, 0.0), 1)
        target_km = target_km_by_sport.get(sport)
        actual_km = round(actual_km_by_sport.get(sport, 0.0), 1)
        on_track_pct = (
            round(actual_minutes / target_minutes * 100, 1)
            if target_minutes  # falsy for both None and 0 - avoids ZeroDivisionError
            else None
        )
        on_track_distance_pct = (
            round(actual_km / target_km * 100, 1)
            if target_km  # falsy for both None and 0
            else None
        )
        rollup.append(
            SportRollup(
                sport=sport,
                target_minutes=target_minutes,
                actual_minutes=actual_minutes,
                target_distance_km=target_km,
                actual_distance_km=actual_km,
                on_track_pct=on_track_pct,
                on_track_distance_pct=on_track_distance_pct,
            )
        )

    rest_days = [
        week_start_date + timedelta(days=i)
        for i in range(7)
        if (week_start_date + timedelta(days=i)) not in active_days
    ]

    return WeekSummary(
        week_start_date=week_start_date,
        week_label=targets[0].week_label if targets else None,
        sports=rollup,
        rest_days=rest_days,
    )


@router.post("/targets", response_model=TargetOut)
def create_target(payload: TargetCreate, db: Session = Depends(get_db)):
    target = WeeklyTrainingTarget(**payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


@router.get("/targets", response_model=list[TargetOut])
def list_targets(db: Session = Depends(get_db)):
    return db.query(WeeklyTrainingTarget).order_by(WeeklyTrainingTarget.week_start_date).all()
