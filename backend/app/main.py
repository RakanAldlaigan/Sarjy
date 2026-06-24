from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import timing
from app.routes import calendar, health, notes, sessions, voice

app = FastAPI(title="Sarjy API")

# Only expose Server-Timing cross-origin when the timing harness is enabled. With
# the flag off this stays [] (Starlette's default), so no Access-Control-Expose-
# Headers header is added and CORS behavior is byte-identical to before.
_expose_headers = ["Server-Timing"] if timing.TIMING_ENABLED else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://sarjy-mauve.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=_expose_headers,
)

app.include_router(health.router)
app.include_router(voice.router)
app.include_router(sessions.router)
app.include_router(calendar.router)
app.include_router(notes.router)
