create table sessions (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    last_active_at timestamptz not null default now(),
    closed_at timestamptz
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
