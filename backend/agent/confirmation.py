"""Deterministic misheard-yes guard for voice confirmation.

A destructive write must never execute on an ambiguous or misheard affirmative, so
confirm_pending_action does not rely on the model's judgement alone: it runs
classify_affirmation over the actual last user transcript and only executes when the
literal words are an unambiguous affirmative.

classify_affirmation returns AFFIRMATIVE / NEGATIVE / AMBIGUOUS over the normalized
utterance:
  1. NEGATIVE wins first: any negation or correction signal (a correction like
     "actually make it 4pm" is a non-confirmation, not a yes).
  2. AFFIRMATIVE only if it has a clear affirmative token, no hedge, and is not a question.
  3. Everything else is AMBIGUOUS (re-ask once, then cancel — never execute).

Pure and agent-local (no I/O); the /chat path is untouched.
"""

import re

AFFIRMATIVE = "affirmative"
NEGATIVE = "negative"
AMBIGUOUS = "ambiguous"

_NEGATIVE_PHRASES = (
    "no", "nope", "nah", "dont", "do not", "stop", "cancel", "cancel it",
    "never mind", "nevermind", "forget it", "wait", "hold on", "not yet",
    "actually", "instead", "rather", "make it", "change it", "change to",
)

_HEDGE_PHRASES = (
    "maybe", "i guess", "guess so", "i think", "probably", "not sure",
    "kind of", "kinda", "sort of", "sorta", "possibly", "perhaps", "i suppose",
    "um", "uh", "hmm", "dunno", "i dunno", "if you want", "i mean",
)

_AFFIRMATIVE_PHRASES = (
    "yes", "yeah", "yep", "yup", "yes please", "confirm", "confirmed", "correct",
    "go ahead", "go for it", "do it", "sounds good", "thats right", "that is right",
    "please do", "absolutely", "definitely", "ok", "okay", "sure", "alright", "all right",
)

_WH_WORDS = frozenset({"what", "why", "when", "where", "who", "how", "which", "should",
                       "could", "would", "can"})


def _normalize(text: str) -> str:
    """Lowercase, replace any non-alphanumeric run with a single space, and pad with
    spaces so phrase lookups match on word boundaries (" no " won't hit "now")."""
    lowered = (text or "").lower()
    collapsed = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    return f" {collapsed} " if collapsed else ""


def _contains_any(padded: str, phrases) -> bool:
    return any(f" {p} " in padded for p in phrases)


def classify_affirmation(text: str) -> str:
    """Classify a spoken response to a confirmation read-back. See module docstring for
    the exact rule. Only AFFIRMATIVE should ever execute a staged destructive action."""
    is_question = (text or "").strip().endswith("?")
    padded = _normalize(text)
    if not padded.strip():
        return AMBIGUOUS

    first = padded.split()[0]
    if first in _WH_WORDS:
        is_question = True

    if _contains_any(padded, _NEGATIVE_PHRASES):
        return NEGATIVE

    has_affirmative = _contains_any(padded, _AFFIRMATIVE_PHRASES)
    has_hedge = _contains_any(padded, _HEDGE_PHRASES)

    if has_affirmative and not has_hedge and not is_question:
        return AFFIRMATIVE

    return AMBIGUOUS
