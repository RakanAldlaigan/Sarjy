# Sarjy

A voice assistant web app for capturing notes, tasks, and reminders by voice,
with Google Calendar integration.

## Tech stack

- **Frontend**: Next.js (App Router, TypeScript, Tailwind CSS)
- **Backend**: FastAPI (Python)
- **Realtime voice**: LiveKit (streaming agent worker)
- **Database**: PostgreSQL via Supabase
- **Auth**: Google OAuth via Supabase Auth
- **STT**: Deepgram &nbsp;&nbsp; **TTS**: ElevenLabs &nbsp;&nbsp; **LLM**: Google Gemini 2.5 Flash

## To run locally

The app has three components: the **backend** API, the **agent worker** (the
streaming voice agent), and the **frontend**. Run all three.

### 1. Backend (API)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`. Requires a `backend/.env` file (see the env
vars below).

### 2. Agent worker (streaming voice)

The LiveKit voice agent is a self-contained worker in `backend/agent/`. It vendors
the backend service code it reuses (under `backend/agent/app/`) so it can be built
and deployed on its own, and it has its own dependency set.

```bash
cd backend/agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py download-files   # first run only: fetch VAD / turn-detector weights
python main.py dev
```

The worker reads the same `backend/.env` as the backend. It registers with
LiveKit under `LIVEKIT_AGENT_NAME` and is dispatched into each voice room when
the frontend connects. A `Dockerfile` is included for container deploys (e.g.
LiveKit Cloud: `lk agent deploy` from `backend/agent/`).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:3000`. Requires a `frontend/.env.local` file (see
below).

## Environment variables

### `backend/.env`

Read by both the backend API and the agent worker. See `.env.example` for a
template.

```
# LLM / STT / TTS
GEMINI_API_KEY=
DEEPGRAM_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# Supabase (the backend runs as the service role)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Google OAuth (Calendar access)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/calendar/oauth/callback

# Fernet key used to encrypt stored Google refresh tokens.
# Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
REFRESH_TOKEN_ENCRYPTION_KEY=

# LiveKit (realtime voice)
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
LIVEKIT_AGENT_NAME=sarjy-agent

# URL the frontend is served from (CORS + OAuth redirects)
FRONTEND_URL=http://localhost:3000
```

`GOOGLE_REDIRECT_URI`, `LIVEKIT_AGENT_NAME`, and `FRONTEND_URL` have the
defaults shown above and can be omitted locally. Everything else is required.

### `frontend/.env.local`

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=

# Optional — defaults to http://localhost:8000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The frontend gets its LiveKit connection URL and access token from the backend
at runtime, so no LiveKit variables are needed here.

## Supabase setup

Run the SQL in `backend/app/db/schema.sql` against your Supabase project, and
enable the Google provider in Supabase Auth settings using the same Google
OAuth client credentials.
