"""Phase-gate checklist evaluation (spec item 7).

Pass/fail rules per item come from `PhaseGateItem.evaluation`:
  lt / lte / gte  numeric result vs. target (e.g. HM TT < 2:00:00)
  recorded        passes once a result exists (baseline tests - the plan's
                  criterion is "baseline recorded", not a number)
  manual          Chris sets pass/fail himself (e.g. "ITBS asymptomatic")
  auto_swim_freq  derived from Strava: >=N swims in each of the last 3
                  complete Mon-Sun weeks before the gate (or before today,
                  provisionally, while the gate is still in the future)
A manual_status on any item overrides the automatic result.

Before the gate date an item without a result is "pending"; after it,
"overdue" - never silently "fail", since a missing entry usually means
"not logged yet" rather than "failed".
"""

from datetime import date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.activity import Activity
from ..models.performance import THRESHOLD_METRICS, InjuryLog, PhaseGateItem, ThresholdTest

SWIM_FREQ_WEEKS = 3

# Recording one of these gate results also appends a row to the threshold
# history, so the trend lines and the gate share a single source of truth.
GATE_THRESHOLD_METRIC = {
    "p1_hm_tt": ("hm_time", "Phase 1 exit gate HM time trial"),
    "p1_css": ("css_pace", "400m + 200m CSS test"),
    "p1_lthr": ("lthr_bike", "20-min bike LTHR test"),
}

ITBS_REGION_HINTS = ("itb", "it band", "itbs", "knee", "iliotibial")


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def swim_frequency(db: Session, gate_date: date, today: date) -> dict:
    """Swims per week for the last SWIM_FREQ_WEEKS complete weeks ending
    before min(gate_date, today)."""
    reference = min(gate_date, today)
    # Most recent *complete* Mon-Sun week strictly before the reference day's week,
    # unless the reference is a Sunday (then that week is complete).
    last_week_start = _monday(reference) - (
        timedelta(days=0) if reference.weekday() == 6 else timedelta(days=7)
    )
    weeks = [last_week_start - timedelta(days=7 * i) for i in range(SWIM_FREQ_WEEKS)][::-1]
    window_start = weeks[0]
    window_end = weeks[-1] + timedelta(days=7)
    swims = (
        db.query(Activity.date)
        .filter(
            Activity.sport == "swim",
            Activity.date >= datetime.combine(window_start, datetime.min.time()),
            Activity.date < datetime.combine(window_end, datetime.min.time()),
        )
        .all()
    )
    counts = {w: 0 for w in weeks}
    for (d,) in swims:
        counts[_monday(d.date())] += 1
    return {"weeks": [{"week_start": w, "swims": counts[w]} for w in weeks]}


def _itbs_evidence(db: Session) -> str | None:
    rows = db.query(InjuryLog).order_by(InjuryLog.date.desc()).all()
    for row in rows:
        region = row.body_region.lower()
        if any(h in region for h in ITBS_REGION_HINTS):
            return (
                f"Last ITB/knee entry in the niggle log: {row.date.isoformat()} "
                f"({row.body_region}, pain {row.pain_scale}/10)."
            )
    return "No ITB/knee entries in the niggle log." if rows else "Niggle log is empty."


def evaluate_item(db: Session, item: PhaseGateItem, today: date) -> dict:
    status = "pending"
    detail = None

    if item.evaluation in ("lt", "lte", "gte") and item.result_value is not None:
        if item.target_value is None:
            status = "recorded"
        else:
            v, t = item.result_value, item.target_value
            ok = {"lt": v < t, "lte": v <= t, "gte": v >= t}[item.evaluation]
            status = "pass" if ok else "fail"
    elif item.evaluation == "recorded" and item.result_value is not None:
        status = "pass"
    elif item.evaluation == "auto_swim_freq":
        freq = swim_frequency(db, item.gate_date, today)
        counts = [w["swims"] for w in freq["weeks"]]
        target = item.target_value or 4
        detail = "Swims in last 3 complete weeks: " + ", ".join(str(c) for c in counts)
        if all(c >= target for c in counts):
            status = "pass" if today >= item.gate_date else "on_track"
        elif today >= item.gate_date:
            status = "fail"
        else:
            status = "behind"
    elif item.evaluation == "manual":
        detail = _itbs_evidence(db) if item.key.endswith("itbs") else None

    if item.manual_status in ("pass", "fail"):
        status = item.manual_status
    elif status == "pending" and today > item.gate_date:
        status = "overdue"

    return {
        "id": item.id,
        "key": item.key,
        "title": item.title,
        "criterion": item.criterion,
        "evaluation": item.evaluation,
        "target_value": item.target_value,
        "unit": item.unit,
        "result_value": item.result_value,
        "result_text": item.result_text,
        "recorded_on": item.recorded_on,
        "manual_status": item.manual_status,
        "status": status,
        "detail": detail,
    }


def gate_summary(db: Session, today: date | None = None) -> list[dict]:
    today = today or date.today()
    items = db.query(PhaseGateItem).order_by(PhaseGateItem.gate_date, PhaseGateItem.sort_order).all()
    gates: dict[date, dict] = {}
    for item in items:
        gate = gates.setdefault(
            item.gate_date,
            {
                "gate_date": item.gate_date,
                "gate_name": item.gate_name,
                "days_remaining": (item.gate_date - today).days,
                "source_note": item.source_note,
                "items": [],
            },
        )
        gate["items"].append(evaluate_item(db, item, today))

    for gate in gates.values():
        statuses = [i["status"] for i in gate["items"]]
        if any(s == "fail" for s in statuses):
            overall = "fail"
        elif all(s == "pass" for s in statuses):
            overall = "pass"
        elif any(s == "overdue" for s in statuses):
            overall = "incomplete"
        else:
            overall = "pending"
        gate["overall"] = overall
        gate["passed"] = sum(1 for s in statuses if s == "pass")
        gate["total"] = len(statuses)
    return list(gates.values())


def record_threshold_from_gate(db: Session, item: PhaseGateItem) -> None:
    """Mirror a gate result into the threshold history (upsert on a stable
    external_key, so re-editing the gate result updates rather than duplicates)."""
    mapping = GATE_THRESHOLD_METRIC.get(item.key)
    if not mapping or item.result_value is None:
        return
    metric, protocol = mapping
    discipline, unit, _ = THRESHOLD_METRICS[metric]
    key = f"gate:{item.key}"
    fields = dict(
        test_date=item.recorded_on or item.gate_date,
        discipline=discipline,
        metric=metric,
        value=item.result_value,
        unit=unit,
        source="phase_gate",
        protocol=protocol,
        note=item.result_text,
    )
    row = db.query(ThresholdTest).filter(ThresholdTest.external_key == key).first()
    if row is None:
        row = ThresholdTest(external_key=key, **fields)
        db.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.query(ThresholdTest).filter(ThresholdTest.external_key == key).first()
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
