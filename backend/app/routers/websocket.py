"""WebSocket endpoint for real-time audio streaming and PersonaPlex bridge."""
import asyncio
import json
import base64
import logging
import ssl
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.database import get_db
from app.config import get_settings
from app.session_manager import session_manager, ConversationState
from app.services.extraction_service import ExtractionService
from app.services.reservation_service import ReservationService
from app.personas import build_system_prompt

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["websocket"])


# Demo restaurant config (same as sessions.py)
DEMO_RESTAURANT = {
    "name": "The Riverside Grill",
    "address": "456 Harbor View Drive, Lakeside CA 92040",
    "hours": "Tuesday-Sunday 11 AM - 10 PM, Closed Mondays",
    "phone": "(555) 234-5678",
    "policies": {
        "dress_code": "Smart casual. No athletic wear please.",
        "cancellation": "24 hours notice appreciated.",
        "pets": "Service animals welcome inside. Dogs allowed on patio.",
        "parking": "Free parking lot. Valet available Friday-Sunday evenings.",
        "children": "Family-friendly! Kids menu and high chairs available.",
    }
}


class PersonaPlexBridge:
    """Bridge between client WebSocket and PersonaPlex server."""
    
    def __init__(self, session_id: str, client_ws: WebSocket):
        self.session_id = session_id
        self.client_ws = client_ws
        self.personaplex_ws = None
        self.extraction_service = ExtractionService()
        self.is_connected = False
        self._tasks = []
    
    async def connect_to_personaplex(self) -> bool:
        """Establish connection to PersonaPlex server."""
        try:
            import websockets
            
            # Create SSL context for self-signed certs (demo only)
            ssl_context = None
            if settings.personaplex_use_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            self.personaplex_ws = await websockets.connect(
                settings.personaplex_ws_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=30
            )
            self.is_connected = True
            logger.info(f"Connected to PersonaPlex at {settings.personaplex_ws_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to PersonaPlex: {e}")
            # Continue in simulation mode
            self.is_connected = False
            return False
    
    async def send_config(self, session):
        """Send initial configuration to PersonaPlex."""
        if not self.personaplex_ws:
            return
        
        # Build system prompt
        system_prompt = build_system_prompt(
            session.persona_type,
            DEMO_RESTAURANT,
            session.facts
        )
        
        # Send text prompt configuration
        config_message = {
            "type": "config",
            "text_prompt": system_prompt,
            "voice_id": session.voice_id
        }
        
        try:
            await self.personaplex_ws.send(json.dumps(config_message))
        except Exception as e:
            logger.error(f"Error sending config: {e}")
    
    async def forward_to_personaplex(self, audio_data: bytes):
        """Forward audio from client to PersonaPlex."""
        if self.personaplex_ws and self.is_connected:
            try:
                await self.personaplex_ws.send(audio_data)
            except Exception as e:
                logger.error(f"Error forwarding to PersonaPlex: {e}")
    
    async def receive_from_personaplex(self):
        """Receive and forward messages from PersonaPlex to client."""
        if not self.personaplex_ws:
            return
        
        try:
            async for message in self.personaplex_ws:
                if isinstance(message, bytes):
                    # Audio data - forward to client
                    await self.client_ws.send_bytes(message)
                else:
                    # JSON message (transcript, etc.)
                    try:
                        data = json.loads(message)
                        await self.handle_personaplex_message(data)
                    except json.JSONDecodeError:
                        pass
                        
        except Exception as e:
            logger.error(f"PersonaPlex receive error: {e}")
    
    async def handle_personaplex_message(self, data: dict):
        """Handle messages from PersonaPlex (transcripts, etc.)."""
        msg_type = data.get("type")
        
        session = await session_manager.get_session(self.session_id)
        if not session:
            return
        
        if msg_type == "transcript":
            speaker = data.get("speaker", "agent")
            text = data.get("text", "")
            
            # Add to session transcript
            session.add_transcript(speaker, text)
            
            # Extract information from user speech
            if speaker == "user" and text:
                session.extracted = self.extraction_service.extract_from_text(
                    text, session.extracted
                )
                
                # Determine next state
                new_state = self.extraction_service.determine_next_state(
                    session.state, session.extracted
                )
                if new_state != session.state:
                    session.state = new_state
            
            # Send update to client
            await self.client_ws.send_json({
                "type": "transcript",
                "speaker": speaker,
                "text": text,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Send extraction update
            await self.client_ws.send_json({
                "type": "extraction",
                "data": session.extracted.to_dict(),
                "missing_fields": session.extracted.get_missing_fields()
            })
            
            # Send state update
            await self.client_ws.send_json({
                "type": "state",
                "state": session.state.value
            })
        
        elif msg_type == "speaking":
            is_agent = data.get("agent", False)
            is_user = data.get("user", False)
            
            session.agent_speaking = is_agent
            session.user_speaking = is_user
            
            await self.client_ws.send_json({
                "type": "speaking",
                "agent_speaking": is_agent,
                "user_speaking": is_user
            })
    
    async def close(self):
        """Close PersonaPlex connection."""
        if self.personaplex_ws:
            try:
                await self.personaplex_ws.close()
            except:
                pass
        self.is_connected = False


class SimulatedBridge:
    """Simulated bridge for testing without PersonaPlex server."""
    
    def __init__(self, session_id: str, client_ws: WebSocket):
        self.session_id = session_id
        self.client_ws = client_ws
        self.extraction_service = ExtractionService()
        self.audio_buffer = bytearray()
        self.last_response_time = datetime.utcnow()
    
    async def process_audio(self, audio_data: bytes):
        """Simulate processing audio input."""
        self.audio_buffer.extend(audio_data)
        
        # Simulate user speaking indicator
        await self.client_ws.send_json({
            "type": "speaking",
            "agent_speaking": False,
            "user_speaking": True
        })
    
    async def simulate_response(self, user_text: str):
        """Generate a simulated agent response based on user input."""
        session = await session_manager.get_session(self.session_id)
        if not session:
            return
        
        # Add user transcript
        session.add_transcript("user", user_text)
        await self.client_ws.send_json({
            "type": "transcript",
            "speaker": "user",
            "text": user_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Extract information
        session.extracted = self.extraction_service.extract_from_text(
            user_text, session.extracted
        )
        
        # Send extraction update
        await self.client_ws.send_json({
            "type": "extraction",
            "data": session.extracted.to_dict(),
            "missing_fields": session.extracted.get_missing_fields()
        })
        
        # Determine state and generate response
        new_state = self.extraction_service.determine_next_state(
            session.state, session.extracted
        )
        session.state = new_state
        
        # Generate contextual response
        response = self._generate_response(session)
        
        # Simulate agent speaking
        await self.client_ws.send_json({
            "type": "speaking",
            "agent_speaking": True,
            "user_speaking": False
        })
        
        # Small delay to simulate processing
        await asyncio.sleep(0.5)
        
        # Send agent transcript
        session.add_transcript("agent", response)
        await self.client_ws.send_json({
            "type": "transcript",
            "speaker": "agent",
            "text": response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Send state update
        await self.client_ws.send_json({
            "type": "state",
            "state": session.state.value
        })
        
        # Done speaking
        await asyncio.sleep(0.3)
        await self.client_ws.send_json({
            "type": "speaking",
            "agent_speaking": False,
            "user_speaking": False
        })
    
    def _generate_response(self, session) -> str:
        """Generate a contextual response based on session state."""
        state = session.state
        extracted = session.extracted
        
        if state == ConversationState.GREETING:
            return (
                f"Thank you for calling {DEMO_RESTAURANT['name']}! "
                "How may I help you today? Would you like to make a reservation?"
            )
        
        if state == ConversationState.COLLECTING_RESERVATION:
            next_q = self.extraction_service.get_next_question(extracted)
            if next_q:
                return f"Perfect! {next_q}"
            return "Great, let me check that availability for you."
        
        if state == ConversationState.CHECKING_AVAILABILITY:
            if extracted.date_time and extracted.party_size:
                time_str = extracted.date_time.strftime("%I:%M %p")
                return (
                    f"Let me check availability for {extracted.party_size} "
                    f"at {time_str}... Yes, we have that available! "
                    "Would you like me to confirm this reservation?"
                )
        
        if state == ConversationState.CONFIRMING:
            if extracted.guest_name:
                return (
                    f"Wonderful, {extracted.guest_name}! I have you down for "
                    f"{extracted.party_size} at {extracted.date_time.strftime('%I:%M %p') if extracted.date_time else 'your requested time'}. "
                    "You'll receive a confirmation text shortly. Is there anything else I can help with?"
                )
        
        if state == ConversationState.FAQ_MODE:
            return (
                "Of course! We're open Tuesday through Sunday, 11 AM to 10 PM. "
                "We have free parking in our lot, and valet is available on weekends. "
                "Is there anything else you'd like to know?"
            )
        
        return "I'd be happy to help you with that. Could you tell me a bit more?"


@router.websocket("/ws/sessions/{session_id}/audio")
async def audio_websocket(
    websocket: WebSocket,
    session_id: str
):
    """WebSocket endpoint for real-time audio streaming."""
    await websocket.accept()
    
    session = await session_manager.get_session(session_id)
    if not session:
        await websocket.send_json({
            "type": "error",
            "message": "Session not found"
        })
        await websocket.close()
        return
    
    # Try to connect to PersonaPlex
    bridge = PersonaPlexBridge(session_id, websocket)
    connected = await bridge.connect_to_personaplex()
    
    if connected:
        await bridge.send_config(session)
        
        # Start receive task
        receive_task = asyncio.create_task(bridge.receive_from_personaplex())
        
        try:
            while True:
                data = await websocket.receive()
                
                if "bytes" in data:
                    # Audio data
                    await bridge.forward_to_personaplex(data["bytes"])
                elif "text" in data:
                    # Control message
                    try:
                        msg = json.loads(data["text"])
                        await handle_control_message(session_id, msg, websocket)
                    except json.JSONDecodeError:
                        pass
                        
        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {session_id}")
        finally:
            receive_task.cancel()
            await bridge.close()
    
    else:
        # Use simulated bridge for demo
        sim_bridge = SimulatedBridge(session_id, websocket)
        
        await websocket.send_json({
            "type": "info",
            "message": "Running in simulation mode (PersonaPlex server not available)"
        })
        
        # Send initial greeting
        await sim_bridge.simulate_response("")
        
        try:
            while True:
                data = await websocket.receive()
                
                if "bytes" in data:
                    # Process audio (in simulation, just buffer it)
                    await sim_bridge.process_audio(data["bytes"])
                elif "text" in data:
                    try:
                        msg = json.loads(data["text"])
                        
                        if msg.get("type") == "text_input":
                            # Simulate response to text input
                            await sim_bridge.simulate_response(msg.get("text", ""))
                        else:
                            await handle_control_message(session_id, msg, websocket)
                    except json.JSONDecodeError:
                        pass
                        
        except WebSocketDisconnect:
            logger.info(f"Client disconnected (sim): {session_id}")


async def handle_control_message(session_id: str, msg: dict, websocket: WebSocket):
    """Handle control messages from client."""
    action = msg.get("action")
    session = await session_manager.get_session(session_id)
    
    if not session:
        return
    
    if action == "inject_fact":
        fact = msg.get("fact")
        if fact:
            session.add_fact(fact)
            await websocket.send_json({
                "type": "facts_updated",
                "facts": session.facts
            })
    
    elif action == "update_persona":
        persona_type = msg.get("persona_type")
        if persona_type:
            session.persona_type = persona_type
            await websocket.send_json({
                "type": "persona_updated",
                "persona_type": persona_type
            })
    
    elif action == "update_voice":
        voice_id = msg.get("voice_id")
        if voice_id:
            session.voice_id = voice_id
            await websocket.send_json({
                "type": "voice_updated",
                "voice_id": voice_id
            })
    
    elif action == "clear_transcript":
        session.transcript = []
        await websocket.send_json({
            "type": "transcript_cleared"
        })
    
    elif action == "reset_extraction":
        from app.session_manager import ExtractedInfo
        session.extracted = ExtractedInfo()
        session.state = ConversationState.GREETING
        await websocket.send_json({
            "type": "extraction_reset"
        })
