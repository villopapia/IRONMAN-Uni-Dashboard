from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from sqlalchemy.orm import relationship

from ..database import Base


class WeightedAverageSnapshot(Base):
    """Timestamped series of the module-weighted % (spec item 13). One row per
    academic year per day - the latest recompute that day wins - written
    whenever a mark / level / credit value changes, so the series only moves
    when the underlying number actually does.
    """

    __tablename__ = "weighted_average_snapshots"
    __table_args__ = (UniqueConstraint("academic_year", "recorded_on"),)

    id = Column(Integer, primary_key=True)
    academic_year = Column(String, nullable=False, index=True)
    recorded_on = Column(Date, nullable=False)
    weighted_average_pct = Column(Float, nullable=False)
    classification_estimate = Column(String, nullable=True)
    modules_counted = Column(Integer, nullable=False)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AcademicDeadline(Base):
    """Assignment / exam due dates (spec item 12). Manual entry only - the
    Google Calendar has [ASSIGN]/[EXAM] *study blocks* but no actual due-date
    events (checked against the live calendar 2026-09-23), so there is no
    connected source to pull these from yet.
    """

    __tablename__ = "academic_deadlines"

    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("academic_modules.id"), nullable=True, index=True)
    assessment_id = Column(Integer, ForeignKey("academic_assessments.id"), nullable=True)
    title = Column(String, nullable=False)
    due_at = Column(DateTime, nullable=False, index=True)
    kind = Column(String, nullable=False, default="assignment")  # assignment/exam/test/other
    weight_pct = Column(Float, nullable=True)  # % of the module mark, if known
    status = Column(String, nullable=False, default="pending")  # pending/submitted
    note = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    module = relationship("AcademicModule")
    assessment = relationship("AcademicAssessment")


class StudyLog(Base):
    __tablename__ = "study_logs"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    hours = Column(Float, nullable=False)
    module_id = Column(Integer, ForeignKey("academic_modules.id"), nullable=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StudyTarget(Base):
    """Manual weekly study-hours target, timestamped so changing it doesn't
    rewrite past weeks' compliance. When none is set, the compliance view
    falls back to the hours of study blocks planned in Google Calendar.
    """

    __tablename__ = "study_targets"

    id = Column(Integer, primary_key=True)
    effective_from = Column(Date, nullable=False, index=True)
    weekly_hours = Column(Float, nullable=False)
    note = Column(String, nullable=True)


class ExamPrepItem(Base):
    """One topic or past paper on a module's exam-prep checklist (spec item
    15). Coverage % = done / total per module.
    """

    __tablename__ = "exam_prep_items"

    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("academic_modules.id"), nullable=False, index=True)
    kind = Column(String, nullable=False, default="topic")  # topic/past_paper
    title = Column(String, nullable=False)
    done = Column(Boolean, nullable=False, default=False)
    done_on = Column(Date, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
