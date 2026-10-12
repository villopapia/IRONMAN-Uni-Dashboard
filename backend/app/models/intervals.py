from sqlalchemy import Column, Date, DateTime, Float, String

from ..database import Base


class IntervalsActivity(Base):
    __tablename__ = "intervals_activities"

    # sport / duration_min / name / date mirror Activity so overlay.rates_from
    # runs on either table.
    id = Column(String, primary_key=True)  # intervals.icu activity id
    name = Column(String, nullable=False)
    date = Column(DateTime, nullable=False, index=True)  # start_date_local
    type = Column(String, nullable=False)
    sport = Column(String, nullable=False, index=True)
    duration_min = Column(Float, nullable=False)  # moving_time / 60
    icu_training_load = Column(Float, nullable=True)


class IntervalsWellness(Base):
    __tablename__ = "intervals_wellness"

    date = Column(Date, primary_key=True)
    ctl = Column(Float, nullable=True)
    atl = Column(Float, nullable=True)
    ramp_rate = Column(Float, nullable=True)
    resting_hr = Column(Float, nullable=True)
    hrv = Column(Float, nullable=True)
    sleep_secs = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
