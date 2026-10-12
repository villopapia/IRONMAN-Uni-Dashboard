from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.season import london_today, season_status

router = APIRouter()


class Named(BaseModel):
    name: str
    date: date


class Phase(BaseModel):
    name: str
    start: date
    end: date


class CurrentPhase(BaseModel):
    name: str
    week: int  # Mon-Sun weeks, counted from the Monday of the phase start
    weeks: int


class NextGate(Named):
    days: int


class Season(BaseModel):
    today: date  # Europe/London
    race: Named
    days_to_race: int
    weeks_to_race: int
    phase: CurrentPhase | None
    next_gate: NextGate | None
    gates: list[Named]
    phases: list[Phase]
    season_start: date


@router.get("", response_model=Season)
def season():
    return season_status(london_today())
