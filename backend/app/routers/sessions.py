"""Session management API endpoints."""
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.session_manager import session_manager, ConversationState
from app.personas import (
    build_system_prompt,
    get_available_personas,
    get_available_voices,
    DEFAULT_VOICES
)
from app.schemas import SessionCreate, SessionResponse, PersonaUpdate, VoiceUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


# Demo restaurant config
DEMO_RESTAURANT = {
    "name": "The Riverside Grill",
    "address": "456 Harbor View Drive, Lakeside CA 92040",
    "hours": "Tuesday-Sunday 11 AM - 10 PM, Closed Mondays",
    "phone": "(555) 234-5678",
    "policies": {
        "dress_code": "Smart casual. No athletic wear please.",
        "cancellation": "24 hours notice appreciated. Same-day cancellations may incur a $20/person fee.",
        "pets": "Service animals welcome inside. Dogs allowed on patio.",
        "parking": "Free parking lot. Valet available Friday-Sunday evenings.",
        "children": "Family-friendly! Kids menu, high chairs, and booster seats available.",
    }
}


@router.post("", response_model=SessionResponse)
async def create_session(request: SessionCreate):
    """Create a new conversation session."""
    session = await session_manager.create_session(request.restaurant_id)
    
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
async def update_persona(session_id: str, request: PersonaUpdate):
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
    
    # Build the new system prompt
    system_prompt = build_system_prompt(
        request.persona_type,
        DEMO_RESTAURANT,
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
