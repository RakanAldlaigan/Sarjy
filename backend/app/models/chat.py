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
    transcript: str
    reply: str
    audio_base64: str
