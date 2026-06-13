from fastapi import APIRouter, HTTPException

from app.models.chat import NewSessionResponse, SessionMessage, SessionSummary
from app.services import message_service, session_service

router = APIRouter()


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions():
    try:
        return session_service.list_sessions()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list sessions: {e}")


@router.get("/sessions/{session_id}/messages", response_model=list[SessionMessage])
def get_session_messages(session_id: str):
    try:
        return message_service.get_session_messages(session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch session messages: {e}")


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    try:
        session_service.delete_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to delete session: {e}")


@router.post("/sessions/new", response_model=NewSessionResponse)
def new_session():
    try:
        session_id = session_service.get_or_create_empty_session()
        return NewSessionResponse(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to create session: {e}")
