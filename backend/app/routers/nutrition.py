from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.nutrition import MEAL_SLOTS, NutritionLog, SupplementLog, SupplementProtocol
from ..schemas.nutrition import (
    NutritionDaySummary,
    NutritionLogCreate,
    NutritionLogOut,
    NutritionPlanResponse,
    SupplementDaySummary,
    SupplementLogCreate,
    SupplementLogOut,
    SupplementProtocolOut,
)
from ..services.nutrition_plan import MEAL_OPTIONS, PROSOXI_NOTES, SLOT_LABELS

router = APIRouter()


def _to_protocol_out(protocol: SupplementProtocol) -> SupplementProtocolOut:
    return SupplementProtocolOut(
        id=protocol.id,
        name=protocol.name,
        dose=protocol.dose,
        unit=protocol.unit,
        timing=protocol.timing,
        note=protocol.note,
        needs_dose=protocol.dose is None,
    )


@router.get("/plan", response_model=NutritionPlanResponse)
def get_plan():
    return NutritionPlanResponse(
        slot_labels=SLOT_LABELS, meal_options=MEAL_OPTIONS, notes=PROSOXI_NOTES
    )


@router.post("/log", response_model=NutritionLogOut)
def log_meal(payload: NutritionLogCreate, db: Session = Depends(get_db)):
    if payload.slot not in MEAL_SLOTS:
        raise HTTPException(400, f"slot must be one of {MEAL_SLOTS}")
    entry = NutritionLog(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/day", response_model=NutritionDaySummary)
def nutrition_day(day: date, db: Session = Depends(get_db)):
    logs = db.query(NutritionLog).filter(NutritionLog.date == day).all()
    logged_slots = {log.slot for log in logs}
    return NutritionDaySummary(
        date=day,
        logs=logs,
        slots_missing=[slot for slot in MEAL_SLOTS if slot not in logged_slots],
    )


@router.get("/supplements", response_model=list[SupplementProtocolOut])
def list_supplements(db: Session = Depends(get_db)):
    return [_to_protocol_out(p) for p in db.query(SupplementProtocol).all()]


@router.post("/supplements/log", response_model=SupplementLogOut)
def log_supplement(payload: SupplementLogCreate, db: Session = Depends(get_db)):
    protocol = db.get(SupplementProtocol, payload.supplement_id)
    if not protocol:
        raise HTTPException(404, "Supplement protocol not found")
    entry = SupplementLog(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/supplements/day", response_model=SupplementDaySummary)
def supplements_day(day: date, db: Session = Depends(get_db)):
    protocols = db.query(SupplementProtocol).all()
    taken = (
        db.query(SupplementLog)
        .filter(SupplementLog.date == day, SupplementLog.taken.is_(True))
        .all()
    )
    return SupplementDaySummary(
        date=day,
        protocols=[_to_protocol_out(p) for p in protocols],
        taken_supplement_ids=[log.supplement_id for log in taken],
    )
