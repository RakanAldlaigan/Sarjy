"""Latency instrumentation harness for the voice turn.

Entirely gated behind the SARJY_TIMING=1 environment flag. With the flag unset,
nothing is installed, no timer is created, and every public entry point here is a
zero-cost no-op — the app behaves exactly as it does without this module.

What it measures (per /chat turn):
  - Wall-clock spans of the external calls: stt (Deepgram), memory (the memory
    lookup), llm (all Gemini rounds), tool_calls (tool execution), tts (ElevenLabs).
  - Every Supabase round-trip individually, captured at the postgrest .execute()
    layer with an auto-derived label ("sessions:UPDATE") and tagged with the
    handler's current phase (session / db_chain / memory / tool / db_persist).
  - Gemini usage_metadata token counts (prompt / completion / thoughts).
  - A coarse utterance-size signal (Deepgram audio duration; transcript length).
  - server_total (true handler wall-clock), env (local/railway), cold (first
    turn after boot).
  - First-token / first-byte slots (llm_first, tts_first) — null today; the
    structure holds them so streaming can light them up later without a reshape.

Double-counting rule: memory and tool_calls are wall-clock spans, and the DB
round-trips they make are tagged "memory"/"tool" — those are reported under their
spans, NOT in the db_session/db_chain/db_persist buckets. So the canonical
non-overlapping decomposition is:
    stt + memory + llm + tool_calls + tts + db_session + db_chain + db_persist
and that sum is <= server_total (remainder = local CPU glue). `total_db` is a
separate cross-cutting view = sum of ALL DB calls (incl. memory/tool) and is
intentionally allowed to overlap the spans.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

TIMING_ENABLED = os.getenv("SARJY_TIMING") == "1"

_current_timer: contextvars.ContextVar = contextvars.ContextVar("sarjy_timer", default=None)
_current_phase: contextvars.ContextVar = contextvars.ContextVar("sarjy_db_phase", default="db_chain")

# Flipped false after the first turn finishes post-boot.
_first_turn_done = False

# DB phases that form the non-overlapping "db" portion of the stage breakdown.
# memory/tool DB calls are excluded here (attributed to their wall-clock spans).
_CHAIN_PHASES = ("session", "db_chain", "db_persist")

# Origins allowed to read the high-resolution Server-Timing values cross-origin
# (Resource Timing API). Mirrors the CORS allow_origins: dev + Vercel prod.
TIMING_ALLOW_ORIGIN = "http://localhost:3000, https://sarjy-mauve.vercel.app"


def _env() -> str:
    return "railway" if os.getenv("RAILWAY_ENVIRONMENT") else "local"


class TurnTimer:
    def __init__(self) -> None:
        global _first_turn_done
        self.turn_id = uuid.uuid4().hex
        self.ts = datetime.now(UTC).isoformat()
        self.env = _env()
        self.cold = not _first_turn_done
        self._t0 = time.perf_counter()

        self.spans: dict[str, float] = {}          # stt, memory, llm, tool_calls, tts
        self.firsts: dict[str, float | None] = {"llm_first": None, "tts_first": None}
        self.db_calls: list[dict] = []             # {"phase","label","ms"}
        self.tool_rounds = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.thoughts_tokens = 0
        self.utterance_ms: float | None = None
        self.transcript_len: int | None = None
        self.server_total: float | None = None

    # --- recording -------------------------------------------------------
    def add_span(self, name: str, ms: float) -> None:
        self.spans[name] = round(self.spans.get(name, 0.0) + ms, 1)

    def set_first(self, name: str, ms: float) -> None:
        if name in self.firsts and self.firsts[name] is None:
            self.firsts[name] = round(ms, 1)

    def add_db(self, phase: str, label: str, ms: float) -> None:
        self.db_calls.append({"phase": phase, "label": label, "ms": round(ms, 1)})

    def add_tokens(self, prompt: int | None, completion: int | None, thoughts: int | None) -> None:
        self.prompt_tokens += prompt or 0
        self.completion_tokens += completion or 0
        self.thoughts_tokens += thoughts or 0

    # --- derived ---------------------------------------------------------
    def db_by_phase(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for call in self.db_calls:
            out[call["phase"]] = round(out.get(call["phase"], 0.0) + call["ms"], 1)
        return out

    def total_db(self) -> float:
        return round(sum(call["ms"] for call in self.db_calls), 1)

    def stages_payload(self) -> dict:
        by = self.db_by_phase()
        return {
            "stt": self.spans.get("stt"),
            "memory": self.spans.get("memory"),
            "llm": self.spans.get("llm"),
            "llm_first": self.firsts["llm_first"],
            "tool_calls": self.spans.get("tool_calls"),
            "tts": self.spans.get("tts"),
            "tts_first": self.firsts["tts_first"],
            "db_session": by.get("session", 0.0),
            "db_chain": by.get("db_chain", 0.0),
            "db_persist": by.get("db_persist", 0.0),
        }

    def finish(self) -> None:
        global _first_turn_done
        if self.server_total is None:
            self.server_total = round((time.perf_counter() - self._t0) * 1000, 1)
            _first_turn_done = True

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "turn_id": self.turn_id,
                "ts": self.ts,
                "env": self.env,
                "cold": self.cold,
                "stages": self.stages_payload(),
                "db_calls": self.db_calls,
                "total_db": self.total_db(),
                "tool_rounds": self.tool_rounds,
                "server_total": self.server_total,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "thoughts_tokens": self.thoughts_tokens,
                "utterance_ms": self.utterance_ms,
                "transcript_len": self.transcript_len,
            },
            separators=(",", ":"),
        )

    def server_timing_header(self) -> str:
        stages = self.stages_payload()
        order = ("stt", "memory", "llm", "tool_calls", "tts", "db_session", "db_chain", "db_persist")
        parts = [f"{k};dur={stages[k]}" for k in order if stages.get(k) is not None]
        parts.append(f"total_db;dur={self.total_db()}")
        if self.server_total is not None:
            parts.append(f"server_total;dur={self.server_total}")
        return ", ".join(parts)


# --- public no-op-when-off API ------------------------------------------


@contextmanager
def start_turn():
    """Wrap the whole handler. Yields the TurnTimer (or None when disabled).
    On exit, finalizes and emits one JSON line to stdout."""
    if not TIMING_ENABLED:
        yield None
        return
    timer = TurnTimer()
    token = _current_timer.set(timer)
    try:
        yield timer
    finally:
        timer.finish()
        _current_timer.reset(token)
        try:
            sys.stdout.write(timer.to_json_line() + "\n")
            sys.stdout.flush()
        except Exception:
            logger.exception("failed to emit timing line")


def get_timer() -> TurnTimer | None:
    if not TIMING_ENABLED:
        return None
    return _current_timer.get()


@contextmanager
def span(name: str, db_phase: str | None = None):
    """Wall-clock span of an external call. Optionally tag nested DB calls with
    db_phase (so memory/tool DB round-trips are attributed to the span)."""
    if not TIMING_ENABLED:
        yield
        return
    timer = _current_timer.get()
    if timer is None:
        yield
        return
    phase_token = _current_phase.set(db_phase) if db_phase is not None else None
    start = time.perf_counter()
    try:
        yield
    finally:
        timer.add_span(name, (time.perf_counter() - start) * 1000)
        if phase_token is not None:
            _current_phase.reset(phase_token)


@contextmanager
def db_phase(name: str):
    """Tag DB round-trips made in this block with `name` (session/db_chain/db_persist)."""
    if not TIMING_ENABLED:
        yield
        return
    token = _current_phase.set(name)
    try:
        yield
    finally:
        _current_phase.reset(token)


def set_transcript_len(n: int) -> None:
    if not TIMING_ENABLED:
        return
    timer = _current_timer.get()
    if timer is not None:
        timer.transcript_len = n


def set_utterance_ms(ms: float) -> None:
    if not TIMING_ENABLED:
        return
    timer = _current_timer.get()
    if timer is not None:
        timer.utterance_ms = round(ms, 1)


def add_tokens(prompt: int | None, completion: int | None, thoughts: int | None) -> None:
    if not TIMING_ENABLED:
        return
    timer = _current_timer.get()
    if timer is not None:
        timer.add_tokens(prompt, completion, thoughts)


def bump_tool_round() -> None:
    if not TIMING_ENABLED:
        return
    timer = _current_timer.get()
    if timer is not None:
        timer.tool_rounds += 1


def attach_header(timer, response) -> None:
    """Finalize the timer and attach the Server-Timing response header."""
    if not TIMING_ENABLED or timer is None:
        return
    timer.finish()
    response.headers["Server-Timing"] = timer.server_timing_header()
    # Timing-Allow-Origin gates the browser from exposing the high-resolution
    # Server-Timing values (and restricted resource-timing attributes) cross-origin.
    response.headers["Timing-Allow-Origin"] = TIMING_ALLOW_ORIGIN


# --- per-round-trip DB instrumentation (installed once, only when enabled) ---


def _db_label(builder) -> str:
    try:
        req = builder.request
        method = getattr(req, "http_method", "?")
        path = str(getattr(req, "path", "")).split("?", 1)[0].rstrip("/")
        table = path.rsplit("/", 1)[-1] or "?"
        return f"{table}:{method}"
    except Exception:
        return "db:?"


def _install_db_instrumentation() -> None:
    try:
        from postgrest._sync.request_builder import SyncQueryRequestBuilder
    except Exception:
        logger.exception("SARJY_TIMING: could not import postgrest builder; DB timing disabled")
        return
    if getattr(SyncQueryRequestBuilder, "_sarjy_timed", False):
        return

    original_execute = SyncQueryRequestBuilder.execute

    def timed_execute(self):
        timer = _current_timer.get()
        if timer is None:
            return original_execute(self)
        phase = _current_phase.get()
        label = _db_label(self)
        start = time.perf_counter()
        try:
            return original_execute(self)
        finally:
            timer.add_db(phase, label, (time.perf_counter() - start) * 1000)

    SyncQueryRequestBuilder.execute = timed_execute
    SyncQueryRequestBuilder._sarjy_timed = True
    logger.info("SARJY_TIMING enabled: per-round-trip DB instrumentation installed")


if TIMING_ENABLED:
    _install_db_instrumentation()
