"""Auth bridge for the LiveKit hybrid: mints a LiveKit AccessToken on our backend,
behind the existing Supabase-JWT check. The verified Supabase user_id is stamped as the
token identity, so the agent reads participant.identity -> user_id and the user-scoped
security model is preserved.

Separate from backend/agent/mint_token.py, which mints a throwaway-identity token for
manual dev/Playground testing only. LIVEKIT_API_SECRET only ever signs the JWT here,
server-side; the frontend receives the minted token (+ public URL + room), never the secret.
"""

import json
import uuid
from datetime import timedelta

from livekit import api
from livekit.protocol.agent_dispatch import RoomAgentDispatch
from livekit.protocol.room import RoomConfiguration

from app.core.config import settings

TOKEN_TTL = timedelta(hours=2)


def room_name_for_user(user_id: str) -> str:
    """Per-session room, derived server-side from the verified identity (never client
    input), with a fresh uuid suffix per connect so every connect creates a brand-new room.
    This fixes the reconnect bug: a fixed per-user room could outlive its agent, and
    automatic dispatch only fired on room creation, so a reconnect latched onto a dead
    agent. Security is unchanged — the user_id prefix comes from the verified identity and
    the grant scopes room_join to this room."""
    return f"sarjy-{user_id}-{uuid.uuid4().hex[:8]}"


def mint_access_token(user_id: str, room: str) -> str:
    """Mint a LiveKit join token carrying `user_id` as identity, scoped to `room`.

    Raises RuntimeError if the LiveKit API credentials are not configured, so the
    route can surface a clear 503 rather than emitting an unsigned/garbage token.
    """
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise RuntimeError("LIVEKIT_API_KEY / LIVEKIT_API_SECRET not configured")

    dispatch = RoomAgentDispatch(
        agent_name=settings.livekit_agent_name,
        metadata=json.dumps({"user_id": user_id}),
    )

    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(user_id)
        .with_name(user_id)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_room_config(RoomConfiguration(agents=[dispatch]))
        .with_ttl(TOKEN_TTL)
        .to_jwt()
    )
