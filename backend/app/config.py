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
