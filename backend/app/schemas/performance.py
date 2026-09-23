from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.performance import THRESHOLD_METRICS


# --- Phase gates -----------------------------------------------------------


class GateItemOut(BaseModel):
    id: int
    key: str
    title: str
    criterion: str
    evaluation: str
    target_value: float | None
    unit: str | None
    result_value: float | None
    result_text: str | None
    recorded_on: date | None
    manual_status: str | None
    # pass/fail/pending/overdue/on_track/behind/recorded
    status: str
    detail: str | None


class GateOut(BaseModel):
    gate_date: date
    gate_name: str
    days_remaining: int
    source_note: str | None
    overall: str
    passed: int
    total: int
    items: list[GateItemOut]


class GateItemUpdate(BaseModel):
    result_value: float | None = None
    result_text: str | None = None
    manual_status: str | None = None  # pass/fail/null
    recorded_on: date | None = None
    # CSS protocol convenience: send the two split times and CSS is derived.
    t400_s: float | None = Field(default=None, gt=0)
    t200_s: float | None = Field(default=None, gt=0)

    @field_validator("manual_status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v not in (None, "pass", "fail"):
            raise ValueError("manual_status must be pass, fail or null")
        return v


# --- Milestones ------------------------------------------------------------


class MilestoneOut(BaseModel):
    id: int
    key: str
    title: str
    target_date: date | None
    done: bool
    done_on: date | None
    note: str | None
    days_remaining: int | None
    overdue: bool
    model_config = ConfigDict(from_attributes=True)


class MilestoneUpdate(BaseModel):
    done: bool | None = None
    done_on: date | None = None
    target_date: date | None = None
    note: str | None = None


# --- Threshold history -----------------------------------------------------


class ThresholdCreate(BaseModel):
    test_date: date
    metric: str
    value: float = Field(gt=0)
    protocol: str | None = None
    note: str | None = None

    @field_validator("metric")
    @classmethod
    def _metric(cls, v: str) -> str:
        if v not in THRESHOLD_METRICS:
            raise ValueError(f"metric must be one of {sorted(THRESHOLD_METRICS)}")
        return v


class ThresholdOut(BaseModel):
    id: int
    test_date: date
    discipline: str
    metric: str
    value: float
    unit: str
    source: str
    protocol: str | None
    note: str | None
    model_config = ConfigDict(from_attributes=True)


class PhaseOut(BaseModel):
    number: int
    name: str
    start_date: date
    end_date: date | None  # day before the next phase starts / race day


class ThresholdHistory(BaseModel):
    tests: list[ThresholdOut]
    phases: list[PhaseOut]
    race_date: date | None
    metric_units: dict[str, str]


# --- Injury / niggle log ---------------------------------------------------


class InjuryCreate(BaseModel):
    date: date
    body_region: str = Field(min_length=1)
    pain_scale: int = Field(ge=1, le=10)
    note: str | None = None


class InjuryOut(InjuryCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class InjuryWeek(BaseModel):
    week_start: date
    max_pain: int
    entries: int
    regions: list[str]


class InjurySummary(BaseModel):
    entries: list[InjuryOut]
    weekly: list[InjuryWeek]


# --- Goal gap ----------------------------------------------------------------


class GoalLeg(BaseModel):
    leg: str
    budget_s: int
    projected_s: int | None
    delta_s: int | None
    basis: str | None
    source: str | None
    estimate_date: date | None
    assumption: str


class GoalRequired(BaseModel):
    css_pace_s_per_100m: float
    ftp_w: int
    hm_standalone_s: int
    run_pace_s_per_km: int


class GoalGap(BaseModel):
    target_low_s: int
    target_high_s: int
    transitions_s: int
    legs: list[GoalLeg]
    projected_total_s: int
    delta_to_target_high_s: int
    delta_to_target_low_s: int
    complete: bool
    missing_legs: list[str]
    required: GoalRequired
    race_date: date | None = None
    days_to_race: int | None = None
    note: str
