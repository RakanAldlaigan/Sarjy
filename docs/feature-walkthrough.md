# Sarjy — Feature Walkthrough (Presentation Handout)

Speaker notes for how each feature actually works in the code. File references are
`path:line`. Quotes are verbatim from the source.

---

## 1. Calendar conflict detection

**Code:** `calendar_service.detect_conflicts()` (`backend/app/services/calendar_service.py:89`),
formatted by `_format_conflict_warning()` (`backend/app/services/assistant_tools.py:684`).

Two categories, different severity:

- **Overlapping** — candidate `[start, end)` intersects an existing event (half-open interval test):
  ```python
  if event_start < end and event_end > start:
      overlapping.append(event)
  ```
- **Adjacent (back-to-back)** — an event ends exactly when yours starts, or vice versa:
  ```python
  elif event_end == start or event_start == end:
      adjacent.append(event)
  ```

**The window.** Google's `events.list` excludes events ending exactly at `timeMin`, so a
back-to-back event would be invisible. Fetch is padded 1 minute each side:
```python
ADJACENCY_WINDOW = timedelta(minutes=1)
events = find_events(user_id, time_min=start - ADJACENCY_WINDOW,
                     time_max=end + ADJACENCY_WINDOW, max_results=25)
```
The pad only widens retrieval; the exact `<`/`>`/`==` comparisons classify, so the pad never
creates false adjacents.

**Messaging is severity-ranked** — overlap beats adjacency, never both:
```python
if overlapping: return f'Heads up — this overlaps with {names}.'
if adjacent:    return f'Note — this is back-to-back with {names}.'
```

**Update path** (`assistant_tools.py:312`): conflict check runs only when both `new_start` and
`new_end` are given, with `exclude_event_id=event["id"]` so the moved event doesn't flag itself.

**Key decision:** a conflict is a **warning, not a block**. It's appended to the read-back
(`summary_text += f" {conflict_warning}"`); the user still confirms on the card.

---

## 2. Duplicate detection

Two separate checks that decide "duplicate" differently.

**Events** (`_check_duplicates` → `_format_duplicate_warning`, `assistant_tools.py:666`/`:694`):
- Fetch events matching the title `query` in a **±1 day window**:
  ```python
  find_events(user_id, query=summary, time_min=start - timedelta(days=1),
              time_max=end + timedelta(days=1), max_results=10)
  ```
- Google's `q=` is fuzzy, so narrow to **exact case-insensitive title equality**:
  ```python
  matches = [e for e in duplicates if e["summary"].strip().lower() == summary.strip().lower()]
  ```
  Duplicate = same name, within a day. 1 → "an event called X"; many → "several events called X".

**Reminders** (`reminder_service.check_duplicate_reminders`, `reminder_service.py:117`): text only,
no time window — `ilike` with no wildcards = case-insensitive equality on the description.

**Anti-loop guard** (`_handle_create_event`, `assistant_tools.py:234`): the duplicate check runs
only on the first call (no `reminder_minutes_before`). Once the reminder question is answered the
step is skipped, otherwise "keep the name" would loop forever. Like conflicts, a duplicate is a
warning, not a block.

---

## 3. Confirmation state machine / pending action

A pending action is a fully-resolved, not-yet-executed mutation stored on the session row.

**Stored** as JSON on `sessions.pending_action` with a TTL (`session_service.py:140`):
```python
def set_pending_action(session_id, user_id, pending_action, ttl_minutes=5):
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    .update({"pending_action": pending_action,
             "pending_action_expires_at": expires_at.isoformat()})
```
Shape:
```python
{"action_type": "create_calendar_event",
 "params": {...fully resolved, ISO-serialized, IDs already looked up...},
 "requires_ui_confirmation": True/False,
 "summary": <spoken read-back>, "conflict_warning": ...}
```
`params` holds everything needed to execute independently — nothing is re-resolved at execution.

**Two confirmation channels** (keyed off `requires_ui_confirmation`):
- Calendar create/update/delete → `True` → confirmed on the on-screen card via
  `POST /chat/pending-action`.
- Reminder create/update/delete → `False` → confirmed by **voice** (model calls
  `confirm_pending_action` / `cancel_pending_action`).

**Tool gating reinforces it** (`get_available_tools`, `assistant_tools.py:46`): while pending, note
tools are removed; voice confirm/cancel tools are added only for voice-confirmable actions.

**Executed.** `execute_pending_action()` (`assistant_tools.py:104`) is the single executor shared by
both channels — switches on `action_type`, rebuilds datetimes from ISO strings. UI path also gets a
deterministic spoken result from `describe_execution_result()` (no LLM round-trip).

