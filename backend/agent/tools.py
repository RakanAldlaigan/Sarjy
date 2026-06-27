"""The agent's capability tools, exposed as LiveKit @function_tools. Each tool only
declares the schema the model needs (its docstring is the model-facing description and
per-param docs) and delegates to the existing assistant_tools.execute_tool dispatcher,
so the app/services business logic is reused, not rewritten.

user_id comes from ctx.userdata (set in main.py) and is passed into every dispatcher
call, preserving the services' per-user scoping. Write tools (calendar/reminder
create/update/delete) stage a pending_action for voice confirmation rather than writing;
confirm_pending_action runs the real write only after a strict affirmative (see
agent/confirmation.py). The synchronous services run via asyncio.to_thread so blocking
work doesn't stall turn-taking.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from google.auth.exceptions import RefreshError
from livekit.agents import RunContext, function_tool

import confirmation
from userdata import PENDING_ACTION_TTL_MINUTES, SarjyUserData
from app.services import assistant_tools, google_auth_service

logger = logging.getLogger("sarjy-agent")

_CALENDAR_TOOLS = frozenset({
    "get_calendar_events",
    "create_calendar_event",
    "update_calendar_event",
    "delete_calendar_event",
    "create_reminder",
    "update_reminder",
    "delete_reminder",
})


def _session_credentials(ud: SarjyUserData):
    """Return this session's cached Google credential, building it on first calendar use
    via google_auth_service.get_credentials (which refreshes eagerly and disconnects on a
    revoked grant). Returns None if the user hasn't connected Calendar. The credential
    lives only in this session's userdata, so it can't reach another user's session."""
    if ud.google_credentials is None:
        ud.google_credentials = google_auth_service.get_credentials(ud.user_id)
    return ud.google_credentials


_prewarm_tasks: set[asyncio.Task] = set()


async def _prewarm_credentials(ud: SarjyUserData) -> None:
    """Best-effort build of this session's Google credential at session start (reusing the
    lazy _session_credentials builder) so the one unavoidable OAuth refresh overlaps
    connection/greeting instead of the first calendar call. Never raises: no calendar
    connected resolves to None, and any other failure is swallowed so the lazy path
    rebuilds on first use."""
    try:
        cred = await asyncio.to_thread(_session_credentials, ud)
        logger.info(
            "calendar credential pre-warm: %s",
            "ready" if cred else "no calendar connected",
        )
    except Exception:
        logger.info("calendar credential pre-warm skipped (best-effort)", exc_info=True)


def schedule_credential_prewarm(ud: SarjyUserData) -> None:
    """Fire the credential pre-warm as a non-blocking background task at session start.
    Idempotent with the lazy path via _session_credentials' None-check."""
    task = asyncio.create_task(_prewarm_credentials(ud))
    _prewarm_tasks.add(task)
    task.add_done_callback(_prewarm_tasks.discard)


def _run_sync(tool_name: str, args: dict, ud: SarjyUserData) -> dict:
    """Delegate to the dispatcher (in a worker thread), threading session state via
    userdata and staging any proposed write as a pending action for voice confirmation."""
    credentials = _session_credentials(ud) if tool_name in _CALENDAR_TOOLS else None

    try:
        execution = assistant_tools.execute_tool(
            tool_name,
            args,
            user_id=ud.user_id,
            timezone_name=ud.timezone_name,
            pending_action=None,
            session_id=None,
            note_draft=ud.note_draft,
            credentials=credentials,
        )
    except RefreshError:
        ud.google_credentials = None
        return {"status": "not_connected"}

    if execution.clear_note_draft:
        ud.note_draft = None
    elif execution.note_draft is not None:
        ud.note_draft = execution.note_draft

    if execution.pending_action is not None:
        ud.pending_action = execution.pending_action
        ud.pending_action_expires_at = datetime.now(UTC) + timedelta(minutes=PENDING_ACTION_TTL_MINUTES)
        ud.confirm_reasks = 0

    return execution.result


