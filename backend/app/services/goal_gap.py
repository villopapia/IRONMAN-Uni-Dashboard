"""Race-goal gap tracker (spec item 8) - a deliberately rough, directional
projection of 70.3 finish time from the latest threshold estimates, vs. the
split budget.

Budget (Chris's numbers): swim ~30:00, bike 2:25 @ ~190 W NP, run 1:22 @
3:53/km, total 4:20-4:25. The splits sum to 4:17:00, so T1+T2 are budgeted
at the remainder to the middle of the target range (5:30).

Conversion constants - wherever possible taken from Chris's own plan notes
in Google Calendar, not invented:
  swim  race pace = CSS + 2.7 s/100m. From the Mid-Phase-4 gate note: "CSS
        <= 1:32/100m (locks in 30-min 1900m as achievable)" -> 1900 m in 30:00
        is 1:34.7/100m, i.e. 2.7 s/100m slower than CSS.
  bike  race power = 0.82 x FTP. From the same note: FTP target 232 W for a
        190 W race power (190 / 232 = 0.82). Time then scales with
        (190 W / race power)^(1/3) - the aero-dominated flat-course
        power-speed relationship (generic physics, not from the plan).
  run   off-bike run = standalone half-marathon + 7 min. From the Sheffield
        Half gate note: "your 21k time here + 6-8 minutes ~ what you can run
        off the bike in July" (midpoint used).
        If only a threshold pace is logged, standalone HM pace is taken as
        threshold pace x 1.03 - a GENERIC assumption (HM is run slightly
        slower than ~1-hour threshold pace), not from the plan.
Which estimate feeds each leg is reported in the response, so the basis of
every number is visible. Missing estimates fall back to the budget split and
are marked "no estimate" - the total is then flagged as incomplete.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models.performance import ThresholdTest

HM_KM = 21.0975
SWIM_M = 1900

BUDGET = {"swim": 30 * 60, "bike": (2 * 60 + 25) * 60, "run": (60 + 22) * 60}
BIKE_BUDGET_POWER_W = 190.0
RUN_BUDGET_PACE_S_PER_KM = 3 * 60 + 53
TARGET_LOW_S = (4 * 60 + 20) * 60
TARGET_HIGH_S = (4 * 60 + 25) * 60
TRANSITIONS_S = round((TARGET_LOW_S + TARGET_HIGH_S) / 2 - sum(BUDGET.values()))

SWIM_RACE_OFFSET_S = round(BUDGET["swim"] / (SWIM_M / 100) - 92.0, 1)  # 2.7
BIKE_IF = round(BIKE_BUDGET_POWER_W / 232.0, 3)  # 0.819
RUN_OFF_BIKE_PENALTY_S = 7 * 60
THRESHOLD_TO_HM_PACE = 1.03  # generic assumption, see module docstring
RECENT_DAYS = 90

REAL_SOURCES = ("manual", "phase_gate")


def _latest(db: Session, metric: str, sources: tuple[str, ...]) -> ThresholdTest | None:
    return (
        db.query(ThresholdTest)
        .filter(ThresholdTest.metric == metric, ThresholdTest.source.in_(sources))
        .order_by(ThresholdTest.test_date.desc(), ThresholdTest.id.desc())
        .first()
    )


def _fmt(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _leg(leg: str, projected: float | None, basis: str | None, source: str | None,
         test_date: date | None, assumption: str) -> dict:
    budget = BUDGET[leg]
    return {
        "leg": leg,
        "budget_s": budget,
        "projected_s": round(projected) if projected is not None else None,
        "delta_s": round(projected - budget) if projected is not None else None,
        "basis": basis,
        "source": source,
        "estimate_date": test_date,
        "assumption": assumption,
    }


def _swim(db: Session) -> dict:
    css = _latest(db, "css_pace", ("manual", "phase_gate", "garmin"))
    assumption = f"Race pace = CSS + {SWIM_RACE_OFFSET_S} s/100m (from your CSS 1:32 -> 30:00 swim gate note)."
    if not css:
        return _leg("swim", None, None, None, None, assumption)
    projected = (css.value + SWIM_RACE_OFFSET_S) * SWIM_M / 100
    return _leg("swim", projected, f"CSS {_fmt(css.value)}/100m", css.source, css.test_date, assumption)


def _bike(db: Session) -> dict:
    assumption = (
        f"Race power = {BIKE_IF} x FTP (your 190 W / 232 W plan targets); "
        "time scales with (190 W / race power)^(1/3)."
    )
    # Deliberately real tests only (manual LTHR/FTP test or a logged phase-gate
    # result) - NOT the Garmin-profile FTP fallback used previously. That value
    # (source="garmin") is a passive profile field (biometricSourceType
    # CHANGE_LOG) with no confirmed origin - not derived from a real test or
    # from Chris's actual ride history (no power data on any of his rides, and
    # none since Jul 2026) - so it doesn't belong in a projection presented as
    # a specific time+delta. Same treatment as swim: no real test -> no
    # projection, budget split shown, leg flagged incomplete.
    ftp = _latest(db, "ftp", REAL_SOURCES)
    if not ftp:
        return _leg("bike", None, None, None, None, assumption)
    race_power = ftp.value * BIKE_IF
    projected = BUDGET["bike"] * (BIKE_BUDGET_POWER_W / race_power) ** (1 / 3)
    basis = f"FTP {round(ftp.value)} W -> ~{round(race_power)} W race power"
    return _leg("bike", projected, basis, ftp.source, ftp.test_date, assumption)


def _run(db: Session, today: date) -> dict:
    assumption = "Off-bike run = standalone half-marathon + 7:00 (your Sheffield Half note: '+6-8 minutes')."
    recent = today - timedelta(days=RECENT_DAYS)
    hm = _latest(db, "hm_time", REAL_SOURCES)
    tp = _latest(db, "threshold_pace", REAL_SOURCES)
    pred = _latest(db, "hm_prediction", ("garmin",))

    candidates = []
    if hm and hm.test_date >= recent:
        candidates.append((hm.value, f"Half-marathon result {_fmt(hm.value)}", hm))
    if tp and tp.test_date >= recent:
        candidates.append(
            (tp.value * THRESHOLD_TO_HM_PACE * HM_KM,
             f"Threshold pace {_fmt(tp.value)}/km x {THRESHOLD_TO_HM_PACE} (generic HM factor)", tp)
        )
    if not candidates and pred:
        candidates.append((pred.value, f"Garmin HM prediction {_fmt(pred.value)}", pred))
    if not candidates:  # stale real results are still better than nothing
        for row, label in ((hm, "Half-marathon result"), (tp, "Threshold pace")):
            if row:
                hm_s = row.value if row.metric == "hm_time" else row.value * THRESHOLD_TO_HM_PACE * HM_KM
                candidates.append((hm_s, f"{label} from {row.test_date.isoformat()} (older than {RECENT_DAYS}d)", row))
                break
    if not candidates:
        return _leg("run", None, None, None, None, assumption)

    # Most recent estimate wins among the candidates that qualified.
    standalone, basis, row = max(candidates, key=lambda c: c[2].test_date)
    return _leg("run", standalone + RUN_OFF_BIKE_PENALTY_S, basis, row.source, row.test_date, assumption)


def goal_gap(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    legs = [_swim(db), _bike(db), _run(db, today)]
    complete = all(l["projected_s"] is not None for l in legs)
    projected_total = sum(
        l["projected_s"] if l["projected_s"] is not None else l["budget_s"] for l in legs
    ) + TRANSITIONS_S
    return {
        "target_low_s": TARGET_LOW_S,
        "target_high_s": TARGET_HIGH_S,
        "transitions_s": TRANSITIONS_S,
        "legs": legs,
        "projected_total_s": projected_total,
        "delta_to_target_high_s": projected_total - TARGET_HIGH_S,
        "delta_to_target_low_s": projected_total - TARGET_LOW_S,
        "complete": complete,
        "missing_legs": [l["leg"] for l in legs if l["projected_s"] is None],
        # The thresholds the budget implies, under the same conversions.
        "required": {
            "css_pace_s_per_100m": round(BUDGET["swim"] / (SWIM_M / 100) - SWIM_RACE_OFFSET_S, 1),
            "ftp_w": round(BIKE_BUDGET_POWER_W / BIKE_IF),
            "hm_standalone_s": BUDGET["run"] - RUN_OFF_BIKE_PENALTY_S,
            "run_pace_s_per_km": RUN_BUDGET_PACE_S_PER_KM,
        },
        "note": (
            "Directional only. Each leg converts your latest threshold estimate with "
            "the assumption shown; legs without an estimate use the budget split and "
            "make the total incomplete. T1+T2 are budgeted at the gap between your "
            "splits (4:17:00) and the middle of the 4:20-4:25 target."
        ),
    }
