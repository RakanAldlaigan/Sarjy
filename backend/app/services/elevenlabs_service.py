from elevenlabs import ElevenLabs

from app.core.config import settings

_client = ElevenLabs(api_key=settings.elevenlabs_api_key)

MAX_TTS_CHARS = 2000


def synthesize_speech(text: str) -> bytes:
    text = _truncate(text, MAX_TTS_CHARS)
    audio_chunks = _client.text_to_speech.convert(
        voice_id=settings.elevenlabs_voice_id,
        text=text,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    )
    return b"".join(audio_chunks)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind(". ")
    if last_period > 0:
        return truncated[: last_period + 1]
    return truncated.rstrip() + "..."
