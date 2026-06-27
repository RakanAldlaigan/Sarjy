import threading
from datetime import datetime, timedelta, timezone

from app.services.supabase_service import get_client

TIMEZONE_KEY = "timezone"

TZ_WRITE_THROTTLE_MINUTES = 30
_tz_write_cache: dict[str, tuple[str, datetime]] = {}
_tz_cache_lock = threading.Lock()


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


def set_user_timezone_throttled(user_id: str, timezone_name: str) -> None:
    """Persist the timezone at most once per TZ_WRITE_THROTTLE_MINUTES per user,
    plus immediately whenever the value changes. Skips the redundant per-turn write
    when the same tz was persisted recently."""
    now = datetime.now(timezone.utc)
    with _tz_cache_lock:
        cached = _tz_write_cache.get(user_id)
        if cached and cached[0] == timezone_name and now - cached[1] < timedelta(minutes=TZ_WRITE_THROTTLE_MINUTES):
            return
        _tz_write_cache[user_id] = (timezone_name, now)
    set_user_timezone(user_id, timezone_name)
