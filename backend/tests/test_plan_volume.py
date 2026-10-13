"""Run from backend/: python -m tests.test_plan_volume (also pytest-compatible)."""

from datetime import date, datetime
from types import SimpleNamespace

from app.services.plan_volume import (
    entry_class,
    intensity_class,
    is_race,
    keep_manual_values,
    match_plan_entry,
    planned_load,
    prescribed_value,
    realised_rates,
    session_sports,
    status_for,
    volume_status,
    weekly_planned_load,
)


def _d(month, day, year=2026):
    return date(year, month, day)


LONG_BIKE = """SESSION:
- 10' easy warm-up → Z2 (HR 136-156) → last 20' upper Z2
- Oct 3 (recovery): 70' all Z2
- Oct 10 / Oct 17: 120'
- Oct 24 (test week): 90' easy Z2 only, no upper-Z2 finish — HM time trial is Sunday

FUEL:
- 120' rides: gel (~25-30g) at 25', 50', 75', 100'"""

WEEKLY_BIKE = """SESSION: 10' easy warm-up → Z2 → 10' easy cool-down.

DURATION BY WEEK (3:1 loading):
- Wk1-3 (Oct 26 / Nov 2 / Nov 9): 70' → 75' → 80'
- Wk4 recovery (Nov 16): 60'
- Wk9-11 (Dec 21 / Dec 28 / Jan 4): 100' -> 105' -> 110'
Calendar block is sized for the 110' peak — finish earlier in lighter weeks."""

SWIM = """SESSION (50'):
- 300 easy
- Main: 200s steady, 30" rest
  · Oct 6: 4x200 → 1,500m total
  · Oct 13: 5x200 → 1,700m total
  · Oct 20 (test week): 3x200 easy -> 1,300m total
- 200 easy cool-down"""


def test_dates_then_a_duration():
    assert prescribed_value(LONG_BIKE, "Long Bike", _d(10, 10), "bike")[0] == 120
    assert prescribed_value(LONG_BIKE, "Long Bike", _d(10, 17), "bike")[0] == 120  # second date of "Oct 10 / Oct 17"
    assert prescribed_value(LONG_BIKE, "Long Bike", _d(10, 3), "bike")[0] == 70  # label in brackets before the colon
    assert prescribed_value(LONG_BIKE, "Long Bike", _d(10, 24), "bike")[0] == 90
    value, why = prescribed_value(LONG_BIKE, "Long Bike", _d(10, 31), "bike")
    assert value is None and "not in the description" in why  # a date the table does not list is never guessed


def test_week_rows_with_one_value_per_date():
    assert [prescribed_value(WEEKLY_BIKE, "Z2 Bike", _d(m, d), "bike")[0] for m, d in ((10, 26), (11, 2), (11, 9))] == [70, 75, 80]
    assert prescribed_value(WEEKLY_BIKE, "Z2 Bike", _d(11, 16), "bike")[0] == 60  # "Wk4 recovery (Nov 16): 60'"
    assert prescribed_value(WEEKLY_BIKE, "Z2 Bike", _d(12, 28), "bike")[0] == 105  # ASCII arrows too
    assert prescribed_value(WEEKLY_BIKE, "Z2 Bike", _d(1, 4, 2027), "bike")[0] == 110  # the list runs into the new year


def test_swim_total_after_the_arrow():
    assert prescribed_value(SWIM, "Endurance Swim", _d(10, 13), "swim")[0] == 1700
    assert prescribed_value(SWIM, "Endurance Swim", _d(10, 20), "swim")[0] == 1300
    longer = "- Wk9-11 (Dec 26 / Jan 2 / Jan 9): 1,900m continuous steady (race-distance rehearsal) → 2,800m"
    assert prescribed_value(longer, "Long Swim", _d(1, 9, 2027), "swim")[0] == 2800  # the total, not the main set


