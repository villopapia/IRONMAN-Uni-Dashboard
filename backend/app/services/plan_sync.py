"""Syncs the *plan* out of Google Calendar into `planned_sessions`, so
compliance (planned vs. completed) can be computed without calling Google on
every page load.

Recurring events: Google expands RRULEs server-side when asked for
`singleEvents=true` - every instance comes back as its own event with a
stable per-instance id (`<baseId>_<YYYYMMDDTHHMMSSZ>`), with EXDATEs and
edited instances already applied. That's more reliable than re-implementing
RRULE/EXDATE/override handling here, so this module never parses RRULEs
itself.

Classification is by the title's leading emoji / bracket tag only - the same
tags confirmed in the live calendar (2026-09-23). Event *descriptions* are
never parsed (their free text embeds several weeks' numbers and shifts on
every edit - see calendar_schedule.py):

  🏊 / 🌊 swim   🚴 bike   🏃 run   💪 gym (strength)
  🔗 brick (one bike row + one run row, both is_brick)
  🏁 "PHASE N: NAME — Start"   phase marker (📍 duplicates are ignored)
  ⚠️ "TAPER ..."               treated as Phase 5 (Taper) - the plan has no
                               explicit PHASE 5 marker
  🏁 non-phase with Bike + Run  brick (e.g. the 90k + 21k dress rehearsal)
  🏆 / 🏅                       race day / gate race
  🎯 🔺 ✈️ 🔁 📍 other ⚠️        plan markers (stored, not counted as sessions)
  [LEC] [DEEP] [ASSIGN] [RECALL] [CONSOL] [REVIEW] [EXAM] [PP]   study block
  [APP] [OUT], untagged events (e.g. plain "Gym", "htz")         ignored

Untagged events are ignored on purpose: the summer's plain "Gym"/"htz"
recurring blocks aren't part of the tagged training plan, and guessing at
them would inflate or deflate compliance.
"""

import logging
import re
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models.performance import PlannedSession
from .calendar_schedule import GOOGLE_EVENTS_URL, _get_access_token

logger = logging.getLogger(__name__)

WINDOW_BACK_DAYS = 120
WINDOW_AHEAD_DAYS = 300

STUDY_TAGS = {"LEC", "DEEP", "ASSIGN", "RECALL", "CONSOL", "REVIEW", "EXAM", "PP"}
EMOJI_DISCIPLINE = {"🏊": "swim", "🌊": "swim", "🚴": "bike", "🏃": "run", "💪": "gym"}
MARKER_EMOJI = ("🎯", "🔺", "✈", "🔁", "📍", "⚠")
# Stops at an em dash or a spaced hyphen, not the hyphen inside "HALF-MAR".
PHASE_RE = re.compile(r"PHASE\s+(\d+)\s*:?\s*(.+?)\s*(?:—|\s-\s|$)", re.IGNORECASE)


def _prefix(summary: str) -> str:
    """The leading run of non-alphanumeric characters (the emoji tag)."""
    for i, ch in enumerate(summary):
        if ch.isalnum() or ch == "[":
            return summary[:i]
    return summary


def _strength_type(title: str) -> str:
    upper = title.upper()
    if "UPPER A" in upper:
        return "upper_a"
    if "UPPER B" in upper:
        return "upper_b"
    if "MOBILITY" in upper:
        return "mobility"
    return "other"


def classify(summary: str) -> list[dict]:
    """Title -> zero or more planned-row dicts (kind, discipline, ...)."""
    s = summary.strip()
    upper = s.upper()

    if s.startswith("["):
        tag = s[1 : s.find("]")] if "]" in s else ""
        return [{"kind": "study", "study_tag": tag}] if tag in STUDY_TAGS else []

    prefix = _prefix(s)
    if not prefix.strip():
        return []

    if "🏁" in prefix and "PHASE" in upper:
        m = PHASE_RE.search(s)
        if m:
            return [{"kind": "phase", "phase_number": int(m.group(1)), "phase_name": m.group(2)}]
    if "⚠" in prefix and "TAPER" in upper:
        return [{"kind": "phase", "phase_number": 5, "phase_name": "TAPER"}]
    if "🏆" in prefix or "🏅" in prefix:
        return [{"kind": "race"}]
    both_legs = "BIKE" in upper and "RUN" in upper and "+" in s
    if "🔗" in prefix or ("🏁" in prefix and both_legs):
        # "🔗 Brick: Bike 3h + Run 30'" carries both legs in one event, but
        # Phase 2's "🔗 Brick Run (off Sat bike)" is only the run leg - its
        # bike is a separate "🚴 Long Bike Z2 (Sat, brick)" event, so emitting
        # a bike row here too would double-count that Saturday's bike.
        legs = ["bike", "run"] if both_legs else (["run"] if "RUN" in upper else ["bike"])
        return [{"kind": "session", "discipline": d, "is_brick": True} for d in legs]

    disciplines: list[str] = []
    for ch in prefix:
        d = EMOJI_DISCIPLINE.get(ch)
        if d and d not in disciplines:
            disciplines.append(d)
    if disciplines:
        is_brick = "BRICK" in upper
        return [
            {
                "kind": "session",
                "discipline": d,
                "is_brick": is_brick,
                "strength_type": _strength_type(s) if d == "gym" else None,
            }
            for d in disciplines
        ]

    if any(e in prefix for e in MARKER_EMOJI) or "🏁" in prefix:
        return [{"kind": "marker"}]
    return []


