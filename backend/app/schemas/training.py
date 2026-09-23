from datetime import date

from pydantic import BaseModel, ConfigDict


class TargetBase(BaseModel):
    week_label: str
    week_start_date: date
    sport: str
    target_minutes: float
    target_distance_km: float | None = None
    note: str | None = None


class TargetCreate(TargetBase):
    pass


class TargetOut(TargetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SportRollup(BaseModel):
    sport: str
    target_minutes: float | None
    actual_minutes: float
    target_distance_km: float | None
    actual_distance_km: float
    on_track_pct: float | None  # actual_minutes / target_minutes * 100, when a target exists
    on_track_distance_pct: float | None  # actual_distance_km / target_distance_km * 100


class WeekSummary(BaseModel):
    week_start_date: date
    week_label: str | None
    sports: list[SportRollup]
    rest_days: list[date]


class DisciplineWeek(BaseModel):
    minutes: float
    distance_km: float
    sessions: int
    load: float  # sum of Strava Relative Effort (see services/training_load.py)


class WeekDisciplineRollup(BaseModel):
    week_start: date
    sports: dict[str, DisciplineWeek]  # swim / bike / run / gym / other
