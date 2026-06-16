from typing import Literal

from pydantic import BaseModel


class PendingActionView(BaseModel):
    action_type: str
    summary: str
    conflict_warning: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    transcript: str
    reply: str
    audio_base64: str
    pending_action: PendingActionView | None = None


class PendingActionRequest(BaseModel):
    session_id: str
    action: Literal["confirm", "cancel"]


class SessionMessage(BaseModel):
    role: str
    content: str


class SessionSummary(BaseModel):
    id: str
    created_at: str
    last_active_at: str
    preview: str
    is_empty: bool


class NewSessionResponse(BaseModel):
    session_id: str


class ConnectCalendarResponse(BaseModel):
    authorization_url: str


class CalendarStatusResponse(BaseModel):
    connected: bool
