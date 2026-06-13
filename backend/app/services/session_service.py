from datetime import datetime, timedelta, timezone

from app.services.supabase_service import get_client

SESSION_TIMEOUT_MINUTES = 30


def get_or_create_session() -> tuple[str, bool]:
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
            return session["id"], False
        client.table("sessions").update({"closed_at": now.isoformat()}).eq("id", session["id"]).execute()

    new_session = client.table("sessions").insert({}).execute()
    return new_session.data[0]["id"], True
