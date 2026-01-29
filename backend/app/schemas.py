"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models import ReservationStatus, WaitlistStatus, TableArea


# ============== Session Schemas ==============

class SessionCreate(BaseModel):
    """Create a new conversation session."""
    restaurant_id: int = 1


class SessionResponse(BaseModel):
    """Session creation response."""
    session_id: str
    created_at: datetime


class PersonaUpdate(BaseModel):
    """Update session persona (text prompt)."""
    persona_type: str = Field(..., description="fine_dining, family, sports_bar")
    custom_prompt: Optional[str] = None


class VoiceUpdate(BaseModel):
    """Update session voice embedding."""
    voice_id: str = Field(..., description="NATF0, NATF1, NATF2, NATM0, NATM1, NATM2, etc.")


# ============== Reservation Schemas ==============

class AvailabilityCheck(BaseModel):
    """Check availability request."""
    date_time: datetime
    party_size: int
    area_pref: Optional[TableArea] = None


class TimeSlot(BaseModel):
    """Available time slot."""
    time: datetime
    area: TableArea
    tables_available: int


class AvailabilityResponse(BaseModel):
    """Availability check response."""
    requested_available: bool
    requested_slot: Optional[TimeSlot] = None
    alternatives: List[TimeSlot] = []


class ReservationCreate(BaseModel):
    """Create reservation request."""
    guest_name: str
    phone: str
    party_size: int
    start_time: datetime
    area_pref: Optional[TableArea] = None
    notes: Optional[str] = None


class ReservationModify(BaseModel):
    """Modify reservation request."""
    reservation_id: Optional[int] = None
    confirmation_code: Optional[str] = None
    guest_name: Optional[str] = None
    phone: Optional[str] = None
    party_size: Optional[int] = None
    start_time: Optional[datetime] = None
    area_pref: Optional[TableArea] = None
    notes: Optional[str] = None


class ReservationCancel(BaseModel):
    """Cancel reservation request."""
    reservation_id: Optional[int] = None
    confirmation_code: Optional[str] = None
    phone: Optional[str] = None


class ReservationResponse(BaseModel):
    """Reservation response."""
    id: int
    confirmation_code: str
    guest_name: str
    phone: str
    party_size: int
    start_time: datetime
    area_pref: Optional[TableArea]
    notes: Optional[str]
    status: ReservationStatus

    class Config:
        from_attributes = True


# ============== Waitlist Schemas ==============

class WaitlistAdd(BaseModel):
    """Add to waitlist request."""
    guest_name: str
    phone: str
    party_size: int
    notes: Optional[str] = None


class WaitlistResponse(BaseModel):
    """Waitlist entry response."""
    id: int
    guest_name: str
    phone: str
    party_size: int
    position: int
    estimated_wait_min: int
    status: WaitlistStatus

    class Config:
        from_attributes = True


# ============== SMS Schemas ==============

class SMSNotification(BaseModel):
    """Send SMS notification."""
    phone: str
    message_type: str = Field(..., description="confirmation, reminder, waitlist_ready")
    reservation_id: Optional[int] = None
    custom_message: Optional[str] = None


class SMSResponse(BaseModel):
    """SMS send response."""
    success: bool
    message_sid: Optional[str] = None
    error: Optional[str] = None


# ============== Transcript & Extraction Schemas ==============

class TranscriptEntry(BaseModel):
    """Single transcript entry."""
    speaker: str = Field(..., description="user or agent")
    text: str
    timestamp: datetime
    confidence: Optional[float] = None


class ExtractedFields(BaseModel):
    """Fields extracted from conversation."""
    guest_name: Optional[str] = None
    phone: Optional[str] = None
    party_size: Optional[int] = None
    date_time: Optional[datetime] = None
    area_pref: Optional[TableArea] = None
    notes: Optional[str] = None
    intent: Optional[str] = None  # reserve, modify, cancel, faq, waitlist


class ConversationState(BaseModel):
    """Current conversation state."""
    session_id: str
    state: str  # greeting, collecting, checking, confirming, complete, faq
    extracted: ExtractedFields
    transcript: List[TranscriptEntry]
    missing_fields: List[str]
    facts: List[str]


# ============== WebSocket Message Schemas ==============

class WSMessage(BaseModel):
    """WebSocket message wrapper."""
    type: str  # audio, transcript, extraction, state, error, control
    data: dict


class AudioChunk(BaseModel):
    """Audio chunk for streaming."""
    audio: bytes  # base64 encoded
    sample_rate: int = 24000
    channels: int = 1


class ControlMessage(BaseModel):
    """Control message for session."""
    action: str  # start, stop, mute, unmute, inject_fact
    payload: Optional[dict] = None
