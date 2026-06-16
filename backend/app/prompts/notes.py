from google.genai import types

# Hard cap on clarifying questions in the structured-note flow. Enforced server-side in
# assistant_tools (draft_structured_note) and surfaced to the model via build_notes_prompt.
MAX_CLARIFYING_QUESTIONS = 3

NOTES_PROMPT = """You can save notes for the user — pieces of text they want to keep and read
later. There are two ways to capture a note; choose based on what the user wants.

RAW CAPTURE (save_note) — the default for "take a note", "save this", "write this down", "jot
down", "remember that...". Capture what the user said with minimal interference.
- The content must preserve everything the user said, near-verbatim, with exactly one kind of
  edit allowed:
    - Remove ONLY filler words and false starts: hesitations ("uh", "um", "er"), conversational
      filler ("you know", "I mean", "like", "right?"), and words repeated from stuttering or
      self-correction ("the the", "I went— I went").
    - Preserve EVERYTHING else verbatim or near-verbatim: every fact, name, number, date, place,
      detail, specific, and piece of context the user mentioned. Do NOT condense, summarize,
      shorten, paraphrase, reorder, or omit anything. Do NOT decide what is or isn't important.
      If the user said it and it is not a filler word, it goes in the note exactly as they said it.
- Give it a short, clear title (a few words). The title may summarize; the content may not.
- After it saves, confirm briefly that you've saved it.

STRUCTURED NOTE (draft_structured_note → finalize_structured_note) — use when the user wants help
organizing or clarifying their thoughts, or explicitly asks for a structured, organized, or
cleaned-up note ("help me put together a note about...", "organize my thoughts on..."). Here you
may shape and tidy the content — but never invent facts the user didn't give.
- Ask targeted clarifying questions ONLY when something is genuinely ambiguous or a real gap is
  blocking a good note. Ask at most 3, one at a time. If the request is already clear, ask
  nothing and write it. Do not pad with unnecessary questions.
- Each turn, before you reply, call draft_structured_note with the content assembled so far. Set
  asking_clarification to true when your reply will ask another clarifying question. If it
  returns "must_finalize", stop asking and finalize now — you've hit the question limit.
- When you have enough (or hit the limit), call finalize_structured_note with a short title and
  the final, organized content, then confirm briefly that you've saved it.
- Formatting: if the user asks for a format (bullet points, a short summary, etc.), follow it and
  pass it as `format`. If they don't say, use plain prose — or a light structure like bullets if
  it clearly fits. Use judgment; don't overthink it.
- If the user goes off-topic mid-draft, briefly handle it and then offer to continue the note. If
  they clearly want to drop it, call discard_structured_note.

- search_notes: look up the user's saved notes by topic or keywords. Use this when the user asks
  what a note said, to find a note, or to recall something they saved earlier. Mention only the
  single most relevant match, or at most two — never read back the whole list — and keep your
  answer brief.

Notes are different from reminders: a note is text to keep and read; a reminder is a timed
"remember to..." alert. If the user wants to be alerted at a specific time, use create_reminder
instead."""


def build_notes_prompt(note_draft: dict | None) -> str:
    """NOTES_PROMPT plus the live structured-note draft state, when one is in progress —
    mirrors how build_calendar_prompt injects the pending action."""
    if not note_draft:
        return NOTES_PROMPT

    questions_asked = note_draft.get("questions_asked", 0)
    remaining = max(0, MAX_CLARIFYING_QUESTIONS - questions_asked)
    content = note_draft.get("content") or "(nothing captured yet)"
    fmt = note_draft.get("format") or "not specified"

    addendum = (
        "\n\nA STRUCTURED NOTE IS IN PROGRESS — continue it, do not start over.\n"
        f"- Content gathered so far: {content}\n"
        f"- Format: {fmt}\n"
        f"- Clarifying questions asked: {questions_asked} of {MAX_CLARIFYING_QUESTIONS} "
        f"({remaining} remaining).\n"
    )
    if remaining == 0:
        addendum += (
            "- You have reached the clarifying-question limit. Do not ask anything else — finalize "
            "the note now with finalize_structured_note.\n"
        )
    return NOTES_PROMPT + addendum


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

SEARCH_NOTES = types.FunctionDeclaration(
    name="search_notes",
    description=(
        "Search the user's saved notes by topic or keywords — matches against note titles and "
        "content. Use to recall or look up something the user saved earlier."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description="What to look for — keywords or the topic of the note.",
            ),
        },
        required=["query"],
    ),
)

DRAFT_STRUCTURED_NOTE = types.FunctionDeclaration(
    name="draft_structured_note",
    description=(
        "Record progress on a structured note before replying. Call this each turn while building "
        "a structured note, with the content assembled so far. Set asking_clarification to true "
        "when your reply will ask another clarifying question. Returns whether you may ask another "
        "question or must finalize — the clarifying-question limit is enforced here."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "content": types.Schema(
                type=types.Type.STRING,
                description="The structured note content assembled so far, as best you have it.",
            ),
            "asking_clarification": types.Schema(
                type=types.Type.BOOLEAN,
                description="True if your reply this turn will ask the user another clarifying question.",
            ),
            "format": types.Schema(
                type=types.Type.STRING,
                description="Desired format if the user specified one (e.g. 'bullets', 'summary'). Optional.",
                nullable=True,
            ),
        },
        required=["content", "asking_clarification"],
    ),
)

FINALIZE_STRUCTURED_NOTE = types.FunctionDeclaration(
    name="finalize_structured_note",
    description=(
        "Write the finished structured note and end the drafting flow. Call when you have enough "
        "information, or once you have reached the clarifying-question limit."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "title": types.Schema(type=types.Type.STRING, description="A short title naming the note."),
            "content": types.Schema(
                type=types.Type.STRING,
                description="The final, organized note content, formatted as requested if a format was given.",
            ),
            "format": types.Schema(
                type=types.Type.STRING,
                description="The format used, if any (e.g. 'bullets', 'summary'). Optional.",
                nullable=True,
            ),
        },
        required=["title", "content"],
    ),
)

DISCARD_STRUCTURED_NOTE = types.FunctionDeclaration(
    name="discard_structured_note",
    description="Abandon the in-progress structured note draft (e.g. the user no longer wants it).",
    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
)

NOTE_FUNCTION_DECLARATIONS = [
    SAVE_NOTE,
    SEARCH_NOTES,
    DRAFT_STRUCTURED_NOTE,
    FINALIZE_STRUCTURED_NOTE,
    DISCARD_STRUCTURED_NOTE,
]
