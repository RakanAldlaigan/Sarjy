"""EU-placed streaming voice agent worker: streaming STT (EU Deepgram) -> Gemini
-> streaming TTS with VAD turn-taking. A separate worker process that does not touch
the /chat pipeline.

Run locally (uses your mic/speakers; no LiveKit server or token needed):
    cd backend && python -m agent.main console
First run only, to fetch the bundled VAD model weights:
    cd backend && python -m livekit.agents download-files
Connect a real client (needs LIVEKIT_* env + a token from mint_token.py):
    cd backend && python -m agent.main dev
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime

from google.genai import types
from livekit.agents import (
    Agent,
    AgentSession,
    EndpointingOptions,
    JobContext,
    RoomInputOptions,
    TurnHandlingOptions,
    WorkerOptions,
    cli,
    inference,
)
from livekit.plugins import deepgram, elevenlabs, google

from agent import config, tools
from agent.tools import ALL_TOOLS
from agent.userdata import SarjyUserData
from app.prompts.calendar import build_calendar_prompt
from app.prompts.notes import build_notes_prompt
from app.prompts.system import SYSTEM_PROMPT
from app.services import assistant_tools

logger = logging.getLogger("sarjy-agent")


def build_instructions(timezone_name: str) -> str:
    """The same SYSTEM_PROMPT + calendar + notes prose /chat uses, with the calendar
    prose in voice-confirmation mode (read-back + strict-yes protocol)."""
    prompt = SYSTEM_PROMPT
    prompt += f"\n\n{build_calendar_prompt(datetime.now(UTC), timezone_name, None, confirm_mode='voice')}"
    prompt += f"\n\n{build_notes_prompt(None)}"
    return prompt


class Assistant(Agent):
    def __init__(self, timezone_name: str) -> None:
        super().__init__(instructions=build_instructions(timezone_name), tools=ALL_TOOLS)


def _user_id_from_metadata(raw: str) -> str | None:
    """Read user_id from explicit-dispatch job metadata (a JSON string set by the
    backend in the token's RoomConfiguration). Returns None for empty/invalid;
    never raises."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("job metadata is not valid JSON; ignoring and falling back")
        return None
    user_id = data.get("user_id") if isinstance(data, dict) else None
    return user_id or None


async def entrypoint(ctx: JobContext) -> None:
    missing = config.missing_provider_keys()
    if missing:
        raise RuntimeError(
            f"Missing required provider keys in backend/.env: {', '.join(missing)}"
        )

    logger.info("livekit creds present: %s", config.livekit_creds_present())

    await ctx.connect()

    user_id = _user_id_from_metadata(ctx.job.metadata)
    if user_id:
        logger.info("user_id from job metadata (explicit dispatch): %s", user_id)
    else:
        user_id = os.getenv("SARJY_DEV_USER_ID")
        if user_id:
            logger.info("user_id from SARJY_DEV_USER_ID shim (console/dev): %s", user_id)
        else:
            participant = await ctx.wait_for_participant()
            user_id = participant.identity
            logger.info("user_id from participant.identity (fallback): %s", user_id)

    timezone_name = await asyncio.to_thread(assistant_tools.get_effective_timezone, user_id, None)
    logger.info("resolved timezone: %s", timezone_name)

    thinking_config = types.ThinkingConfig(thinking_budget=config.GEMINI_THINKING_BUDGET)

    logger.info(
        "agent config | deepgram model=%s base_url=%s | gemini model=%s thinking_budget=%s | "
        "eleven model=%s voice_id=%s | min_endpointing_delay=%ss",
        config.DEEPGRAM_MODEL,
        config.DEEPGRAM_BASE_URL,
        config.GEMINI_MODEL,
        config.GEMINI_THINKING_BUDGET,
        config.ELEVEN_MODEL,
        config.ELEVEN_VOICE_ID,
        config.MIN_ENDPOINTING_DELAY,
    )

    userdata = SarjyUserData(user_id=user_id, timezone_name=timezone_name)

    session = AgentSession[SarjyUserData](
        userdata=userdata,
        stt=deepgram.STT(
            api_key=config.DEEPGRAM_API_KEY,
            model=config.DEEPGRAM_MODEL,
            language=config.DEEPGRAM_LANGUAGE,
            base_url=config.DEEPGRAM_BASE_URL,
        ),
        llm=google.LLM(
            api_key=config.GEMINI_API_KEY,
            model=config.GEMINI_MODEL,
            thinking_config=thinking_config,
        ),
        tts=elevenlabs.TTS(
            api_key=config.ELEVEN_API_KEY,
            voice_id=config.ELEVEN_VOICE_ID,
            model=config.ELEVEN_MODEL,
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            endpointing=EndpointingOptions(min_delay=config.MIN_ENDPOINTING_DELAY),
        ),
    )

    await session.start(
        agent=Assistant(timezone_name),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            close_on_disconnect=True,
            delete_room_on_close=True,
        ),
    )

    tools.schedule_credential_prewarm(userdata)

    await session.generate_reply(instructions="Greet the user in one short sentence.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=config.AGENT_NAME))
