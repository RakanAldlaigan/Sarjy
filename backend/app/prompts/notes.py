from google.genai import types

NOTES_PROMPT = """You can save notes for the user — short pieces of text they want to keep and read later.

- save_note: capture a note. Use this when the user asks you to take, save, write down, jot
  down, or remember a note. This is raw capture mode. The content must preserve everything the
  user said, near-verbatim, with exactly one kind of edit allowed:
    - Remove ONLY filler words and false starts: hesitations ("uh", "um", "er"), conversational
      filler ("you know", "I mean", "like", "right?"), and words repeated from stuttering or
      self-correction ("the the", "I went— I went").
    - Preserve EVERYTHING else verbatim or near-verbatim: every fact, name, number, date, place,
      detail, specific, and piece of context the user mentioned. Do NOT condense, summarize,
      shorten, paraphrase, reorder, or omit anything. Do NOT decide what is or isn't important —
      that judgment is not yours to make. If the user said it and it is not a filler word, it
      goes in the note exactly as they said it.
  Give it a short, clear title (a few words) naming what the note is about — the title may
  summarize, but the content may not. After it saves, confirm briefly that you've saved it.

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
                    "The note body. Reproduce what the user said near-verbatim. Remove ONLY filler "
                    "words and false starts (\"uh\", \"um\", \"you know\", \"I mean\", stuttered/repeated "
                    "words). Preserve every fact, name, number, date, detail, and piece of context "
                    "exactly — do not summarize, condense, paraphrase, reorder, or drop anything."
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
