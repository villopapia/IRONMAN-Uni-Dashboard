from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
)

from ..database import Base


class DailyTrainingLoad(Base):
    """Per-day, per-sport session load (sum of Strava Relative Effort, or the
    documented fallback). Rebuilt from `activities` after every Strava sync;
    CTL/ATL/TSB are computed from this on read, never stored, so they can't
    drift from a recomputation.
    """

    __tablename__ = "daily_training_loads"
    __table_args__ = (UniqueConstraint("date", "sport"),)

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    sport = Column(String, nullable=False)
    load = Column(Float, nullable=False)
    sessions = Column(Integer, nullable=False)
    # Sessions whose load came from the duration fallback rather than a real
    # Strava Relative Effort value.
    estimated_sessions = Column(Integer, nullable=False, default=0)


# metric -> (discipline, unit, lower_is_better)
THRESHOLD_METRICS: dict[str, tuple[str, str, bool]] = {
    "css_pace": ("swim", "s/100m", True),
    "ftp": ("bike", "W", False),
    "np_proxy": ("bike", "W", False),
    "lthr_bike": ("bike", "bpm", False),
    "lthr_run": ("run", "bpm", False),
    "threshold_pace": ("run", "s/km", True),
    "hm_time": ("run", "s", True),
    "hm_prediction": ("run", "s", True),
}


class ThresholdTest(Base):
    """One timestamped threshold test / estimate (spec item 3) - never a
    single overwritten "current value". `source` distinguishes a real test
    Chris logged ("manual", "phase_gate") from a device estimate ("garmin").
    """

    __tablename__ = "threshold_tests"

    id = Column(Integer, primary_key=True)
    test_date = Column(Date, nullable=False, index=True)
    discipline = Column(String, nullable=False)  # swim/bike/run
    metric = Column(String, nullable=False, index=True)  # key of THRESHOLD_METRICS
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    source = Column(String, nullable=False, default="manual")  # manual/phase_gate/garmin
    protocol = Column(String, nullable=True)  # e.g. "400/200 CSS test"
    note = Column(String, nullable=True)
    # Dedupe key for automated rows (e.g. "garmin:hm_prediction:2026-09-23");
    # null for manual entries.
    external_key = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PlannedSession(Base):
    """One planned item pulled from Google Calendar. Recurring (RRULE) events
    are expanded by Google itself (`singleEvents=true`), so each instance is
    its own row - more robust than re-implementing RRULE/EXDATE handling.

    kind: "session" (training, has a discipline), "study" (a bracket-tagged
    study block), "phase" (a PHASE N start marker), "race" (race / gate race
    days), "marker" (other plan markers - taper, peak week, gate test weeks).
    A multi-discipline event (a brick, "🚴🏊 Bike + Swim") produces one row
    per discipline, sharing `event_id`.
    """

    __tablename__ = "planned_sessions"

    id = Column(Integer, primary_key=True)
    external_id = Column(String, nullable=False, unique=True)  # event instance id + ":" + discipline
    event_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    start_at = Column(DateTime, nullable=True)  # local wall-clock; null for all-day
    end_at = Column(DateTime, nullable=True)
    kind = Column(String, nullable=False, index=True)
    discipline = Column(String, nullable=True)  # swim/bike/run/gym for kind=session
    title = Column(String, nullable=False)
    is_brick = Column(Boolean, nullable=False, default=False)
    strength_type = Column(String, nullable=True)  # upper_a/upper_b/mobility/other
    study_tag = Column(String, nullable=True)  # LEC/DEEP/... for kind=study
    # Chris's own override - for sessions Strava can't see (e.g. unrecorded
    # gym work) or to mark a planned session deliberately skipped.
    manual_status = Column(String, nullable=True)  # done/skipped
    synced_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PhaseGateItem(Base):
    """One criterion on a fixed-date phase gate checklist (spec item 7)."""

    __tablename__ = "phase_gate_items"

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)  # e.g. "p1_hm_tt"
    gate_date = Column(Date, nullable=False, index=True)
    gate_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    criterion = Column(String, nullable=False)  # human-readable pass criterion
    # How pass/fail is decided: "lt" (result < target), "lte", "gte",
    # "recorded" (pass once a result exists), "auto_swim_freq" (derived from
    # Strava), "manual" (Chris sets manual_status).
    evaluation = Column(String, nullable=False)
    target_value = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    result_value = Column(Float, nullable=True)
    result_text = Column(String, nullable=True)
    manual_status = Column(String, nullable=True)  # pass/fail - override
    recorded_on = Column(Date, nullable=True)
    source_note = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)


class Milestone(Base):
    """Equipment / logistics milestones that gate Phase 2+ specificity work
    (spec item 11)."""

    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    target_date = Column(Date, nullable=True)
    done = Column(Boolean, nullable=False, default=False)
    done_on = Column(Date, nullable=True)
    note = Column(String, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)


class InjuryLog(Base):
    """Free-text niggle log with a 1-10 pain scale and body region (spec
    item 9)."""

    __tablename__ = "injury_logs"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    body_region = Column(String, nullable=False)
    pain_scale = Column(Integer, nullable=False)  # 1-10, validated in the schema
    note = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RecoveryBaseline(Base):
    """A stored HRV / RHR baseline (spec item 10), timestamped so resetting it
    later doesn't erase what deviations were measured against before."""

    __tablename__ = "recovery_baselines"

    id = Column(Integer, primary_key=True)
    metric = Column(String, nullable=False, index=True)  # hrv/rhr
    value = Column(Float, nullable=False)
    effective_from = Column(Date, nullable=False)
    method = Column(String, nullable=False)  # manual / snapshot_28d
    note = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
