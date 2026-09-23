"""Display-only read of this week's Google Calendar events - what's planned per
day, and rest-day cross-check. Does NOT try to parse numeric training targets
out of event text (the plan's session descriptions embed multiple weeks'
numbers as free text that shifts on every edit - too fragile to parse
reliably; WeeklyTrainingTarget stays manually seeded for that).
"""

from datetime import date, datetime, timedelta

import httpx

from ..config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def _get_access_token() -> str:
    resp = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": settings.google_refresh_token,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_week_events(week_start_date: date) -> dict[str, list[dict]]:
    """Returns {iso_date: [{"summary": ..., "start": ...}, ...]} for the 7 days
    starting week_start_date.
    """
    if not settings.google_refresh_token:
        raise RuntimeError(
            "GOOGLE_REFRESH_TOKEN is not set - see backend/.env.example for setup."
        )

    token = _get_access_token()
    time_min = datetime.combine(week_start_date, datetime.min.time()).isoformat() + "Z"
    time_max = (
        datetime.combine(week_start_date + timedelta(days=7), datetime.min.time()).isoformat()
        + "Z"
    )

    resp = httpx.get(
        GOOGLE_EVENTS_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
        },
    )
    resp.raise_for_status()

    by_day: dict[str, list[dict]] = {
        (week_start_date + timedelta(days=i)).isoformat(): [] for i in range(7)
    }
    for event in resp.json().get("items", []):
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
        if not start:
            continue
        day_key = start[:10]
        if day_key in by_day:
            by_day[day_key].append(
                {"summary": event.get("summary", "(no title)"), "start": start}
            )

    return by_day
