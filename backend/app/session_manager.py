"""Session management for conversation state and PersonaPlex connections."""
import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ConversationState(str, Enum):
    """Conversation state machine states."""
    GREETING = "greeting"
    IDENTIFY_INTENT = "identify_intent"
    COLLECTING_RESERVATION = "collecting_reservation"
    CHECKING_AVAILABILITY = "checking_availability"
    OFFERING_ALTERNATIVES = "offering_alternatives"
    CONFIRMING = "confirming"
    COMPLETE = "complete"
    FAQ_MODE = "faq_mode"
    MODIFY_FLOW = "modify_flow"
    CANCEL_FLOW = "cancel_flow"
    WAITLIST_FLOW = "waitlist_flow"


@dataclass
class ExtractedInfo:
    """Information extracted from conversation."""
    guest_name: Optional[str] = None
    phone: Optional[str] = None
    party_size: Optional[int] = None
    date_time: Optional[datetime] = None
    area_pref: Optional[str] = None
    notes: Optional[str] = None
    intent: Optional[str] = None  # reserve, modify, cancel, faq, waitlist
    confirmation_code: Optional[str] = None  # for modify/cancel flows
    
    def to_dict(self) -> dict:
        return {
            "guest_name": self.guest_name,
            "phone": self.phone,
            "party_size": self.party_size,
            "date_time": self.date_time.isoformat() if self.date_time else None,
            "area_pref": self.area_pref,
            "notes": self.notes,
            "intent": self.intent,
            "confirmation_code": self.confirmation_code,
        }
    
    def get_missing_fields(self) -> list[str]:
        """Get list of required fields that are still missing for reservation."""
        required = ["guest_name", "phone", "party_size", "date_time"]
        return [f for f in required if getattr(self, f) is None]


@dataclass
class TranscriptEntry:
    """Single transcript entry."""
    speaker: str  # "user" or "agent"
    text: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
        }


@dataclass
class Session:
    """Conversation session state."""
    session_id: str
    restaurant_id: int
    created_at: datetime
    
    # Persona and voice settings
    persona_type: str = "family"
    voice_id: str = "NATF1"
    custom_prompt: Optional[str] = None
    
    # Conversation state
    state: ConversationState = ConversationState.GREETING
    extracted: ExtractedInfo = field(default_factory=ExtractedInfo)
    transcript: list[TranscriptEntry] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    
    # Connection state
    is_active: bool = True
    user_speaking: bool = False
    agent_speaking: bool = False
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "restaurant_id": self.restaurant_id,
            "created_at": self.created_at.isoformat(),
            "persona_type": self.persona_type,
            "voice_id": self.voice_id,
            "state": self.state.value,
            "extracted": self.extracted.to_dict(),
            "transcript": [t.to_dict() for t in self.transcript],
            "facts": self.facts,
            "missing_fields": self.extracted.get_missing_fields(),
            "is_active": self.is_active,
            "user_speaking": self.user_speaking,
            "agent_speaking": self.agent_speaking,
        }
    
    def add_transcript(self, speaker: str, text: str, confidence: float = None):
        """Add entry to transcript."""
        self.transcript.append(TranscriptEntry(
            speaker=speaker,
            text=text,
            confidence=confidence
        ))
    
    def add_fact(self, fact: str):
        """Add a fact for the agent to use."""
        if fact not in self.facts:
            self.facts.append(fact)
    
    def clear_facts(self):
        """Clear temporary facts."""
        self.facts = []


class SessionManager:
    """Manages all active conversation sessions."""
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(self, restaurant_id: int = 1) -> Session:
        """Create a new session."""
        session_id = str(uuid.uuid4())[:8]
        session = Session(
            session_id=session_id,
            restaurant_id=restaurant_id,
            created_at=datetime.utcnow()
        )
        
        async with self._lock:
            self._sessions[session_id] = session
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self._sessions.get(session_id)
    
    async def update_session(self, session_id: str, **kwargs) -> Optional[Session]:
        """Update session attributes."""
        session = self._sessions.get(session_id)
        if session:
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
        return session
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
        return False
    
    async def get_active_sessions(self) -> list[Session]:
        """Get all active sessions."""
        return [s for s in self._sessions.values() if s.is_active]
    
    def update_extracted_info(self, session_id: str, **kwargs):
        """Update extracted information for a session."""
        session = self._sessions.get(session_id)
        if session:
            for key, value in kwargs.items():
                if hasattr(session.extracted, key):
                    setattr(session.extracted, key, value)
    
    def transition_state(self, session_id: str, new_state: ConversationState):
        """Transition session to a new conversation state."""
        session = self._sessions.get(session_id)
        if session:
            session.state = new_state


# Global session manager instance
session_manager = SessionManager()
