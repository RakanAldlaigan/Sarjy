from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import health, voice

app = FastAPI(title="Sarjy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(voice.router)
