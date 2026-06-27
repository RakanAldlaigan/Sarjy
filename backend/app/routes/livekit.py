"""LiveKit auth-bridge route. POST /livekit/token: behind the Supabase-JWT check, mint
a LiveKit join token carrying the verified user_id as identity."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.models.livekit import LiveKitTokenResponse
from app.services import livekit_service

router = APIRouter(prefix="/livekit", tags=["livekit"])


@router.post("/token", response_model=LiveKitTokenResponse)
def create_livekit_token(user_id: str = Depends(get_current_user_id)) -> LiveKitTokenResponse:
    """Mint a LiveKit join token for the authenticated user.

    Gated by `get_current_user_id` (our ES256/JWKS Supabase verifier) — an
    unauthenticated caller gets 401 and cannot mint a token. The room is derived
    server-side from the verified user_id, never from client input.
    """
    if not settings.livekit_url:
        raise HTTPException(status_code=503, detail="LiveKit is not configured")

    room = livekit_service.room_name_for_user(user_id)
    try:
        token = livekit_service.mint_access_token(user_id, room)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return LiveKitTokenResponse(token=token, url=settings.livekit_url, room=room)