async def _run(tool_name: str, ctx: RunContext[SarjyUserData]) -> dict:
    raw = ctx.function_call.arguments
    args = json.loads(raw) if raw else {}
    return await asyncio.to_thread(_run_sync, tool_name, args, ctx.userdata)


def _last_user_transcript(ctx: RunContext[SarjyUserData]) -> str:
    """The verbatim STT text of the most recent user turn. The misheard-yes guard
    classifies what the user actually said, not what the model claims, so an over-eager
    'yes' can't slip a destructive write."""
    for item in reversed(ctx.session.history.items):
        if getattr(item, "role", None) == "user":
            return item.text_content or ""
    return ""


def _pending_is_live(ud: SarjyUserData) -> bool:
    if ud.pending_action is None:
        return False
    expires = ud.pending_action_expires_at
    return expires is None or expires >= datetime.now(UTC)


def _clear_pending(ud: SarjyUserData) -> None:
    ud.pending_action = None
    ud.pending_action_expires_at = None
    ud.confirm_reasks = 0


def _execute_pending_sync(ud: SarjyUserData) -> dict:
    """The real write — runs only after a strict affirmative. Same cached-credential and
    revoked-grant handling as the dispatch path."""
    credentials = _session_credentials(ud)
    try:
        return assistant_tools.execute_pending_action(
            ud.user_id, ud.pending_action, credentials=credentials
        )
    except RefreshError:
        ud.google_credentials = None
        return {"status": "not_connected"}


@function_tool
async def confirm_pending_action(ctx: RunContext[SarjyUserData]) -> dict:
    """Confirm and EXECUTE the action currently awaiting the user's yes/no — call this only
    after you have read back the specific action and the user has just replied. Whether the
    write actually happens is gated by a strict check on the user's literal words: a clear
    "yes"/"go ahead"/"confirm" executes; a hedge, a question, or anything ambiguous does
    NOT (you'll be told to re-ask); a "no" or a correction does NOT (it cancels). So it is
    always safe to call this when the user appears to be answering the confirmation."""
    ud = ctx.userdata
    if not _pending_is_live(ud):
        _clear_pending(ud)
        return {"status": "no_pending_action"}

    verdict = confirmation.classify_affirmation(_last_user_transcript(ctx))

    if verdict == confirmation.AFFIRMATIVE:
        outcome = await asyncio.to_thread(_execute_pending_sync, ud)
        _clear_pending(ud)
        return outcome

    if verdict == confirmation.NEGATIVE:
        summary = ud.pending_action.get("summary")
        _clear_pending(ud)
        return {"status": "cancelled", "reason": "user_declined", "summary": summary}

    ud.confirm_reasks += 1
    if ud.confirm_reasks >= 2:
        summary = ud.pending_action.get("summary")
        _clear_pending(ud)
        return {"status": "cancelled", "reason": "unconfirmed", "summary": summary}
    return {
        "status": "needs_explicit_confirmation",
        "summary": ud.pending_action.get("summary"),
        "guidance": (
            "That was not a clear yes or no. The same action is STILL pending — do NOT call "
            "create_/update_/delete_ again (that re-proposes and loops). Just say the action "
            "back in words and ask for a plain 'yes' or 'no'. When the user answers, call "
            "confirm_pending_action for a yes, or cancel_pending_action for a no."
        ),
    }


@function_tool
async def cancel_pending_action(ctx: RunContext[SarjyUserData]) -> dict:
    """Cancel the action currently awaiting confirmation without executing it — call this
    when the user declines, changes their mind, or no longer wants the pending action."""
    ud = ctx.userdata
    if ud.pending_action is None:
        return {"status": "no_pending_action"}
    summary = ud.pending_action.get("summary")
    _clear_pending(ud)
    return {"status": "cancelled", "summary": summary}


