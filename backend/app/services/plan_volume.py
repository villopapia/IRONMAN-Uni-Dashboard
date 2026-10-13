"""Prescribed swim / bike / run volume per calendar session, read from each
event's description - never from the calendar block length, which is sized
for the longest week of a phase.

    python -m app.services.plan_volume build    # rewrites plan/prescribed_sessions.json, keeping hand-made changes
    python -m app.services.plan_volume status   # this week: done vs due per sport (optionally for a given time)

Units: swim = metres, bike and run = minutes.

What counts as a session: events whose title tag is a sport emoji (swim, bike,
run, brick), plus test / dress-rehearsal events that name a sport. Meals,
reminders, checkpoints, study blocks, strength and mobility are not sessions.
A brick or combined event yields one entry per sport it contains.

Where a value comes from, in order:
  1. A line of the description that names this date, e.g.
       "Oct 10 / Oct 17: 120'"
       "Wk1-3 (Oct 26 / Nov 2 / Nov 9): 70' -> 75' -> 80'"   (one value per date)
       "Wk4 recovery (Nov 16): 60'"
       "Oct 13: 5x200 -> 1,700m total"                        (the total after the arrow)
       "SESSION - Oct 7 / 14 (1,800m, 50'):"
     "as above" points at the "SESSION (70'):" header. Interval sets under a
     "Main set" bullet are summed: warm-up + reps + recoveries + cool-down.
  2. With no line for this date and no per-date table at all: a
     "SESSION (45')" / "PROTOCOL (1,700m)" header, a "Bike 2.5h" / "Run 30'"
     leg line, or the sum of a fully specified "10' WU; 35' Z2; 5' CD" list.

Anything else is left null with needs_review: distances in a run or ride,
reps with unstated recoveries, ranges, "about" totals that the parts don't add
up to, and descriptions that vary by week number without naming dates. Nothing
is guessed. Values filled in by hand in the JSON survive a rebuild.
"""

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PLAN_FILE = Path(__file__).resolve().parents[3] / "plan" / "prescribed_sessions.json"
PLAN_UNTIL = date(2027, 7, 11)
UNITS = {"swim": "m", "bike": "min", "run": "min"}

_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
# "Oct 26 / Nov 2 / Nov 9", "Oct 7 / 14", "Oct 27, Nov 3, Nov 10"
_DATE_GROUP = re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?!\d)((?:\s*[/,&]\s*(?:{_MON}\.?\s+)?\d{{1,2}}(?!\d))*)", re.I)
_MIN = r"(\d+)'(?!')"  # 70' but not 20" (written as two quotes in some sources)
# A description that changes by week number ("Wk 1,4,7: ...") without naming dates.
_VARIES = re.compile(r"^\W*Wks?\s*\d|\bAlt\b|Alternative|[Pp]rogression|rotation", re.M)
_TITLE_RANGE = re.compile(r"\d(?:\.\d)?\s*-\s*\d+(?:\.\d)?\s*(?:k\b|km|h\b|'|m\b)")
_SENTENCE = re.compile(r"(?<=[a-z\)'])\.\s+(?=[A-Z])")


def _norm(text: str) -> str:
    return (text or "").replace("→", "->").replace("×", "x").replace("’", "'").replace("′", "'")


# --- which events are sessions -------------------------------------------------


def session_sports(title: str) -> list[str]:
    """Sports an event prescribes, [] when it is not a swim / bike / run session."""
    from .plan_sync import _prefix, classify  # emoji tags: the calendar's own convention

    sports = [c["discipline"] for c in classify(title) if c["kind"] == "session" and c.get("discipline") in UNITS]
    upper = title.upper()
    tag = _prefix(title.strip())
    if not sports and ("\U0001f3af" in tag or "\U0001f3c1" in tag) and "TEST" in upper:  # test events name their sport
        sports = [s for s in UNITS if re.search(rf"\b{s}\b", title, re.I)]
    # "Long Run + Recovery Swim": a second sport named after a plus sign
    if sports and "+" in title:
        for s in UNITS:
            if s not in sports and re.search(rf"\+[^+]*\b{s}\b", title, re.I):
                sports.append(s)
    return sports


