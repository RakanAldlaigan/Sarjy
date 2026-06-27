import hashlib
import hmac
import os
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.core.config import settings
from app.services.supabase_service import get_client

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

STATE_TTL_SECONDS = 600

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.refresh_token_encryption_key.encode())
    return _fernet


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _sign_state(user_id: str) -> str:
    expires_at = int(time.time()) + STATE_TTL_SECONDS
    payload = f"{user_id}.{expires_at}"
    signature = hmac.new(
        settings.refresh_token_encryption_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def _verify_state(state: str) -> str:
    try:
        user_id, expires_at, signature = state.split(".")
    except ValueError:
        raise ValueError("Malformed OAuth state")

    payload = f"{user_id}.{expires_at}"
    expected_signature = hmac.new(
        settings.refresh_token_encryption_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid OAuth state signature")
    if int(expires_at) < time.time():
        raise ValueError("OAuth state expired")

    return user_id


def get_authorization_url(user_id: str) -> str:
    flow = Flow.from_client_config(
        _client_config(),
        scopes=CALENDAR_SCOPES,
        redirect_uri=settings.google_redirect_uri,
        autogenerate_code_verifier=False,
    )
    url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=_sign_state(user_id),
    )
    return url


def exchange_code(code: str, state: str) -> tuple[str, str]:
    user_id = _verify_state(state)

    flow = Flow.from_client_config(_client_config(), scopes=CALENDAR_SCOPES, redirect_uri=settings.google_redirect_uri)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    if not credentials.refresh_token:
        raise ValueError("Google did not return a refresh token — user must re-consent")

    return user_id, credentials.refresh_token


def save_credentials(user_id: str, refresh_token: str) -> None:
    encrypted = _get_fernet().encrypt(refresh_token.encode()).decode()
    get_client().table("google_credentials").upsert({
        "user_id": user_id,
        "encrypted_refresh_token": encrypted,
        "scopes": " ".join(CALENDAR_SCOPES),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def build_credentials(user_id: str) -> Credentials | None:
    """Construct the user's Credentials object from the stored refresh token WITHOUT
    eagerly refreshing it. Returns None if the user hasn't connected Calendar.

    The returned object knows how to refresh itself: Google's client library calls
    `credentials.refresh()` lazily before a request only when the access token is
    missing or expired. The long-lived agent worker caches this object per session
    (see SarjyUserData.google_credentials) and reuses it, so the ~2.8s OAuth refresh
    happens at most once per token lifetime instead of on every calendar call.

    `get_credentials` is the eager counterpart used by the stateless /chat path.
    """
    result = (
        get_client()
        .table("google_credentials")
        .select("encrypted_refresh_token, scopes")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None

    row = result.data[0]
    if "calendar" not in row["scopes"]:
        return None

    refresh_token = _get_fernet().decrypt(row["encrypted_refresh_token"].encode()).decode()
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=CALENDAR_SCOPES,
    )


def get_credentials(user_id: str) -> Credentials | None:
    """Load the user's credentials and eagerly refresh them so the returned object
    carries a live access token. Used by the /chat path (which can't cache, so it pays
    the refresh each request) and for the agent's first build of the session, after which
    Google's library refreshes the cached object lazily on expiry."""
    credentials = build_credentials(user_id)
    if credentials is None:
        return None

    try:
        credentials.refresh(Request())
    except RefreshError:
        disconnect(user_id)
        return None

    return credentials


def has_calendar_access(user_id: str) -> bool:
    return get_credentials(user_id) is not None


def disconnect(user_id: str) -> None:
    get_client().table("google_credentials").delete().eq("user_id", user_id).execute()


def get_reminders_calendar_id(user_id: str) -> str | None:
    result = (
        get_client()
        .table("google_credentials")
        .select("sarjy_reminders_calendar_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0]["sarjy_reminders_calendar_id"] if result.data else None


def save_reminders_calendar_id(user_id: str, calendar_id: str) -> None:
    get_client().table("google_credentials").update({
        "sarjy_reminders_calendar_id": calendar_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", user_id).execute()
