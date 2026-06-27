from supabase import Client, create_client

from app.core.config import settings

_client: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_client() -> Client:
    return _client
