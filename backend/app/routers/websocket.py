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

from app.database import get_db, async_session_maker
from app.config import get_settings
from app.session_manager import session_manager, ConversationState
from app.services.extraction_service import ExtractionService
from app.services.reservation_service import ReservationService
from app.services.menu_service import MenuService
from app.personas import build_system_prompt
from app.models import MenuCategory

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(tags=["websocket"])


# Restaurant configs by ID
RESTAURANT_CONFIGS = {
    1: {
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
    },
    2: {
        "name": "Tony's Pizzeria",
        "address": "789 Main Street, Downtown CA 92101",
        "hours": "Daily 11 AM - 11 PM, Late night Fri-Sat until midnight",
        "phone": "(555) 789-0123",
        "policies": {
            "dress_code": "Super casual - come as you are!",
            "cancellation": "Just give us a call if you can't make it.",
            "pets": "Dogs welcome on the patio!",
            "parking": "Street parking and lot behind the building.",
            "children": "Very family-friendly! Kids eat free on Tuesdays.",
            "delivery": "Free delivery within 3 miles. 30-45 minute estimate.",
        }
    }
}

# Default to restaurant 1 for backwards compatibility
DEMO_RESTAURANT = RESTAURANT_CONFIGS[1]


async def handle_menu_query(
    session_id: str,
    query_info: dict,
    websocket: WebSocket,
    restaurant_id: int = 2
) -> list:
    """
    Handle menu queries by querying the database and injecting facts.

    Args:
        session_id: The session ID
        query_info: Query details from extraction service
        websocket: Client WebSocket to send updates
        restaurant_id: Restaurant ID (default 2 for Tony's Pizzeria)

    Returns:
        List of facts that were injected
    """
    async with async_session_maker() as db:
        menu_service = MenuService(db)

        # Determine what to query based on query_info
        category = None
        dietary = None
        items = []

        if query_info.get('category'):
            category_map = {
                'pizza': MenuCategory.PIZZA,
                'appetizer': MenuCategory.APPETIZER,
                'salad': MenuCategory.SALAD,
                'dessert': MenuCategory.DESSERT,
                'beverage': MenuCategory.BEVERAGE,
            }
            category = category_map.get(query_info['category'])

        if query_info.get('dietary'):
            dietary = query_info['dietary']

        if query_info.get('query_type') == 'specific_item' and query_info.get('item_name'):
            # Search for specific item
            items = await menu_service.get_items_by_name(
                restaurant_id=restaurant_id,
                name=query_info['item_name'],
                available_only=True
            )
        elif category:
            # Get items by category
            items = await menu_service.get_menu_items(
                restaurant_id=restaurant_id,
                category=category,
                available_only=True,
                dietary=dietary
            )
        elif dietary:
            # Get items by dietary restriction
            items = await menu_service.get_menu_items(
                restaurant_id=restaurant_id,
                available_only=True,
                dietary=dietary
            )
        elif query_info.get('query_type') == 'browse':
            # Get category summary
            categories = await menu_service.get_categories(restaurant_id)
            summary = menu_service.format_category_summary(categories)
            facts = [summary]

            # Also get a few popular items
            pizzas = await menu_service.get_menu_items(
                restaurant_id=restaurant_id,
                category=MenuCategory.PIZZA,
                available_only=True
            )
            if pizzas:
                pizza_facts = menu_service.format_items_as_facts(pizzas[:6], max_items=6)
                facts.extend(pizza_facts)

            # Inject facts into session
            session = await session_manager.get_session(session_id)
            if session:
                for fact in facts:
                    session.add_fact(fact)

                await websocket.send_json({
                    "type": "menu_facts",
                    "facts": facts,
                    "query_type": "browse"
                })

            return facts

        # Format items as facts
        if items:
            facts = menu_service.format_items_as_facts(items, max_items=10)

            # Inject facts into session
            session = await session_manager.get_session(session_id)
            if session:
                for fact in facts:
                    session.add_fact(fact)

                await websocket.send_json({
                    "type": "menu_facts",
                    "facts": facts,
                    "query_type": query_info.get('query_type'),
                    "category": query_info.get('category'),
                    "item_name": query_info.get('item_name')
                })

            return facts

        return []


