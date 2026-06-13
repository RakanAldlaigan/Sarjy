import base64

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.chat import ChatResponse, LLMRequest, LLMResponse, TranscriptResponse, TTSRequest
from app.prompts.system import SYSTEM_PROMPT
from app.services import deepgram_service, elevenlabs_service, llm_service

router = APIRouter()

FALLBACK_TEXT = "Sorry, something went wrong. Please try again."


@router.post("/stt", response_model=TranscriptResponse)
async def speech_to_text(audio: UploadFile):
    try:
        audio_bytes = await audio.read()
        transcript = deepgram_service.transcribe_audio(audio_bytes)
        return TranscriptResponse(transcript=transcript)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Speech-to-text failed: {e}")


@router.post("/llm", response_model=LLMResponse)
def chat_with_llm(body: LLMRequest):
    try:
        reply = llm_service.generate_reply([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": body.transcript},
        ])
        return LLMResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {e}")


@router.post("/tts")
def text_to_speech(body: TTSRequest):
    try:
        audio_bytes = elevenlabs_service.synthesize_speech(body.text)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Text-to-speech failed: {e}")


@router.post("/chat", response_model=ChatResponse)
async def chat(audio: UploadFile):
    transcript = ""
    try:
        audio_bytes = await audio.read()
        transcript = deepgram_service.transcribe_audio(audio_bytes)
        reply = llm_service.generate_reply([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ])
        audio_reply = elevenlabs_service.synthesize_speech(reply)
    except Exception:
        reply = FALLBACK_TEXT
        try:
            audio_reply = elevenlabs_service.synthesize_speech(reply)
        except Exception:
            audio_reply = b""

    return ChatResponse(
        transcript=transcript,
        reply=reply,
        audio_base64=base64.b64encode(audio_reply).decode("ascii"),
    )