# --- reading a value out of a description ---------------------------------------


def _dates_in(match: re.Match, near: date) -> list[date]:
    month = _MONTHS.index(match.group(1)[:3].lower()) + 1
    out = []
    for token in [match.group(2)] + re.findall(rf"(?:({_MON})\.?\s+)?(\d{{1,2}})(?!\d)", match.group(3), re.I):
        if isinstance(token, tuple):
            if token[0]:
                month = _MONTHS.index(token[0][:3].lower()) + 1
            day = int(token[1])
        else:
            day = int(token)
        best = None
        for year in (near.year - 1, near.year, near.year + 1):
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            if best is None or abs((d - near).days) < abs((best - near).days):
                best = d
        if best is None:
            return []  # "Half-Mar 90": not a date
        out.append(best)
    return out


def _segments(description: str) -> list[tuple[int, str]]:
    """(line index, sentence) for every sentence of every line."""
    out = []
    for i, line in enumerate(description.splitlines()):
        out.extend((i, s) for s in _SENTENCE.split(line))
    return out


def _header_value(description: str, unit: str) -> float | None:
    """The total in a "SESSION (70'):" / "PROTOCOL (1,700m):" header."""
    m = re.search(r"^\s*(?:SESSION|PROTOCOL)\s*\(([^)]*)\)", description, re.M)
    if not m:
        return None
    return _unit_value(m.group(1), unit)


def _unit_value(text: str, unit: str) -> float | None:
    if unit == "m":
        m = re.search(r"([\d,]{3,})\s*m\b", text)
        return float(m.group(1).replace(",", "")) if m else None
    m = re.search(_MIN, text)
    return float(m.group(1)) if m else None


def _under_main_set(lines: list[str], index: int) -> bool:
    if not lines[index].lstrip().startswith(("·", "*", "•")) or not lines[index][:1].isspace():
        return False
    for line in reversed(lines[:index]):
        if line.startswith("- "):
            return bool(re.match(r"- Main\b", line))
    return False


def _interval_total(lines: list[str], index: int, reps_text: str) -> float | None:
    """Warm-up + reps + recoveries + cool-down for an interval set listed under
    a "Main set" bullet. None if any part is not a plain duration."""
    reps = re.match(rf"\s*(\d+)\s*x\s*{_MIN}", reps_text)
    if not reps:
        return None
    start = index
    while start > 0 and lines[start - 1].strip():
        start -= 1
    end = index
    while end < len(lines) and lines[end].strip():
        end += 1
    block = lines[start:end]
    main = next((line for line in block if re.match(r"- Main\b", line)), "")
    recovery = re.search(rf"[(,]\s*{_MIN}\s+\w+\s+between", reps_text) or re.search(rf"\(\s*{_MIN}\s+\w+\s+between", main)
    if not recovery:
        return None
    total = 0.0
    for line in block:
        if not line.startswith("- ") or line is main:
            continue
        part = re.match(rf"- {_MIN}", line)
        if not part or " + " in line:  # e.g. "+ 4x20\" strides (full recovery between)": length unknown
            return None
        total += float(part.group(1))
    n, each = int(reps.group(1)), float(reps.group(2))
    return total + n * each + (n - 1) * float(recovery.group(1))


