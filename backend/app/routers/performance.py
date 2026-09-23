"""Race-prep endpoints: phase gates, equipment milestones, threshold-test
history, and the injury / niggle log."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.performance import (
    THRESHOLD_METRICS,
    InjuryLog,
    Milestone,
    PhaseGateItem,
    ThresholdTest,
)
from ..schemas.performance import (
    GoalGap,
    GateItemUpdate,
    GateOut,
    InjuryCreate,
    InjuryOut,
    InjurySummary,
    InjuryWeek,
    MilestoneOut,
    MilestoneUpdate,
    ThresholdCreate,
    ThresholdHistory,
    ThresholdOut,
)
from ..services.goal_gap import goal_gap
from ..services.phase_gates import gate_summary, record_threshold_from_gate
from ..services.plan_sync import get_phases, get_race_date

router = APIRouter()


# --- Phase gates -----------------------------------------------------------


@router.get("/gates", response_model=list[GateOut])
def list_gates(db: Session = Depends(get_db)):
    return gate_summary(db)


@router.patch("/gates/{key}", response_model=list[GateOut])
def update_gate_item(key: str, payload: GateItemUpdate, db: Session = Depends(get_db)):
    item = db.query(PhaseGateItem).filter(PhaseGateItem.key == key).first()
    if not item:
        raise HTTPException(404, "Gate item not found")

    data = payload.model_dump(exclude_unset=True)
    t400, t200 = data.pop("t400_s", None), data.pop("t200_s", None)
    if t400 is not None or t200 is not None:
        if t400 is None or t200 is None or t400 <= t200:
            raise HTTPException(400, "CSS needs both splits, with the 400m slower than the 200m")
        # Standard CSS formula: pace per 100m = (T400 - T200) / 2.
        data["result_value"] = round((t400 - t200) / 2, 1)
        data["result_text"] = f"400m {_fmt(t400)} / 200m {_fmt(t200)}"

    for field, value in data.items():
        setattr(item, field, value)
    if item.result_value is not None and item.recorded_on is None:
        item.recorded_on = date.today()
    db.commit()
    db.refresh(item)
    record_threshold_from_gate(db, item)
    return gate_summary(db)


def _fmt(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


# --- Goal gap ----------------------------------------------------------------


@router.get("/goal-gap", response_model=GoalGap)
def get_goal_gap(db: Session = Depends(get_db)):
    result = goal_gap(db)
    race = get_race_date(db)
    result["race_date"] = race
    result["days_to_race"] = (race - date.today()).days if race else None
    return result


# --- Milestones ------------------------------------------------------------


def _milestone_out(m: Milestone, today: date) -> MilestoneOut:
    days = (m.target_date - today).days if m.target_date else None
    return MilestoneOut(
        id=m.id,
        key=m.key,
        title=m.title,
        target_date=m.target_date,
        done=m.done,
        done_on=m.done_on,
        note=m.note,
        days_remaining=days,
        overdue=bool(days is not None and days < 0 and not m.done),
    )


@router.get("/milestones", response_model=list[MilestoneOut])
def list_milestones(db: Session = Depends(get_db)):
    today = date.today()
    return [
        _milestone_out(m, today)
        for m in db.query(Milestone).order_by(Milestone.sort_order).all()
    ]


@router.patch("/milestones/{milestone_id}", response_model=MilestoneOut)
def update_milestone(
    milestone_id: int, payload: MilestoneUpdate, db: Session = Depends(get_db)
):
    m = db.get(Milestone, milestone_id)
    if not m:
        raise HTTPException(404, "Milestone not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(m, field, value)
    if data.get("done") is True and m.done_on is None:
        m.done_on = date.today()
    if data.get("done") is False:
        m.done_on = None
    db.commit()
    db.refresh(m)
    return _milestone_out(m, date.today())


# --- Threshold history -----------------------------------------------------


@router.get("/thresholds", response_model=ThresholdHistory)
def threshold_history(metric: str | None = None, db: Session = Depends(get_db)):
    query = db.query(ThresholdTest)
    if metric:
        query = query.filter(ThresholdTest.metric == metric)
    return ThresholdHistory(
        tests=query.order_by(ThresholdTest.test_date, ThresholdTest.id).all(),
        phases=get_phases(db),
        race_date=get_race_date(db),
        metric_units={k: v[1] for k, v in THRESHOLD_METRICS.items()},
    )


@router.post("/thresholds", response_model=ThresholdOut)
def create_threshold(payload: ThresholdCreate, db: Session = Depends(get_db)):
    discipline, unit, _ = THRESHOLD_METRICS[payload.metric]
    row = ThresholdTest(
        discipline=discipline, unit=unit, source="manual", **payload.model_dump()
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/thresholds/{test_id}")
def delete_threshold(test_id: int, db: Session = Depends(get_db)):
    row = db.get(ThresholdTest, test_id)
    if not row:
        raise HTTPException(404, "Threshold test not found")
    if row.source != "manual":
        raise HTTPException(
            400,
            "Only manually-entered tests can be deleted here - gate results are "
            "edited via the gate, Garmin estimates are re-synced automatically.",
        )
    db.delete(row)
    db.commit()
    return {"deleted": test_id}


# --- Injury / niggle log ---------------------------------------------------


@router.get("/injuries", response_model=InjurySummary)
def list_injuries(db: Session = Depends(get_db)):
    entries = db.query(InjuryLog).order_by(InjuryLog.date.desc(), InjuryLog.id.desc()).all()
    weeks: dict[date, dict] = {}
    for e in entries:
        wk = e.date - timedelta(days=e.date.weekday())
        w = weeks.setdefault(wk, {"week_start": wk, "max_pain": 0, "entries": 0, "regions": []})
        w["max_pain"] = max(w["max_pain"], e.pain_scale)
        w["entries"] += 1
        if e.body_region not in w["regions"]:
            w["regions"].append(e.body_region)
    return InjurySummary(
        entries=entries,
        weekly=[InjuryWeek(**w) for w in sorted(weeks.values(), key=lambda w: w["week_start"])],
    )


@router.post("/injuries", response_model=InjuryOut)
def create_injury(payload: InjuryCreate, db: Session = Depends(get_db)):
    row = InjuryLog(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/injuries/{injury_id}")
def delete_injury(injury_id: int, db: Session = Depends(get_db)):
    row = db.get(InjuryLog, injury_id)
    if not row:
        raise HTTPException(404, "Entry not found")
    db.delete(row)
    db.commit()
    return {"deleted": injury_id}
