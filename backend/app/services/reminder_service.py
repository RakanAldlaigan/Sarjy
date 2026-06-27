import re
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials

from app.services import calendar_service
from app.services.supabase_service import get_client

REMINDER_EVENT_DURATION = timedelta(minutes=30)

LIST_MAX_RESULTS = 20
FIND_MAX_RESULTS = 25


MIRROR_ATTEMPTS = 2


def _mirror_to_calendar(
    user_id: str,
    text: str,
    remind_at: datetime,
    timezone_name: str,
    credentials: Credentials | None = None,
) -> tuple[str | None, str | None]:
    """Creates the Google Calendar mirror for a reminder. Returns (google_event_id, calendar_warning).

    Retries once on a transient API error before giving up."""
    for attempt in range(MIRROR_ATTEMPTS):
        try:
            calendar_id = calendar_service.get_or_create_reminders_calendar(user_id, credentials=credentials)
            event = calendar_service.create_event(
                user_id,
                summary=text,
                start=remind_at,
                end=remind_at + REMINDER_EVENT_DURATION,
                timezone_name=timezone_name,
                reminder_minutes_before=0,
                tag_as_sarjy=True,
                calendar_id=calendar_id,
                credentials=credentials,
            )
            return event["id"], None
        except calendar_service.CalendarNotConnectedError:
            return None, "not_connected"
        except calendar_service.CalendarAPIError as e:
            if attempt + 1 == MIRROR_ATTEMPTS:
                return None, str(e)


def create_reminder(
    user_id: str,
    text: str,
    remind_at: datetime,
    timezone_name: str,
    credentials: Credentials | None = None,
) -> dict:
    google_event_id, calendar_warning = _mirror_to_calendar(
        user_id, text, remind_at, timezone_name, credentials=credentials
    )

    inserted = (
        get_client()
        .table("reminders")
        .insert({
            "user_id": user_id,
            "description": text,
            "remind_at": remind_at.isoformat(),
            "google_event_id": google_event_id,
        })
        .execute()
    )

    reminder = inserted.data[0]
    reminder["calendar_warning"] = calendar_warning
    return reminder


def _cleanup_expired(user_id: str) -> None:
    """Removes reminders whose time has passed from Supabase. The mirrored calendar event,
    if any, is left alone — it's harmless for it to remain on the user's calendar."""
    now = datetime.now(timezone.utc)
    get_client().table("reminders").delete().eq("user_id", user_id).lt("remind_at", now.isoformat()).execute()


def list_reminders(
    user_id: str, time_min: datetime | None = None, time_max: datetime | None = None, max_results: int = LIST_MAX_RESULTS
) -> list[dict]:
    _cleanup_expired(user_id)

    query = (
        get_client()
        .table("reminders")
        .select("id, description, remind_at")
        .eq("user_id", user_id)
    )
    if time_min:
        query = query.gte("remind_at", time_min.isoformat())
    if time_max:
        query = query.lte("remind_at", time_max.isoformat())

    return query.order("remind_at").limit(max_results).execute().data


def find_reminders(
    user_id: str,
    reference: str | None = None,
    time_min: datetime | None = None,
    time_max: datetime | None = None,
    max_results: int = FIND_MAX_RESULTS,
) -> list[dict]:
    _cleanup_expired(user_id)

    query = (
        get_client()
        .table("reminders")
        .select("id, description, remind_at, google_event_id")
        .eq("user_id", user_id)
    )
    if time_min:
        query = query.gte("remind_at", time_min.isoformat())
    if time_max:
        query = query.lte("remind_at", time_max.isoformat())

    words = [w for w in re.findall(r"\w+", reference) if len(w) > 2] if reference else []
    if words:
        query = query.or_(",".join(f"description.ilike.%{w}%" for w in words))

    return query.order("remind_at").limit(max_results).execute().data


def check_duplicate_reminders(user_id: str, text: str) -> list[dict]:
    return (
        get_client()
        .table("reminders")
        .select("id, description")
        .eq("user_id", user_id)
        .ilike("description", text.strip())
        .execute()
        .data
    )


def update_reminder(
    user_id: str,
    reminder_id: str,
    timezone_name: str,
    text: str | None = None,
    remind_at: datetime | None = None,
    credentials: Credentials | None = None,
) -> dict:
    updates: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if text is not None:
        updates["description"] = text
    if remind_at is not None:
        updates["remind_at"] = remind_at.isoformat()

    updated = (
        get_client()
        .table("reminders")
        .update(updates)
        .eq("id", reminder_id)
        .eq("user_id", user_id)
        .execute()
    )
    reminder = updated.data[0]

    calendar_warning = None
    google_event_id = reminder.get("google_event_id")
    if google_event_id and (text is not None or remind_at is not None):
        try:
            calendar_id = calendar_service.get_or_create_reminders_calendar(user_id, credentials=credentials)
            calendar_service.update_event(
                user_id,
                event_id=google_event_id,
                timezone_name=timezone_name,
                summary=text,
                start=remind_at,
                end=remind_at + REMINDER_EVENT_DURATION if remind_at else None,
                calendar_id=calendar_id,
                credentials=credentials,
            )
        except calendar_service.CalendarNotConnectedError:
            calendar_warning = "not_connected"
        except calendar_service.CalendarAPIError as e:
            calendar_warning = str(e)

    reminder["calendar_warning"] = calendar_warning
    return reminder


def delete_reminder(user_id: str, reminder_id: str, credentials: Credentials | None = None) -> dict | None:
    existing = (
        get_client()
        .table("reminders")
        .select("google_event_id")
        .eq("id", reminder_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        return None

    google_event_id = existing.data[0]["google_event_id"]

    get_client().table("reminders").delete().eq("id", reminder_id).eq("user_id", user_id).execute()

    if google_event_id:
        try:
            calendar_id = calendar_service.get_or_create_reminders_calendar(user_id, credentials=credentials)
            calendar_service.delete_event(
                user_id, event_id=google_event_id, calendar_id=calendar_id, credentials=credentials
            )
        except (calendar_service.CalendarNotConnectedError, calendar_service.CalendarAPIError):
            pass

    return {"id": reminder_id}
