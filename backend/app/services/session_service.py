import threading
from datetime import datetime, timedelta, timezone

from app.services.supabase_service import get_client

SESSION_TIMEOUT_MINUTES = 30

_new_session_lock = threading.Lock()


def get_or_create_session() -> str:
    client = get_client()
    now = datetime.now(timezone.utc)

    result = (
        client.table("sessions")
        .select("id, last_active_at")
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

    return create_session()


def create_session() -> str:
    client = get_client()
    new_session = client.table("sessions").insert({}).execute()
    return new_session.data[0]["id"]


def touch_session(session_id: str) -> None:
    now = datetime.now(timezone.utc)
    get_client().table("sessions").update({"last_active_at": now.isoformat()}).eq("id", session_id).execute()


def close_active_session() -> None:
    now = datetime.now(timezone.utc)
    get_client().table("sessions").update({"closed_at": now.isoformat()}).is_("closed_at", "null").execute()


def mark_session_non_empty(session_id: str) -> None:
    get_client().table("sessions").update({"is_empty": False}).eq("id", session_id).execute()


def get_empty_session() -> str | None:
    result = (
        get_client()
        .table("sessions")
        .select("id")
        .eq("is_empty", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0]["id"] if result.data else None


def get_or_create_empty_session() -> str:
    # Serializes check-then-create so concurrent "New session" requests
    # can't each pass the empty-session check and create duplicates.
    with _new_session_lock:
        empty_session_id = get_empty_session()
        if empty_session_id:
            return empty_session_id

        close_active_session()
        return create_session()


def delete_session(session_id: str) -> None:
    get_client().table("sessions").delete().eq("id", session_id).execute()


def list_sessions() -> list[dict]:
    client = get_client()

    sessions = (
        client.table("sessions")
        .select("id, created_at, last_active_at, is_empty")
        .order("last_active_at", desc=True)
        .execute()
    ).data

    messages = (
        client.table("messages")
        .select("session_id, content")
        .eq("role", "user")
        .order("created_at")
        .execute()
    ).data

    previews: dict[str, str] = {}
    for message in messages:
        previews.setdefault(message["session_id"], message["content"])

    for session in sessions:
        session["preview"] = previews.get(session["id"], "")

    return sessions
