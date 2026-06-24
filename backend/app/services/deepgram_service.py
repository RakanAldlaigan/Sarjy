from deepgram import DeepgramClient
from deepgram.environment import DeepgramClientEnvironment

from app.core.config import settings

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
    return response.results.channels[0].alternatives[0].transcript
