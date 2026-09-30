import os
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Path to the downloaded service account JSON key, placed at the backend project root
CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "google-calendar-credentials.json",
)

# The calendar to write events into — this must be a calendar the service
# account has been explicitly shared on with "Make changes to events" access.
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "gfs.amine@gmail.com")

DEFAULT_DURATION_MINUTES = 30
TIMEZONE = "Africa/Tunis"


def _get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def _has_conflict(start_dt: datetime, end_dt: datetime) -> bool:
    """Checks whether the given time window already has something scheduled
    on the target calendar, using Google's freebusy.query endpoint — this
    only asks 'is this window busy or free', without needing to fetch and
    parse full event details."""
    try:
        service = _get_calendar_service()
        body = {
            "timeMin": start_dt.isoformat(),
            "timeMax": end_dt.isoformat(),
            "timeZone": TIMEZONE,
            "items": [{"id": CALENDAR_ID}],
        }
        result = service.freebusy().query(body=body).execute()
        busy_periods = result["calendars"][CALENDAR_ID]["busy"]
        return len(busy_periods) > 0
    except Exception as e:
        # If the conflict check itself fails (network hiccup, API issue),
        # fail open rather than blocking event creation entirely — a missed
        # conflict check is a smaller problem than silently losing a task.
        print(f"[calendar] Conflict check failed, proceeding without it: {e}")
        return False


def create_calendar_event(text: str, scheduled_at: str) -> dict | None:
    """Creates a Google Calendar event for a task with a known date/time.
    Returns the created event dict on success, or None if creation failed
    or was skipped (failures/skips are swallowed here so a calendar issue
    never breaks the main note-processing flow)."""
    try:
        start_dt = datetime.fromisoformat(scheduled_at)
    except (ValueError, TypeError):
        return None

    # Defensive guard: even with prompt-level instructions to always resolve
    # forward, an LLM can occasionally misresolve a relative date into the
    # past. Skip creating an event rather than silently scheduling something
    # that already happened.
    if start_dt < datetime.now():
        print(f"[calendar] Skipped '{text}': resolved date {start_dt} is in the past.")
        return None

    end_dt = start_dt + timedelta(minutes=DEFAULT_DURATION_MINUTES)

    if _has_conflict(start_dt, end_dt):
        print(f"[calendar] Skipped '{text}': conflicts with an existing event at {start_dt}.")
        return None

    event_body = {
        "summary": text,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
    }

    try:
        service = _get_calendar_service()
        created = service.events().insert(
            calendarId=CALENDAR_ID, body=event_body
        ).execute()
        return created
    except Exception as e:
        print(f"[calendar] Failed to create event for '{text}': {e}")
        return None