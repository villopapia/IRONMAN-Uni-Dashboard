from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEADLINE_KINDS = ("assignment", "exam", "test", "other")


class SnapshotOut(BaseModel):
    recorded_on: date
    weighted_average_pct: float
    classification_estimate: str | None
    modules_counted: int
    model_config = ConfigDict(from_attributes=True)


class WeightedHistory(BaseModel):
    academic_year: str
    snapshots: list[SnapshotOut]
    first_threshold_pct: float
    current_pct: float | None
    modules_missing_level_credits: list[str]
    note: str


class DeadlineCreate(BaseModel):
    title: str = Field(min_length=1)
    due_at: datetime
    kind: str = "assignment"
    module_id: int | None = None
    assessment_id: int | None = None
    weight_pct: float | None = Field(default=None, ge=0, le=100)
    note: str | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in DEADLINE_KINDS:
            raise ValueError(f"kind must be one of {DEADLINE_KINDS}")
        return v


class DeadlineUpdate(BaseModel):
    title: str | None = None
    due_at: datetime | None = None
    kind: str | None = None
    module_id: int | None = None
    assessment_id: int | None = None
    weight_pct: float | None = Field(default=None, ge=0, le=100)
    status: str | None = None
    note: str | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v not in (None, "pending", "submitted"):
            raise ValueError("status must be pending or submitted")
        return v


class DeadlineOut(BaseModel):
    id: int
    module_id: int | None
    module_name: str | None
    assessment_id: int | None
    assessment_name: str | None
    title: str
    due_at: datetime
    kind: str
    weight_pct: float | None
    status: str
    note: str | None
    days_until: float
    overdue: bool


class StudyLogCreate(BaseModel):
    date: date
    hours: float = Field(gt=0, le=24)
    module_id: int | None = None
    note: str | None = None


class StudyLogOut(StudyLogCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class StudyTargetCreate(BaseModel):
    weekly_hours: float = Field(gt=0, le=100)
    effective_from: date | None = None  # defaults to this week's Monday
    note: str | None = None


class StudyWeek(BaseModel):
    week_start: date
    logged_hours: float
    target_hours: float | None
    target_source: str | None  # manual / calendar / null
    calendar_planned_hours: float
    pct: float | None
    in_progress: bool
    flag: bool


class StudySummary(BaseModel):
    weeks: list[StudyWeek]
    recent_logs: list[StudyLogOut]
    manual_target_hours: float | None
    flag_threshold_pct: float
    note: str


class PrepItemCreate(BaseModel):
    module_id: int
    title: str = Field(min_length=1)
    kind: str = "topic"

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in ("topic", "past_paper"):
            raise ValueError("kind must be topic or past_paper")
        return v


class PrepItemOut(BaseModel):
    id: int
    module_id: int
    kind: str
    title: str
    done: bool
    done_on: date | None
    model_config = ConfigDict(from_attributes=True)


class ModulePrep(BaseModel):
    module_id: int
    module_name: str
    total: int
    done: int
    pct: float | None
    topics_done: int
    topics_total: int
    papers_done: int
    papers_total: int
    items: list[PrepItemOut]
