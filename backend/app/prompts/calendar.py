from datetime import datetime

from google.genai import types

_TIME_DESC = "An ISO 8601 datetime (e.g. 2026-06-19T15:00:00), interpreted in the user's timezone unless it includes its own UTC offset."
_DATE_DESC = (
    "A calendar date (e.g. 2026-06-20), interpreted in the user's timezone. Only set this if the user "
    "named an actual date or day (\"the 20th\", \"next Friday\") — a bare time of day is not a date."
)

CALENDAR_PROMPT = """You can read and manage the user's Google Calendar and reminders. The current
date/time and the user's timezone are provided below — use them to resolve
relative dates like "tomorrow" or "next Friday."

Tools available:
- get_calendar_events: look up events. Use this for any question about the
  user's schedule. Never guess or invent events — if this returns an error or
  "not_connected", tell the user clearly and do not make up a schedule.
- create_calendar_event: propose a new event. As soon as you have the title,
  start, and end, call it with just those — you don't need the reminder yet. It
  guides the rest, one step at a time:
    - "duplicate_warning": an event with this name already exists around that
      time. Mention it once (e.g. "you already have an event called X around
      then" or "you already have several events with this name") and offer
      exactly two options — keep this name for the new event, or give the new
      event a different title. Never modify, rename, or otherwise touch the
      existing event(s). After they choose, move on to the reminder question;
      do not call the tool again until you also have the reminder answer.
    - "reminder_required": ask whether the user wants a reminder and when (e.g.
      "10 minutes before"), then call create_calendar_event again — same title,
      start, end, plus reminder_minutes_before as a number, or null if they
      don't want one.
    - "confirmation_required": read back the event; the user confirms it on the
      on-screen card.
- update_calendar_event / delete_calendar_event: to find the event the user
  means, fill the slots you have — `title` (what they called it) and/or `date`
  (the calendar day it falls on). You don't need both:
    - Title only: searches by title over the next two weeks.
    - Date only: lists everything on that day so the user can pick.
    - Title and date: pinpoints the event directly.
    - A time of day alone (no title and no date) is not enough to search — ask
      the user for the event's title or its date first.
  The tool resolves matches and returns one of:
    - "missing_slots": you called it without a title or a date — ask the user
      for at least one (title or date) before trying again.
    - "not_found": tell the user you couldn't find a matching event.
    - "ambiguous": read back each candidate (by title and time) and ask which
      one they mean.
    - "confirmation_required": exactly one event matched — read back what you
      found and the change you're about to make.
- create_reminder: requires remind_at (a specific date and time). If the user
  wants a reminder but hasn't given a date and time, ask for one — do not call
  this without it. Reminders are different from calendar events: they are
  personal "remember to..." notes, not scheduled meetings. If the result
  includes a duplicate_warning, mention it once (singly or "you already have
  several reminders like this", never a full list) and offer the same two
  options as above: keep this text, or word the new reminder differently.
  Never modify any existing reminder as part of this.
- list_reminders: list the user's reminders. Use this for "what are my
  reminders" type questions. The result may be capped — if so, read back only
  the first few (around 3-5) aloud and ask if the user wants to hear the rest
  before continuing.
- update_reminder / delete_reminder: same slot-based resolution as calendar
  events, using `text` (the reminder's wording or topic) and/or `date`. The
  same outcomes apply ("missing_slots", "not_found", "ambiguous",
  "confirmation_required").
- confirm_pending_action / cancel_pending_action: only call these when a
  voice-confirmable action is awaiting the user's yes/no and they have just
  replied.

Rules:
- Never assume a missing time, date, or title — ask.
- If a tool returns "confirmation_required", read back a short, clear summary
  of exactly what will happen (including any conflict or duplicate warning).
  Calendar event changes (create, update, delete) are confirmed on an on-screen
  card — tell the user to use it; a spoken "yes" does not confirm them. Reminder
  changes are confirmed by voice — ask the user and wait for their reply before
  calling confirm_pending_action.
- If a tool returns "missing_slots", ask the user for at least a title or a
  date so you can find what they mean.
- If a tool returns "missing_info" or "datetime_required", ask for that
  specific detail.
- If a tool returns "error" or "not_connected", tell the user clearly what
  went wrong. Do not retry — just report it.
- After any create/update/delete executes, state plainly whether it succeeded
  or failed."""


