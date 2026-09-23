from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class GarminDailyMetricOut(BaseModel):
    date: date
    updated_at: datetime
    sleep_score: int | None
    sleep_duration_min: float | None
    body_battery_high: int | None
    body_battery_low: int | None
    training_readiness: int | None
    hrv_status: str | None
    hrv_value: float | None
    resting_hr: int | None
    vo2max_running: float | None
    training_status: str | None
    model_config = ConfigDict(from_attributes=True)
