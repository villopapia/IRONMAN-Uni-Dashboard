"""One-time interactive Garmin Connect login (unofficial API - garminconnect -
using your own account, not an official developer API since Garmin doesn't
approve those for personal projects).

Run this yourself, in your own terminal, NOT via an automated/background
shell: `python -m app.services.garmin_login`. If your account has MFA
enabled, it will prompt you for the current code right here - that's
expected and only needed the first time (or whenever the cached session
expires). Garmin.login(tokenstore) tries the cached session first and only
falls back to email/password if that fails, auto-persisting the refreshed
session back to the same path - so this same call is also what a re-run
after expiry should use.

Needs GARMIN_EMAIL / GARMIN_PASSWORD in backend/.env.
"""

from pathlib import Path

from garminconnect import Garmin

from ..config import settings

TOKEN_STORE = str(Path(__file__).resolve().parent.parent.parent / ".garmin_tokens")


def _prompt_mfa() -> str:
    return input("Enter Garmin MFA code: ")


def login() -> None:
    if not settings.garmin_email or not settings.garmin_password:
        raise RuntimeError(
            "GARMIN_EMAIL / GARMIN_PASSWORD are not set - see backend/.env.example."
        )

    garmin = Garmin(
        email=settings.garmin_email,
        password=settings.garmin_password,
        prompt_mfa=_prompt_mfa,
    )
    garmin.login(TOKEN_STORE)
    print(f"Logged in. Session cached to {TOKEN_STORE}")


if __name__ == "__main__":
    login()
