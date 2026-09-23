from datetime import date

from pydantic import BaseModel, ConfigDict


class CompetitorActivityBase(BaseModel):
    date: date
    sport: str
    duration_min: float
    distance_km: float | None = None
    note: str | None = None


class CompetitorActivityCreate(CompetitorActivityBase):
    pass


class CompetitorActivityOut(CompetitorActivityBase):
    id: int
    competitor_id: int
    model_config = ConfigDict(from_attributes=True)


class CompetitorBase(BaseModel):
    name: str
    note: str | None = None


class CompetitorCreate(CompetitorBase):
    pass


class CompetitorOut(CompetitorBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CompetitorWeekTotal(BaseModel):
    competitor_id: int
    name: str
    total_minutes: float


class WeekComparison(BaseModel):
    week_start_date: date
    you_minutes: float
    competitors: list[CompetitorWeekTotal]
