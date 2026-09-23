# Fitness Dashboard

FastAPI + SQLite backend, React/Vite/Tailwind/Recharts frontend. Panels:
academic progress (Sheffield weighted-mean classification estimate), weekly
training rollup (actual vs. target minutes *and* km per sport, on-track %,
this week's calendar plan), recovery metrics (Garmin), nutrition + supplement
adherence, and manual competitor tracking.

## Backend

```
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m alembic upgrade head        # creates dashboard.db
.venv\Scripts\python.exe -m app.seed activities          # real Strava snapshot for local dev
.venv\Scripts\python.exe -m app.seed supplements         # collagen + electrolyte mix (dose TBD)
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Copy `.env.example` to `.env` and fill in credentials as you set each one up
(see below). The scheduler (`app/services/scheduler.py`) auto-enables each
sync job the moment its credentials are present — no code change needed.

### Strava (activity sync, every 6 min)

From https://www.strava.com/settings/api: `STRAVA_CLIENT_ID` /
`STRAVA_CLIENT_SECRET` come straight off that page. `STRAVA_REFRESH_TOKEN`
needs the actual OAuth consent flow (the page's own "Your Refresh Token"
field is `read`-scope only and can't fetch activities):

```
https://www.strava.com/oauth/authorize?client_id=YOUR_ID&redirect_uri=http://localhost/exchange_token&response_type=code&approval_prompt=force&scope=activity:read_all
```

Authorize, copy the `code=` param from the broken redirect, then:

```powershell
Invoke-RestMethod -Uri "https://www.strava.com/oauth/token" -Method Post -Body @{client_id="YOUR_ID"; client_secret="YOUR_SECRET"; code="YOUR_CODE"; grant_type="authorization_code"}
```

Put the response's `refresh_token` in `.env`.

### Google Calendar (this week's plan, display-only)

1. https://console.cloud.google.com → new project → enable the **Google
   Calendar API** → **OAuth consent screen**: add scope
   `calendar.readonly`, and **set publishing status to "In production," not
   "Testing."** Testing-mode refresh tokens for this scope silently expire
   after 7 days — the calendar panel would quietly stop working every week
   if left in Testing.
2. **Credentials** → **Create OAuth client ID** → Desktop app → gives you
   `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.
3. Open (swap in your client ID):
   `https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_ID&redirect_uri=http://localhost/exchange_token&response_type=code&scope=https://www.googleapis.com/auth/calendar.readonly&access_type=offline&prompt=consent`
4. Copy the `code=` param from the broken redirect, then:
   ```powershell
   Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method Post -Body @{client_id="YOUR_ID"; client_secret="YOUR_SECRET"; code="YOUR_CODE"; grant_type="authorization_code"; redirect_uri="http://localhost/exchange_token"}
   ```
5. Put the response's `refresh_token` in `.env` as `GOOGLE_REFRESH_TOKEN`.

This only ever reads event titles/times for "what's planned this week" — it
does not try to parse numeric targets out of session descriptions (too
fragile; `WeeklyTrainingTarget` stays manually seeded for that).

### Garmin Connect (recovery metrics: sleep, Body Battery, Training Readiness, HRV)

Unofficial API (`garminconnect` package) using your own account — there's no
realistic official developer key for a personal project. Put
`GARMIN_EMAIL` / `GARMIN_PASSWORD` in `.env`, then run, yourself, in your own
interactive terminal (not through an automated script — if your account has
MFA, it'll prompt you for the code right here):

```
.venv\Scripts\python.exe -m app.services.garmin_login
```

This caches a session to `backend/.garmin_tokens/` (gitignored) — scheduled
syncs afterward never touch your password again. If a sync ever fails (API
drift, rate limit, expired session), the Recovery panel keeps showing the
last successfully synced day with a "synced Xh ago" note rather than going
blank — check the backend logs / re-run the login script if that note
sticks around.

**Note:** the exact Garmin field paths in `garmin_sync.py` are written
defensively (nothing crashes on a missing field) but haven't been verified
against a live account — this needs a real first sync to confirm, same as
the two real bugs (Strava scope, pagination duplicates) that only surfaced
once tested for real.

### Manual data (add via POST, no credentials needed)

```
POST /api/training/targets      {"week_label": "Wk9", "week_start_date": "2026-10-05", "sport": "run", "target_minutes": 120, "target_distance_km": 20}
POST /api/academic/modules      {"academic_year": "2026/2027", "name": "...", "fheq_level": 2, "credits": 20}
POST /api/academic/modules/{id}/assessments  {"name": "Exam", "weight_pct": 60, "mark_pct": null}
POST /api/nutrition/log         {"date": "2026-09-23", "slot": "breakfast", "description": "..."}
POST /api/nutrition/supplements/log  {"date": "2026-09-23", "supplement_id": 1, "taken": true}
POST /api/competitors            {"name": "Alex"}
POST /api/competitors/{id}/activities  {"date": "2026-09-23", "sport": "run", "duration_min": 45}
```

## Training load, compliance, race prep & academic trajectory (Sep 2026 extension)

Four tabs: **Overview** (the original panels + the load-vs-deadlines "burnout
watch"), **Training** (fitness/fatigue/form, weekly volume by discipline,
session compliance, HRV/RHR trend, niggle log), **Race prep** (goal gap,
Oct 25 phase gate, threshold trends, equipment milestones), **Academic**
(weighted-average trajectory, deadlines, study hours, exam-prep coverage).

One-time setup after pulling this in (already done on this machine):

```
.venv\Scripts\python.exe -m alembic upgrade head       # adds the new tables
.venv\Scripts\python.exe -m app.seed extension         # modules, Oct 25 gate, milestones
# with the server running:
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/training/sync?full=true"   # full Strava history
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/garmin/backfill"           # 90d RHR + HM predictions + FTP
```

After that everything refreshes on its own: Strava every 6 min (also rebuilds
the daily-load table), Garmin hourly (also HM-prediction / FTP estimates),
Google Calendar plan every 30 min.

### Load formula (one method for every sport)

Per-session load = **Strava Relative Effort** (API field `suffer_score`), not
a hand-rolled TRIMP: Banister/Edwards TRIMP needs a confirmed max HR, and the
only candidates are Garmin's unconfirmed 205 or 220-age. Relative Effort is
Strava's own HR-zone-weighted score, present on 131/134 activities; the other
3 use `duration × your own median effort-per-minute for that sport` and are
counted as estimated in the API. CTL = 42-day, ATL = 7-day EWMA of daily load,
TSB = yesterday's CTL − ATL, computed on read from `daily_training_loads`.
Limitation: all sports share one set of HR zones, and swim HR is wrist-in-water.

### How the plan is read from Google Calendar

Google expands recurring events itself (`singleEvents=true`), so no RRULE
parsing here. Only the title's emoji / bracket tag is read, never the
description: 🏊/🌊 swim, 🚴 bike, 🏃 run, 💪 strength (Upper A / Upper B /
Mobility split from the title), 🔗 brick, `🏁 PHASE N` phase starts (⚠️ TAPER
= Phase 5), 🏆 race day; `[LEC] [DEEP] [ASSIGN] [RECALL] [CONSOL] [REVIEW]
[EXAM] [PP]` = study blocks. Untagged events (the summer "Gym"/"htz" blocks)
are ignored. Compliance matching rules are in `app/services/compliance.py`.

### Still needs your input (flagged in the UI, not guessed)

- **Module FHEQ level + credits** for all four seeded modules — they're
  excluded from the weighted average until set (Academic tab → inline form).
- **"Test Module"** (L2, 20 credits, no assessments) is left over from setup
  testing — delete it if it isn't real.
- **TT frame purchase date** — your Phase 1 notes say "buy by Jan 2027", but
  you've also said the bike arrives Nov 2026. TT bike fit has no date either.
- **Deadlines / exam dates** — manual entry; the calendar has none.
- **Threshold tests** — no CSS, LTHR or threshold pace logged yet. The bike
  goal-gap leg currently runs on Garmin's profile FTP (172 W, May 2026,
  unconfirmed — no power meter), the run leg on Garmin's HM prediction.

## Frontend

Node isn't on PATH via the standard installer on this machine (the MSI install
needs an admin prompt this session couldn't answer); a portable Node 22 was
extracted to `%LOCALAPPDATA%\NodePortable\node-v22.14.0-win-x64` and added to
your user PATH. Open a new terminal for it to take effect, then:

```
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to :8000
npm run build    # typecheck + production build
```

## Still needs your input (not fabricated, flagged instead)

- **Supplement doses**: collagen + vitamin C and the electrolyte mix are
  seeded with `dose: null` (`needs_dose: true` in the API/UI) — training
  notes never gave exact amounts. Ashwagandha isn't seeded at all yet — same
  reason, plus it wasn't in scope of what was already established.
- **Academic modules**: none seeded — need FHEQ level, credit value, and
  assessment weighting per module from you.
- **Google Calendar / Garmin credentials**: walkthroughs above — these are
  yours to complete, I can't do the browser-consent or account-login steps
  for you.

## Other notes

- **Classification math**: Sheffield's published weighted-mean method
  (Level 1 excluded, Level 3 credits double-weighted vs. Level 2, First
  threshold 70%) but *not* the secondary grade-distribution check — see the
  `methodology_note` in the API response and the caveat text under the panel.
- **Sport normalization**: `Activity.sport` collapses Strava's `sport_type`
  (`Run`, `Ride`, `VirtualRide`, `Swim`, `WeightTraining`, ...) into
  `run`/`bike`/`swim`/`gym`/`walk`/`other`. Indoor vs. outdoor is tracked
  separately via `is_indoor` (Strava's `trainer` flag), so an indoor trainer
  ride still counts as `bike` in the weekly rollup.
- **Competitor tracking is manual entry only** — Strava doesn't expose other
  athletes' activities to third-party apps (locked down in 2020), and
  scraping the authenticated `strava.com/dashboard` feed to work around that
  was ruled out on purpose.
#   I R O N M A N - U n i - D a s h b o a r d  
 