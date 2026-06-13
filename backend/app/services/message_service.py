from app.services.supabase_service import get_client


def save_message(session_id: str, role: str, content: str) -> None:
    get_client().table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()


def get_session_messages(session_id: str) -> list[dict]:
    result = (
        get_client()
        .table("messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return result.data
