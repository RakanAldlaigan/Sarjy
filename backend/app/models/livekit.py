from pydantic import BaseModel


class LiveKitTokenResponse(BaseModel):
    """Response for POST /livekit/token. `token` is the minted LiveKit join JWT,
    `url` is the public LIVEKIT_URL the client connects to, `room` is the room the
    token grants join access to. The API secret is NEVER part of this response."""

    token: str
    url: str
    room: str
