import base64
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, UploadFile

from app.core.auth import get_current_user_id
from app.models.chat import (
    ChatResponse,
    PendingActionRequest,
    PendingActionView,
)
from app.prompts.calendar import build_calendar_prompt
from app.prompts.system import SYSTEM_PROMPT
from app.services import (
    assistant_tools,
    deepgram_service,
    elevenlabs_service,
    llm_service,
    memory_service,
    message_service,
    session_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()

FALLBACK_TEXT = "Sorry, something went wrong. Please try again."

MAX_TOOL_ROUNDS = 4


@router.post("/chat", response_model=ChatResponse)
async def chat(
    audio: UploadFile,
    session_id: str | None = Form(None),
    timezone: str | None = Form(None),
    user_id: str = Depends(get_current_user_id),
):
    if session_id and session_service.touch_session(session_id, user_id):
        pass
    else:
        session_id = session_service.get_or_create_session(user_id)

    transcript = ""
    pending_action_view = None
    try:
        audio_bytes = await audio.read()
        transcript = deepgram_service.transcribe_audio(audio_bytes)
        message_service.save_message(session_id, "user", transcript)

        history = message_service.get_session_messages(session_id, user_id)

        system_prompt = SYSTEM_PROMPT
        if len(history) == 1:
            session_service.mark_session_non_empty(session_id, user_id)
            memory_context = memory_service.get_memory_context(session_id, user_id)
            if memory_context:
                system_prompt = f"{SYSTEM_PROMPT}\n\n{memory_context}"

        timezone_name = assistant_tools.get_effective_timezone(user_id, timezone)
        pending_action = session_service.get_pending_action(session_id, user_id)
        system_prompt = f"{system_prompt}\n\n{build_calendar_prompt(datetime.now(UTC), timezone_name, pending_action)}"

        tools = assistant_tools.get_available_tools(pending_action)
        messages = [{"role": "system", "content": system_prompt}] + history

        reply = None
        pending_action_changed = False

        for _ in range(MAX_TOOL_ROUNDS):
            model_response = llm_service.generate_with_tools(messages, tools)

            if model_response["type"] == "text":
                reply = model_response["text"]
                break

            execution = assistant_tools.execute_tool(
                model_response["name"], model_response["args"], user_id, timezone_name, pending_action
            )

            messages.append({"role": "tool_call", "name": model_response["name"], "args": model_response["args"]})
            messages.append({"role": "tool_result", "name": model_response["name"], "result": execution.result})

            if execution.pending_action is not None:
                pending_action = execution.pending_action
                pending_action_changed = True
                if execution.ui_confirmation:
                    pending_action_view = PendingActionView(**execution.ui_confirmation)
            if execution.clear_pending:
                pending_action = None
                pending_action_changed = True

            tools = assistant_tools.get_available_tools(pending_action)
        else:
            reply = FALLBACK_TEXT

        if pending_action_changed:
            if pending_action is None:
                session_service.clear_pending_action(session_id, user_id)
            else:
                session_service.set_pending_action(session_id, user_id, pending_action)

        message_service.save_message(session_id, "assistant", reply)
        audio_reply = elevenlabs_service.synthesize_speech(reply)
    except Exception:
        logger.exception("/chat failed for session %s; returning spoken fallback", session_id)
        reply = FALLBACK_TEXT
        try:
            audio_reply = elevenlabs_service.synthesize_speech(reply)
        except Exception:
            logger.exception("Fallback TTS also failed for session %s", session_id)
            audio_reply = b""

    return ChatResponse(
        session_id=session_id,
        transcript=transcript,
        reply=reply,
        audio_base64=base64.b64encode(audio_reply).decode("ascii"),
        pending_action=pending_action_view,
    )


@router.post("/chat/pending-action", response_model=ChatResponse)
def handle_pending_action(body: PendingActionRequest, user_id: str = Depends(get_current_user_id)):
    pending_action = session_service.get_pending_action(body.session_id, user_id)

    if pending_action is None:
        reply = "There's nothing waiting for confirmation right now."
    else:
        if body.action == "confirm":
            result = assistant_tools.execute_pending_action(user_id, pending_action)
        else:
            result = assistant_tools.cancel_action()
        session_service.clear_pending_action(body.session_id, user_id)
        reply = assistant_tools.describe_execution_result(result, pending_action)

    message_service.save_message(body.session_id, "assistant", reply)
    try:
        audio_reply = elevenlabs_service.synthesize_speech(reply)
    except Exception:
        audio_reply = b""

    return ChatResponse(
        session_id=body.session_id,
        transcript="",
        reply=reply,
        audio_base64=base64.b64encode(audio_reply).decode("ascii"),
    )
