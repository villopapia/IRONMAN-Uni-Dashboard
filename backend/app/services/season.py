"""Race countdown, current phase and next gate, from the season plan in config.

Days to race = race date - today, with today taken in Europe/London. Weeks =
whole weeks in that. A phase's weeks are Mon-Sun weeks counted from the Monday
of the week the phase starts in, so a phase starting on a Wednesday is in its
week 1 until that Sunday. The next gate is the earliest one not yet past; a
gate dated today is "in 0 days".
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..config import GATES, PHASES, RACE, SEASON_START

LONDON = ZoneInfo("Europe/London")


def london_today() -> date:
    return datetime.now(LONDON).date()


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def season_status(today: date) -> dict:
    days = (RACE["date"] - today).days
    phase = next((p for p in PHASES if p["start"] <= today <= p["end"]), None)
    gate = next((g for g in sorted(GATES, key=lambda g: g["date"]) if g["date"] >= today), None)
    return {
        "today": today,
        "race": RACE,
        "days_to_race": days,
        "weeks_to_race": max(days, 0) // 7,
        "phase": phase
        and {
            "name": phase["name"],
            "week": (_monday(today) - _monday(phase["start"])).days // 7 + 1,
            "weeks": (_monday(phase["end"]) - _monday(phase["start"])).days // 7 + 1,
        },
        "next_gate": gate and {**gate, "days": (gate["date"] - today).days},
        "gates": GATES,
        "phases": PHASES,
        "season_start": SEASON_START,
    }
