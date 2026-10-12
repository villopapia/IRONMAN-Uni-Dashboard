"""Readiness (Overview): resting HR, HRV, sleep and weight from the
intervals.icu wellness cache, each PASS / AMBER / RED, and one action line.

Chris's rules - the numbers are the constants below:
  RHR     7-day average: PASS below 55 bpm, AMBER 55 to under 58, RED 58+.
  HRV     the last 3 days against a band of mean +/- 1 SD over the 30 days
          before them (the days being judged are never in their own baseline):
          PASS if none is below the band, AMBER if 1-2 are, RED if all 3.
          No status if more than half of the 30 days have no reading, or one of
          the 3 days is missing. The 3 days end today, or yesterday while
          today's reading hasn't synced yet.
  Sleep   7-day average: PASS 7.5 h+, AMBER 7.0 to under 7.5, RED under 7.0.
  Weight  latest reading within +/- 1.5 kg of 61 kg = PASS, else AMBER; the row
          only exists with 4+ readings in the last 14 days.
  Action  0 RED = Continue, exactly 1 = fix that one thing, 2+ = recovery volume.
          AMBER never changes the action; it is only listed.

Missing data is "no_data": never a pass, never counted as RED. A 7-day average
needs AVG_MIN_VALUES readings to exist at all.
"""

from datetime import date, timedelta
from statistics import mean, stdev

from sqlalchemy.orm import Session

from ..models.intervals import IntervalsWellness

RHR_AMBER_FROM = 55.0  # bpm, 7-day average (baseline 49-51); below this = PASS
RHR_RED_FROM = 58.0
SLEEP_PASS_FROM = 7.5  # hours, 7-day average
SLEEP_AMBER_FROM = 7.0  # below this = RED
HRV_BASELINE_DAYS = 30
HRV_MAX_MISSING = 0.5  # share of the baseline days allowed to have no reading
HRV_RECENT_DAYS = 3
WEIGHT_TARGET_KG = 61.0
WEIGHT_TOLERANCE_KG = 1.5
WEIGHT_WINDOW_DAYS = 14
WEIGHT_MIN_VALUES = 4
AVG_DAYS = 7
AVG_MIN_VALUES = 4
SPARK_DAYS = 28
TREND_DAYS = 42
ACTIONS = ("Continue", "Fix that one thing this week", "Next week at recovery volume")


def average(values: list[float | None]) -> float | None:
    """Mean of the readings present; None (no data) with fewer than AVG_MIN_VALUES."""
    present = [v for v in values if v is not None]
    return mean(present) if len(present) >= AVG_MIN_VALUES else None


def rhr_status(avg: float | None) -> str:
    if avg is None:
        return "no_data"
    return "red" if avg >= RHR_RED_FROM else "amber" if avg >= RHR_AMBER_FROM else "pass"


def sleep_status(avg_hours: float | None) -> str:
    if avg_hours is None:
        return "no_data"
    return "pass" if avg_hours >= SLEEP_PASS_FROM else "amber" if avg_hours >= SLEEP_AMBER_FROM else "red"


def hrv_band(baseline: list[float | None]) -> tuple[float, float] | None:
    """(low, high) = mean +/- 1 SD of the baseline days; None when too many are missing."""
    present = [v for v in baseline if v is not None]
    if len(present) < 2 or len(baseline) - len(present) > HRV_MAX_MISSING * len(baseline):
        return None
    m, sd = mean(present), stdev(present)
    return m - sd, m + sd


def hrv_windows(daily: list[float | None]) -> tuple[list[float | None], list[float | None]]:
    """(baseline, recent) from daily readings, oldest first: the last
    HRV_RECENT_DAYS are judged, the HRV_BASELINE_DAYS before them are the baseline."""
    return daily[:-HRV_RECENT_DAYS][-HRV_BASELINE_DAYS:], daily[-HRV_RECENT_DAYS:]


def hrv_status(recent: list[float | None], band: tuple[float, float] | None) -> str:
    if band is None or not recent or any(v is None for v in recent):
        return "no_data"
    below = sum(v < band[0] for v in recent)
    return "red" if below == len(recent) else "amber" if below else "pass"


def weight_status(window: list[float | None]) -> str | None:
    """None = not enough readings: the row is hidden."""
    present = [v for v in window if v is not None]
    if len(present) < WEIGHT_MIN_VALUES:
        return None
    return "pass" if abs(present[-1] - WEIGHT_TARGET_KG) <= WEIGHT_TOLERANCE_KG else "amber"


def overall_action(statuses: list[str]) -> str:
    if all(s == "no_data" for s in statuses):
        return "No data"
    return ACTIONS[min(statuses.count("red"), 2)]