def _from_date_line(description: str, lines: list[str], line_index: int, tail: str, position: int, count: int, unit: str):
    """(value, reason) from the text that follows this date in its line."""
    if unit == "m":
        arrows = re.findall(r"->\s*([\d,]+)\s*m\b", tail)
        if arrows:
            return float(arrows[-1].replace(",", "")), "total on the line for this date"
        m = re.match(r"\s*\)?\s*\(([^)]*)\)", tail)
        if m and _unit_value(m.group(1), "m") is not None:
            return _unit_value(m.group(1), "m"), "total on the line for this date"
        pointer = re.search(r"([A-Z][A-Z ]{3,}?)\s*↓", tail)
        if pointer:
            target = re.search(rf"^{re.escape(pointer.group(1).strip())}\s*\(([^)]*)\)", description, re.M)
            if target and _unit_value(target.group(1), "m") is not None:
                return _unit_value(target.group(1), "m"), f"total of the {pointer.group(1).strip().title()} block"
        if re.search(r"\bas above\b", tail):
            return _header_value(description, "m"), "session header total"
        return None, "the line for this date gives no total distance"

    text = re.sub(r"^\s*\)", "", tail)
    m = re.match(r"\s*\(([^)]*)\)", text)
    if m:
        if re.search(_MIN, m.group(1)) and not re.search(r"\d\s*x\s*\d", m.group(1)):
            return _unit_value(m.group(1), "min"), "duration on the line for this date"
        text = text[m.end() :]
    text = re.sub(r"^[\s:=—-]+", "", text)
    under_main = _under_main_set(lines, line_index)
    if re.match(r"\d+\s*x\s*\d", text):
        if re.search(r"\d\s*(?:km|m)\b", re.match(r"[^,(]*", text).group(0)):
            return None, "reps are a distance, not a time"
        total = _interval_total(lines, line_index, text) if under_main else None
        return total, "warm-up + reps + recoveries + cool-down" if total is not None else "interval set with a part of unknown length"
    if under_main:
        # A recovery or test week replacing the intervals ("no intervals - 30' easy Z2",
        # "30' easy Z2 + 4 strides"): Chris's rule is the stated minutes only, no warm-up
        # or cool-down added, plus 2 minutes when strides are listed.
        easy = re.match(rf"(?:no intervals\W+)?{_MIN}\s+easy\b", text)
        if easy:
            return float(easy.group(1)) + (2 if "strides" in text else 0), "stated minutes for an easy week (plus 2 for strides)"
        return None, "the main-set line for this date is not a plain duration or interval set"
    m = re.match(rf"(?:full\s+)?{_MIN}((?:\s*->\s*\d+'(?!'))*)", text)
    if m:
        values = [float(m.group(1))] + [float(v) for v in re.findall(_MIN, m.group(2))]
        if len(values) == 1:
            return values[0], "duration on the line for this date"
        if len(values) == count:
            return values[position], "duration on the line for this date"
        return None, f"{len(values)} durations listed for {count} dates"
    if re.search(r"\bas above\b", text):
        return _header_value(description, "min"), "session header total"
    return None, "the line for this date gives no duration"


def _sum_minutes(text: str) -> float | None:
    """"10' WU; 35' Z2 (HR 136-156); 5' CD" -> 50. None unless every part is a duration."""
    parts = [p for p in text.split(";") if p.strip()]
    if len(parts) < 2:
        return None
    total = 0.0
    for part in parts:
        part = re.split(r"(?<=[A-Za-z)])\.\s", part.strip())[0]  # drop trailing sentences after the last part
        m = re.match(rf"(?:(\d+)\s*x\s*)?{_MIN}", part)
        if not m or '"' in part or " + " in part:
            return None
        n = int(m.group(1) or 1)
        total += n * float(m.group(2))
        if n > 1:
            rec = re.search(rf"w/\s*{_MIN}", part)
            if not rec:
                return None
            total += (n - 1) * float(rec.group(1))
    return total


def _sum_metres(text: str, separators: str = ";") -> float | None:
    """"300 WU; 1x 1000m @ race pace; 4x50 sprint; 200 CD" -> 1700."""
    total, found = 0.0, 0
    for part in re.split(f"[{separators}]", text):
        for piece in part.split(" + "):
            piece = piece.strip()
            if not piece:
                continue
            m = re.match(r"(?:(\d+)\s*x\s*)?([\d,]+)\s*m?\b(?!')", piece)
            if not m:
                return None
            total += int(m.group(1) or 1) * float(m.group(2).replace(",", ""))
            found += 1
    return total if found >= 2 else None


