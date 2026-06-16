from datetime import datetime, timezone

from app.services.supabase_service import get_client

TIMEZONE_KEY = "timezone"


def get_user_timezone(user_id: str) -> str | None:
    result = (
        get_client()
        .table("user_preferences")
        .select("value")
        .eq("user_id", user_id)
        .eq("key", TIMEZONE_KEY)
        .limit(1)
        .execute()
    )
    return result.data[0]["value"] if result.data else None


def set_user_timezone(user_id: str, timezone_name: str) -> None:
    get_client().table("user_preferences").upsert({
        "user_id": user_id,
        "key": TIMEZONE_KEY,
        "value": timezone_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
