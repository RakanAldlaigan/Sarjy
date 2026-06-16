from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.services import google_auth_service

PRIMARY_CALENDAR_ID = "primary"
REMINDERS_CALENDAR_NAME = "Sarjy Reminders"
CREATED_BY_KEY = "createdBy"
CREATED_BY_VALUE = "sarjy"

# Window used to detect back-to-back ("adjacent") events around a candidate
# time range, since Google's timeMin/timeMax query excludes events that end
# exactly at timeMin.
ADJACENCY_WINDOW = timedelta(minutes=1)


class CalendarNotConnectedError(Exception):
    """User hasn't granted (or has since revoked) Calendar access."""


class CalendarAPIError(Exception):
    """A Google Calendar API call failed."""


def _get_service(user_id: str):
    credentials = google_auth_service.get_credentials(user_id)
    if credentials is None:
        raise CalendarNotConnectedError(user_id)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def parse_event_datetime(value: str) -> datetime:
    """Parses a start/end value from an event dict (date or dateTime) into an aware datetime."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _event_to_dict(event: dict) -> dict:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event["id"],
        "summary": event.get("summary", "(no title)"),
        "description": event.get("description", ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "all_day": "date" in start,
        "created_by_sarjy": (
            event.get("extendedProperties", {}).get("private", {}).get(CREATED_BY_KEY) == CREATED_BY_VALUE
        ),
    }


def find_events(
    user_id: str,
    query: str | None = None,
    time_min: datetime | None = None,
    time_max: datetime | None = None,
    max_results: int = 10,
    calendar_id: str = PRIMARY_CALENDAR_ID,
) -> list[dict]:
    service = _get_service(user_id)

    params: dict = {
        "calendarId": calendar_id,
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": max_results,
    }
    if query:
        params["q"] = query
    if time_min:
        params["timeMin"] = time_min.isoformat()
    if time_max:
        params["timeMax"] = time_max.isoformat()

    try:
        result = service.events().list(**params).execute()
    except HttpError as e:
        raise CalendarAPIError(str(e)) from e

    return [_event_to_dict(e) for e in result.get("items", [])]


def detect_conflicts(
    user_id: str, start: datetime, end: datetime, exclude_event_id: str | None = None
) -> tuple[list[dict], list[dict]]:
    """Returns (overlapping, adjacent) events on the primary calendar near [start, end)."""
    events = find_events(
        user_id,
        time_min=start - ADJACENCY_WINDOW,
        time_max=end + ADJACENCY_WINDOW,
        max_results=25,
    )

    overlapping = []
    adjacent = []
    for event in events:
        if event["id"] == exclude_event_id:
            continue
        event_start = parse_event_datetime(event["start"])
        event_end = parse_event_datetime(event["end"])
        if event_start < end and event_end > start:
            overlapping.append(event)
        elif event_end == start or event_start == end:
            adjacent.append(event)

    return overlapping, adjacent


def create_event(
    user_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    timezone_name: str,
    description: str | None = None,
    reminder_minutes_before: int | None = None,
    calendar_id: str = PRIMARY_CALENDAR_ID,
    tag_as_sarjy: bool = True,
) -> dict:
    service = _get_service(user_id)

    body: dict = {
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
    }
    if description:
        body["description"] = description
    if tag_as_sarjy:
        body["extendedProperties"] = {"private": {CREATED_BY_KEY: CREATED_BY_VALUE}}
    if reminder_minutes_before is not None:
        body["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes_before}],
        }
    else:
        body["reminders"] = {"useDefault": True}

    try:
        event = service.events().insert(calendarId=calendar_id, body=body).execute()
    except HttpError as e:
        raise CalendarAPIError(str(e)) from e

    return _event_to_dict(event)


def update_event(
    user_id: str,
    event_id: str,
    timezone_name: str,
    summary: str | None = None,
    description: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    calendar_id: str = PRIMARY_CALENDAR_ID,
) -> dict:
    service = _get_service(user_id)

    body: dict = {}
    if summary is not None:
        body["summary"] = summary
    if description is not None:
        body["description"] = description
    if start is not None:
        body["start"] = {"dateTime": start.isoformat(), "timeZone": timezone_name}
    if end is not None:
        body["end"] = {"dateTime": end.isoformat(), "timeZone": timezone_name}

    try:
        event = service.events().patch(calendarId=calendar_id, eventId=event_id, body=body).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise CalendarAPIError("Event not found") from e
        raise CalendarAPIError(str(e)) from e

    return _event_to_dict(event)


def delete_event(user_id: str, event_id: str, calendar_id: str = PRIMARY_CALENDAR_ID) -> None:
    service = _get_service(user_id)
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status == 404:
            return
        raise CalendarAPIError(str(e)) from e


def get_primary_calendar_timezone(user_id: str) -> str | None:
    service = _get_service(user_id)
    try:
        calendar = service.calendars().get(calendarId=PRIMARY_CALENDAR_ID).execute()
    except HttpError as e:
        raise CalendarAPIError(str(e)) from e
    return calendar.get("timeZone")


def get_or_create_reminders_calendar(user_id: str) -> str:
    service = _get_service(user_id)
    calendar_id = google_auth_service.get_reminders_calendar_id(user_id)

    if calendar_id:
        try:
            service.calendars().get(calendarId=calendar_id).execute()
            return calendar_id
        except HttpError as e:
            if e.resp.status != 404:
                raise CalendarAPIError(str(e)) from e
            # User deleted the calendar — fall through and recreate it.

    try:
        created = service.calendars().insert(body={"summary": REMINDERS_CALENDAR_NAME}).execute()
    except HttpError as e:
        raise CalendarAPIError(str(e)) from e

    calendar_id = created["id"]
    google_auth_service.save_reminders_calendar_id(user_id, calendar_id)
    return calendar_id
