from app.services import session_service
from app.services.supabase_service import get_client

# Flat cap across all past sessions combined. 20 proved too small — a fact
# mentioned hours earlier could fall out of the window after normal use in
# other sessions. 60 gives more headroom without a schema change; a proper
# fix (summarization or a dedicated facts table) is a bigger change for later.
CONTEXT_MESSAGE_LIMIT = 60


def get_memory_context(current_session_id: str, user_id: str) -> str:
    other_session_ids = [
        session_id
        for session_id in session_service.get_user_session_ids(user_id)
        if session_id != current_session_id
    ]
    if not other_session_ids:
        return ""

    result = (
        get_client()
        .table("messages")
        .select("role, content")
        .in_("session_id", other_session_ids)
        .order("created_at", desc=True)
        .limit(CONTEXT_MESSAGE_LIMIT)
        .execute()
    )

    if not result.data:
        return ""

    lines = [f"{m['role']}: {m['content']}" for m in reversed(result.data)]
    return "Earlier conversations with this user included:\n" + "\n".join(lines)
