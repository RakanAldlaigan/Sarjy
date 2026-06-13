from app.services.supabase_service import get_client

CONTEXT_MESSAGE_LIMIT = 20


def get_memory_context(current_session_id: str) -> str:
    result = (
        get_client()
        .table("messages")
        .select("role, content")
        .neq("session_id", current_session_id)
        .order("created_at", desc=True)
        .limit(CONTEXT_MESSAGE_LIMIT)
        .execute()
    )

    if not result.data:
        return ""

    lines = [f"{m['role']}: {m['content']}" for m in reversed(result.data)]
    return "Earlier conversations with this user included:\n" + "\n".join(lines)