class PersonaPlexBridge:
    """Bridge between client WebSocket and PersonaPlex server."""
    
    def __init__(self, session_id: str, client_ws: WebSocket):
        self.session_id = session_id
        self.client_ws = client_ws
        self.personaplex_ws = None
        self.extraction_service = ExtractionService()
        self.is_connected = False
        self._tasks = []
        self.opus_writer = None
        self.opus_reader = None
    
    async def connect_to_personaplex(self, session) -> bool:
        """Establish connection to PersonaPlex server with config in URL."""
        try:
            import websockets
            import sphn
            from urllib.parse import urlencode

            # Initialize Opus encoder/decoder for audio conversion
            # Moshi expects 24kHz mono Opus audio
            self.opus_writer = sphn.OpusStreamWriter(24000)
            self.opus_reader = sphn.OpusStreamReader(24000)

            # Build system prompt for URL query params
            restaurant_config = session.restaurant_config
            if not restaurant_config:
                restaurant_config = RESTAURANT_CONFIGS.get(session.restaurant_id, RESTAURANT_CONFIGS[2])

            system_prompt = build_system_prompt(
                session.persona_type,
                restaurant_config,
                session.facts
            )

            # Build URL with query parameters (PersonaPlex expects config in URL)
            query_params = {
                'text_prompt': system_prompt,
            }
            ws_url = f"{settings.personaplex_ws_url}?{urlencode(query_params)}"

            # Create SSL context for self-signed certs (demo only)
            ssl_context = None
            if settings.personaplex_use_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            logger.info(f"Connecting to PersonaPlex at {settings.personaplex_ws_url}")
            self.personaplex_ws = await websockets.connect(
                ws_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=30
            )

            # Wait for handshake byte from PersonaPlex
            logger.info("Waiting for PersonaPlex handshake...")
            try:
                handshake = await asyncio.wait_for(self.personaplex_ws.recv(), timeout=30.0)
                if isinstance(handshake, bytes) and len(handshake) == 1 and handshake[0] == 0:
                    logger.info("PersonaPlex handshake received - ready for audio")
                else:
                    logger.warning(f"Unexpected handshake: {handshake}")
            except asyncio.TimeoutError:
                logger.warning("Handshake timeout - proceeding anyway")

            self.is_connected = True
            logger.info(f"Connected to PersonaPlex successfully")
            return True

        except ImportError as e:
            logger.error(f"sphn library not available for Opus encoding: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to PersonaPlex: {e}")
            # Continue in simulation mode
            self.is_connected = False
            return False

    async def send_config(self, session):
        """Config is now sent via URL query params in connect_to_personaplex."""
        # Config is passed via URL query parameters, not as a message
        pass
    
    async def forward_to_personaplex(self, audio_data: bytes):
        """Forward audio from client to PersonaPlex.
        
        Client sends raw PCM (16-bit, 24kHz, mono).
        PersonaPlex expects Opus-encoded audio with \x01 prefix.
        """
        if self.personaplex_ws and self.is_connected and self.opus_writer:
            try:
                import numpy as np
                
                # Convert raw PCM bytes to numpy array (16-bit signed int)
                pcm_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Encode PCM to Opus
                opus_bytes = self.opus_writer.append_pcm(pcm_array)
                
                if len(opus_bytes) > 0:
                    # Send with \x01 prefix (audio message type for moshi)
                    await self.personaplex_ws.send(b"\x01" + opus_bytes)
            except Exception as e:
                logger.error(f"Error forwarding to PersonaPlex: {e}")
    
    async def receive_from_personaplex(self):
        """Receive and forward messages from PersonaPlex to client.
        
        PersonaPlex sends:
        - \x01 + opus_bytes: Audio response
        - \x02 + text_bytes: Text token
        """
        if not self.personaplex_ws:
            return
        
        try:
            async for message in self.personaplex_ws:
                if isinstance(message, bytes) and len(message) > 0:
                    kind = message[0]
                    payload = message[1:]
                    
                    if kind == 1:  # Audio data (Opus encoded)
                        if self.opus_reader and len(payload) > 0:
                            # Decode Opus to PCM for client
                            pcm = self.opus_reader.append_bytes(payload)
                            if pcm.shape[-1] > 0:
                                import numpy as np
                                # Convert float32 PCM to int16 bytes
                                pcm_int16 = (pcm * 32767).astype(np.int16)
                                await self.client_ws.send_bytes(pcm_int16.tobytes())
                    
                    elif kind == 2:  # Text token
                        text = payload.decode('utf-8', errors='ignore')
                        if text.strip():
                            # Accumulate text and send as transcript
                            session = await session_manager.get_session(self.session_id)
                            if session:
                                session.add_transcript("agent", text)
                                await self.client_ws.send_json({
                                    "type": "transcript",
                                    "speaker": "agent",
                                    "text": text,
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                                # Update speaking state
                                await self.client_ws.send_json({
                                    "type": "speaking",
                                    "agent_speaking": True,
                                    "user_speaking": False
                                })
                else:
                    # JSON message (if any)
                    try:
                        if isinstance(message, str):
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

                # Check for menu queries and inject facts
                menu_query = self.extraction_service.detect_menu_query(text)
                if menu_query:
                    # Get restaurant_id from session (default to 2 for pizza)
                    restaurant_id = getattr(session, 'restaurant_id', 2)
                    await handle_menu_query(
                        self.session_id, menu_query, self.client_ws, restaurant_id
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

        # Check for menu queries and inject facts
        menu_query = self.extraction_service.detect_menu_query(user_text)
        menu_facts = []
        if menu_query:
            # Get restaurant_id from session (default to 2 for pizza)
            restaurant_id = getattr(session, 'restaurant_id', 2)
            menu_facts = await handle_menu_query(
                self.session_id, menu_query, self.client_ws, restaurant_id
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

        # Generate contextual response (include menu info if we have it)
        response = self._generate_response(session, menu_query, menu_facts)
        
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
    
    def _generate_response(self, session, menu_query=None, menu_facts=None) -> str:
        """Generate a contextual response based on session state."""
        state = session.state
        extracted = session.extracted

        # Use restaurant config from session (loaded from database)
        restaurant = session.restaurant_config
        if not restaurant:
            restaurant_id = getattr(session, 'restaurant_id', 2)
            restaurant = RESTAURANT_CONFIGS.get(restaurant_id, RESTAURANT_CONFIGS[2])

        # Handle menu queries first
        if menu_query and menu_facts:
            if menu_query.get('query_type') == 'browse':
                return (
                    f"At {restaurant['name']}, we have a great selection! "
                    "Our menu includes delicious pizzas, appetizers, salads, desserts, and beverages. "
                    "We have options for everyone - including vegetarian and gluten-free choices. "
                    "What sounds good to you?"
                )
            elif menu_query.get('query_type') == 'specific_item':
                item_name = menu_query.get('item_name', 'that item')
                if menu_facts:
                    return f"Great choice! {menu_facts[0]} Would you like to add that to your order?"
                return f"Let me check on {item_name} for you..."
            elif menu_query.get('category') == 'pizza':
                return (
                    "We have some amazing pizzas! Our most popular ones are the Pepperoni Classic "
                    "and the BBQ Chicken. All pizzas come in Small, Medium, and Large. "
                    "Would you like to hear about our specialty options?"
                )
            elif menu_query.get('dietary'):
                dietary = menu_query.get('dietary', '')
                return (
                    f"We have great {dietary} options! "
                    f"{'Our Veggie Deluxe pizza and Garden Salad are popular vegetarian choices.' if dietary == 'vegetarian' else ''}"
                    f"{'We can make our Veggie Deluxe with vegan cheese!' if dietary == 'vegan' else ''}"
                    f"{'We offer gluten-free crust for an extra $2.' if dietary == 'gluten_free' else ''} "
                    "What would you like to try?"
                )
            else:
                return "Here's what we have available. What would you like to order?"

        if state == ConversationState.GREETING:
            return (
                f"Thank you for calling {restaurant['name']}! "
                "How may I help you today? Would you like to order some pizza or make a reservation?"
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
                f"{restaurant['name']} is open {restaurant['hours']}. "
                f"{restaurant['policies'].get('parking', 'Parking available.')} "
                "Is there anything else you'd like to know?"
            )

        return "I'd be happy to help you with that. What would you like to know about our menu or make a reservation?"


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
    
    # Try to connect to PersonaPlex (config is passed via URL query params)
    bridge = PersonaPlexBridge(session_id, websocket)
    connected = await bridge.connect_to_personaplex(session)

    if connected:
        
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
