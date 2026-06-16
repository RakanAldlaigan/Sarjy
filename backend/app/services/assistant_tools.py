from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from google.genai import types

from app.prompts import calendar as calendar_prompts
from app.services import calendar_service, preferences_service, reminder_service

# Window for a title-only resolution ("the dentist thing") when no date is given,
# and the cap on how many candidates to read back when a reference is ambiguous.
RESOLUTION_WINDOW = timedelta(days=14)
MAX_CANDIDATES = 5


@dataclass
class ToolExecution:
    result: dict
    pending_action: dict | None = None
    clear_pending: bool = False
    ui_confirmation: dict | None = None


def get_effective_timezone(user_id: str, browser_timezone: str | None) -> str:
    if browser_timezone:
        preferences_service.set_user_timezone(user_id, browser_timezone)
        return browser_timezone

    stored = preferences_service.get_user_timezone(user_id)
    if stored:
        return stored

    try:
        primary_tz = calendar_service.get_primary_calendar_timezone(user_id)
    except (calendar_service.CalendarNotConnectedError, calendar_service.CalendarAPIError):
        primary_tz = None

    timezone_name = primary_tz or "UTC"
    preferences_service.set_user_timezone(user_id, timezone_name)
    return timezone_name


def get_available_tools(pending_action: dict | None) -> list[types.Tool]:
    declarations = list(calendar_prompts.BASE_FUNCTION_DECLARATIONS)
    if pending_action and not pending_action.get("requires_ui_confirmation"):
        declarations = declarations + [
            calendar_prompts.CONFIRM_PENDING_ACTION,
            calendar_prompts.CANCEL_PENDING_ACTION,
        ]
    return [types.Tool(function_declarations=declarations)]


def execute_tool(tool_name: str, args: dict, user_id: str, timezone_name: str, pending_action: dict | None) -> ToolExecution:
    if tool_name == "get_calendar_events":
        return _handle_get_events(user_id, args, timezone_name)
    if tool_name == "create_calendar_event":
        return _handle_create_event(user_id, args, timezone_name)
    if tool_name == "update_calendar_event":
        return _handle_update_event(user_id, args, timezone_name)
    if tool_name == "delete_calendar_event":
        return _handle_delete_event(user_id, args, timezone_name)
    if tool_name == "create_reminder":
        return _handle_create_reminder(user_id, args, timezone_name)
    if tool_name == "list_reminders":
        return _handle_list_reminders(user_id, args, timezone_name)
    if tool_name == "update_reminder":
        return _handle_update_reminder(user_id, args, timezone_name)
    if tool_name == "delete_reminder":
        return _handle_delete_reminder(user_id, args, timezone_name)
    if tool_name == "confirm_pending_action":
        return _handle_confirm(user_id, pending_action)
    if tool_name == "cancel_pending_action":
        return _handle_cancel(pending_action)
    return ToolExecution(result={"status": "error", "message": f"Unknown tool: {tool_name}"})


