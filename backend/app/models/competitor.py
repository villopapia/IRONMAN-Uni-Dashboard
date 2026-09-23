from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    note = Column(String, nullable=True)

    activities = relationship(
        "CompetitorActivity", back_populates="competitor", cascade="all, delete-orphan"
    )


class CompetitorActivity(Base):
    __tablename__ = "competitor_activities"

    id = Column(Integer, primary_key=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    sport = Column(String, nullable=False)  # run/bike/swim/gym/walk/other
    duration_min = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=True)
    note = Column(String, nullable=True)

    competitor = relationship("Competitor", back_populates="activities")