def test_swim_total_in_brackets_and_pointer():
    text = "SESSION — Oct 7 / 14 (1,800m, 50'):\n- 300 easy\nOCT 21 (test week): same but 4x100 → 1,600m."
    assert prescribed_value(text, "Technique Swim", _d(10, 14), "swim")[0] == 1800  # "Oct 7 / 14": month carries over
    assert prescribed_value(text, "Technique Swim", _d(10, 21), "swim")[0] == 1600
    per_date = "- Oct 17 (2,500m, 70'): 400 easy · 2x600 steady, 60\" rest · 200 easy"
    assert prescribed_value(per_date, "Long Swim", _d(10, 17), "swim")[0] == 2500
    retest = "- Wk4 (Nov 20): CSS RETEST ↓\n\nCSS RETEST (1,700m): 400 easy + 4x50 build · 200 easy"
    assert prescribed_value(retest, "CSS Swim", _d(11, 20), "swim")[0] == 1700


def test_as_above_and_headers():
    monday = "SESSION (70'):\n- 10' easy warm-up\n- 50' Z2\n- 10' easy cool-down\n\nDATES: Oct 5 / Oct 12 as above. Oct 19 = LTHR/FTP test (see that day's event)."
    assert prescribed_value(monday, "Z2 Bike", _d(10, 12), "bike")[0] == 70
    assert prescribed_value(monday, "Z2 Bike", _d(10, 19), "bike")[0] is None  # pointed elsewhere
    assert prescribed_value("- Oct 8 / Oct 15: full 80' as above", "Long Z2 Bike", _d(10, 15), "bike")[0] == 80
    assert prescribed_value("SESSION — Oct 10 / Oct 17 (40'):\n- First 10': easy", "Brick Run", _d(10, 17), "run")[0] == 40
    assert prescribed_value("PROTOCOL (55'):\n- 15' warm-up", "Bike test", _d(10, 19), "bike")[0] == 55  # no dates at all: the header
    assert prescribed_value("PROTOCOL (1,700m):\n- 400 easy", "Swim test", _d(10, 23), "swim")[0] == 1700


SWEET_SPOT = """SESSION (80' block):
- 15' warm-up incl. 3x30" fast pedalling in the last 5'
- Main set (3' easy between reps):
  · Wk1-3 (Oct 28, Nov 4, Nov 11): 4x8'
  · Wk4 recovery (Nov 18): 45' easy Z2, no intervals
  · Wk9-11 (Dec 23, Dec 30, Jan 6): 3x15' (5' easy between)
- 10' easy cool-down"""

TEMPO = """SESSION:
- 15' easy warm-up + 4x20" strides (full recovery between)
- Main set:
  · Oct 13: 2x6' tempo, 2' jog between
- 10' easy cool-down"""


def test_structured_sessions_are_summed_or_left_for_review():
    assert prescribed_value(SWEET_SPOT, "Sweet Spot", _d(11, 4), "bike")[0] == 15 + 4 * 8 + 3 * 3 + 10  # 66, not the 80' block
    assert prescribed_value(SWEET_SPOT, "Sweet Spot", _d(12, 30), "bike")[0] == 15 + 3 * 15 + 2 * 5 + 10  # its own recovery
    assert prescribed_value(TEMPO, "Tempo Run", _d(10, 13), "run")[0] is None  # strides with unstated recoveries
    retest = SWEET_SPOT.replace("45' easy Z2, no intervals", "FTP RETEST — same 20' protocol (15' warm-up · 20' max · 15' easy)")
    assert prescribed_value(retest, "Sweet Spot", _d(11, 18), "bike")[0] is None  # not a plain duration: left for review


