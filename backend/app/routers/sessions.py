"""Session management API endpoints."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.session_manager import session_manager, ConversationState
from app.services.restaurant_service import RestaurantService
from app.personas import (
    build_system_prompt,
    get_available_personas,
    get_available_voices,
    DEFAULT_VOICES
)
from app.schemas import SessionCreate, SessionResponse, PersonaUpdate, VoiceUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    request: SessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation session with pre-loaded facts from database."""
    # Create the session
    session = await session_manager.create_session(request.restaurant_id)

    # Load all facts from database
    restaurant_service = RestaurantService(db)
    facts = await restaurant_service.load_all_facts(request.restaurant_id)

    # Pre-load facts into session
    for fact in facts:
        session.add_fact(fact)

    # Store restaurant config in session for later use
    restaurant_config = await restaurant_service.get_restaurant_config(request.restaurant_id)
    session.restaurant_config = restaurant_config

    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at
    )


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session state and details."""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.to_dict()


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """End and delete a session."""
    deleted = await session_manager.delete_session(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "deleted", "session_id": session_id}


@router.post("/{session_id}/persona")
async def update_persona(
    session_id: str,
    request: PersonaUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update session persona (text prompt)."""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate persona type
    available = get_available_personas()
    if request.persona_type not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid persona. Available: {list(available.keys())}"
        )

    # Update session
    session.persona_type = request.persona_type
    if request.custom_prompt:
        session.custom_prompt = request.custom_prompt

    # Set default voice for persona
    session.voice_id = DEFAULT_VOICES.get(request.persona_type, "NATF1")

    # Get restaurant config from database
    restaurant_service = RestaurantService(db)
    restaurant_config = await restaurant_service.get_restaurant_config(session.restaurant_id)

    # Build the new system prompt with database-backed config
    system_prompt = build_system_prompt(
        request.persona_type,
        restaurant_config,
        session.facts
    )

    return {
        "status": "updated",
        "persona_type": request.persona_type,
        "voice_id": session.voice_id,
        "system_prompt_preview": system_prompt[:500] + "..."
    }


@router.post("/{session_id}/voice")
async def update_voice(session_id: str, request: VoiceUpdate):
    """Update session voice embedding."""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate voice ID
    available = get_available_voices()
    if request.voice_id not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice. Available: {list(available.keys())}"
        )

    session.voice_id = request.voice_id

    return {
        "status": "updated",
        "voice_id": request.voice_id,
        "voice_description": available[request.voice_id]
    }


@router.post("/{session_id}/inject-fact")
async def inject_fact(session_id: str, fact: str):
    """Inject a fact into the session for the agent to use."""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.add_fact(fact)

    return {
        "status": "injected",
        "facts": session.facts
    }


@router.post("/{session_id}/reload-facts")
async def reload_facts(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Reload all facts from database (useful if menu/policies changed)."""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clear existing facts
    session.clear_facts()

    # Reload from database
    restaurant_service = RestaurantService(db)
    facts = await restaurant_service.load_all_facts(session.restaurant_id)

    for fact in facts:
        session.add_fact(fact)

    return {
        "status": "reloaded",
        "facts_count": len(session.facts),
        "facts": session.facts
    }


@router.get("/{session_id}/transcript")
async def get_transcript(session_id: str):
    """Get the full conversation transcript."""
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "transcript": [t.to_dict() for t in session.transcript]
    }


@router.get("/config/personas")
async def list_personas():
    """List available personas."""
    return get_available_personas()


@router.get("/config/voices")
async def list_voices():
    """List available voice embeddings."""
    return get_available_voices()
