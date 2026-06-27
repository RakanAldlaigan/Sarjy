"""Per-session userdata threaded into every tool call via RunContext.userdata.

- user_id        — the verified user; passed into every service call so the services'
                   per-user (.eq("user_id", ...)) scoping holds.
- timezone_name  — resolved once at session start, reused for date parsing/formatting.
- note_draft     — the in-progress structured-note draft (cross-turn, in worker memory).
- google_credentials — the user's Google Calendar credential, built lazily on first
                   calendar use and reused for the session. It lives only in this session's
                   userdata (one verified user), so it's structurally isolated; this avoids
                   the per-request OAuth refresh the stateless /chat path pays.
- pending_action / pending_action_expires_at / confirm_reasks — voice-confirmation state.
                   A write tool stages its resolved action here instead of executing; the
                   model reads it back and confirm/cancel resolves it next turn. confirm_reasks
                   caps re-asks on an ambiguous response. The dict shape and 5-min TTL mirror
                   the /chat machinery.
"""

from dataclasses import dataclass
from datetime import datetime

from google.oauth2.credentials import Credentials

PENDING_ACTION_TTL_MINUTES = 5


@dataclass
class SarjyUserData:
    user_id: str
    timezone_name: str
    note_draft: dict | None = None
    google_credentials: Credentials | None = None
    pending_action: dict | None = None
    pending_action_expires_at: datetime | None = None
    confirm_reasks: int = 0
