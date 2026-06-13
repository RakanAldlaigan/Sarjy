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
    now = datetime.now(timezone.utc)
    result = (
        get_client()
        .table("sessions")
        .update({"last_active_at": now.isoformat()})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)


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
    # Serializes check-then-create so concurrent "New session" requests
    # can't each pass the empty-session check and create duplicates.
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
