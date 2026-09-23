"""Pulls recent activities from the real Strava API v3 (not the MCP connector,
which is only reachable from inside a Claude session) and upserts them into the
activities table. Requires STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN in the
environment - see backend/.env.example for where to get these.

Existing rows are refreshed on every sync (not just inserted once), so edits
made on Strava - a renamed activity, a corrected sport type - and fields added
later (Relative Effort, power) flow through without a manual backfill.
"""

from datetime import datetime

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models.activity import Activity, normalize_sport

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def _get_access_token() -> str:
    resp = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": settings.strava_client_id,
            "client_secret": settings.strava_client_secret,
            "refresh_token": settings.strava_refresh_token,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _fields(raw: dict) -> dict:
    sport_type = raw.get("sport_type") or raw.get("type", "Workout")
    return dict(
        name=raw.get("name", ""),
        date=datetime.fromisoformat(raw["start_date_local"].replace("Z", "+00:00")).replace(
            tzinfo=None
        ),
        sport_type=sport_type,
        sport=normalize_sport(sport_type),
        is_indoor=bool(raw.get("trainer", False)),
        duration_min=raw.get("moving_time", 0) / 60,
        distance_km=(raw.get("distance") or 0) / 1000,
        avg_hr=raw.get("average_heartrate"),
        max_hr=raw.get("max_heartrate"),
        calories=raw.get("calories"),
        source="strava",
        # Strava's API names Relative Effort `suffer_score` (verified against
        # the live account 2026-09-23: present on all 100 recent activities,
        # every sport type).
        relative_effort=raw.get("suffer_score"),
        average_watts=raw.get("average_watts"),
        weighted_average_watts=raw.get("weighted_average_watts"),
        device_watts=raw.get("device_watts"),
    )


def _upsert_activity(db: Session, raw: dict, seen_ids: set[str]) -> bool:
    """Returns True if a new row was inserted."""
    external_id = str(raw["id"])
    if external_id in seen_ids:
        return False
    seen_ids.add(external_id)

    fields = _fields(raw)
    existing = db.query(Activity).filter(Activity.external_id == external_id).first()
    if existing:
        for key, value in fields.items():
            # Never overwrite a value we already have with a missing one
            # (e.g. a summary payload that omits calories).
            if value is not None:
                setattr(existing, key, value)
        return False

    db.add(Activity(external_id=external_id, **fields))
    return True


def sync_activities(db: Session, per_page: int = 50, pages: int = 2) -> int:
    if not settings.strava_refresh_token:
        raise RuntimeError(
            "STRAVA_REFRESH_TOKEN is not set - see backend/.env.example for setup."
        )

    token = _get_access_token()
    raw_batch: list[dict] = []

    with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
        for page in range(1, pages + 1):
            resp = client.get(
                STRAVA_ACTIVITIES_URL, params={"per_page": per_page, "page": page}
            )
            if resp.status_code == 401:
                raise RuntimeError(
                    "Strava returned 401 Unauthorized - the refresh token's scope "
                    "doesn't include activity:read_all. Re-run the OAuth authorize "
                    "flow with scope=activity:read_all and update .env with the "
                    "new refresh token."
                )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            raw_batch.extend(batch)

    def _apply() -> int:
        seen_ids: set[str] = set()
        return sum(1 for raw in raw_batch if _upsert_activity(db, raw, seen_ids))

    inserted = _apply()
    try:
        db.commit()
    except IntegrityError:
        # Scheduled sync and a manual /sync raced and both inserted the same
        # new activity - roll back and re-apply as updates.
        db.rollback()
        inserted = _apply()
        db.commit()

    # Keep the per-day load table in step with the activities it's derived from.
    from .training_load import rebuild_daily_loads

    rebuild_daily_loads(db)
    return inserted
