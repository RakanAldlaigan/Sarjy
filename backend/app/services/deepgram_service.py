from deepgram import DeepgramClient

from app.core.config import settings

_client = DeepgramClient(api_key=settings.deepgram_api_key)


def transcribe_audio(audio_bytes: bytes) -> str:
    response = _client.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model="nova-2",
        smart_format=True,
    )
    return response.results.channels[0].alternatives[0].transcript
