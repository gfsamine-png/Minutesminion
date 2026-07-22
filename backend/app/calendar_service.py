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


def _get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def create_calendar_event(text: str, scheduled_at: str) -> dict | None:
    """Creates a Google Calendar event for a task with a known date/time.
    Returns the created event dict on success, or None if creation failed
    (failures are swallowed here so a calendar issue never breaks the
    main note-processing flow)."""
    try:
        start_dt = datetime.fromisoformat(scheduled_at)
    except (ValueError, TypeError):
        return None

    end_dt = start_dt + timedelta(minutes=DEFAULT_DURATION_MINUTES)

    event_body = {
        "summary": text,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Africa/Tunis"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Africa/Tunis"},
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
