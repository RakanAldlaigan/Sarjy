import threading
from datetime import datetime, timedelta, timezone

from app.services.supabase_service import get_client

SESSION_TIMEOUT_MINUTES = 30

_new_session_lock = threading.Lock()


def get_or_create_session(user_id: str) -> str:
    client = get_client()
    now = datetime.now(timezone.utc)

    result = (
        client.table("sessions")
        .select("id, last_active_at")
        .eq("user_id", user_id)
        .is_("closed_at", "null")
        .order("last_active_at", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        session = result.data[0]
        last_active_at = datetime.fromisoformat(session["last_active_at"])
        if now - last_active_at < timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            client.table("sessions").update({"last_active_at": now.isoformat()}).eq("id", session["id"]).execute()
            return session["id"]
        client.table("sessions").update({"closed_at": now.isoformat()}).eq("id", session["id"]).execute()

    return create_session(user_id)


def create_session(user_id: str) -> str:
    client = get_client()
    new_session = client.table("sessions").insert({"user_id": user_id}).execute()
    return new_session.data[0]["id"]


def touch_session(session_id: str, user_id: str) -> bool:
    """Synchronous ownership/existence gate for the chat path. The load-bearing
    return bool stays on the critical path; the last_active_at refresh is deferred
    to update_last_active (off the critical path) so the response never blocks on a
    cosmetic timestamp write (readers are only the sidebar sort + a 30-min timeout
    the live frontend never triggers)."""
    return session_belongs_to_user(session_id, user_id)


def update_last_active(session_id: str, user_id: str) -> None:
    now = datetime.now(timezone.utc)
    (
        get_client()
        .table("sessions")
        .update({"last_active_at": now.isoformat()})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )


def close_active_session(user_id: str) -> None:
    now = datetime.now(timezone.utc)
    get_client().table("sessions").update({"closed_at": now.isoformat()}).eq("user_id", user_id).is_(
        "closed_at", "null"
    ).execute()


def mark_session_non_empty(session_id: str, user_id: str) -> None:
    get_client().table("sessions").update({"is_empty": False}).eq("id", session_id).eq("user_id", user_id).execute()


def get_empty_session(user_id: str) -> str | None:
    result = (
        get_client()
        .table("sessions")
        .select("id")
        .eq("user_id", user_id)
        .eq("is_empty", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0]["id"] if result.data else None


def get_or_create_empty_session(user_id: str) -> str:
    with _new_session_lock:
        empty_session_id = get_empty_session(user_id)
        if empty_session_id:
            return empty_session_id

        close_active_session(user_id)
        return create_session(user_id)


def delete_session(session_id: str, user_id: str) -> None:
    get_client().table("sessions").delete().eq("id", session_id).eq("user_id", user_id).execute()


def session_belongs_to_user(session_id: str, user_id: str) -> bool:
    result = (
        get_client()
        .table("sessions")
        .select("id")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def get_user_session_ids(user_id: str) -> list[str]:
    result = get_client().table("sessions").select("id").eq("user_id", user_id).execute()
    return [session["id"] for session in result.data]


def _resolve_pending_action(session_id: str, user_id: str, pending_action: dict | None, expires_at: str | None) -> dict | None:
    if not pending_action:
        return None
    if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        clear_pending_action(session_id, user_id)
        return None
    return pending_action


def get_pending_action(session_id: str, user_id: str) -> dict | None:
    result = (
        get_client()
        .table("sessions")
        .select("pending_action, pending_action_expires_at")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None

    row = result.data[0]
    return _resolve_pending_action(session_id, user_id, row["pending_action"], row["pending_action_expires_at"])


def set_pending_action(session_id: str, user_id: str, pending_action: dict, ttl_minutes: int = 5) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    get_client().table("sessions").update({
        "pending_action": pending_action,
        "pending_action_expires_at": expires_at.isoformat(),
    }).eq("id", session_id).eq("user_id", user_id).execute()


def clear_pending_action(session_id: str, user_id: str) -> None:
    get_client().table("sessions").update({
        "pending_action": None,
        "pending_action_expires_at": None,
    }).eq("id", session_id).eq("user_id", user_id).execute()


NOTE_DRAFT_TTL_MINUTES = 30


def _resolve_note_draft(session_id: str, user_id: str, note_draft: dict | None) -> dict | None:
    if not note_draft:
        return None
    updated_at = note_draft.get("updated_at")
    if updated_at and datetime.fromisoformat(updated_at) < datetime.now(timezone.utc) - timedelta(
        minutes=NOTE_DRAFT_TTL_MINUTES
    ):
        clear_note_draft(session_id, user_id)
        return None
    return note_draft


def get_session_turn_state(session_id: str, user_id: str) -> tuple[dict | None, dict | None]:
    """One round-trip read of both per-turn state fields from the single sessions
    row. Replaces separate get_pending_action + get_note_draft on the chat path;
    identical validation/expiry behavior (pending validated first, then note)."""
    result = (
        get_client()
        .table("sessions")
        .select("pending_action, pending_action_expires_at, note_draft")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None, None

    row = result.data[0]
    pending_action = _resolve_pending_action(session_id, user_id, row["pending_action"], row["pending_action_expires_at"])
    note_draft = _resolve_note_draft(session_id, user_id, row["note_draft"])
    return pending_action, note_draft


def set_note_draft(session_id: str, user_id: str, note_draft: dict) -> None:
    note_draft = {**note_draft, "updated_at": datetime.now(timezone.utc).isoformat()}
    get_client().table("sessions").update({"note_draft": note_draft}).eq("id", session_id).eq(
        "user_id", user_id
    ).execute()


def clear_note_draft(session_id: str, user_id: str) -> None:
    get_client().table("sessions").update({"note_draft": None}).eq("id", session_id).eq(
        "user_id", user_id
    ).execute()


def list_sessions(user_id: str) -> list[dict]:
    client = get_client()

    sessions = (
        client.table("sessions")
        .select("id, created_at, last_active_at, is_empty")
        .eq("user_id", user_id)
        .order("last_active_at", desc=True)
        .execute()
    ).data

    session_ids = [session["id"] for session in sessions]

    previews: dict[str, str] = {}
    if session_ids:
        messages = (
            client.table("messages")
            .select("session_id, content")
            .eq("role", "user")
            .in_("session_id", session_ids)
            .order("created_at")
            .execute()
        ).data
        for message in messages:
            previews.setdefault(message["session_id"], message["content"])

    for session in sessions:
        session["preview"] = previews.get(session["id"], "")

    return sessions