def readiness(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    span = HRV_BASELINE_DAYS + HRV_RECENT_DAYS + 1  # + 1: the HRV windows may end yesterday
    rows = db.query(IntervalsWellness).filter(IntervalsWellness.date > today - timedelta(days=span)).all()
    by_day = {w.date: w for w in rows}

    def window(field: str, days: int, end: date = today, scale: float = 1.0) -> list[float | None]:
        out = []
        for i in range(days - 1, -1, -1):
            v = getattr(by_day.get(end - timedelta(days=i)), field, None)
            out.append(v / scale if v is not None else None)
        return out

    def metric(key, label, status, value, unit, basis, field, scale=1.0, band=None) -> dict:
        spark = window(field, SPARK_DAYS, scale=scale)
        return {
            "key": key,
            "label": label,
            "status": status,
            "value": round(value, 1) if value is not None else None,
            "unit": unit,
            "basis": basis,
            "series": [
                {"date": today - timedelta(days=SPARK_DAYS - 1 - i), "value": round(v, 2) if v is not None else None}
                for i, v in enumerate(spark)
            ],
            "band": [round(b, 1) for b in band] if band else None,
        }

    def avg_basis(values: list[float | None]) -> str:
        n = sum(v is not None for v in values)
        return f"{AVG_DAYS}-day average" if n >= AVG_MIN_VALUES else f"insufficient data ({n} of {AVG_DAYS} days)"

    rhr = window("resting_hr", AVG_DAYS)
    sleep = window("sleep_secs", AVG_DAYS, scale=3600)

    hrv_end = today if getattr(by_day.get(today), "hrv", None) is not None else today - timedelta(days=1)
    hrv_base, hrv_recent = hrv_windows(window("hrv", HRV_BASELINE_DAYS + HRV_RECENT_DAYS, end=hrv_end))
    band = hrv_band(hrv_base)
    hrv = hrv_status(hrv_recent, band)
    if band is None:
        hrv_basis = f"insufficient data ({sum(v is not None for v in hrv_base)} of {HRV_BASELINE_DAYS} days)"
    elif hrv == "no_data":
        hrv_basis = f"insufficient data (a reading is missing in the last {HRV_RECENT_DAYS} days)"
    else:
        hrv_basis = f"latest; last {HRV_RECENT_DAYS} days vs prior {HRV_BASELINE_DAYS}-day band {band[0]:.0f}-{band[1]:.0f}"

    metrics = [
        metric("rhr", "Resting HR", rhr_status(average(rhr)), average(rhr), "bpm", avg_basis(rhr), "resting_hr"),
        metric("hrv", "HRV", hrv, hrv_recent[-1], "ms", hrv_basis, "hrv", band=band),
        metric("sleep", "Sleep", sleep_status(average(sleep)), average(sleep), "h", avg_basis(sleep), "sleep_secs", 3600),
    ]
    weight = window("weight", WEIGHT_WINDOW_DAYS)
    if weight_status(weight) is not None:
        latest = [v for v in weight if v is not None][-1]
        basis = f"latest; target {WEIGHT_TARGET_KG:g} +/- {WEIGHT_TOLERANCE_KG:g} kg"
        metrics.append(metric("weight", "Weight", weight_status(weight), latest, "kg", basis, "weight"))

    def labels(status: str) -> list[str]:
        return [m["label"] for m in metrics if m["status"] == status]

    return {
        "date": today,
        "action": overall_action([m["status"] for m in metrics]),
        "red": labels("red"),
        "amber": labels("amber"),
        "no_data": labels("no_data"),
        "metrics": metrics,
        "note": (
            f"Resting HR: {AVG_DAYS}-day average, PASS below {RHR_AMBER_FROM:g}, RED from {RHR_RED_FROM:g} bpm. "
            f"HRV: last {HRV_RECENT_DAYS} days against mean +/- 1 SD of the {HRV_BASELINE_DAYS} days before them (the shaded band); "
            f"AMBER if 1-2 are below it, RED if all {HRV_RECENT_DAYS}. "
            f"Sleep: {AVG_DAYS}-day average, PASS from {SLEEP_PASS_FROM:g} h, RED below {SLEEP_AMBER_FROM:g} h. "
            f"Weight shows with {WEIGHT_MIN_VALUES}+ readings in {WEIGHT_WINDOW_DAYS} days. "
            f"Action: 1 RED = fix that one thing, 2+ = recovery volume; AMBER and missing data never change it. "
            f"Source: intervals.icu wellness."
        ),
    }


def recovery_trend(db: Session, days: int = TREND_DAYS, today: date | None = None) -> dict:
    """HRV and resting HR over `days` for the Recovery trends card. The status,
    value, band and thresholds are the ones readiness() reports - the card is a
    longer view of the same judgement, never a second opinion."""
    today = today or date.today()
    ready = readiness(db, today)
    current = {m["key"]: m for m in ready["metrics"]}
    rows = {
        w.date: w
        for w in db.query(IntervalsWellness).filter(IntervalsWellness.date > today - timedelta(days=days + AVG_DAYS))
    }

    def rhr_average(day: date) -> float | None:
        avg = average([getattr(rows.get(day - timedelta(days=i)), "resting_hr", None) for i in range(AVG_DAYS)])
        return round(avg, 1) if avg is not None else None

    def pick(key: str) -> dict:
        return {f: current[key][f] for f in ("status", "value", "unit", "basis", "band")}

    return {
        "series": [
            {
                "date": day,
                "hrv": getattr(rows.get(day), "hrv", None),
                "rhr": getattr(rows.get(day), "resting_hr", None),
                "rhr_7d": rhr_average(day),
            }
            for day in (today - timedelta(days=i) for i in range(days - 1, -1, -1))
        ],
        "hrv": pick("hrv"),
        "rhr": pick("rhr"),
        "rhr_amber_from": RHR_AMBER_FROM,
        "rhr_red_from": RHR_RED_FROM,
        "note": ready["note"],
    }
