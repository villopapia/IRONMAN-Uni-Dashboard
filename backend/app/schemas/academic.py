from pydantic import BaseModel, ConfigDict


class AssessmentBase(BaseModel):
    name: str
    weight_pct: float
    mark_pct: float | None = None


class AssessmentCreate(AssessmentBase):
    pass


class AssessmentUpdate(BaseModel):
    name: str | None = None
    weight_pct: float | None = None
    mark_pct: float | None = None


class AssessmentOut(AssessmentBase):
    id: int
    module_id: int
    model_config = ConfigDict(from_attributes=True)


class ModuleBase(BaseModel):
    academic_year: str
    name: str
    calendar_tag: str | None = None
    fheq_level: int | None = None  # null until confirmed - excluded from the average
    credits: int | None = None


class ModuleCreate(ModuleBase):
    pass


class ModuleOut(ModuleBase):
    id: int
    assessments: list[AssessmentOut] = []
    model_config = ConfigDict(from_attributes=True)


class ModuleUpdate(BaseModel):
    name: str | None = None
    calendar_tag: str | None = None
    fheq_level: int | None = None
    credits: int | None = None


class ModuleBreakdown(BaseModel):
    module_id: int
    name: str
    fheq_level: int | None
    credits: int | None
    mark_pct: float | None
    fully_graded: bool
    needs_level_credits: bool = False


class ClassificationSummary(BaseModel):
    weighted_average_pct: float | None
    classification_estimate: str | None
    modules: list[ModuleBreakdown]
    methodology_note: str