_CARD_CREATE_SENTENCE = (
    '    - "confirmation_required": read back the event; the user confirms it on the\n'
    "      on-screen card."
)
_VOICE_CREATE_SENTENCE = (
    '    - "confirmation_required": read back the event’s specifics (title, day, start\n'
    "      and end time) and ask the user to confirm out loud before it is created."
)
_CARD_RULES_SENTENCE = (
    "  Calendar event changes (create, update, delete) are confirmed on an on-screen\n"
    '  card — tell the user to use it; a spoken "yes" does not confirm them. Reminder\n'
    "  changes are confirmed by voice — ask the user and wait for their reply before\n"
    "  calling confirm_pending_action."
)
_VOICE_RULES_SENTENCE = (
    "  ALL changes (calendar events AND reminders — create, update, delete) are\n"
    "  confirmed by VOICE: always read back the SPECIFIC target (e.g. \"delete the\n"
    '  dentist event on Friday at 3 PM\"), then ask for a yes or no. Only an\n'
    '  unambiguous affirmative ("yes", "go ahead", "confirm") counts — treat a hedge\n'
    '  ("maybe", "I guess"), a question back, silence, or anything unclear as NOT a\n'
    "  yes: re-ask once (\"Sorry — should I [action]? Yes or no?\"), then drop it. On a\n"
    "  clear yes call confirm_pending_action; on a no or a change of mind call\n"
    "  cancel_pending_action. This holds AFTER a re-ask too: a plain yes still means\n"
    "  confirm_pending_action and a plain no still means cancel_pending_action — never\n"
    "  re-issue the create/update/delete tool to answer a yes/no (that re-proposes and\n"
    "  loops). ONLY re-issue the matching tool when the user actually CHANGES a detail\n"
    '  ("make it 4 PM", "call it Jim"), to re-propose the corrected version.'
)


def build_calendar_prompt(
    now: datetime, timezone_name: str, pending_action: dict | None, confirm_mode: str = "card"
) -> str:
    base = CALENDAR_PROMPT
    if confirm_mode == "voice":
        base = base.replace(_CARD_CREATE_SENTENCE, _VOICE_CREATE_SENTENCE)
        base = base.replace(_CARD_RULES_SENTENCE, _VOICE_RULES_SENTENCE)

    prompt = base + f"\n\nCurrent date/time: {now.isoformat()}, timezone: {timezone_name}."

    if pending_action:
        summary = pending_action.get("summary", "")
        if confirm_mode == "card" and pending_action.get("requires_ui_confirmation"):
            prompt += (
                f"\n\nThere is a pending action awaiting confirmation on the on-screen card: {summary} "
                "The user cannot confirm or cancel it by voice. "
                "If their new message changes a detail of this pending action (e.g. \"actually make it 3pm\"), "
                "re-issue the matching tool call with the updated details so a corrected card is shown. "
                "If their message is unrelated to it, do not act on the new request — remind them they need to "
                "confirm or cancel the pending action using the card first."
            )
        else:
            prompt += (
                f"\n\nThere is a pending action awaiting the user's yes/no: {summary} "
                "If they confirm, call confirm_pending_action. If they decline or change their mind, "
                "call cancel_pending_action. "
                "If their message changes a detail of it (e.g. \"actually make it 3pm\"), re-issue the matching "
                "tool call with the updated details to re-confirm the new version instead of confirming the old one. "
                "If their message is clearly unrelated, acknowledge the pending action is still open and ask whether "
                "they want to cancel it before moving on — don't silently drop or replace it."
            )

    return prompt


GET_CALENDAR_EVENTS = types.FunctionDeclaration(
    name="get_calendar_events",
    description="List the user's calendar events in a time range, optionally filtered by a text query.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "time_min": types.Schema(type=types.Type.STRING, description=f"Start of the range. {_TIME_DESC}"),
            "time_max": types.Schema(
                type=types.Type.STRING, description=f"End of the range, if bounded. {_TIME_DESC}", nullable=True
            ),
            "query": types.Schema(
                type=types.Type.STRING,
                description="Optional free-text search across title, description, and attendees.",
                nullable=True,
            ),
        },
        required=["time_min"],
    ),
)

CREATE_CALENDAR_EVENT = types.FunctionDeclaration(
    name="create_calendar_event",
    description="Propose creating a new calendar event. Does not execute until the user confirms.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "summary": types.Schema(type=types.Type.STRING, description="Event title."),
            "start": types.Schema(type=types.Type.STRING, description=f"Event start. {_TIME_DESC}"),
            "end": types.Schema(type=types.Type.STRING, description=f"Event end. {_TIME_DESC}"),
            "description": types.Schema(type=types.Type.STRING, description="Optional event notes.", nullable=True),
            "reminder_minutes_before": types.Schema(
                type=types.Type.INTEGER,
                description=(
                    "Minutes before the event to remind the user, or null if they explicitly don't want a "
                    "reminder. Leave this out on the first call; supply it only after the tool returns "
                    "reminder_required and you've asked the user."
                ),
                nullable=True,
            ),
        },
        required=["summary", "start", "end"],
    ),
)

