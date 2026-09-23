from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from ..database import Base

# Strava's `sport_type` values (confirmed against the live connector: Run, Swim,
# Walk seen so far) collapsed to the four buckets the training rollup filters on.
# Indoor vs. outdoor is carried separately via `is_indoor` (Strava's `trainer`
# flag) rather than folded into this map, so e.g. `Ride` + trainer=true still
# matches the `bike` filter instead of silently falling through to "other" the
# way string-matching on `VirtualRide` alone would.
SPORT_MAP = {
    "Run": "run",
    "TrailRun": "run",
    "VirtualRun": "run",
    "Ride": "bike",
    "VirtualRide": "bike",
    "GravelRide": "bike",
    "MountainBikeRide": "bike",
    "EBikeRide": "bike",
    "Swim": "swim",
    "WeightTraining": "gym",
    "Workout": "gym",
    "Crossfit": "gym",
    "HighIntensityIntervalTraining": "gym",
    "Walk": "walk",
    "Hike": "walk",
}


def normalize_sport(sport_type: str) -> str:
    return SPORT_MAP.get(sport_type, "other")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    external_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    sport_type = Column(String, nullable=False)
    sport = Column(String, nullable=False, index=True)
    is_indoor = Column(Boolean, nullable=False, default=False)
    duration_min = Column(Float, nullable=False)
    distance_km = Column(Float, nullable=True)
    avg_hr = Column(Float, nullable=True)
    max_hr = Column(Float, nullable=True)
    calories = Column(Float, nullable=True)
    source = Column(String, nullable=False, default="strava")

    # Strava's Relative Effort (API field `suffer_score`; the MCP connector
    # calls it `relative_effort`). Computed server-side by Strava from the
    # athlete's own HR zones - this is the per-session load input for
    # CTL/ATL/TSB, see app/services/training_load.py for why.
    relative_effort = Column(Float, nullable=True)
    # Power fields. Only meaningful for sport == "bike" once a power meter is
    # fitted - runs also report these (Garmin running power), so never read
    # them without filtering on sport first.
    average_watts = Column(Float, nullable=True)
    weighted_average_watts = Column(Float, nullable=True)  # Strava's NP-equivalent
    device_watts = Column(Boolean, nullable=True)  # True = measured, False = Strava-estimated
