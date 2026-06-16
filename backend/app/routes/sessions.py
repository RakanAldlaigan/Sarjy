from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user_id
from app.models.chat import NewSessionResponse, PendingActionView, SessionMessage, SessionSummary
from app.services import message_service, session_service

router = APIRouter()


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(user_id: str = Depends(get_current_user_id)):
    try:
        return session_service.list_sessions(user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list sessions: {e}")


@router.get("/sessions/{session_id}/messages", response_model=list[SessionMessage])
def get_session_messages(session_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        return message_service.get_session_messages(session_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch session messages: {e}")


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        session_service.delete_session(session_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to delete session: {e}")


@router.post("/sessions/new", response_model=NewSessionResponse)
def new_session(user_id: str = Depends(get_current_user_id)):
    try:
        session_id = session_service.get_or_create_empty_session(user_id)
        return NewSessionResponse(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to create session: {e}")


@router.get("/sessions/{session_id}/pending-action", response_model=PendingActionView | None)
def get_session_pending_action(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Returns the live UI-confirmation card for a session, if any (expired actions are
    cleared silently by get_pending_action). Voice-confirmed actions have no card, so None."""
    try:
        pending_action = session_service.get_pending_action(session_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch pending action: {e}")

    if not pending_action or not pending_action.get("requires_ui_confirmation"):
        return None

    return PendingActionView(
        action_type=pending_action["action_type"],
        summary=pending_action.get("summary", ""),
        conflict_warning=pending_action.get("conflict_warning"),
    )
