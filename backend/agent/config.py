"""Agent-worker config. Reuses the existing backend settings for the shared provider
keys (Deepgram / Gemini / ElevenLabs) and the LiveKit creds."""

import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_BACKEND_ENV)

from app.core.config import settings  # noqa: E402  (must follow load_dotenv above)

DEEPGRAM_MODEL = "nova-2"
DEEPGRAM_BASE_URL = "https://api.eu.deepgram.com/v1/listen"
DEEPGRAM_LANGUAGE = "en-US"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_THINKING_BUDGET = 0

ELEVEN_MODEL = "eleven_turbo_v2_5"
ELEVEN_VOICE_ID = settings.elevenlabs_voice_id

MIN_ENDPOINTING_DELAY = float(os.getenv("SARJY_MIN_ENDPOINTING_DELAY", "0.8"))

DEEPGRAM_API_KEY = settings.deepgram_api_key
GEMINI_API_KEY = settings.gemini_api_key
ELEVEN_API_KEY = settings.elevenlabs_api_key

LIVEKIT_URL = settings.livekit_url
LIVEKIT_API_KEY = settings.livekit_api_key
LIVEKIT_API_SECRET = settings.livekit_api_secret

AGENT_NAME = settings.livekit_agent_name


def missing_provider_keys() -> list[str]:
    """Names of empty required provider keys, for a clear startup error."""
    required = {
        "DEEPGRAM_API_KEY": DEEPGRAM_API_KEY,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "ELEVENLABS_API_KEY": ELEVEN_API_KEY,
        "ELEVENLABS_VOICE_ID": ELEVEN_VOICE_ID,
    }
    return [name for name, value in required.items() if not value]


def livekit_creds_present() -> dict[str, bool]:
    """Present/absent (never the values) for the three LiveKit vars, read from
    os.environ. Used for a startup sanity log."""
    return {name: bool(os.environ.get(name)) for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")}
