"""One-off local seeding helpers.

`python -m app.seed activities` loads backend/data/strava_seed.json (a real
snapshot pulled from the connected Strava account on 2026-09-23) so the
dashboard has data to show before real STRAVA_* OAuth credentials are wired up
for `app.services.strava_sync`.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

from .database import SessionLocal
from .models.academic import AcademicAssessment, AcademicModule
from .models.activity import Activity, normalize_sport
from .models.nutrition import SupplementProtocol
from .models.performance import Milestone, PhaseGateItem

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "data" / "strava_seed.json"


def seed_activities() -> int:
    db = SessionLocal()
    try:
        raw_activities = json.loads(FIXTURE_PATH.read_text())
        inserted = 0
        for raw in raw_activities:
            if db.query(Activity).filter(Activity.external_id == raw["id"]).first():
                continue
            sport_type = raw["sport_type"]
            db.add(
                Activity(
                    external_id=raw["id"],
                    name=raw["name"],
                    date=datetime.fromisoformat(raw["start_local"]),
                    sport_type=sport_type,
                    sport=normalize_sport(sport_type),
                    is_indoor=raw.get("is_trainer", False),
                    duration_min=raw["moving_time"] / 60,
                    distance_km=raw["distance"] / 1000,
                    avg_hr=raw.get("avg_hr"),
                    max_hr=raw.get("max_hr"),
                    calories=raw.get("calories"),
                    source="strava",
                )
            )
            inserted += 1
        db.commit()
        return inserted
    finally:
        db.close()


def seed_supplements() -> int:
    """Seeds supplements confirmed by the user. Dose/unit are left null until
    they're given explicitly - don't guess a dose for a real supplement stack.
    """
    db = SessionLocal()
    try:
        existing_names = {s.name for s in db.query(SupplementProtocol).all()}
        to_add = [
            ("Collagen + Vitamin C", "pre-training"),
            ("Electrolyte mix (homemade)", None),
            ("Omega 3", None),
            ("Magnesium glycinate", None),
            ("Vitamin D3 + K2", None),
        ]
        inserted = 0
        for name, timing in to_add:
            if name in existing_names:
                continue
            db.add(SupplementProtocol(name=name, dose=None, unit=None, timing=timing))
            inserted += 1
        db.commit()
        return inserted
    finally:
        db.close()


ACADEMIC_YEAR = "2026/2027"

# Modules confirmed in conversation with Chris (assessment weightings) or seen
# as real [LEC] events in his Google Calendar. FHEQ level + credits were never
# given, so they stay null - classify() excludes and flags them rather than
# guessing a weight. Assessment names are generic because only the weights
# were given, not what each component is.
SEED_MODULES = [
    (
        "Automata, Computation & Complexity",
        "Automata, Computation & Complexity",
        [("Exam 1", 50.0), ("Exam 2", 50.0)],
    ),
    (
        "Programming Language Principles",
        "Programming Language Principles",
        [("Component 1", 30.0), ("Component 2", 30.0), ("Component 3", 40.0)],
    ),
    ("Databases and Logic", "Databases and Logic", [("Exam", 100.0)]),
    # In the lecture timetable, but no assessment weighting given yet.
    ("Foundations and Applications", "Foundations and Applications", []),
]

PHASE1_GATE = date(2026, 10, 25)
PHASE1_GATE_NAME = "Phase 1 → 2 exit gate"
_P1_SOURCE = (
    "From your calendar: '🏁 PHASE 1: BASE — Start' (Aug 10) gate list and "
    "'🏃 HM Time Trial — Phase 1 Exit Gate' (Oct 25)."
)

# key, title, criterion, evaluation, target_value, unit
SEED_GATE_ITEMS = [
    (
        "p1_hm_tt",
        "Half-marathon time trial",
        "Sub-2:00 (gate). Event target: sub-1:55, ideally sub-1:50.",
        "lt",
        2 * 3600.0,
        "s",
    ),
    (
        "p1_css",
        "Swim CSS retest (400m + 200m)",
        "Baseline recorded. CSS = (T400 − T200) / 2 per 100m.",
        "recorded",
        None,
        "s/100m",
    ),
    (
        "p1_lthr",
        "Bike 20-min LTHR test",
        "Baseline recorded (HR-based FTP baseline - no power meter yet).",
        "recorded",
        None,
        "bpm",
    ),
    (
        "p1_itbs",
        "ITBS asymptomatic ≥3 weeks",
        "No ITBS symptoms for 3+ consecutive weeks - your call, checked "
        "against the niggle log.",
        "manual",
        None,
        None,
    ),
    (
        "p1_swim_freq",
        "Consistent 4x/week swimming",
        "≥4 Strava swims in each of the last 3 complete weeks before the gate.",
        "auto_swim_freq",
        4.0,
        "swims/wk",
    ),
]

# key, title, target_date, note
SEED_MILESTONES = [
    (
        "tt_frame",
        "TT frame purchase",
        None,
        "Dates conflict: your Phase 1 notes say 'target: buy by Jan 2027' and "
        "the Phase 2→3 gate (Jan 17 2027) needs 'bike ordered / arriving Jan "
        "2027', but you've also said the bike arrives Nov 2026. Set the real date.",
    ),
    (
        "ftp_baseline",
        "FTP baseline test",
        date(2026, 10, 25),
        "Phase 1 exit gate: 'CSS + FTP baseline recorded'. Planned as the "
        "Thu Oct 22 bike 20-min test (HR-based until a power meter arrives).",
    ),
    (
        "power_meter",
        "Power meter arrival",
        date(2027, 1, 18),
        "Phase 2 gate notes: 'move to outdoor+power in Phase 3' - Phase 3 "
        "starts Jan 18 2027.",
    ),
    (
        "tt_fit",
        "TT bike fit",
        None,
        "No date in the plan yet - set once the bike's arrival date is confirmed.",
    ),
    (
        "outdoor_ride",
        "Outdoor ride before race day",
        date(2027, 1, 19),
        "First outdoor bike session in your calendar (Phase 3 'Bike FTP: "
        "3x12' @ FTP (outdoor, 90')'). Race day (Jul 11 2027) is the hard deadline.",
    ),
]


def seed_extension() -> dict[str, int]:
    """Idempotent seed for the training-load / academic-trajectory extension:
    academic modules, the Oct 25 phase-gate checklist, and equipment
    milestones. Safe to re-run - matches on name / key, never overwrites
    anything Chris has edited since.
    """
    counts = {"modules": 0, "assessments": 0, "gate_items": 0, "milestones": 0}
    db = SessionLocal()
    try:
        existing_modules = {
            m.name: m
            for m in db.query(AcademicModule)
            .filter(AcademicModule.academic_year == ACADEMIC_YEAR)
            .all()
        }
        for name, tag, assessments in SEED_MODULES:
            if name in existing_modules:
                continue
            module = AcademicModule(
                academic_year=ACADEMIC_YEAR,
                name=name,
                calendar_tag=tag,
                fheq_level=None,
                credits=None,
            )
            for a_name, weight in assessments:
                module.assessments.append(
                    AcademicAssessment(name=a_name, weight_pct=weight, mark_pct=None)
                )
                counts["assessments"] += 1
            db.add(module)
            counts["modules"] += 1

        existing_gate_keys = {k for (k,) in db.query(PhaseGateItem.key).all()}
        for order, (key, title, criterion, evaluation, target, unit) in enumerate(
            SEED_GATE_ITEMS
        ):
            if key in existing_gate_keys:
                continue
            db.add(
                PhaseGateItem(
                    key=key,
                    gate_date=PHASE1_GATE,
                    gate_name=PHASE1_GATE_NAME,
                    title=title,
                    criterion=criterion,
                    evaluation=evaluation,
                    target_value=target,
                    unit=unit,
                    source_note=_P1_SOURCE,
                    sort_order=order,
                )
            )
            counts["gate_items"] += 1

        existing_milestone_keys = {k for (k,) in db.query(Milestone.key).all()}
        for order, (key, title, target_date, note) in enumerate(SEED_MILESTONES):
            if key in existing_milestone_keys:
                continue
            db.add(
                Milestone(
                    key=key, title=title, target_date=target_date, note=note, sort_order=order
                )
            )
            counts["milestones"] += 1

        db.commit()
        return counts
    finally:
        db.close()


if __name__ == "__main__":
    commands = ("activities", "supplements", "extension")
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("Usage: python -m app.seed activities|supplements|extension")
        sys.exit(1)
    if sys.argv[1] == "activities":
        count = seed_activities()
        print(f"Seeded {count} activities")
    elif sys.argv[1] == "supplements":
        count = seed_supplements()
        print(f"Seeded {count} supplement protocols")
    else:
        print(f"Seeded {seed_extension()}")
