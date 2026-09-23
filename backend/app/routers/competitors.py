from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.activity import Activity
from ..models.competitor import Competitor, CompetitorActivity
from ..schemas.competitor import (
    CompetitorActivityCreate,
    CompetitorActivityOut,
    CompetitorCreate,
    CompetitorOut,
    CompetitorWeekTotal,
    WeekComparison,
)

router = APIRouter()


@router.get("/compare", response_model=WeekComparison)
def compare_week(week_start_date: date, db: Session = Depends(get_db)):
    week_end = week_start_date + timedelta(days=7)

    you_total = (
        db.query(Activity)
        .filter(Activity.date >= week_start_date, Activity.date < week_end)
        .with_entities(Activity.duration_min)
        .all()
    )
    you_minutes = sum(row[0] for row in you_total)

    breakdown = []
    for competitor in db.query(Competitor).all():
        rows = (
            db.query(CompetitorActivity)
            .filter(
                CompetitorActivity.competitor_id == competitor.id,
                CompetitorActivity.date >= week_start_date,
                CompetitorActivity.date < week_end,
            )
            .with_entities(CompetitorActivity.duration_min)
            .all()
        )
        breakdown.append(
            CompetitorWeekTotal(
                competitor_id=competitor.id,
                name=competitor.name,
                total_minutes=round(sum(row[0] for row in rows), 1),
            )
        )

    return WeekComparison(
        week_start_date=week_start_date,
        you_minutes=round(you_minutes, 1),
        competitors=breakdown,
    )


@router.get("", response_model=list[CompetitorOut])
def list_competitors(db: Session = Depends(get_db)):
    return db.query(Competitor).all()


@router.post("", response_model=CompetitorOut)
def create_competitor(payload: CompetitorCreate, db: Session = Depends(get_db)):
    competitor = Competitor(**payload.model_dump())
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor


@router.post("/{competitor_id}/activities", response_model=CompetitorActivityOut)
def log_competitor_activity(
    competitor_id: int, payload: CompetitorActivityCreate, db: Session = Depends(get_db)
):
    competitor = db.get(Competitor, competitor_id)
    if not competitor:
        raise HTTPException(404, "Competitor not found")
    activity = CompetitorActivity(competitor_id=competitor_id, **payload.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.get("/{competitor_id}/activities", response_model=list[CompetitorActivityOut])
def list_competitor_activities(competitor_id: int, db: Session = Depends(get_db)):
    competitor = db.get(Competitor, competitor_id)
    if not competitor:
        raise HTTPException(404, "Competitor not found")
    return (
        db.query(CompetitorActivity)
        .filter(CompetitorActivity.competitor_id == competitor_id)
        .order_by(CompetitorActivity.date.desc())
        .all()
    )
