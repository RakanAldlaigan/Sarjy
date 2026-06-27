from app.services import session_service
from app.services.supabase_service import get_client


def save_message(session_id: str, user_id: str, role: str, content: str) -> bool:
    """Insert a message only if session_id belongs to user_id. Returns True if
    written, False if the session is not owned (no write performed).

    The backend runs as service_role (bypasses RLS), so this app-level ownership
    check is the ONLY guard against writing into another user's session."""
    if not session_service.session_belongs_to_user(session_id, user_id):
        return False
    get_client().table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()
    return True


def get_session_messages(session_id: str, user_id: str) -> list[dict]:
    result = (
        get_client()
        .table("messages")
        .select("role, content, sessions!inner(user_id)")
        .eq("session_id", session_id)
        .eq("sessions.user_id", user_id)
        .order("created_at")
        .execute()
    )
    return [{"role": m["role"], "content": m["content"]} for m in result.data]
