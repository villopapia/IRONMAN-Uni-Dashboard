from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class AcademicModule(Base):
    __tablename__ = "academic_modules"

    id = Column(Integer, primary_key=True)
    academic_year = Column(String, nullable=False, index=True)  # e.g. "2026/2027"
    name = Column(String, nullable=False)
    calendar_tag = Column(String, nullable=True)  # e.g. "COM.UG2" from [LEC] calendar events
    # Nullable so a module can be tracked (deadlines, prep, assessments) before
    # its FHEQ level / credit value is confirmed - classify() excludes modules
    # missing either and flags them, rather than guessing a weight.
    fheq_level = Column(Integer, nullable=True)  # 1, 2, or 3
    credits = Column(Integer, nullable=True)

    assessments = relationship(
        "AcademicAssessment", back_populates="module", cascade="all, delete-orphan"
    )


class AcademicAssessment(Base):
    __tablename__ = "academic_assessments"

    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("academic_modules.id"), nullable=False)
    name = Column(String, nullable=False)
    weight_pct = Column(Float, nullable=False)  # % of module mark
    mark_pct = Column(Float, nullable=True)  # % achieved, null until graded

    module = relationship("AcademicModule", back_populates="assessments")
