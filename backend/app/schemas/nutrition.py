from datetime import date

from pydantic import BaseModel, ConfigDict


class NutritionPlanResponse(BaseModel):
    slot_labels: dict[str, str]
    meal_options: dict[str, list[str]]
    notes: list[str]


class NutritionLogCreate(BaseModel):
    date: date
    slot: str
    description: str
    followed_plan: bool = True


class NutritionLogOut(NutritionLogCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class NutritionDaySummary(BaseModel):
    date: date
    logs: list[NutritionLogOut]
    slots_missing: list[str]


class SupplementProtocolOut(BaseModel):
    id: int
    name: str
    dose: float | None
    unit: str | None
    timing: str | None
    note: str | None
    needs_dose: bool
    model_config = ConfigDict(from_attributes=True)


class SupplementLogCreate(BaseModel):
    date: date
    supplement_id: int
    taken: bool = True


class SupplementLogOut(SupplementLogCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SupplementDaySummary(BaseModel):
    date: date
    protocols: list[SupplementProtocolOut]
    taken_supplement_ids: list[int]