def _parse_when(raw: dict) -> tuple[date, datetime | None]:
    if raw.get("dateTime"):
        # Google returns wall-clock time in the calendar's zone with its
        # offset; keep the wall-clock (naive) so it lines up with Strava's
        # start_date_local on the Activity side.
        dt = datetime.fromisoformat(raw["dateTime"].replace("Z", "+00:00")).replace(tzinfo=None)
        return dt.date(), dt
    return date.fromisoformat(raw["date"]), None


def _fetch_events(time_min: date, time_max: date) -> list[dict]:
    token = _get_access_token()
    items: list[dict] = []
    page_token = None
    with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
        while True:
            params = {
                "timeMin": datetime.combine(time_min, datetime.min.time()).isoformat() + "Z",
                "timeMax": datetime.combine(time_max, datetime.min.time()).isoformat() + "Z",
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 2500,
            }
            if page_token:
                params["pageToken"] = page_token
            resp = client.get(GOOGLE_EVENTS_URL, params=params)
            resp.raise_for_status()
            body = resp.json()
            items.extend(body.get("items", []))
            page_token = body.get("nextPageToken")
            if not page_token:
                return items


def _rows_from_events(events: list[dict]) -> list[dict]:
    rows = []
    for event in events:
        if event.get("status") == "cancelled":
            continue
        summary = event.get("summary") or ""
        classified = classify(summary)
        if not classified:
            continue
        day, start_at = _parse_when(event.get("start", {}))
        _, end_at = _parse_when(event.get("end", {})) if event.get("end") else (None, None)
        for c in classified:
            suffix = c.get("discipline") or c["kind"]
            title = summary
            if c["kind"] == "phase":
                title = f"Phase {c['phase_number']}: {c['phase_name'].title()}"
            rows.append(
                {
                    "external_id": f"{event['id']}:{suffix}",
                    "event_id": event["id"],
                    "date": day,
                    "start_at": start_at,
                    "end_at": end_at,
                    "kind": c["kind"],
                    "discipline": c.get("discipline"),
                    "title": title,
                    "is_brick": bool(c.get("is_brick")),
                    "strength_type": c.get("strength_type"),
                    "study_tag": c.get("study_tag"),
                }
            )
    return rows


def _apply(db: Session, rows: list[dict], window_start: date, window_end: date) -> dict:
    existing = {p.external_id: p for p in db.query(PlannedSession).all()}
    seen: set[str] = set()
    inserted = updated = 0
    now = datetime.utcnow()
    for row in rows:
        ext = row["external_id"]
        if ext in seen:  # in-batch duplicate (autoflush=False won't catch it)
            continue
        seen.add(ext)
        current = existing.get(ext)
        if current is None:
            db.add(PlannedSession(synced_at=now, **row))
            inserted += 1
        else:
            for k, v in row.items():
                setattr(current, k, v)
            current.synced_at = now
            updated += 1

    # Events deleted / re-titled out of the plan inside the synced window.
    removed = 0
    for ext, p in existing.items():
        if ext not in seen and window_start <= p.date < window_end:
            db.delete(p)
            removed += 1
    db.commit()
    return {"inserted": inserted, "updated": updated, "removed": removed}


def sync_plan(db: Session, today: date | None = None) -> dict:
    if not settings.google_refresh_token:
        raise RuntimeError("GOOGLE_REFRESH_TOKEN is not set - see backend/.env.example for setup.")
    today = today or date.today()
    window_start = today - timedelta(days=WINDOW_BACK_DAYS)
    window_end = today + timedelta(days=WINDOW_AHEAD_DAYS)
    rows = _rows_from_events(_fetch_events(window_start, window_end))
    try:
        return _apply(db, rows, window_start, window_end)
    except IntegrityError:
        # A concurrent sync (scheduler vs. manual /sync) inserted the same
        # instances first - roll back and re-run as an update pass.
        db.rollback()
        return _apply(db, rows, window_start, window_end)


# --- Read helpers ------------------------------------------------------------


def get_race_date(db: Session) -> date | None:
    races = (
        db.query(PlannedSession)
        .filter(PlannedSession.kind == "race")
        .order_by(PlannedSession.date.desc())
        .all()
    )
    for r in races:
        if "IRONMAN" in r.title.upper():
            return r.date
    return None


def get_phases(db: Session) -> list[dict]:
    markers = (
        db.query(PlannedSession)
        .filter(PlannedSession.kind == "phase")
        .order_by(PlannedSession.date)
        .all()
    )
    by_number: dict[int, dict] = {}
    for m in markers:
        match = re.match(r"Phase (\d+): (.+)", m.title)
        if not match:
            continue
        n = int(match.group(1))
        if n not in by_number:
            by_number[n] = {"number": n, "name": match.group(2), "start_date": m.date}
    phases = sorted(by_number.values(), key=lambda p: p["start_date"])
    race = get_race_date(db)
    for i, p in enumerate(phases):
        nxt = phases[i + 1]["start_date"] if i + 1 < len(phases) else None
        p["end_date"] = (nxt - timedelta(days=1)) if nxt else race
    return phases