**Expired.** Lazy, read-time expiry (`get_pending_action`, `session_service.py:114`):
```python
if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
    clear_pending_action(session_id, user_id)
    return None
```
No background job — an expired action is simply absent next read.

**Idempotent.** Made idempotent by clearing on resolve. Both confirm/cancel handlers guard a missing
action (`no_pending_action`), and the UI endpoint returns "There's nothing waiting for confirmation
right now." A double-confirm finds nothing the second time and can't execute twice.

**In-place correction:** if the user changes a detail ("actually make it 3pm"), the prompt tells the
model to re-issue the tool call, overwriting the pending action with a corrected one
(`calendar.py:92–112`).

---

## 4. Slot-based resolution

**Code:** `_resolve_target()` (`assistant_tools.py:602`), shared by events and reminders via an
injected `search_fn`. Slots: `title` (name/topic) and `date` (calendar day).

```python
if not title and not date:               # NEITHER
    return "missing_slots", []
if date:                                  # DATE present → that calendar day
    time_min, time_max = _day_window(date, timezone_name)
else:                                     # TITLE only → next 14 days
    time_min, time_max = now, now + RESOLUTION_WINDOW
matches = search_fn(title, time_min, time_max)
if not matches:
    return "not_found", []
if title and len(matches) == 1:           # unique title = high confidence
    return "resolved", matches
return "ambiguous", matches[:MAX_CANDIDATES]   # cap 5
```

| Case | Window | Decision |
|---|---|---|
| Neither | — | `missing_slots` — ask for title or date |
| Title only | now → +14 days | 1 match → resolved; 2+ → ambiguous |
| Date only | that day `[00:00, +1d)` user TZ | **always ambiguous** (even 1 event) |
| Both | that day, title-filtered | 1 → resolved; 2+ → ambiguous |

Deliberate asymmetry: a unique title auto-resolves; a date is a "weak signal," so the code never
auto-picks on date alone (`if title and len(matches) == 1` requires the title).

---

## 5. Tool/function-calling loop in `/chat`

**Code:** route `backend/app/routes/voice.py:35`, model bridge
`backend/app/services/llm_service.py:11`.

Intent detection **is** Gemini function calling — no separate classifier. System + calendar + notes
prompts + tool declarations go to `gemini-2.5-flash`; it emits either a function call or text.
`generate_with_tools` normalizes to `{"type": "tool_call"|"text", ...}` (inspects `parts[0]` — one
call per round).

Loop, capped at **`MAX_TOOL_ROUNDS = 4`**:
```python
for _ in range(MAX_TOOL_ROUNDS):
    model_response = llm_service.generate_with_tools(messages, tools)
    if model_response["type"] == "text":
        reply = model_response["text"]; break
    execution = assistant_tools.execute_tool(...)
    messages.append({"role": "tool_call", ...})
    messages.append({"role": "tool_result", "name": ..., "result": execution.result})
    # apply side effects: pending_action / note_draft / clears
    tools = assistant_tools.get_available_tools(pending_action)   # re-gated each round
else:
    reply = FALLBACK_TEXT
```

Slide points:
- **Results feed back** as Gemini `function_response` parts, so the model chains tools (create →
  `reminder_required` → ask → resolve → confirm).
- **Tools recomputed every round** from current pending state — confirm/cancel appear/disappear
  mid-loop.
- **Round cap → spoken fallback** via `for/else`: 4 rounds with no text ⇒ `FALLBACK_TEXT`.
- The route **never raises**: any exception logs and returns a playable spoken fallback, because the
  frontend always expects audio, not an HTTP error.

---

## 6. Reminders: Supabase source of truth + Calendar mirror

**Code:** `backend/app/services/reminder_service.py`.

**Source of truth = Supabase `reminders` table** (`description`, `remind_at`, nullable
`google_event_id`). The Google event is a **mirror**: a 30-min block on a dedicated "Sarjy
Reminders" calendar with a popup at `remind_at`.
```python
REMINDER_EVENT_DURATION = timedelta(minutes=30)
event = create_event(..., start=remind_at, end=remind_at + REMINDER_EVENT_DURATION,
                     reminder_minutes_before=0, calendar_id=calendar_id)
```

**Create** (`:43`): mirror first (retries once, `MIRROR_ATTEMPTS = 2`), then DB insert **regardless**
— if mirroring fails, `google_event_id` is `None` + a `calendar_warning`; the reminder still exists
in Supabase. Calendar is best-effort; Supabase is authoritative.

