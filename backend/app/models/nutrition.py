from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String

from ..database import Base

# Matches the dietician plan's slot structure: ΠΡΩΙΝΟ, Ενδ, ΚΥΡΙΩΣ ΓΕΥΜΑ, Ενδ, Ενδ, ΒΡΑΔΙΝΟ
MEAL_SLOTS = ["breakfast", "snack1", "main_meal", "snack2", "snack3", "dinner"]


class NutritionLog(Base):
    __tablename__ = "nutrition_logs"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    slot = Column(String, nullable=False)  # one of MEAL_SLOTS
    description = Column(String, nullable=False)  # chosen plan option, or free text
    followed_plan = Column(Boolean, nullable=False, default=True)


class SupplementProtocol(Base):
    __tablename__ = "supplement_protocols"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    dose = Column(Float, nullable=True)  # null until the user provides a real dose
    unit = Column(String, nullable=True)
    timing = Column(String, nullable=True)  # e.g. "pre-training"
    note = Column(String, nullable=True)


class SupplementLog(Base):
    __tablename__ = "supplement_logs"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    supplement_id = Column(Integer, ForeignKey("supplement_protocols.id"), nullable=False)
    taken = Column(Boolean, nullable=False, default=True)
