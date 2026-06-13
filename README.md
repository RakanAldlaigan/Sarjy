# Sarjy

A voice assistant web app for capturing notes, tasks, and reminders by voice,
with cross-session memory and Google Calendar integration. Built as a
take-home project for Sarj.

Core loop: voice input → speech-to-text → LLM → text-to-speech → voice output.

## Current status

- Voice conversations: record audio, transcribe it, get an LLM reply, and
  hear it spoken back
- Session history with a sidebar to browse, switch between, and delete past
  sessions
- Cross-session memory: the assistant recalls relevant context from earlier
  conversations
- Google sign-in via Supabase Auth, with all sessions, messages, and memory
  scoped per user

## Tech stack

- **Frontend**: Next.js (App Router, TypeScript, Tailwind CSS)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL via Supabase
- **Auth**: Google OAuth via Supabase Auth
- **STT**: Deepgram
- **TTS**: ElevenLabs
- **LLM**: Google Gemini 2.5 Flash

## To run locally

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`. Requires a `.env` file in `backend/` (see
`.env.example` at the project root):

```
GEMINI_API_KEY=
DEEPGRAM_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
SUPABASE_URL=
SUPABASE_ANON_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:3000`. Requires a `frontend/.env.local` file:

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

### Supabase setup

Run the SQL in `backend/app/db/schema.sql` against your Supabase project,
and enable the Google provider in Supabase Auth settings using the same
Google OAuth client credentials.

## Next steps

- Google Calendar integration (create/view events by voice)
- "Discussion mode" for open-ended conversation beyond notes/tasks/reminders
- Smarter cross-session memory — currently a flat cap on recent messages
  across past sessions; ideally summarization or a dedicated facts table
- Deployment (frontend and backend hosting, production env config)
