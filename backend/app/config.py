from datetime import date

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dashboard.db"
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    garmin_email: str = ""
    garmin_password: str = ""

    intervals_api_key: str = ""
    intervals_athlete_id: str = ""
    # Load / CTL / ATL source: the intervals.icu cache (true) or Strava Relative
    # Effort through training_load.compute_pmc (false).
    use_icu_pmc: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Season plan, served to the frontend by GET /api/season.
RACE = {"name": "IRONMAN 70.3 Jönköping", "date": date(2027, 7, 11)}
GATES = [
    {"name": "HM time trial", "date": date(2026, 10, 25)},
    {"name": "Sheffield Half", "date": date(2027, 4, 4)},
]
PHASES = [  # more phases added later
    {"name": "Phase 1 Base", "start": date(2026, 9, 30), "end": date(2026, 10, 25)},
]
SEASON_START = date(2026, 9, 1)  # left edge of the "Season" chart range
