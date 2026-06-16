from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user_id
from app.models.chat import NoteDetail, NoteSummary
from app.services import note_service

router = APIRouter()


@router.get("/notes", response_model=list[NoteSummary])
def list_notes(user_id: str = Depends(get_current_user_id)):
    try:
        return note_service.list_notes(user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list notes: {e}")


@router.get("/notes/{note_id}", response_model=NoteDetail)
def get_note(note_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        note = note_service.get_note(note_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch note: {e}")
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        note_service.delete_note(note_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to delete note: {e}")
