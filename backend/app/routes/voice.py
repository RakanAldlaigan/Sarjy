import base64

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.chat import ChatResponse, LLMRequest, LLMResponse, TranscriptResponse, TTSRequest
from app.prompts.system import SYSTEM_PROMPT
from app.services import (
    deepgram_service,
    elevenlabs_service,
    llm_service,
    memory_service,
    message_service,
    session_service,
)

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
    session_id, is_new_session = session_service.get_or_create_session()
    transcript = ""
    try:
        audio_bytes = await audio.read()
        transcript = deepgram_service.transcribe_audio(audio_bytes)
        message_service.save_message(session_id, "user", transcript)

        system_prompt = SYSTEM_PROMPT
        if is_new_session:
            memory_context = memory_service.get_memory_context(session_id)
            if memory_context:
                system_prompt = f"{SYSTEM_PROMPT}\n\n{memory_context}"

        history = message_service.get_session_messages(session_id)
        reply = llm_service.generate_reply([{"role": "system", "content": system_prompt}] + history)
        message_service.save_message(session_id, "assistant", reply)

        audio_reply = elevenlabs_service.synthesize_speech(reply)
    except Exception:
        reply = FALLBACK_TEXT
        try:
            audio_reply = elevenlabs_service.synthesize_speech(reply)
        except Exception:
            audio_reply = b""

    return ChatResponse(
        session_id=session_id,
        transcript=transcript,
        reply=reply,
        audio_base64=base64.b64encode(audio_reply).decode("ascii"),
    )
