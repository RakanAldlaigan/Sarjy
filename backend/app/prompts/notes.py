from google.genai import types

NOTES_PROMPT = """You can save notes for the user — short pieces of text they want to keep and read later.

- save_note: capture a note. Use this when the user asks you to take, save, write down, jot
  down, or remember a note. This is raw capture mode: keep the content close to what the user
  actually said — do not summarize, rewrite, or pad it. Give it a short, clear title (a few
  words) naming what the note is about. After it saves, confirm briefly that you've saved it.

Notes are different from reminders: a note is text to keep and read; a reminder is a timed
"remember to..." alert. If the user wants to be alerted at a specific time, use create_reminder
instead of save_note."""


SAVE_NOTE = types.FunctionDeclaration(
    name="save_note",
    description=(
        "Save a note for the user — text they want to keep and read later. Use for 'take/save/write "
        "down a note' requests. Saves immediately; no confirmation step is needed."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "content": types.Schema(
                type=types.Type.STRING,
                description=(
                    "The note body, kept close to what the user said (raw capture — do not summarize "
                    "or rewrite)."
                ),
            ),
            "title": types.Schema(
                type=types.Type.STRING,
                description="A short title naming what the note is about (a few words).",
            ),
        },
        required=["content", "title"],
    ),
)

NOTE_FUNCTION_DECLARATIONS = [SAVE_NOTE]
