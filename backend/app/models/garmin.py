from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String

from ..database import Base


class GarminDailyMetric(Base):
    __tablename__ = "garmin_daily_metrics"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    sleep_score = Column(Integer, nullable=True)
    sleep_duration_min = Column(Float, nullable=True)
    body_battery_high = Column(Integer, nullable=True)
    body_battery_low = Column(Integer, nullable=True)
    training_readiness = Column(Integer, nullable=True)
    hrv_status = Column(String, nullable=True)  # e.g. "BALANCED", "LOW"
    hrv_value = Column(Float, nullable=True)  # last-night average, ms
    resting_hr = Column(Integer, nullable=True)
    vo2max_running = Column(Float, nullable=True)
    training_status = Column(String, nullable=True)  # e.g. "PRODUCTIVE", "PEAKING"