def test_easy_week_inside_a_main_set_is_the_stated_minutes_only():
    # Chris's rule: no warm-up or cool-down added; plus 2 minutes when strides are listed.
    assert prescribed_value(SWEET_SPOT, "Sweet Spot", _d(11, 18), "bike")[0] == 45
    runs = ("- 15' warm-up: 10' easy + 4x20\" strides\n- Main set (400m jog between reps):\n"
            "  · Wk4 recovery (Nov 17): no intervals — 30' easy Z2\n  · Wk8 recovery (Dec 15): 35' easy Z2\n"
            "  · Wk12 (Jan 12): 30' easy Z2 + 4 strides (test week)\n- 10' easy cool-down")
    assert prescribed_value(runs, "Threshold", _d(11, 17), "run")[0] == 30
    assert prescribed_value(runs, "Threshold", _d(12, 15), "run")[0] == 35
    assert prescribed_value(runs, "Threshold", _d(1, 12, 2027), "run")[0] == 32
    km_reps = "- 15' warm-up\n- Main set (400m jog between reps):\n  · Wk1-3 (Oct 27, Nov 3): 4x1km @ threshold\n- 10' easy cool-down"
    value, why = prescribed_value(km_reps, "Threshold", _d(10, 27), "run")
    assert value is None and "distance" in why


def test_descriptions_without_dates():
    z2 = "**Focus:** Aerobic\n**Structure:** 10' WU; 35' Z2 (HR 136-156); 5' CD\nDistance: 8-10km"
    assert prescribed_value(z2, "Run Z2 (50')", _d(1, 19, 2027), "run")[0] == 50
    assert prescribed_value(z2, "Run Z2 (55')", _d(1, 19, 2027), "run")[0] is None  # parts disagree with the title
    reps = "15' WU; 2x8' @ 78-82% FTP (race power) w/ 4' easy; 15' Z2; 10' CD. All in aerobars."
    assert prescribed_value(reps, "Bike: 2x8' @ race power (60')", _d(6, 29, 2027), "bike")[0] == 60
    rotation = "**Structure:**\n- 20' WU\n- Main 3x12' @ FTP w/ 4' easy\n\nWk 1,4,7: 3x12' @ FTP\nWk 2,5,8: 2x20' @ 95% FTP"
    value, why = prescribed_value(rotation, "Bike FTP (outdoor, 90')", _d(1, 19, 2027), "bike")
    assert value is None and "week number" in why
    assert prescribed_value("300 WU; 1x 1000m @ race pace; 4x50 sprint on 20\"; 200 CD. Total ~1700m.", "Swim", _d(6, 23, 2027), "swim")[0] == 1700
    assert prescribed_value("300 WU; 8x50 drill; 6x100 aerobic + 4x50 build; 200 CD. Total ~1800m.", "Swim", _d(6, 25, 2027), "swim")[0] is None  # adds up to 1,700
    brick = "- Bike 2.5h: 15' Z2 WU, 2x30' @ race power\n- T2 sim\n- Run 30' off-bike @ target race pace"
    assert prescribed_value(brick, "Brick", _d(6, 26, 2027), "bike", multi_sport=True)[0] == 150
    assert prescribed_value(brick, "Brick", _d(6, 26, 2027), "run", multi_sport=True)[0] == 30


def test_which_events_are_sessions():
    assert session_sports("\U0001f3ca Endurance Swim · 200s steady") == ["swim"]
    assert session_sports("\U0001f3c3 Tempo Run · RPE 7 · gym kit for after") == ["run"]  # "gym" in a run title
    assert session_sports("\U0001f6b4 Z2 + Cadence · spin-ups 100-110 rpm") == ["bike"]  # no sport word, bike tag
    assert session_sports("\U0001f517 Brick: Bike 3h + Run 30' @ HMP off-bike") == ["bike", "run"]
    assert session_sports("\U0001f517 Brick Run · out the door <3'") == ["run"]
    assert session_sports("\U0001f3af Run TEST — HM Time Trial (Phase 1 exit gate)") == ["run"]
    assert session_sports("\U0001f3c3 Long Run + Recovery Swim") == ["run", "swim"]
    for title in ("\U0001f34c Banana before swim", "\U0001f392 Pack swim bag + banana", "\U0001f963 Breakfast · oats bowl (after brick)",
                  "\U0001f4aa Strength: Compound (maintenance)", "[LEC] Databases", "\U0001f4ca CHECKPOINT 1 · bike +3%"):
        assert session_sports(title) == [], title


