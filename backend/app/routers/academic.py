from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.academic import AcademicAssessment, AcademicModule
from ..schemas.academic import (
    AssessmentCreate,
    AssessmentOut,
    AssessmentUpdate,
    ClassificationSummary,
    ModuleCreate,
    ModuleOut,
    ModuleUpdate,
)
from ..services.academic_tracking import snapshot_weighted_average
from ..services.classification import classify

router = APIRouter()


@router.get("/modules", response_model=list[ModuleOut])
def list_modules(academic_year: str | None = None, db: Session = Depends(get_db)):
    query = db.query(AcademicModule).options(joinedload(AcademicModule.assessments))
    if academic_year:
        query = query.filter(AcademicModule.academic_year == academic_year)
    return query.all()


@router.post("/modules", response_model=ModuleOut)
def create_module(payload: ModuleCreate, db: Session = Depends(get_db)):
    module = AcademicModule(**payload.model_dump())
    db.add(module)
    db.commit()
    db.refresh(module)
    snapshot_weighted_average(db, module.academic_year)
    return module


@router.patch("/modules/{module_id}", response_model=ModuleOut)
def update_module(module_id: int, payload: ModuleUpdate, db: Session = Depends(get_db)):
    """Mainly for filling in a module's FHEQ level + credits once confirmed -
    until then it's excluded from the weighted average."""
    module = db.get(AcademicModule, module_id)
    if not module:
        raise HTTPException(404, "Module not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(module, field, value)
    db.commit()
    db.refresh(module)
    snapshot_weighted_average(db, module.academic_year)
    return module


@router.post("/modules/{module_id}/assessments", response_model=AssessmentOut)
def create_assessment(
    module_id: int, payload: AssessmentCreate, db: Session = Depends(get_db)
):
    module = db.get(AcademicModule, module_id)
    if not module:
        raise HTTPException(404, "Module not found")
    assessment = AcademicAssessment(module_id=module_id, **payload.model_dump())
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    snapshot_weighted_average(db, module.academic_year)
    db.refresh(assessment)
    return assessment


@router.patch("/assessments/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: int, payload: AssessmentUpdate, db: Session = Depends(get_db)
):
    assessment = db.get(AcademicAssessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(assessment, field, value)
    db.commit()
    db.refresh(assessment)
    snapshot_weighted_average(db, assessment.module.academic_year)
    db.refresh(assessment)
    return assessment


@router.get("/summary", response_model=ClassificationSummary)
def summary(academic_year: str, db: Session = Depends(get_db)):
    modules = (
        db.query(AcademicModule)
        .options(joinedload(AcademicModule.assessments))
        .filter(AcademicModule.academic_year == academic_year)
        .all()
    )
    return classify(modules)