@function_tool
async def get_calendar_events(
    ctx: RunContext[SarjyUserData],
    time_min: str,
    time_max: str | None = None,
    query: str | None = None,
) -> dict:
    """List the user's calendar events in a time range, optionally filtered by a text query.

    Args:
        time_min: Start of the range. An ISO 8601 datetime (e.g. 2026-06-19T15:00:00),
            interpreted in the user's timezone unless it includes its own UTC offset.
        time_max: End of the range, if bounded. Same ISO 8601 format as time_min.
        query: Optional free-text search across title, description, and attendees.
    """
    return await _run("get_calendar_events", ctx)


@function_tool
async def create_calendar_event(
    ctx: RunContext[SarjyUserData],
    summary: str,
    start: str,
    end: str,
    description: str | None = None,
    reminder_minutes_before: int | None = None,
) -> dict:
    """Propose creating a new calendar event. As soon as you have title, start, and end,
    call it with just those — you don't need the reminder yet; it guides the rest one step
    at a time (duplicate_warning, then reminder_required, then it is created).

    Args:
        summary: Event title.
        start: Event start. An ISO 8601 datetime, interpreted in the user's timezone
            unless it includes its own UTC offset.
        end: Event end. Same ISO 8601 format as start.
        description: Optional event notes.
        reminder_minutes_before: Minutes before the event to remind the user, or null if
            they explicitly don't want a reminder. Leave this out on the first call; supply
            it only after the tool returns reminder_required and you've asked the user.
    """
    return await _run("create_calendar_event", ctx)


@function_tool
async def update_calendar_event(
    ctx: RunContext[SarjyUserData],
    title: str | None = None,
    date: str | None = None,
    new_summary: str | None = None,
    new_start: str | None = None,
    new_end: str | None = None,
    new_description: str | None = None,
) -> dict:
    """Resolve and propose an update to an existing event. Fill the slots you have —
    `title` (what they called it) and/or `date` (the day it falls on); you don't need both.

    Args:
        title: The event's title or topic, if the user named it.
        date: A calendar date (e.g. 2026-06-20), interpreted in the user's timezone. Only
            set this if the user named an actual date or day; a bare time of day is not a date.
        new_summary: New title, if changing.
        new_start: New start time, if changing (ISO 8601, user's timezone).
        new_end: New end time, if changing (ISO 8601, user's timezone).
        new_description: New description, if changing.
    """
    return await _run("update_calendar_event", ctx)


@function_tool
async def delete_calendar_event(
    ctx: RunContext[SarjyUserData],
    title: str | None = None,
    date: str | None = None,
) -> dict:
    """Resolve and propose deleting an existing event. Fill `title` and/or `date` to find it.

    Args:
        title: The event's title or topic, if the user named it.
        date: A calendar date (e.g. 2026-06-20), interpreted in the user's timezone. Only
            set this if the user named an actual date or day; a bare time of day is not a date.
    """
    return await _run("delete_calendar_event", ctx)


@function_tool
async def create_reminder(ctx: RunContext[SarjyUserData], text: str, remind_at: str) -> dict:
    """Propose creating a reminder — a personal 'remember to...' note, not a calendar event.
    Requires a specific date and time; if the user hasn't given one, ask before calling.

    Args:
        text: What the user wants to be reminded about.
        remind_at: When to remind the user — a specific date and time. An ISO 8601 datetime,
            interpreted in the user's timezone unless it includes its own UTC offset.
    """
    return await _run("create_reminder", ctx)


@function_tool
async def list_reminders(
    ctx: RunContext[SarjyUserData],
    time_min: str | None = None,
    time_max: str | None = None,
) -> dict:
    """List the user's reminders, optionally within a time range. The result may be capped —
    if so, read back only the first few aloud and ask before continuing.

    Args:
        time_min: Start of the range, if filtering (ISO 8601, user's timezone).
        time_max: End of the range, if filtering (ISO 8601, user's timezone).
    """
    return await _run("list_reminders", ctx)


