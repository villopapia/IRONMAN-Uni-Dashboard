from datetime import date

from fastapi import APIRouter, HTTPException

from ..schemas.calendar import WeekSchedule
from ..services.calendar_schedule import get_week_events

router = APIRouter()


@router.get("/week", response_model=WeekSchedule)
def week_schedule(week_start_date: date):
    try:
        days = get_week_events(week_start_date)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return WeekSchedule(week_start_date=week_start_date, days=days)