def test_hand_filled_values_survive_a_rebuild():
    new = [{"source_event_id": "a", "sport": "run", "start": "2026-10-13T18:15", "prescribed_value": None, "needs_review": True, "note": "x"},
           {"source_event_id": "b", "sport": "bike", "start": "2026-10-12T06:00", "prescribed_value": 70.0, "needs_review": False, "note": "y"}]
    old = [{"source_event_id": "a", "sport": "run", "prescribed_value": 39}, {"source_event_id": "b", "sport": "bike", "prescribed_value": 999}]
    assert keep_manual_values(new, old) == 1
    run, bike = (next(e for e in new if e["sport"] == s) for s in ("run", "bike"))
    assert (run["prescribed_value"], run["needs_review"], run["hand_filled"]) == (39, False, True)
    assert bike["prescribed_value"] == 70.0  # a parsed value is not overridden by an old unmarked one


def test_hand_filled_flag_and_manual_entries_survive_a_rebuild():
    new = [{"source_event_id": "b", "sport": "bike", "start": "2026-11-18T18:00", "prescribed_value": 66.0, "needs_review": False, "note": "sum"}]
    old = [{"source_event_id": "b", "sport": "bike", "start": "2026-11-18T18:00", "prescribed_value": 45.0, "hand_filled": True},
           {"source_event_id": "race", "sport": "run", "start": "2027-04-04T09:00", "prescribed_value": 105.0, "hand_filled": True, "manual_entry": True}]
    assert keep_manual_values(new, old) == 2
    assert new[0]["prescribed_value"] == 45.0  # marked hand-filled: wins even over a parsed value
    assert [e["source_event_id"] for e in new] == ["b", "race"]  # the manual entry is carried over, in date order
    assert keep_manual_values(new, old) == 2 and len(new) == 2  # and not duplicated by a second rebuild


# --- done vs due -----------------------------------------------------------------


def _plan(day, start, end, sport, value, title="Session"):
    return {"date": f"2026-10-{day}", "start": f"2026-10-{day}T{start}", "end": f"2026-10-{day}T{end}", "sport": sport,
            "prescribed_value": value, "unit": "m" if sport == "swim" else "min", "title": title}


def _done(day, hour, sport, metres=None, minutes=0.0):
    return SimpleNamespace(date=datetime(2026, 10, day, hour), sport=sport, distance_m=metres, duration_min=minutes, type=sport)


WEEK = [  # Mon 12 - Sun 18 Oct 2026
    _plan(12, "06:00", "07:15", "bike", 70.0),
    _plan(13, "06:00", "07:00", "swim", 1700.0),
    _plan(13, "18:15", "19:05", "run", 44.0),
    _plan(14, "06:00", "07:00", "swim", 1800.0),
    _plan(15, "06:00", "07:20", "bike", 80.0),
]


def _by_sport(result):
    return {s["sport"]: s for s in result["sports"]}


def test_due_is_what_has_ended_and_done_is_cumulative():
    acts = [_done(12, 18, "bike", minutes=60.1), _done(12, 20, "swim", metres=200), _done(13, 6, "swim", metres=1175)]
    r = _by_sport(volume_status(WEEK, acts, datetime(2026, 10, 13, 9, 30)))
    assert (r["bike"]["due"], r["swim"]["due"], r["run"]["due"]) == (70.0, 1700.0, 0.0)  # Tue 09:30: Mon bike + Tue swim
    assert r["swim"]["done"] == 1375 and r["swim"]["line"] == "Swim: 1,375 of 1,700 m due (81%) - Slightly behind"
    assert r["bike"]["line"] == "Bike: 60 of 70 min due (86%) - Slightly behind"  # indoor ride, no distance: minutes
    assert r["run"]["line"] == "Run: No sessions due yet"
    assert r["swim"]["week_line"] == "Swim week to date: 1,375 of 3,500 m"
    assert r["bike"]["pct_of_due"] == 100 * 60.1 / 70  # unrounded: rounding is for display only


