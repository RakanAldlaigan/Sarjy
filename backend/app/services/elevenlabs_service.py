import logging
import time

from elevenlabs import ElevenLabs

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = ElevenLabs(api_key=settings.elevenlabs_api_key)

MAX_TTS_CHARS = 2000


def synthesize_speech(text: str) -> bytes:
    text = _truncate(text, MAX_TTS_CHARS)
    started = time.monotonic()
    try:
        audio_chunks = _client.text_to_speech.convert(
            voice_id=settings.elevenlabs_voice_id,
            text=text,
            model_id="eleven_turbo_v2_5",
            output_format="mp3_44100_128",
        )
        audio = b"".join(audio_chunks)
    except Exception:
        logger.exception(
            "ElevenLabs TTS failed after %.0f ms (%d chars)", (time.monotonic() - started) * 1000, len(text)
        )
        raise

    elapsed_ms = (time.monotonic() - started) * 1000
    logger.info("ElevenLabs TTS ok: %d chars -> %d bytes in %.0f ms", len(text), len(audio), elapsed_ms)
    if not audio:
        logger.warning("ElevenLabs TTS returned 0 bytes for %d chars", len(text))
    return audio


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > 0:
        return truncated[: last_period + 1]
    return truncated.rstrip() + "..."
