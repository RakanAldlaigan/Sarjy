"""Standalone LiveKit access-token helper for manual testing (Agents Playground or a
browser client in `dev` mode). The identity here is a throwaway test value.

TTL is set explicitly to 2 hours (the LiveKit default is 6h); it only gates the initial
connection, not reconnects.

Usage (from backend/, with LIVEKIT_API_KEY/SECRET in .env):
    python -m agent.mint_token            # prints a token for room "sarjy-dev"
    python -m agent.mint_token my-room me # custom room / identity
"""

import sys
from datetime import timedelta

from livekit import api

from agent import config

TOKEN_TTL = timedelta(hours=2)
DEFAULT_ROOM = "sarjy-dev"
DEFAULT_IDENTITY = "test-user"


def mint_token(room: str = DEFAULT_ROOM, identity: str = DEFAULT_IDENTITY) -> str:
    if not config.LIVEKIT_API_KEY or not config.LIVEKIT_API_SECRET:
        raise RuntimeError("LIVEKIT_API_KEY / LIVEKIT_API_SECRET missing in backend/.env")
    return (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_ttl(TOKEN_TTL)
        .to_jwt()
    )


if __name__ == "__main__":
    room = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOM
    identity = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_IDENTITY
    token = mint_token(room, identity)
    print(f"# room={room} identity={identity} ttl={TOKEN_TTL}")
    print(f"# url={config.LIVEKIT_URL}")
    print(token)