def _without_date_line(description: str, title: str, sport: str, multi_sport: bool):
    unit = UNITS[sport]
    if _VARIES.search(description):
        return None, "varies by week number or rotation, with no dates"
    if _TITLE_RANGE.search(title):
        return None, "the title gives a range, not one value"
    header = _header_value(description, unit)
    if header is not None:
        return header, "session header total"
    body = [line for line in description.splitlines() if line.strip()]
    # The parts list: the "Structure:" line when there is one, else the first line.
    first = next((line for line in body if re.match(r"\W*Structure\b", line)), body[0] if body else "")
    if multi_sport or re.search(rf"^\W*{sport}\s+\d", description, re.I | re.M):
        leg = re.search(rf"^\W*{sport}\s+(\d+(?:\.\d+)?)\s*(h\b|')(.*)$", description, re.I | re.M)
        if leg and unit == "min":
            return float(leg.group(1)) * (60 if leg.group(2).lower() == "h" else 1), f"the {sport} leg line"
        if leg and unit == "m":
            inner = re.search(r"\(([^)]*)\)", leg.group(3))
            metres = _sum_metres(inner.group(1), ",") if inner else None
            return metres, "sum of the listed swim parts" if metres is not None else "swim leg given in minutes, not metres"
        return None, f"no {sport} leg line"
    if unit == "min":
        structure = re.sub(r"^\W*(?:Structure:?\W*)?", "", first.replace("*", ""))
        total = _sum_minutes(structure)
        stated = re.search(rf"{_MIN}\)", title)
        if total is not None:
            if stated and float(stated.group(1)) != total:
                return None, f"parts add up to {total:g}' but the title says {stated.group(1)}'"
            return total, "sum of the listed parts"
        if stated and re.search(rf"\b{stated.group(1)}'(?!')", re.split(r"\.\s", first)[0]):
            return float(stated.group(1)), "duration in the title and first line"
        return None, "no total duration, and the parts cannot all be added up"
    stated = re.search(r"Total:?\W*(~)?\s*([\d,]+)\s*m\b", description.replace("*", ""))
    total = _sum_metres(re.split(r"\bTotal\b", first.replace("*", ""))[0].rstrip(". "))
    if stated:
        value = float(stated.group(2).replace(",", ""))
        if total == value or (total is None and not stated.group(1)):
            return value, "stated total"
        if total is not None:
            return None, f"parts add up to {total:,.0f} m but the stated total is {value:,.0f} m"
        return None, "only an approximate total is given"
    return None, "no total distance"


def prescribed_value(description: str, title: str, day: date, sport: str, multi_sport: bool = False) -> tuple[float | None, str]:
    """(value in the sport's unit or None, how it was found / why it was not)."""
    description = _norm(description)
    unit = UNITS[sport]
    lines = description.splitlines()
    results, has_table = [], False
    for line_index, segment in _segments(description):
        groups = list(_DATE_GROUP.finditer(segment))
        for g, match in enumerate(groups):
            dates = _dates_in(match, day)
            end = groups[g + 1].start() if g + 1 < len(groups) else len(segment)
            tail = segment[match.end() : end]
            if dates and re.match(r"\s*(?:\([^)]*\))?\s*\)?\s*(?:\([^)]*\))?\s*:", tail):
                has_table = True
            if day in dates:
                results.append(_from_date_line(description, lines, line_index, tail, dates.index(day), len(dates), unit))
    values = {v for v, _ in results if v is not None}
    if len(values) == 1:
        return next((v, why) for v, why in results if v is not None)
    if len(values) > 1:
        return None, "conflicting values for this date: " + " / ".join(f"{v:g}" for v in sorted(values))
    if results:
        return None, results[0][1]
    if has_table:
        return None, "this date is not in the description's list of dates"
    return _without_date_line(description, _norm(title), sport, multi_sport)


# --- the plan file ---------------------------------------------------------------


def build_entries(events: list[dict], since: date, until: date = PLAN_UNTIL) -> list[dict]:
    from .plan_sync import _parse_when

    entries = []
    for event in events:
        if event.get("status") == "cancelled" or not event.get("start", {}).get("dateTime"):
            continue
        title = event.get("summary") or ""
        sports = session_sports(title)
        day, start = _parse_when(event["start"])
        _, end = _parse_when(event["end"])
        if not sports or not since <= day <= until:
            continue
        for sport in sports:
            value, note = prescribed_value(event.get("description") or "", title, day, sport, multi_sport=len(sports) > 1)
            entries.append(
                {
                    "date": day.isoformat(),
                    "start": start.isoformat(timespec="minutes"),
                    "end": end.isoformat(timespec="minutes"),
                    "sport": sport,
                    "prescribed_value": value,
                    "unit": UNITS[sport],
                    "title": title,
                    "source_event_id": event["id"],
                    "needs_review": value is None,
                    "note": note,
                }
            )
    return sorted(entries, key=lambda e: (e["start"], e["sport"]))