**Dedicated calendar** (`calendar_service.py:204`): stored id is verified each use and **recreated if
the user deleted it** (404 → re-insert).

**Update** (`:129`): DB first (always), then mirror the change only if a `google_event_id` exists.

**Delete** (`:175`): DB row first, then best-effort delete the mirror; calendar errors swallowed.

**Cleanup of expired** (`_cleanup_expired`, `:63`): lazy, runs at the top of `list_reminders` and
`find_reminders`:
```python
get_client().table("reminders").delete().eq("user_id", user_id)\
    .lt("remind_at", now.isoformat()).execute()
```
Deletes past-due rows from **Supabase only** — the mirror event is left (harmless, and it's what
fired the popup). No cron; cleanup is read-triggered.

---

## 7. Structured note mode

**Code:** prompt `backend/app/prompts/notes.py`; state in `session_service` (`note_draft`); handlers
`assistant_tools.py:521`.

**Draft storage:** JSON on `sessions.note_draft`. `set_note_draft` stamps `updated_at` every write;
`get_note_draft` lazily expires drafts older than `NOTE_DRAFT_TTL_MINUTES = 30`. Shape:
`{"content", "format", "questions_asked", "updated_at"}`.

**Injection** (mirrors the pending-action pattern). `build_notes_prompt` appends a live addendum each
turn (`notes.py:52`):
```
A STRUCTURED NOTE IS IN PROGRESS — continue it, do not start over.
- Content gathered so far: {content}
- Format: {fmt}
- Clarifying questions asked: {questions_asked} of {MAX_CLARIFYING_QUESTIONS} ({remaining} remaining).
```
When `remaining == 0` it adds: *"You have reached the clarifying-question limit. Do not ask anything
else — finalize the note now with finalize_structured_note."*

**3-question cap is server-enforced**, not trusted to the model (`MAX_CLARIFYING_QUESTIONS = 3`):
```python
if args.get("asking_clarification"):
    if draft.get("questions_asked", 0) >= MAX_CLARIFYING_QUESTIONS:
        return ToolExecution(result={"status": "must_finalize"}, note_draft=draft)
    draft["questions_asked"] += 1
    remaining = MAX_CLARIFYING_QUESTIONS - draft["questions_asked"]
    return ToolExecution(result={"status": "ok", "questions_remaining": remaining}, note_draft=draft)
return ToolExecution(result={"status": "ok"}, note_draft=draft)
```
Counter increments only when the model declares `asking_clarification: true`. At the cap the tool
returns `must_finalize` **and** the prompt flips to "stop asking" — both signals push to finalize.

**Drafting contract** (`NOTES_PROMPT`, quoted):
> *Ask targeted clarifying questions ONLY when something is genuinely ambiguous or a real gap is
> blocking a good note. Ask at most 3, one at a time. If the request is already clear, ask nothing
> and write it… Each turn, before you reply, call draft_structured_note with the content assembled
> so far. Set asking_clarification to true when your reply will ask another clarifying question. If
> it returns "must_finalize", stop asking and finalize now…*

**Off-script recovery** (quoted):
> *If the user goes off-topic mid-draft, briefly handle it and then offer to continue the note. If
> they clearly want to drop it, call discard_structured_note.*

`finalize` and `discard` both return `clear_note_draft=True`; the draft survives in the session
(until TTL / discard / finalize), so an interruption doesn't lose gathered content.

---

## 8. Note search

**Code:** `note_service.search_notes` (`backend/app/services/note_service.py:42`).

Tokenize the query, keep words longer than 2 chars, OR case-insensitive substring matches across
**both title and content**:
```python
words = [w for w in re.findall(r"\w+", query) if len(w) > 2] if query else []
if words:
    conditions = [f"title.ilike.%{w}%" for w in words] + [f"content.ilike.%{w}%" for w in words]
    db_query = db_query.or_(",".join(conditions))
```
Logical OR (recall-oriented), `ILIKE '%word%'` substring — **not** full-text or semantic. Ordered
`created_at desc`. No surviving word ⇒ falls back to most-recent.

**Cap:** `SEARCH_MAX_RESULTS = 3` in the DB; the prompt further limits spoken output to *"the single
most relevant match, or at most two — never read back the whole list."*

---

## 9. Raw mode

**Code:** `NOTES_PROMPT` (`notes.py:11`) + the `save_note` `content` description (`notes.py:87`).

