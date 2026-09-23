from datetime import date, datetime

from pydantic import BaseModel, field_validator


class ComplianceRollup(BaseModel):
    planned: int
    due: int  # planned minus still-pending
    completed: int
    pending: int
    pct: float | None
    flag: bool  # pct below the flag threshold


class DisciplineCompliance(ComplianceRollup):
    extras: int  # unplanned Strava sessions of this discipline


class StrengthCompliance(ComplianceRollup):
    label: str


class BrickDay(BaseModel):
    date: date
    # done / split (both legs, not back-to-back) / partial / missed / pending / in_progress
    status: str
    titles: list[str]
    bike_activity: str | None
    run_activity: str | None


class BrickSummary(BaseModel):
    days: list[BrickDay]
    planned: int
    completed: int
    pct: float | None
    flag: bool


class PlannedSlot(BaseModel):
    ids: list[int]
    date: date
    start_at: datetime | None
    discipline: str
    titles: list[str]
    is_brick: bool
    strength_type: str | None
    # done / moved / manual_done / skipped / missed / pending
    status: str
    manual_status: str | None
    activity_name: str | None
    activity_date: datetime | None


class ExtraActivity(BaseModel):
    name: str
    date: datetime
    sport: str
    duration_min: float


class WeekCompliance(BaseModel):
    week_start: date
    has_plan: bool
    overall: ComplianceRollup
    by_discipline: dict[str, DisciplineCompliance]
    strength: dict[str, StrengthCompliance]
    bricks: BrickSummary
    sessions: list[PlannedSlot]
    extras: list[ExtraActivity]
    flag_threshold_pct: float


class ComplianceRange(BaseModel):
    weeks: list[WeekCompliance]
    plan_synced_at: datetime | None
    note: str


class ManualStatusUpdate(BaseModel):
    ids: list[int]
    manual_status: str | None  # done / skipped / null

    @field_validator("manual_status")
    @classmethod
    def _v(cls, v: str | None) -> str | None:
        if v not in (None, "done", "skipped"):
            raise ValueError("manual_status must be done, skipped or null")
        return v