def keep_manual_values(entries: list[dict], previous: list[dict]) -> int:
    """Carry hand-made changes over a rebuild: a value marked hand_filled always
    wins, a value typed into an entry the parser cannot resolve becomes
    hand_filled, and manual entries (sessions with no parsed calendar event,
    e.g. a gate race) are kept. Returns how many were carried over."""
    old = {(e["source_event_id"], e["sport"]): e for e in previous}
    kept = 0
    for e in entries:
        before = old.get((e["source_event_id"], e["sport"]))
        if not before or before.get("prescribed_value") is None:
            continue
        if before.get("hand_filled") or e["needs_review"]:
            e.update(prescribed_value=before["prescribed_value"], needs_review=False, hand_filled=True, note="filled in by hand")
            kept += 1
    keys = {(e["source_event_id"], e["sport"]) for e in entries}
    manual = [e for e in previous if e.get("manual_entry") and (e["source_event_id"], e["sport"]) not in keys]
    entries.extend(manual)
    entries.sort(key=lambda e: (e["start"], e["sport"]))
    return kept + len(manual)


def build(today: date | None = None) -> list[dict]:
    from .plan_sync import _fetch_events
    from .season import london_today

    today = today or london_today()
    monday = today - timedelta(days=today.weekday())  # the current week is compared from its Monday
    entries = build_entries(_fetch_events(monday, PLAN_UNTIL + timedelta(days=1)), monday)
    previous = json.loads(PLAN_FILE.read_text(encoding="utf-8"))["sessions"] if PLAN_FILE.exists() else []
    kept = keep_manual_values(entries, previous)
    PLAN_FILE.parent.mkdir(exist_ok=True)
    payload = {"generated": datetime.now().isoformat(timespec="seconds"), "from": monday.isoformat(), "to": PLAN_UNTIL.isoformat(), "sessions": entries}
    PLAN_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(entries)} entries written to {PLAN_FILE} ({kept} hand-filled values kept)")
    return entries


# --- done vs due, this week --------------------------------------------------------
#
# Cumulative per sport, never session against session: everything prescribed with a
# scheduled end before now is due, everything recorded since Monday 00:00 is done. A
# session moved to another day, or done early, therefore still counts.

STATUS_BANDS = ((115.0, "Ahead"), (95.0, "On track"), (80.0, "Slightly behind"))  # below the last: "Behind"


def load_plan() -> list[dict]:
    return json.loads(PLAN_FILE.read_text(encoding="utf-8"))["sessions"] if PLAN_FILE.exists() else []


def volume_done(activities: list, week_start: datetime, now: datetime) -> tuple[dict[str, float], list]:
    """({sport: volume}, the activities counted). Swim = metres, bike and run =
    moving minutes; an indoor ride with no distance is still bike minutes."""
    done = dict.fromkeys(UNITS, 0.0)
    counted = []
    for a in activities:
        if a.sport in UNITS and week_start <= a.date <= now:
            done[a.sport] += (a.distance_m or 0.0) if a.sport == "swim" else (a.duration_min or 0.0)
            counted.append(a)
    return done, counted


def status_for(done: float, due: float) -> str:
    if due <= 0:
        return "Ahead" if done > 0 else "No sessions due yet"
    pct = 100 * done / due
    return next((label for floor, label in STATUS_BANDS if pct >= floor), "Behind")


def _plain(title: str) -> str:
    return re.sub(r"^[^\w\[]+", "", title).split(" · ")[0].strip()


def _amount(value: float, unit: str) -> str:
    return f"{round(value):,}"


