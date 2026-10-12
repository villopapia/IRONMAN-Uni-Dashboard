from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, String, false

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
    hr_zone_secs = Column(JSON, nullable=True)  # icu_hr_zone_times: seconds in Z1..Z7, their zone boundaries
    distance_m = Column(Float, nullable=True)  # null for indoor rides
    race = Column(Boolean, nullable=False, default=False, server_default=false())  # intervals.icu's race flag


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