def test_moved_and_early_sessions_count_through_the_cumulative_total():
    # Thursday's 80' ride done on Tuesday evening instead, on top of Monday's.
    acts = [_done(12, 6, "bike", minutes=70), _done(13, 19, "bike", minutes=80)]
    wed = _by_sport(volume_status(WEEK, acts, datetime(2026, 10, 14, 12, 0)))
    assert wed["bike"]["due"] == 70 and wed["bike"]["done"] == 150 and wed["bike"]["status"] == "Ahead"  # early, not lost
    fri = _by_sport(volume_status(WEEK, acts, datetime(2026, 10, 16, 12, 0)))
    assert fri["bike"]["due"] == 150 and fri["bike"]["status"] == "On track"  # the moved session now squares up
    # A swim with nothing due yet is "Ahead", and nothing due and nothing done is "No sessions due yet".
    early = _by_sport(volume_status(WEEK, [_done(12, 5, "swim", metres=500)], datetime(2026, 10, 12, 5, 30)))
    assert early["swim"]["status"] == "Ahead" and early["bike"]["status"] == "No sessions due yet"


def test_status_bands():
    assert [status_for(done, 100) for done in (115, 114.9, 95, 94.9, 80, 79.9, 0)] == [
        "Ahead", "On track", "On track", "Slightly behind", "Slightly behind", "Behind", "Behind"]
    assert status_for(0, 0) == "No sessions due yet" and status_for(10, 0) == "Ahead"


def test_week_boundary():
    acts = [_done(11, 23, "run", minutes=58), _done(12, 0, "run", minutes=30), _done(18, 23, "bike", minutes=45)]
    monday = _by_sport(volume_status(WEEK, acts, datetime(2026, 10, 12, 0, 0)))  # Monday 00:00 exactly
    assert monday["run"]["done"] == 30  # Sunday 23:00 belongs to last week; Monday 00:00 is in
    assert monday["bike"]["due"] == 0 and monday["bike"]["status"] == "No sessions due yet"
    sunday = _by_sport(volume_status(WEEK, acts, datetime(2026, 10, 18, 23, 59)))
    assert sunday["bike"]["due"] == 150 and sunday["bike"]["done"] == 45 and sunday["run"]["due"] == 44
    next_week = volume_status(WEEK, acts, datetime(2026, 10, 19, 0, 0))  # the next Monday: a fresh week
    assert next_week["week_start"] == date(2026, 10, 19) and next_week["sports"] == []
    ending_now = _by_sport(volume_status(WEEK, [], datetime(2026, 10, 12, 7, 15)))
    assert ending_now["bike"]["due"] == 0  # due only once the scheduled end is before now


def test_missing_plan_value_is_never_zero_and_never_ahead():
    week = WEEK + [_plan(13, "07:30", "08:20", "run", None, "\U0001f3c3 Tempo Run · RPE 7")]
    r = _by_sport(volume_status(week, [_done(13, 7, "run", minutes=50)], datetime(2026, 10, 13, 12, 0)))
    assert r["run"]["status"] is None
    assert r["run"]["line"] == "Run: Plan value missing for Tempo Run on 2026-10-13 - fill in plan/prescribed_sessions.json"
    assert "1 session without a plan value" in r["run"]["week_line"]
    assert r["bike"]["status"] == "Behind"  # other sports are still judged
    before = _by_sport(volume_status(week, [], datetime(2026, 10, 13, 7, 0)))
    assert before["run"]["status"] == "No sessions due yet"  # not due yet: the gap does not block anything


# --- planned load ----------------------------------------------------------------

TODAY = date(2026, 10, 13)


def _act(day, sport, load, minutes, metres=None, hour=6, name="Session", month=10):
    return SimpleNamespace(date=datetime(2026, month, day, hour), sport=sport, icu_training_load=load, duration_min=minutes,
                           distance_m=metres, name=name, race=False)


