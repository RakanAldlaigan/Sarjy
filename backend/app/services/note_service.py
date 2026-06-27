import re

from app.services.supabase_service import get_client

SEARCH_MAX_RESULTS = 3


def create_note(
    user_id: str,
    content: str,
    title: str,
    kind: str = "note",
    session_id: str | None = None,
) -> dict:
    inserted = (
        get_client()
        .table("notes")
        .insert({
            "user_id": user_id,
            "session_id": session_id,
            "title": title,
            "content": content,
            "kind": kind,
        })
        .execute()
    )
    return inserted.data[0]


def list_notes(user_id: str) -> list[dict]:
    return (
        get_client()
        .table("notes")
        .select("id, title, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


def search_notes(user_id: str, query: str | None = None, max_results: int = SEARCH_MAX_RESULTS) -> list[dict]:
    db_query = (
        get_client()
        .table("notes")
        .select("id, title, content, created_at")
        .eq("user_id", user_id)
    )

    words = [w for w in re.findall(r"\w+", query) if len(w) > 2] if query else []
    if words:
        conditions = [f"title.ilike.%{w}%" for w in words] + [f"content.ilike.%{w}%" for w in words]
        db_query = db_query.or_(",".join(conditions))

    return db_query.order("created_at", desc=True).limit(max_results).execute().data


def get_note(note_id: str, user_id: str) -> dict | None:
    result = (
        get_client()
        .table("notes")
        .select("id, title, content, created_at")
        .eq("id", note_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_note(note_id: str, user_id: str) -> None:
    get_client().table("notes").delete().eq("id", note_id).eq("user_id", user_id).execute()
