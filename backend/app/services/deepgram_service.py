from deepgram import DeepgramClient
from deepgram.environment import DeepgramClientEnvironment

from app.core import timing
from app.core.config import settings

# Backend runs in Amsterdam; use Deepgram's EU in-region endpoint for low-latency STT
# (no US transatlantic hop). The batch transcribe_file path reads environment.base
# (verified in deepgram-sdk 7.3.1), so we override that field rather than httpx_client,
# which the batch path ignores.
_EU_ENVIRONMENT = DeepgramClientEnvironment(
    base="https://api.eu.deepgram.com",
    production=DeepgramClientEnvironment.PRODUCTION.production,
    agent=DeepgramClientEnvironment.PRODUCTION.agent,
    agent_rest=DeepgramClientEnvironment.PRODUCTION.agent_rest,
)

_client = DeepgramClient(api_key=settings.deepgram_api_key, environment=_EU_ENVIRONMENT)


def transcribe_audio(audio_bytes: bytes) -> str:
    response = _client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model="nova-2",
        smart_format=True,
    )
    if timing.TIMING_ENABLED:
        metadata = getattr(response, "metadata", None)
        duration = getattr(metadata, "duration", None) if metadata is not None else None
        if duration is not None:
            timing.set_utterance_ms(duration * 1000)
    return response.results.channels[0].alternatives[0].transcript