def test_intensity_class_from_the_title():
    hard = ["Tempo Run · RPE 7", "Threshold 1km Reps · HM-TT pace", "Sweet Spot · 88-93% FTP", "CSS Swim · hard", "Bike TEST · 20' FTP/LTHR",
            "Swim: CSS Retest", "Run TEST — 10k TT", "Run TEST — HM Time Trial"]
    easy = ["Z2 Bike · HR 136-156", "Long Run · HR <=156", "Technique Swim · drills · Tempo Trainer",  # a metronome, not a tempo session
            "Endurance Swim · 200s @ CSS+8-10s",  # an easy pace written relative to CSS
            "Long Swim · steady", "Brick Run · out the door"]
    assert [intensity_class(t) for t in hard] == ["hard"] * len(hard)
    assert [intensity_class(t) for t in easy] == ["easy"] * len(easy)


def test_intensity_overrides_win_and_survive_a_rebuild():
    assert entry_class({"title": "Tempo Run · RPE 7", "intensity_class": "easy"}) == "easy"  # test-week easy run
    assert entry_class({"title": "Z2 Bike · HR 136-156", "intensity_class": "hard"}) == "hard"  # the FTP test
    assert entry_class({"title": "Tempo Run · RPE 7"}) == "hard"  # no field: the title rule
    new = [{"source_event_id": "t", "sport": "run", "start": "2026-10-20T18:15", "prescribed_value": None, "needs_review": True,
            "note": "x", "intensity_class": "hard"}]
    old = [{"source_event_id": "t", "sport": "run", "start": "2026-10-20T18:15", "prescribed_value": 30.0, "hand_filled": True,
            "intensity_class": "easy", "intensity_hand_set": True}]
    keep_manual_values(new, old)
    assert (new[0]["intensity_class"], new[0]["intensity_hand_set"], new[0]["prescribed_value"]) == ("easy", True, 30.0)
    untouched = [{"source_event_id": "u", "sport": "run", "start": "2026-10-21T18:15", "prescribed_value": 40.0, "needs_review": False,
                  "note": "x", "intensity_class": "hard"}]
    keep_manual_values(untouched, [{"source_event_id": "u", "sport": "run", "prescribed_value": 40.0, "intensity_class": "easy"}])
    assert untouched[0]["intensity_class"] == "hard"  # an old class that was not hand-set does not override the rule


def test_activity_takes_the_class_of_the_closest_plan_entry():
    plan = [_plan(13, "06:00", "07:00", "run", 40.0, "Z2 Run"), _plan(13, "18:15", "19:05", "run", 44.0, "Tempo Run"),
            _plan(13, "06:00", "07:00", "swim", 1700.0, "Endurance Swim")]
    assert match_plan_entry(_act(13, "run", 30, 40, hour=19), plan)["title"] == "Tempo Run"  # same day and sport, nearest start
    assert match_plan_entry(_act(13, "run", 30, 40, hour=7), plan)["title"] == "Z2 Run"
    assert match_plan_entry(_act(13, "bike", 30, 40), plan) is None  # other sport
    assert match_plan_entry(_act(14, "run", 30, 40), plan) is None  # other day


def _rates(acts, plan):
    return realised_rates(acts, plan, TODAY)


def test_rate_is_total_load_over_total_hours_with_fallbacks():
    plan = [_plan(d, "06:00", "07:00", "run", 60.0, "Z2 Run") for d in (10, 11, 12)] + [_plan(13, "06:00", "07:00", "run", 44.0, "Tempo Run")]
    acts = [_act(10, "run", 30, 60), _act(11, "run", 40, 60), _act(12, "run", 50, 120), _act(13, "run", 60, 60),
            _act(9, "bike", 30, 60), _act(8, "bike", 50, 60)]  # two unmatched rides
    r = _rates(acts, plan)["table"]
    assert r[("run", "easy")] == {"sport": "run", "intensity": "easy", "rate": 120 / 4, "activities": 3, "source": "own bucket"}  # not the mean of 30/40/25
    assert r[("run", "hard")]["source"] == "sport overall" and r[("run", "hard")]["activities"] == 1
    assert r[("run", "hard")]["rate"] == 180 / 5  # all four runs
    assert r[("bike", "easy")]["source"] == "all sports" and r[("bike", "easy")]["rate"] == 260 / 7  # under 3 rides: every activity
    assert r[("swim", "easy")]["rate"] == 260 / 7 and r[("swim", "easy")]["activities"] == 0
    assert _rates([], plan)["table"][("run", "easy")]["rate"] is None  # no activities at all: unknown, not zero


