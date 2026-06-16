create table sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    last_active_at timestamptz not null default now(),
    closed_at timestamptz,
    is_empty boolean not null default true
);

create table messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references sessions(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    created_at timestamptz not null default now()
);

create table notes (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references sessions(id) on delete set null,
    content text not null,
    created_at timestamptz not null default now()
);

create table tasks (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references sessions(id) on delete set null,
    description text not null,
    is_complete boolean not null default false,
    due_at timestamptz,
    created_at timestamptz not null default now()
);

create table reminders (
    id uuid primary key default gen_random_uuid(),
    session_id uuid references sessions(id) on delete set null,
    description text not null,
    remind_at timestamptz not null,
    is_sent boolean not null default false,
    created_at timestamptz not null default now()
);

create table user_preferences (
    key text primary key,
    value jsonb not null,
    updated_at timestamptz not null default now()
);

-- user_preferences: was global (key as sole PK); needs to be per-user
-- to store e.g. timezone
alter table user_preferences
    drop constraint user_preferences_pkey,
    add column user_id uuid not null references auth.users(id) on delete cascade,
    add primary key (user_id, key);

-- google_credentials: one row per user, stores encrypted Google OAuth refresh token
create table google_credentials (
    user_id uuid primary key references auth.users(id) on delete cascade,
    encrypted_refresh_token text not null,
    scopes text not null,
    sarjy_reminders_calendar_id text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- reminders: scope to user directly, allow nullable remind_at for future
-- undated reminders, track mirrored Google Calendar event
alter table reminders
    add column user_id uuid not null references auth.users(id) on delete cascade,
    add column google_event_id text,
    add column updated_at timestamptz not null default now();

alter table reminders
    alter column remind_at drop not null;

-- sessions: holds the in-flight multi-turn confirmation state
alter table sessions
    add column pending_action jsonb,
    add column pending_action_expires_at timestamptz;

-- ── Service role + Row-Level Security ────────────────────────────────────────
-- The backend connects as service_role (bypasses RLS); RLS is the safety net
-- against the public anon key shipped in the frontend bundle. Each user-data
-- table scopes rows to auth.uid(); messages scope through their parent session.

-- Grant service_role DML on every app table. All tables were created via raw
-- SQL and only ever received the anon grant (why the anon-keyed backend worked);
-- service_role bypasses RLS but still needs table-level grants. The default-
-- privileges line ensures tables created later inherit the grant automatically.
grant select, insert, update, delete on public.google_credentials to service_role;
grant select, insert, update, delete on public.sessions to service_role;
grant select, insert, update, delete on public.messages to service_role;
grant select, insert, update, delete on public.reminders to service_role;
grant select, insert, update, delete on public.user_preferences to service_role;
grant select, insert, update, delete on public.notes to service_role;
grant select, insert, update, delete on public.tasks to service_role;
alter default privileges in schema public
    grant select, insert, update, delete on tables to service_role;

alter table google_credentials enable row level security;
create policy "users can manage their own google credentials" on google_credentials
    for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- sessions
alter table sessions enable row level security;
create policy "users manage own sessions" on sessions
    for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- messages: no direct user_id — ownership flows through the parent session
alter table messages enable row level security;
create policy "users manage own messages" on messages
    for all
    using (
        exists (
            select 1 from sessions
            where sessions.id = messages.session_id
              and sessions.user_id = auth.uid()
        )
    )
    with check (
        exists (
            select 1 from sessions
            where sessions.id = messages.session_id
              and sessions.user_id = auth.uid()
        )
    );

-- reminders
alter table reminders enable row level security;
create policy "users manage own reminders" on reminders
    for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- user_preferences
alter table user_preferences enable row level security;
create policy "users manage own preferences" on user_preferences
    for all
    using (user_id = auth.uid())
    with check (user_id = auth.uid());