def execute_pending_action(user_id: str, pending_action: dict) -> dict:
    """Executes a fully-resolved pending action against Google Calendar. Used by both
    confirm_pending_action (voice flow) and the UI confirmation card endpoint."""
    action_type = pending_action["action_type"]
    params = pending_action["params"]

    try:
        if action_type == "create_calendar_event":
            event = calendar_service.create_event(
                user_id,
                summary=params["summary"],
                start=datetime.fromisoformat(params["start"]),
                end=datetime.fromisoformat(params["end"]),
                timezone_name=params["timezone_name"],
                description=params.get("description"),
                reminder_minutes_before=params.get("reminder_minutes_before"),
            )
            return {"status": "success", "event": event}

        if action_type == "update_calendar_event":
            event = calendar_service.update_event(
                user_id,
                event_id=params["event_id"],
                timezone_name=params["timezone_name"],
                summary=params.get("new_summary"),
                description=params.get("new_description"),
                start=datetime.fromisoformat(params["new_start"]) if params.get("new_start") else None,
                end=datetime.fromisoformat(params["new_end"]) if params.get("new_end") else None,
            )
            return {"status": "success", "event": event}

        if action_type == "delete_calendar_event":
            calendar_service.delete_event(user_id, event_id=params["event_id"])
            return {"status": "success"}

        if action_type == "create_reminder":
            reminder = reminder_service.create_reminder(
                user_id,
                text=params["text"],
                remind_at=datetime.fromisoformat(params["remind_at"]),
                timezone_name=params["timezone_name"],
            )
            return {"status": "success", "reminder": reminder}

        if action_type == "update_reminder":
            reminder = reminder_service.update_reminder(
                user_id,
                reminder_id=params["reminder_id"],
                timezone_name=params["timezone_name"],
                text=params.get("new_text"),
                remind_at=datetime.fromisoformat(params["new_remind_at"]) if params.get("new_remind_at") else None,
            )
            return {"status": "success", "reminder": reminder}

        if action_type == "delete_reminder":
            reminder_service.delete_reminder(user_id, reminder_id=params["reminder_id"])
            return {"status": "success"}

        return {"status": "error", "message": f"Unknown action type: {action_type}"}

    except calendar_service.CalendarNotConnectedError:
        return {"status": "not_connected"}
    except calendar_service.CalendarAPIError as e:
        return {"status": "error", "message": str(e)}


def cancel_action() -> dict:
    return {"status": "cancelled"}


def describe_execution_result(result: dict, pending_action: dict) -> str:
    """Deterministic spoken outcome for the UI confirmation card flow (no LLM round-trip)."""
    action_type = pending_action["action_type"]
    status = result["status"]

    if status == "success":
        if action_type == "create_calendar_event":
            return f'Done — I\'ve added "{result["event"]["summary"]}" to your calendar.'
        if action_type == "update_calendar_event":
            return f'Done — I\'ve updated "{result["event"]["summary"]}".'
        if action_type == "delete_calendar_event":
            return "Done — that event has been deleted."
        if action_type == "create_reminder":
            return f'Done — I\'ll remind you "{result["reminder"]["description"]}".'
        if action_type == "update_reminder":
            return "Done — I've updated that reminder."
        if action_type == "delete_reminder":
            return "Done — that reminder has been deleted."

    if status == "cancelled":
        return "Okay, I won't make that change."
    if status == "not_connected":
        return "I can't reach your Google Calendar right now — you may need to reconnect it."
    if status == "error":
        return "Sorry, something went wrong talking to Google Calendar, so I couldn't complete that. Please try again."

    return "Something unexpected happened, so I didn't make that change."


# --- tool handlers -----------------------------------------------------------