Default for "take a note / save this / jot down." Strip-vs-preserve rule (verbatim):
> *Remove ONLY filler words and false starts: hesitations ("uh", "um", "er"), conversational filler
> ("you know", "I mean", "like", "right?"), and words repeated from stuttering or self-correction
> ("the the", "I went— I went").*
> *Preserve EVERYTHING else verbatim or near-verbatim: every fact, name, number, date, place, detail,
> specific, and piece of context… Do NOT condense, summarize, shorten, paraphrase, reorder, or omit
> anything. Do NOT decide what is or isn't important.*
> *Give it a short, clear title… The title may summarize; the content may not.*

The same rule is duplicated on the tool parameter so it holds even if the model leans on the schema.
Server-side, raw save is minimal: strip, derive a ≤6-word title if none, save immediately — **no
confirmation step** (`assistant_tools.py:506`).

---

## 10. Browser autoplay fix

**Code:** `frontend/app/lib/audio.ts` + `frontend/app/components/VoiceInput.tsx`.

**Before** (commit `5a3859b`) — inline, in the same try as the network call:
```js
const audio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
await audio.play();   // autoplay rejection → catch → bogus "something went wrong"
```
Problems: (a) an autoplay block surfaced as a fake error; (b) nothing stopped a prior clip.

**After** — a single shared player (`audio.ts`):
```js
let current: HTMLAudioElement | null = null;

export async function playAudio(base64: string): Promise<void> {
  stopAudio();                                    // stop whatever's playing first
  const audio = new Audio(`data:audio/mpeg;base64,${base64}`);
  current = audio;
  try { await audio.play(); }
  catch (err) { console.warn("Audio playback failed", err); }   // log, don't throw
}

export function stopAudio(): void {
  if (current) { current.pause(); current.currentTime = 0; current = null; }
}
```
What it fixes:
1. **Autoplay rejection no longer surfaces as an error** — `play()` has its own try/catch that logs
   and returns. File comment: *"Playback rejections (e.g. the browser's autoplay policy) are logged,
   not thrown."*
2. **No overlap** — module-level `current` means new audio calls `stopAudio()` first.

`VoiceInput.tsx` now calls `playAudio(result.audioBase64)`; its surrounding try/catch only catches
real `sendAudioToChat` failures, so playback can't trip the "something went wrong" fallback. Playback
still starts within the record-button gesture chain, which is what keeps autoplay permitted; the
try/catch is the safety net.

---

## 11. System prompts

Assembled per-request: `SYSTEM_PROMPT` (+ memory on first turn) + calendar prompt + notes prompt
(`voice.py:56–67`). Live state (pending action, note draft, question budget, current time/timezone)
is injected fresh each turn.

### `system.py` (full)
```python
SYSTEM_PROMPT = (
    "You are Sarjy, a voice assistant that helps users capture notes, tasks, and reminders. "
    "Be concise — your responses will be spoken aloud, so avoid long paragraphs, bullet points, "
    "or markdown formatting. Respond naturally as if speaking."
)
```
Whole prompt is shaped by the voice channel ("spoken aloud," "avoid… markdown," "as if speaking").
Change-protected per backend CLAUDE.md.

### `calendar.py` — behavior guidance to highlight
- **Staged event creation** — model reacts to `duplicate_warning` → `reminder_required` →
  `confirmation_required`, "one step at a time."
- **Anti-loop / anti-tamper duplicate handling** — "offer exactly two options… Never modify, rename,
  or otherwise touch the existing event(s)… do not call the tool again until you also have the
  reminder answer."
- **Slot resolution** explained to the model (title-only / date-only / both / time-alone) + the four
  return statuses — the prompt half of `_resolve_target`.
- **Confirmation-channel split** — "Calendar event changes… are confirmed on an on-screen card…
  a spoken 'yes' does not confirm them. Reminder changes are confirmed by voice."
- **Anti-hallucination** — "Never guess or invent events," "do not make up a schedule," "Do not
  retry — just report it."
- `build_calendar_prompt` appends current date/time + timezone and, when pending, channel-specific
  correct-vs-drop instructions.

### `notes.py` — behavior guidance to highlight
- **Raw-vs-structured routing** by trigger phrase.
- **Verbatim-preservation block** for raw mode (caps to fight summarizing).
- **Clarifying-question discipline** for structured mode + the `must_finalize` stop signal.
- **Notes-vs-reminders disambiguation** — "a note is text to keep and read; a reminder is a timed
  'remember to...' alert… use create_reminder instead."
- **Search read-back restraint** — "at most two — never read back the whole list."

**Cross-cutting design point:** guidance is stated **twice** — in the prose prompt and in each tool's
description/parameters — so rules hold whether the model reasons from the system prompt or the
function schema.