UPDATE_CALENDAR_EVENT = types.FunctionDeclaration(
    name="update_calendar_event",
    description="Resolve and propose an update to an existing event. Does not execute until the user confirms.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "title": types.Schema(
                type=types.Type.STRING,
                description="The event's title or topic, if the user named it.",
                nullable=True,
            ),
            "date": types.Schema(type=types.Type.STRING, description=_DATE_DESC, nullable=True),
            "new_summary": types.Schema(type=types.Type.STRING, description="New title, if changing.", nullable=True),
            "new_start": types.Schema(
                type=types.Type.STRING, description=f"New start time, if changing. {_TIME_DESC}", nullable=True
            ),
            "new_end": types.Schema(
                type=types.Type.STRING, description=f"New end time, if changing. {_TIME_DESC}", nullable=True
            ),
            "new_description": types.Schema(
                type=types.Type.STRING, description="New description, if changing.", nullable=True
            ),
        },
    ),
)

DELETE_CALENDAR_EVENT = types.FunctionDeclaration(
    name="delete_calendar_event",
    description="Resolve and propose deleting an existing event. Does not execute until the user confirms.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "title": types.Schema(
                type=types.Type.STRING,
                description="The event's title or topic, if the user named it.",
                nullable=True,
            ),
            "date": types.Schema(type=types.Type.STRING, description=_DATE_DESC, nullable=True),
        },
    ),
)

CREATE_REMINDER = types.FunctionDeclaration(
    name="create_reminder",
    description=(
        "Propose creating a reminder — a personal 'remember to...' note, not a calendar event. "
        "Does not execute until the user confirms."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "text": types.Schema(type=types.Type.STRING, description="What the user wants to be reminded about."),
            "remind_at": types.Schema(
                type=types.Type.STRING,
                description=f"When to remind the user — a specific date and time. {_TIME_DESC}",
            ),
        },
        required=["text", "remind_at"],
    ),
)

LIST_REMINDERS = types.FunctionDeclaration(
    name="list_reminders",
    description="List the user's reminders, optionally within a time range.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "time_min": types.Schema(
                type=types.Type.STRING, description=f"Start of the range, if filtering. {_TIME_DESC}", nullable=True
            ),
            "time_max": types.Schema(
                type=types.Type.STRING, description=f"End of the range, if filtering. {_TIME_DESC}", nullable=True
            ),
        },
    ),
)

UPDATE_REMINDER = types.FunctionDeclaration(
    name="update_reminder",
    description="Resolve and propose a change to an existing reminder. Does not execute until the user confirms.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "text": types.Schema(
                type=types.Type.STRING,
                description="The reminder's wording or topic, if the user gave it.",
                nullable=True,
            ),
            "date": types.Schema(type=types.Type.STRING, description=_DATE_DESC, nullable=True),
            "new_text": types.Schema(type=types.Type.STRING, description="New reminder text, if changing.", nullable=True),
            "new_remind_at": types.Schema(
                type=types.Type.STRING, description=f"New date/time, if changing. {_TIME_DESC}", nullable=True
            ),
        },
    ),
)

DELETE_REMINDER = types.FunctionDeclaration(
    name="delete_reminder",
    description="Resolve and propose deleting an existing reminder. Does not execute until the user confirms.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "text": types.Schema(
                type=types.Type.STRING,
                description="The reminder's wording or topic, if the user gave it.",
                nullable=True,
            ),
            "date": types.Schema(type=types.Type.STRING, description=_DATE_DESC, nullable=True),
        },
    ),
)

CONFIRM_PENDING_ACTION = types.FunctionDeclaration(
    name="confirm_pending_action",
    description="Call when the user has just confirmed (said yes) to the pending action that was described to them.",
    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
)

CANCEL_PENDING_ACTION = types.FunctionDeclaration(
    name="cancel_pending_action",
    description="Call when the user has just declined (said no) to the pending action that was described to them.",
    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
)

BASE_FUNCTION_DECLARATIONS = [
    GET_CALENDAR_EVENTS,
    CREATE_CALENDAR_EVENT,
    UPDATE_CALENDAR_EVENT,
    DELETE_CALENDAR_EVENT,
    CREATE_REMINDER,
    LIST_REMINDERS,
    UPDATE_REMINDER,
    DELETE_REMINDER,
]
