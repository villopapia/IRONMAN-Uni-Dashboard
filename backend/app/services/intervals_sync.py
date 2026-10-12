"""intervals.icu as a second data source: activities (icu_training_load) and
daily wellness (their CTL/ATL, HRV, sleep...), cached in SQLite. Requires
INTERVALS_API_KEY / INTERVALS_ATHLETE_ID - see backend/.env.example.

    python -m app.services.intervals_sync probe    # live field-name check
    python -m app.services.intervals_sync sync     # backfill / refresh the cache
    python -m app.services.intervals_sync resync   # re-pull everything from BACKFILL_FROM
    python -m app.services.intervals_sync compare  # 14 days: Strava RE vs icu load, their PMC vs ours

Field names verified against the live account 2026-10-11 (all activities
source GARMIN_CONNECT, so none are the data-less stubs intervals.icu returns
for Strava-sourced activities).
"""

import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models.activity import Activity, normalize_sport
from ..models.intervals import IntervalsActivity, IntervalsWellness
from .training_load import compute_pmc

BASE_URL = "https://intervals.icu/api/v1"
BACKFILL_FROM = date(2026, 4, 1)
REFRESH_DAYS = 14
WANTED = {
    "activities": ["type", "start_date_local", "moving_time", "icu_training_load", "race", "icu_hr_zone_times", "distance"],
    "wellness": ["id", "ctl", "atl", "rampRate", "restingHR", "hrv", "sleepSecs", "weight"],
}


def _get(path: str, oldest: date) -> list[dict]:
    if not (settings.intervals_api_key and settings.intervals_athlete_id):
        raise RuntimeError("INTERVALS_API_KEY / INTERVALS_ATHLETE_ID not set - see backend/.env.example.")
    resp = httpx.get(
        f"{BASE_URL}/athlete/{settings.intervals_athlete_id}/{path}",
        params={"oldest": oldest.isoformat(), "newest": date.today().isoformat()},
        auth=("API_KEY", settings.intervals_api_key),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def probe() -> None:
    for path, wanted in WANTED.items():
        rows = _get(path, date.today() - timedelta(days=REFRESH_DAYS))
        names = sorted({k for r in rows for k in r})
        print(f"{path}: {len(rows)} rows\n  fields: {names}")
        print(f"  missing: {[w for w in wanted if w not in names] or 'none'}")
        if path == "activities":
            print(f"  source: {dict(Counter(r.get('source') for r in rows))}")


def sync_intervals(db: Session, full: bool = False) -> dict[str, int]:
    """First run (or full=True) backfills from BACKFILL_FROM; otherwise the last
    REFRESH_DAYS. A new column, or thresholds changed on intervals.icu, need full."""
    backfilled = db.query(IntervalsWellness).first() is not None
    oldest = date.today() - timedelta(days=REFRESH_DAYS) if backfilled and not full else BACKFILL_FROM

    # Strava-sourced activities come back as stubs with no type/load - skip them.
    # ponytail: activities deleted on intervals.icu stay cached; prune if that ever matters
    activities = [a for a in _get("activities", oldest) if a.get("type")]
    for a in activities:
        db.merge(
            IntervalsActivity(
                id=str(a["id"]),
                name=a.get("name") or "",
                date=datetime.fromisoformat(a["start_date_local"]),
                type=a["type"],
                sport=normalize_sport(a["type"]),
                duration_min=(a.get("moving_time") or 0) / 60,
                icu_training_load=a.get("icu_training_load"),
                race=bool(a.get("race")),
                hr_zone_secs=a.get("icu_hr_zone_times"),
                distance_m=a.get("distance"),
            )
        )
    wellness = _get("wellness", oldest)
    for w in wellness:
        db.merge(
            IntervalsWellness(
                date=date.fromisoformat(w["id"]),
                ctl=w.get("ctl"),
                atl=w.get("atl"),
                ramp_rate=w.get("rampRate"),
                resting_hr=w.get("restingHR"),
                hrv=w.get("hrv"),
                sleep_secs=w.get("sleepSecs"),
                weight=w.get("weight"),
            )
        )
    db.commit()
    return {"activities": len(activities), "wellness": len(wellness)}


def compare(db: Session, days: int = 14) -> None:
    start = date.today() - timedelta(days=days - 1)
    since = datetime.combine(start, time.min)
    strava: dict[date, float] = defaultdict(float)
    icu: dict[date, float] = defaultdict(float)
    for a in db.query(Activity).filter(Activity.date >= since):
        strava[a.date.date()] += a.relative_effort or 0
    for a in db.query(IntervalsActivity).filter(IntervalsActivity.date >= since):
        icu[a.date.date()] += a.icu_training_load or 0
    wellness = {w.date: w for w in db.query(IntervalsWellness).filter(IntervalsWellness.date >= start)}

    def num(v: float | None) -> str:
        return f"{v:8.1f}" if v is not None else "       -"

    print("date        RE sum  icu load  icu ctl  icu atl  our ctl  our atl")
    for p in compute_pmc(db, start=start)["series"]:
        d, w = p["date"], wellness.get(p["date"])
        print(d, num(strava[d]), num(icu[d]), num(w and w.ctl), num(w and w.atl), num(p["ctl"]), num(p["atl"]))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "probe":
        probe()
    elif command in ("sync", "resync", "compare"):
        db = SessionLocal()
        try:
            compare(db) if command == "compare" else print(sync_intervals(db, full=command == "resync"))
        finally:
            db.close()
    else:
        sys.exit(__doc__)
