from datetime import date

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    summary: str
    start: str


class WeekSchedule(BaseModel):
    week_start_date: date
    days: dict[str, list[CalendarEvent]]
