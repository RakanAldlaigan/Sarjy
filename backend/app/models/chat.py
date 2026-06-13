from pydantic import BaseModel


class TranscriptResponse(BaseModel):
    transcript: str


class LLMRequest(BaseModel):
    transcript: str


class LLMResponse(BaseModel):
    reply: str


class TTSRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    session_id: str
    transcript: str
    reply: str
    audio_base64: str


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