def volume_status(sessions: list[dict], activities: list, now: datetime) -> dict:
    """Per sport for the Mon-Sun week containing `now` (naive Europe/London time):
    done, due so far and the full-week total, with one display line each. A due
    session without a prescribed value is never counted as 0: the sport shows what
    is missing and gets no status until the plan file is filled in."""
    week_start = datetime.combine(now.date() - timedelta(days=now.weekday()), datetime.min.time())
    week_end = week_start + timedelta(days=7)
    done, counted = volume_done(activities, week_start, now)
    sports = []
    for sport, unit in UNITS.items():
        week = [s for s in sessions if s["sport"] == sport and week_start <= datetime.fromisoformat(s["start"]) < week_end]
        due_sessions = [s for s in week if datetime.fromisoformat(s["end"]) < now]
        missing_due = [s for s in due_sessions if s["prescribed_value"] is None]
        missing_week = [s for s in week if s["prescribed_value"] is None]
        due = sum(s["prescribed_value"] or 0.0 for s in due_sessions)
        week_total = sum(s["prescribed_value"] or 0.0 for s in week)
        if not week and done[sport] <= 0:
            continue
        name = sport.capitalize()
        if missing_due:
            first = missing_due[0]
            status = None
            line = f"{name}: Plan value missing for {_plain(first['title'])} on {first['date']} - fill in plan/prescribed_sessions.json"
        else:
            status = status_for(done[sport], due)
            if due > 0:
                line = f"{name}: {_amount(done[sport], unit)} of {_amount(due, unit)} {unit} due ({round(100 * done[sport] / due)}%) - {status}"
            elif done[sport] > 0:
                line = f"{name}: {_amount(done[sport], unit)} {unit} done, none due yet - {status}"
            else:
                line = f"{name}: {status}"
        week_line = f"{name} week to date: {_amount(done[sport], unit)} of {_amount(week_total, unit)} {unit}"
        if missing_week:
            week_line += f" ({len(missing_week)} session{'s' if len(missing_week) > 1 else ''} without a plan value not included)"
        sports.append(
            {
                "sport": sport,
                "unit": unit,
                "done": done[sport],
                "due": due,
                "week_total": week_total,
                "pct_of_due": 100 * done[sport] / due if due > 0 else None,
                "status": status,
                "missing": [{"title": s["title"], "date": s["date"]} for s in missing_due],
                "line": line,
                "week_line": week_line,
            }
        )
    return {"as_of": now, "week_start": week_start.date(), "sports": sports, "counted": counted}


def current_volume_status(db, now: datetime | None = None) -> dict:
    from ..models.intervals import IntervalsActivity
    from .season import LONDON

    now = now or datetime.now(LONDON).replace(tzinfo=None)  # activity and plan times are naive London time
    week_start = datetime.combine(now.date() - timedelta(days=now.weekday()), datetime.min.time())
    activities = db.query(IntervalsActivity).filter(IntervalsActivity.date >= week_start).order_by(IntervalsActivity.date).all()
    return volume_status(load_plan(), activities, now)


def _print_status(now: datetime | None = None) -> None:
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        result = current_volume_status(db, now)
    finally:
        db.close()
    now = result["as_of"]
    print(f"As of {now:%a %Y-%m-%d %H:%M} (week from {result['week_start']})\n\nPlan entries this week:")
    week_end = result["week_start"] + timedelta(days=7)
    for s in load_plan():
        if result["week_start"].isoformat() <= s["date"] < week_end.isoformat():
            value = "missing" if s["prescribed_value"] is None else f"{s['prescribed_value']:g} {s['unit']}"
            due = "due" if datetime.fromisoformat(s["end"]) < now else "not yet due"
            print(f"  {s['date']} {s['start'][11:]}-{s['end'][11:]}  {s['sport']:4}  {value:>9}  {due:11}  {_plain(s['title'])}")
    print("\nActivities counted (intervals.icu):")
    for a in result["counted"]:
        distance = f"{a.distance_m:,.0f} m" if a.distance_m else "no distance"
        print(f"  {a.date:%Y-%m-%d %H:%M}  {a.type:12} -> {a.sport:4}  {distance:>11}  {a.duration_min:6.1f} min moving")
    print()
    for s in result["sports"]:
        print(s["line"])
    for s in result["sports"]:
        print(s["week_line"])


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    elif sys.argv[1:2] == ["status"]:  # optional: "2026-10-13T09:30" to recompute for a fixed moment
        _print_status(datetime.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else None)
    else:
        sys.exit(__doc__)
