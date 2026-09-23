"""HRV / resting-HR as a rolling trend against a baseline (spec item 10).

- 7-day rolling mean of whatever days have a reading (needs >= 3 of 7).
- Baseline: the latest stored RecoveryBaseline for that metric (manual or a
  saved snapshot) if there is one; otherwise an automatic one - the mean of
  days 8-35 before today (28 days, excluding the current week so a bad week
  doesn't drag its own baseline down), needing >= 14 readings.
- "Normal range" = baseline +/- 1 SD of that same 28-day window. The trend
  is flagged when the 7-day mean leaves it in the unfavourable direction
  (HRV below, RHR above). This is a documented heuristic, not a clinical
  threshold; with no SD available (too little history) nothing is flagged.
"""

from datetime import date, timedelta
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from ..models.garmin import GarminDailyMetric
from ..models.performance import RecoveryBaseline

ROLLING_DAYS = 7
MIN_ROLLING = 3
BASELINE_WINDOW = (8, 35)  # days back, inclusive
MIN_BASELINE = 14

METRICS = {"hrv": ("hrv_value", "ms", "low"), "rhr": ("resting_hr", "bpm", "high")}


def _window_values(values: dict[date, float], today: date) -> list[float]:
    lo, hi = BASELINE_WINDOW
    return [
        v for d, v in values.items() if today - timedelta(days=hi) <= d <= today - timedelta(days=lo)
    ]


def baseline_for(db: Session, metric: str, values: dict[date, float], today: date) -> dict:
    window = _window_values(values, today)
    sd = round(pstdev(window), 1) if len(window) >= MIN_BASELINE else None
    stored = (
        db.query(RecoveryBaseline)
        .filter(RecoveryBaseline.metric == metric, RecoveryBaseline.effective_from <= today)
        .order_by(RecoveryBaseline.effective_from.desc(), RecoveryBaseline.id.desc())
        .first()
    )
    if stored:
        return {
            "value": stored.value,
            "method": stored.method,
            "effective_from": stored.effective_from,
            "sd": sd,
            "n": len(window),
        }
    if len(window) >= MIN_BASELINE:
        return {
            "value": round(mean(window), 1),
            "method": "auto_28d",
            "effective_from": None,
            "sd": sd,
            "n": len(window),
        }
    return {"value": None, "method": "insufficient_history", "effective_from": None, "sd": None, "n": len(window)}


def recovery_trend(db: Session, days: int = 42, today: date | None = None) -> dict:
    today = today or date.today()
    # Pull enough history for the baseline window as well as the chart.
    earliest = today - timedelta(days=max(days, BASELINE_WINDOW[1]) + ROLLING_DAYS)
    rows = (
        db.query(GarminDailyMetric)
        .filter(GarminDailyMetric.date >= earliest, GarminDailyMetric.date <= today)
        .all()
    )
    values: dict[str, dict[date, float]] = {m: {} for m in METRICS}
    for r in rows:
        for m, (field, _, _) in METRICS.items():
            v = getattr(r, field)
            if v is not None:
                values[m][r.date] = float(v)

    def rolling(m: str, d: date) -> float | None:
        vals = [
            values[m][d - timedelta(days=i)]
            for i in range(ROLLING_DAYS)
            if (d - timedelta(days=i)) in values[m]
        ]
        return round(mean(vals), 1) if len(vals) >= MIN_ROLLING else None

    series = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        series.append(
            {
                "date": d,
                "hrv": values["hrv"].get(d),
                "rhr": values["rhr"].get(d),
                "hrv_7d": rolling("hrv", d),
                "rhr_7d": rolling("rhr", d),
            }
        )

    summary = {}
    for m, (_, unit, bad_direction) in METRICS.items():
        base = baseline_for(db, m, values[m], today)
        current = rolling(m, today)
        # If today has no reading yet, fall back to the latest rolling value.
        if current is None:
            current = next((p[f"{m}_7d"] for p in reversed(series) if p[f"{m}_7d"] is not None), None)
        deviation = (
            round((current - base["value"]) / base["value"] * 100, 1)
            if current is not None and base["value"]
            else None
        )
        flag = None
        if current is not None and base["value"] is not None and base["sd"]:
            if bad_direction == "low" and current < base["value"] - base["sd"]:
                flag = "below_normal"
            elif bad_direction == "high" and current > base["value"] + base["sd"]:
                flag = "above_normal"
            else:
                flag = "normal"
        summary[m] = {
            "unit": unit,
            "rolling_7d": current,
            "baseline": base,
            "deviation_pct": deviation,
            "flag": flag,
            "readings": len(values[m]),
            "first_reading": min(values[m]) if values[m] else None,
        }

    return {"series": series, "metrics": summary}