@function_tool
async def update_reminder(
    ctx: RunContext[SarjyUserData],
    text: str | None = None,
    date: str | None = None,
    new_text: str | None = None,
    new_remind_at: str | None = None,
) -> dict:
    """Resolve and propose a change to an existing reminder. Fill `text` (its wording/topic)
    and/or `date` to find it.

    Args:
        text: The reminder's wording or topic, if the user gave it.
        date: A calendar date the reminder falls on, in the user's timezone. Only set this
            if the user named an actual date or day.
        new_text: New reminder text, if changing.
        new_remind_at: New date/time, if changing (ISO 8601, user's timezone).
    """
    return await _run("update_reminder", ctx)


@function_tool
async def delete_reminder(
    ctx: RunContext[SarjyUserData],
    text: str | None = None,
    date: str | None = None,
) -> dict:
    """Resolve and propose deleting an existing reminder. Fill `text` and/or `date` to find it.

    Args:
        text: The reminder's wording or topic, if the user gave it.
        date: A calendar date the reminder falls on, in the user's timezone. Only set this
            if the user named an actual date or day.
    """
    return await _run("delete_reminder", ctx)


@function_tool
async def save_note(ctx: RunContext[SarjyUserData], content: str, title: str) -> dict:
    """Save a note for the user — text they want to keep and read later. Use for
    'take/save/write down a note' requests. Saves immediately; no confirmation needed.

    Args:
        content: The note body. Reproduce what the user said near-verbatim. Remove ONLY
            filler words and false starts ("uh", "um", "you know", "I mean",
            stuttered/repeated words). Preserve every fact, name, number, date, detail, and
            piece of context exactly — do not summarize, condense, paraphrase, reorder, or
            drop anything.
        title: A short title naming what the note is about (a few words).
    """
    return await _run("save_note", ctx)


@function_tool
async def search_notes(ctx: RunContext[SarjyUserData], query: str) -> dict:
    """Search the user's saved notes by topic or keywords — matches against note titles and
    content. Use to recall or look up something the user saved earlier.

    Args:
        query: What to look for — keywords or the topic of the note.
    """
    return await _run("search_notes", ctx)


@function_tool
async def draft_structured_note(
    ctx: RunContext[SarjyUserData],
    content: str,
    asking_clarification: bool,
    format: str | None = None,
) -> dict:
    """Record progress on a structured note before replying. Call this each turn while
    building a structured note, with the content assembled so far. Set asking_clarification
    to true when your reply will ask another clarifying question. Returns whether you may ask
    another question or must finalize — the clarifying-question limit is enforced here.

    Args:
        content: The structured note content assembled so far, as best you have it.
        asking_clarification: True if your reply this turn will ask another clarifying question.
        format: Desired format if the user specified one (e.g. 'bullets', 'summary'). Optional.
    """
    return await _run("draft_structured_note", ctx)


@function_tool
async def finalize_structured_note(
    ctx: RunContext[SarjyUserData],
    title: str,
    content: str,
    format: str | None = None,
) -> dict:
    """Write the finished structured note and end the drafting flow. Call when you have
    enough information, or once you have reached the clarifying-question limit.

    Args:
        title: A short title naming the note.
        content: The final, organized note content, formatted as requested if a format was given.
        format: The format used, if any (e.g. 'bullets', 'summary'). Optional.
    """
    return await _run("finalize_structured_note", ctx)


@function_tool
async def discard_structured_note(ctx: RunContext[SarjyUserData]) -> dict:
    """Abandon the in-progress structured note draft (e.g. the user no longer wants it)."""
    return await _run("discard_structured_note", ctx)


ALL_TOOLS = [
    get_calendar_events,
    create_calendar_event,
    update_calendar_event,
    delete_calendar_event,
    create_reminder,
    list_reminders,
    update_reminder,
    delete_reminder,
    save_note,
    search_notes,
    draft_structured_note,
    finalize_structured_note,
    discard_structured_note,
    confirm_pending_action,
    cancel_pending_action,
]