def test_unmatched_activities_count_only_towards_the_sport_overall():
    acts = [_act(d, "bike", 36, 60) for d in (1, 2, 3, 4)]  # before the plan file starts: no entry to match
    r = _rates(acts, [])
    assert r["table"][("bike", "easy")] == {"sport": "bike", "intensity": "easy", "rate": 36.0, "activities": 0, "source": "sport overall"}
    assert r["sport_activities"]["bike"] == 4


def test_races_and_old_activities_are_left_out_of_the_rates():
    plan = [_plan(11, "17:00", "19:00", "run", 114.0, "Run TEST — HM Time Trial (Phase 1 exit gate)"),
            _plan(12, "06:00", "07:00", "run", 51.0, "Threshold 1km Reps · HM-TT pace")]
    race_by_plan, training = _act(11, "run", 150, 110, hour=17), _act(12, "run", 50, 50)
    assert is_race(race_by_plan, match_plan_entry(race_by_plan, plan)) and not is_race(training, match_plan_entry(training, plan))
    assert is_race(_act(5, "run", 90, 95, name="Sheffield Half Marathon"), None)  # by recorded name
    assert is_race(_act(20, "run", 123, 118, month=9), None)  # the listed 20 Sep half marathon
    assert not is_race(_act(20, "bike", 40, 60, month=9), None)
    acts = [race_by_plan, training, _act(20, "run", 123, 118, month=9), _act(1, "run", 40, 60), _act(2, "run", 40, 60),
            _act(1, "run", 999, 60, month=9)]  # 1 Sep: outside the 28-day window
    r = _rates(acts, plan)
    assert len(r["excluded"]) == 2 and r["sport_activities"]["run"] == 3
    assert r["table"][("run", "easy")]["rate"] == 130 / (170 / 60)


def test_swim_metres_become_hours_at_the_realised_pace():
    acts = [_act(d, "swim", 20, 40, metres=2000) for d in (10, 11, 12)] + [_act(9, "swim", 5, 10, metres=None)]  # one with no distance
    r = _rates(acts, [])
    assert r["swim_hours_per_m"] == (120 / 60) / 6000  # 2:00 per 100 m; the swim without a distance is not in the pace
    rate = r["table"][("swim", "easy")]["rate"]  # 65 load over 130 min, the no-distance swim included
    swim = {"sport": "swim", "prescribed_value": 1500.0, "title": "Endurance Swim"}
    assert abs(planned_load(swim, r) - 0.5 * rate) < 1e-9  # 1,500 m = 30 min
    run = {"sport": "run", "prescribed_value": 90.0, "title": "Long Run"}
    assert planned_load(run, {**r, "table": {**r["table"], ("run", "easy"): {"rate": 40.0}}}) == 60.0  # minutes / 60 x rate
    assert planned_load(swim, {**r, "swim_hours_per_m": None}) is None  # no pace yet: unknown


def test_a_week_with_a_missing_value_has_no_planned_total():
    rates = {"table": {("bike", "easy"): {"rate": 36.0}, ("run", "hard"): {"rate": 45.0}}, "swim_hours_per_m": None}
    week = [{"sport": "bike", "prescribed_value": 60.0, "title": "Z2 Bike"}, {"sport": "run", "prescribed_value": 40.0, "title": "Tempo Run"}]
    assert weekly_planned_load(week, rates) == {"load": 66.0, "known_load": 66.0, "missing": 0, "hours": 60 / 60 + 40 / 60, "sessions": 2}
    gap = weekly_planned_load(week + [{"sport": "run", "prescribed_value": None, "title": "Tempo Run"}], rates)
    assert gap["load"] is None and gap["missing"] == 1 and gap["known_load"] == 66.0 and gap["sessions"] == 3  # never 66, never 0
    assert weekly_planned_load([], rates)["load"] == 0.0  # a week with nothing planned is a real zero


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
