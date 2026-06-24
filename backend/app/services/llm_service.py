from google import genai
from google.genai import types

from app.core import timing
from app.core.config import settings

_client = genai.Client(api_key=settings.gemini_api_key)

MODEL_NAME = "gemini-2.5-flash"


def generate_with_tools(messages: list[dict], tools: list[types.Tool]) -> dict:
    """messages: the system + user/assistant chat history, plus two extra roles for the tool-calling loop:
    - {"role": "tool_call", "name": str, "args": dict} — a model-issued function call
    - {"role": "tool_result", "name": str, "result": dict} — the result we executed for it

    Returns either {"type": "text", "text": str} or {"type": "tool_call", "name": str, "args": dict}.
    """
    system_instruction = None
    contents = []

    for message in messages:
        role = message["role"]
        if role == "system":
            system_instruction = message["content"]
        elif role == "tool_call":
            contents.append(types.Content(
                role="model",
                parts=[types.Part(function_call=types.FunctionCall(name=message["name"], args=message["args"]))],
            ))
        elif role == "tool_result":
            contents.append(types.Content(
                role="user",
                parts=[types.Part(function_response=types.FunctionResponse(name=message["name"], response=message["result"]))],
            ))
        else:
            model_role = "model" if role == "assistant" else "user"
            contents.append(types.Content(role=model_role, parts=[types.Part(text=message["content"])]))

    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_instruction, tools=tools),
    )

    if timing.TIMING_ENABLED:
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            timing.add_tokens(
                getattr(usage, "prompt_token_count", None),
                getattr(usage, "candidates_token_count", None),
                getattr(usage, "thoughts_token_count", None),
            )

    part = response.candidates[0].content.parts[0]
    if part.function_call:
        return {"type": "tool_call", "name": part.function_call.name, "args": dict(part.function_call.args)}
    return {"type": "text", "text": response.text}
