import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.models.chat import CalendarStatusResponse, ConnectCalendarResponse
from app.services import google_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/connect", response_model=ConnectCalendarResponse)
def connect_calendar(user_id: str = Depends(get_current_user_id)):
    return ConnectCalendarResponse(authorization_url=google_auth_service.get_authorization_url(user_id))


@router.get("/oauth/callback")
def oauth_callback(code: str | None = Query(None), state: str | None = Query(None), error: str | None = Query(None)):
    if error or not code or not state:
        return RedirectResponse(f"{settings.frontend_url}/?calendar=error")

    try:
        user_id, refresh_token = google_auth_service.exchange_code(code, state)
        google_auth_service.save_credentials(user_id, refresh_token)
    except Exception:
        logger.exception("OAuth callback failed during code exchange")
        return RedirectResponse(f"{settings.frontend_url}/?calendar=error")

    return RedirectResponse(f"{settings.frontend_url}/?calendar=connected")


@router.get("/status", response_model=CalendarStatusResponse)
def calendar_status(user_id: str = Depends(get_current_user_id)):
    return CalendarStatusResponse(connected=google_auth_service.has_calendar_access(user_id))


@router.delete("/disconnect", status_code=204)
def disconnect_calendar(user_id: str = Depends(get_current_user_id)):
    google_auth_service.disconnect(user_id)
