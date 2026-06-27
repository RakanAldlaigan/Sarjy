from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import calendar, health, livekit, notes, sessions, voice

app = FastAPI(title="Sarjy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://sarjy-mauve.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(voice.router)
app.include_router(sessions.router)
app.include_router(calendar.router)
app.include_router(notes.router)
app.include_router(livekit.router)
