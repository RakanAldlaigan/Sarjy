from google import genai
from google.genai import types

from app.core.config import settings

_client = genai.Client(api_key=settings.gemini_api_key)

MODEL_NAME = "gemini-2.5-flash"


def generate_reply(messages: list[dict]) -> str:
    """messages: list of {"role": "system" | "user" | "assistant", "content": str}"""
    system_instruction = None
    contents = []

    for message in messages:
        if message["role"] == "system":
            system_instruction = message["content"]
            continue
        role = "model" if message["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=message["content"])]))

    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    return response.text
