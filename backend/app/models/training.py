from sqlalchemy import Column, Date, Float, Integer, String

from ..database import Base


class WeeklyTrainingTarget(Base):
    __tablename__ = "weekly_training_targets"

    id = Column(Integer, primary_key=True)
    week_label = Column(String, nullable=False)  # e.g. "Wk9"
    week_start_date = Column(Date, nullable=False, index=True)
    sport = Column(String, nullable=False)  # run/bike/swim/gym/walk/other
    target_minutes = Column(Float, nullable=False)
    target_distance_km = Column(Float, nullable=True)
    note = Column(String, nullable=True)