def _handle_get_events(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    time_min = _parse_optional_dt(args.get("time_min"), timezone_name) or datetime.now(timezone.utc)
    time_max = _parse_optional_dt(args.get("time_max"), timezone_name)
    query = args.get("query") or None

    try:
        events = calendar_service.find_events(user_id, query=query, time_min=time_min, time_max=time_max, max_results=10)
    except calendar_service.CalendarNotConnectedError:
        return ToolExecution(result={"status": "not_connected"})
    except calendar_service.CalendarAPIError as e:
        return ToolExecution(result={"status": "error", "message": str(e)})

    return ToolExecution(result={"status": "ok", "events": _summarize_events(events)})


def _handle_create_event(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    summary = args.get("summary")
    start = _parse_optional_dt(args.get("start"), timezone_name)
    end = _parse_optional_dt(args.get("end"), timezone_name)
    description = args.get("description")

    missing = [name for name, value in [("summary", summary), ("start", start), ("end", end)] if not value]
    if missing:
        return ToolExecution(result={"status": "missing_info", "missing": missing})

    # Duplicate check runs on the required slots, before the reminder question. Once the
    # user has answered that question (reminder_minutes_before present) we've moved past
    # the duplicate step, so don't re-surface it — otherwise "keep the name" would loop.
    if "reminder_minutes_before" not in args:
        duplicate_warning = _format_duplicate_warning(_check_duplicates(user_id, summary, start, end), summary)
        if duplicate_warning:
            return ToolExecution(result={"status": "duplicate_warning", "duplicate_warning": duplicate_warning})
        return ToolExecution(result={"status": "reminder_required"})

    reminder_minutes_before = args.get("reminder_minutes_before")

    try:
        overlapping, adjacent = calendar_service.detect_conflicts(user_id, start, end)
    except calendar_service.CalendarNotConnectedError:
        return ToolExecution(result={"status": "not_connected"})
    except calendar_service.CalendarAPIError as e:
        return ToolExecution(result={"status": "error", "message": str(e)})

    conflict_warning = _format_conflict_warning(overlapping, adjacent)

    summary_text = _describe_create_event(summary, start, end, timezone_name, reminder_minutes_before)
    if conflict_warning:
        summary_text += f" {conflict_warning}"

    pending_action = {
        "action_type": "create_calendar_event",
        "params": {
            "summary": summary,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "description": description,
            "reminder_minutes_before": reminder_minutes_before,
            "timezone_name": timezone_name,
        },
        "requires_ui_confirmation": True,
        "summary": summary_text,
        "conflict_warning": conflict_warning,
    }

    return ToolExecution(
        result={
            "status": "confirmation_required",
            "summary": summary_text,
            "conflict_warning": conflict_warning,
            "requires_ui_confirmation": True,
        },
        pending_action=pending_action,
        ui_confirmation={
            "action_type": "create_calendar_event",
            "summary": summary_text,
            "conflict_warning": conflict_warning,
        },
    )


def _handle_update_event(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    try:
        status, matches = _resolve_target(_event_search(user_id), args.get("title"), args.get("date"), timezone_name)
    except calendar_service.CalendarNotConnectedError:
        return ToolExecution(result={"status": "not_connected"})
    except calendar_service.CalendarAPIError as e:
        return ToolExecution(result={"status": "error", "message": str(e)})

    if status == "missing_slots":
        return ToolExecution(result={"status": "missing_slots"})
    if status == "not_found":
        return ToolExecution(result={"status": "not_found"})
    if status == "ambiguous":
        return ToolExecution(result={"status": "ambiguous", "candidates": _summarize_events(matches)})

    event = matches[0]

    new_summary = args.get("new_summary")
    new_start = _parse_optional_dt(args.get("new_start"), timezone_name)
    new_end = _parse_optional_dt(args.get("new_end"), timezone_name)
    new_description = args.get("new_description")

    if not any([new_summary, new_start, new_end, new_description is not None]):
        return ToolExecution(result={"status": "missing_info", "missing": ["at least one field to change"]})

    conflict_warning = None
    if new_start and new_end:
        try:
            overlapping, adjacent = calendar_service.detect_conflicts(
                user_id, new_start, new_end, exclude_event_id=event["id"]
            )
        except calendar_service.CalendarAPIError as e:
            return ToolExecution(result={"status": "error", "message": str(e)})
        conflict_warning = _format_conflict_warning(overlapping, adjacent)

    summary_text = _describe_update_event(event, new_summary, new_start, new_end, new_description, timezone_name)
    if conflict_warning:
        summary_text += f" {conflict_warning}"

    pending_action = {
        "action_type": "update_calendar_event",
        "params": {
            "event_id": event["id"],
            "new_summary": new_summary,
            "new_start": new_start.isoformat() if new_start else None,
            "new_end": new_end.isoformat() if new_end else None,
            "new_description": new_description,
            "timezone_name": timezone_name,
        },
        "requires_ui_confirmation": True,
        "summary": summary_text,
        "conflict_warning": conflict_warning,
    }

    return ToolExecution(
        result={
            "status": "confirmation_required",
            "summary": summary_text,
            "conflict_warning": conflict_warning,
            "requires_ui_confirmation": True,
        },
        pending_action=pending_action,
        ui_confirmation={
            "action_type": "update_calendar_event",
            "summary": summary_text,
            "conflict_warning": conflict_warning,
        },
    )


def _handle_delete_event(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    try:
        status, matches = _resolve_target(_event_search(user_id), args.get("title"), args.get("date"), timezone_name)
    except calendar_service.CalendarNotConnectedError:
        return ToolExecution(result={"status": "not_connected"})
    except calendar_service.CalendarAPIError as e:
        return ToolExecution(result={"status": "error", "message": str(e)})

    if status == "missing_slots":
        return ToolExecution(result={"status": "missing_slots"})
    if status == "not_found":
        return ToolExecution(result={"status": "not_found"})
    if status == "ambiguous":
        return ToolExecution(result={"status": "ambiguous", "candidates": _summarize_events(matches)})

    event = matches[0]
    summary_text = _describe_delete_event(event, timezone_name)

    pending_action = {
        "action_type": "delete_calendar_event",
        "params": {"event_id": event["id"]},
        "requires_ui_confirmation": True,
        "summary": summary_text,
        "conflict_warning": None,
    }

    return ToolExecution(
        result={"status": "confirmation_required", "summary": summary_text, "requires_ui_confirmation": True},
        pending_action=pending_action,
        ui_confirmation={"action_type": "delete_calendar_event", "summary": summary_text, "conflict_warning": None},
    )


def _handle_create_reminder(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    text = (args.get("text") or "").strip()
    remind_at = _parse_optional_dt(args.get("remind_at"), timezone_name)

    missing = [name for name, value in [("text", text), ("remind_at", remind_at)] if not value]
    if missing:
        return ToolExecution(result={"status": "datetime_required" if missing == ["remind_at"] else "missing_info", "missing": missing})

    duplicate_warning = _format_duplicate_reminder_warning(reminder_service.check_duplicate_reminders(user_id, text), text)
    summary_text = _describe_create_reminder(text, remind_at, timezone_name)

    pending_action = {
        "action_type": "create_reminder",
        "params": {"text": text, "remind_at": remind_at.isoformat(), "timezone_name": timezone_name},
        "requires_ui_confirmation": False,
        "summary": summary_text,
        "conflict_warning": None,
    }

    return ToolExecution(
        result={"status": "confirmation_required", "summary": summary_text, "duplicate_warning": duplicate_warning},
        pending_action=pending_action,
    )


def _handle_list_reminders(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    time_min = _parse_optional_dt(args.get("time_min"), timezone_name)
    time_max = _parse_optional_dt(args.get("time_max"), timezone_name)

    reminders = reminder_service.list_reminders(user_id, time_min=time_min, time_max=time_max)

    return ToolExecution(result={
        "status": "ok",
        "reminders": _summarize_reminders(reminders),
        "truncated": len(reminders) == reminder_service.LIST_MAX_RESULTS,
    })


def _handle_update_reminder(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    status, matches = _resolve_target(_reminder_search(user_id), args.get("text"), args.get("date"), timezone_name)

    if status == "missing_slots":
        return ToolExecution(result={"status": "missing_slots"})
    if status == "not_found":
        return ToolExecution(result={"status": "not_found"})
    if status == "ambiguous":
        return ToolExecution(result={"status": "ambiguous", "candidates": _summarize_reminders(matches)})

    reminder = matches[0]

    new_text = args.get("new_text")
    new_remind_at = _parse_optional_dt(args.get("new_remind_at"), timezone_name)

    if not any([new_text, new_remind_at]):
        return ToolExecution(result={"status": "missing_info", "missing": ["at least one field to change"]})

    summary_text = _describe_update_reminder(reminder, new_text, new_remind_at, timezone_name)

    pending_action = {
        "action_type": "update_reminder",
        "params": {
            "reminder_id": reminder["id"],
            "new_text": new_text,
            "new_remind_at": new_remind_at.isoformat() if new_remind_at else None,
            "timezone_name": timezone_name,
        },
        "requires_ui_confirmation": False,
        "summary": summary_text,
        "conflict_warning": None,
    }

    return ToolExecution(
        result={"status": "confirmation_required", "summary": summary_text},
        pending_action=pending_action,
    )


def _handle_delete_reminder(user_id: str, args: dict, timezone_name: str) -> ToolExecution:
    status, matches = _resolve_target(_reminder_search(user_id), args.get("text"), args.get("date"), timezone_name)

    if status == "missing_slots":
        return ToolExecution(result={"status": "missing_slots"})
    if status == "not_found":
        return ToolExecution(result={"status": "not_found"})
    if status == "ambiguous":
        return ToolExecution(result={"status": "ambiguous", "candidates": _summarize_reminders(matches)})

    reminder = matches[0]
    summary_text = _describe_delete_reminder(reminder, timezone_name)

    pending_action = {
        "action_type": "delete_reminder",
        "params": {"reminder_id": reminder["id"]},
        "requires_ui_confirmation": False,
        "summary": summary_text,
        "conflict_warning": None,
    }

    return ToolExecution(
        result={"status": "confirmation_required", "summary": summary_text},
        pending_action=pending_action,
    )


def _handle_confirm(user_id: str, pending_action: dict | None) -> ToolExecution:
    if pending_action is None:
        return ToolExecution(result={"status": "no_pending_action"})
    result = execute_pending_action(user_id, pending_action)
    return ToolExecution(result=result, clear_pending=True)


def _handle_cancel(pending_action: dict | None) -> ToolExecution:
    if pending_action is None:
        return ToolExecution(result={"status": "no_pending_action"})
    return ToolExecution(result=cancel_action(), clear_pending=True)


# --- resolution & formatting helpers -----------------------------------------


def _parse_optional_dt(value: str | None, timezone_name: str) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
    return dt


def _day_window(date_value: str, timezone_name: str) -> tuple[datetime, datetime]:
    """[start, end) covering the given calendar date in the user's timezone."""
    day = datetime.fromisoformat(date_value).date()
    start = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(timezone_name))
    return start, start + timedelta(days=1)


def _event_search(user_id: str):
    def search(query: str | None, time_min: datetime, time_max: datetime) -> list[dict]:
        return calendar_service.find_events(
            user_id, query=query, time_min=time_min, time_max=time_max, max_results=25
        )

    return search


def _reminder_search(user_id: str):
    def search(query: str | None, time_min: datetime, time_max: datetime) -> list[dict]:
        return reminder_service.find_reminders(user_id, reference=query, time_min=time_min, time_max=time_max)

    return search


def _resolve_target(search_fn, title: str | None, date: str | None, timezone_name: str) -> tuple[str, list[dict]]:
    """Field-agnostic slot resolution shared by events and reminders.

    `search_fn(query, time_min, time_max) -> list[dict]` abstracts the field difference
    (event title vs. reminder text). Slots: `title` (the name/topic) and `date` (a calendar
    day). Returns (status, matches) where status is one of: "missing_slots", "not_found",
    "ambiguous", "resolved".
    """
    title = (title or "").strip() or None
    date = (date or "").strip() or None

    if not title and not date:
        return "missing_slots", []

    if date:
        time_min, time_max = _day_window(date, timezone_name)
    else:
        now = datetime.now(timezone.utc)
        time_min, time_max = now, now + RESOLUTION_WINDOW

    matches = search_fn(title, time_min, time_max)

    if not matches:
        return "not_found", []

    # A title with a single match is high-confidence. Date-only is a weak signal,
    # so always ask which one — even when only one event falls on that day.
    if title and len(matches) == 1:
        return "resolved", matches
    return "ambiguous", matches[:MAX_CANDIDATES]


def _summarize_reminders(reminders: list[dict]) -> list[dict]:
    return [{"id": r["id"], "text": r["description"], "remind_at": r["remind_at"]} for r in reminders]


def _format_duplicate_reminder_warning(duplicates: list[dict], text: str) -> str | None:
    if not duplicates:
        return None
    if len(duplicates) == 1:
        return f'You already have a reminder that says "{text}".'
    return f'You already have several reminders that say "{text}".'


def _describe_create_reminder(text: str, remind_at: datetime, timezone_name: str) -> str:
    return f'Remind you "{text}" on {_format_dt(remind_at, timezone_name)}.'


def _describe_update_reminder(reminder: dict, new_text: str | None, new_remind_at: datetime | None, timezone_name: str) -> str:
    current_remind_at = calendar_service.parse_event_datetime(reminder["remind_at"])
    changes = []
    if new_text:
        changes.append(f'change it to say "{new_text}"')
    if new_remind_at:
        changes.append(f"move it to {_format_dt(new_remind_at, timezone_name)}")

    return f'Update the reminder "{reminder["description"]}" ({_format_dt(current_remind_at, timezone_name)}): ' + ", ".join(changes) + "."


def _describe_delete_reminder(reminder: dict, timezone_name: str) -> str:
    remind_at = calendar_service.parse_event_datetime(reminder["remind_at"])
    return f'Delete the reminder "{reminder["description"]}" ({_format_dt(remind_at, timezone_name)}).'


def _check_duplicates(user_id: str, summary: str, start: datetime, end: datetime) -> list[dict]:
    try:
        return calendar_service.find_events(
            user_id, query=summary, time_min=start - timedelta(days=1), time_max=end + timedelta(days=1), max_results=10
        )
    except (calendar_service.CalendarNotConnectedError, calendar_service.CalendarAPIError):
        return []


def _summarize_events(events: list[dict]) -> list[dict]:
    return [{"id": e["id"], "summary": e["summary"], "start": e["start"], "end": e["end"]} for e in events]


def _format_dt(dt: datetime, timezone_name: str) -> str:
    local = dt.astimezone(ZoneInfo(timezone_name))
    return local.strftime("%A, %B %-d at %-I:%M %p")


def _format_conflict_warning(overlapping: list[dict], adjacent: list[dict]) -> str | None:
    if overlapping:
        names = ", ".join(f'"{e["summary"]}"' for e in overlapping)
        return f"Heads up — this overlaps with {names}."
    if adjacent:
        names = ", ".join(f'"{e["summary"]}"' for e in adjacent)
        return f"Note — this is back-to-back with {names}."
    return None


def _format_duplicate_warning(duplicates: list[dict], summary: str) -> str | None:
    # Only an exact (case-insensitive) title match counts as "the same name".
    matches = [e for e in duplicates if e["summary"].strip().lower() == summary.strip().lower()]
    if not matches:
        return None
    if len(matches) == 1:
        return f'You already have an event called "{summary}" around that time.'
    return f'You already have several events called "{summary}" around that time.'


def _describe_create_event(summary: str, start: datetime, end: datetime, timezone_name: str, reminder_minutes_before) -> str:
    text = f'Create "{summary}" from {_format_dt(start, timezone_name)} to {_format_dt(end, timezone_name)}.'
    if reminder_minutes_before:
        text += f" With a reminder {reminder_minutes_before} minutes before."
    else:
        text += " With no reminder."
    return text


def _describe_update_event(event, new_summary, new_start, new_end, new_description, timezone_name: str) -> str:
    current_start = calendar_service.parse_event_datetime(event["start"])
    changes = []
    if new_summary:
        changes.append(f'rename it to "{new_summary}"')
    if new_start and new_end:
        changes.append(f"move it to {_format_dt(new_start, timezone_name)} - {_format_dt(new_end, timezone_name)}")
    elif new_start:
        changes.append(f"change the start time to {_format_dt(new_start, timezone_name)}")
    elif new_end:
        changes.append(f"change the end time to {_format_dt(new_end, timezone_name)}")
    if new_description is not None:
        changes.append("update the description")

    return f'Update "{event["summary"]}" ({_format_dt(current_start, timezone_name)}): ' + ", ".join(changes) + "."


def _describe_delete_event(event, timezone_name: str) -> str:
    event_start = calendar_service.parse_event_datetime(event["start"])
    return f'Delete "{event["summary"]}" on {_format_dt(event_start, timezone_name)}.'
