from supabase import Client, create_client

from app.core.config import settings

# Backend runs as a trusted tier on the service_role key (server-only, never
# shipped to the browser). It bypasses RLS; per-user scoping is enforced in app
# code via .eq("user_id", ...). RLS on the tables guards against the public anon key.
_client: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_client() -> Client:
    return _client
