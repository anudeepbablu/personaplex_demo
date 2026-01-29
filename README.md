# PersonaPlex Restaurant Receptionist Demo

A full-duplex voice AI receptionist for restaurant reservations, powered by NVIDIA PersonaPlex.

![Front Desk Console](docs/screenshot.png)

## Features

- **Full-Duplex Voice**: Natural conversation with interruption handling
- **Persona Control**: Switch between Fine Dining, Family, and Sports Bar personalities
- **Voice Selection**: Multiple natural voice options (NATF/NATM embeddings)
- **Real-time Extraction**: Automatic extraction of reservation details
- **Live Transcript**: See the conversation as it happens
- **Reservation Management**: Create, modify, cancel reservations
- **Waitlist Support**: Add guests to waitlist when fully booked
- **SMS Notifications**: Send confirmation texts (optional Twilio integration)

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React UI      │◄───►│  FastAPI Backend │◄───►│  PersonaPlex    │
│  (Front Desk)   │     │   (Orchestrator) │     │    Server       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        │                        ▼
        │               ┌──────────────────┐
        │               │   SQLite DB      │
        │               │  (Reservations)  │
        │               └──────────────────┘
        │
        ▼
   WebSocket Audio Streaming
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- NVIDIA GPU (recommended for PersonaPlex)
- `libopus-dev` (for audio codec)

### 1. Install PersonaPlex

Follow the [NVIDIA PersonaPlex setup instructions](https://github.com/NVIDIA/personaplex):

```bash
# Install moshi package
pip install moshi

# Accept model license on Hugging Face
# Set HF_TOKEN environment variable

# Launch PersonaPlex server
python -m moshi.server --gradio-tunnel
```

### 2. Start the Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 8000
```

### 3. Start the Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

### 4. Open the Console

Navigate to http://localhost:3000

## Configuration

### Environment Variables

Create a `.env` file in the `backend` directory:

```env
# PersonaPlex Server
PERSONAPLEX_HOST=localhost
PERSONAPLEX_PORT=8998
PERSONAPLEX_USE_SSL=true

# Hugging Face (for PersonaPlex)
HF_TOKEN=your_token_here

# Twilio (optional - for SMS)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890

# Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
```

## API Endpoints

### Sessions
- `POST /sessions` - Create new session
- `GET /sessions/{id}` - Get session state
- `POST /sessions/{id}/persona` - Update persona
- `POST /sessions/{id}/voice` - Update voice
- `WS /ws/sessions/{id}/audio` - Audio streaming

### Reservations
- `POST /reservations/check` - Check availability
- `POST /reservations/create` - Create reservation
- `POST /reservations/modify` - Modify reservation
- `POST /reservations/cancel` - Cancel reservation
- `POST /reservations/waitlist/add` - Add to waitlist
- `POST /reservations/notify/sms` - Send SMS

## Demo Scenarios

### 1. Reservation with Interruption
> "I'd like a table for 4 at 7... actually, make that 6... and can we sit outside?"

Shows the agent handling corrections smoothly.

### 2. Fully Booked → Alternatives
The 7pm slot is pre-seeded as full. The agent will offer 6:30pm or 8:15pm alternatives, plus waitlist.

### 3. FAQ Multitasking
> "Do you have gluten-free options? Also, where do I park?"

Agent answers both questions and returns to the reservation flow.

### 4. Persona Switch
Click between Fine Dining, Family, and Sports Bar mid-call to hear the tone change instantly.

## Customization

### Adding a New Persona

Edit `backend/app/personas.py`:

```python
PERSONA_STYLES["your_persona"] = {
    "name": "Your Restaurant",
    "restaurant_type": "your style",
    "style_guidelines": "...",
    "default_policies": {...}
}
```

### Changing Restaurant Config

Edit the `DEMO_RESTAURANT` dict in:
- `backend/app/routers/sessions.py`
- `backend/app/routers/websocket.py`

### Adding Voice Options

Voices are defined in PersonaPlex. See their repo for available embeddings.

## Simulation Mode

If PersonaPlex isn't running, the system falls back to simulation mode:
- Uses text input instead of voice
- Generates contextual responses
- Full extraction and state machine still works

This is useful for UI development and testing.

## Production Deployment

### Docker

```bash
docker-compose up -d
```

### Manual

1. Use PostgreSQL instead of SQLite
2. Set up HTTPS/WSS with proper certificates
3. Configure Twilio for real SMS
4. Set `DEBUG=false`
5. Use proper secrets management

## Safety & Privacy

- Demo banner always visible
- No audio storage by default
- Phone numbers masked in logs
- Content filtering for inappropriate requests
- Rate limiting on sessions

## Tech Stack

- **Frontend**: React 18, TypeScript, Tailwind CSS, Framer Motion
- **Backend**: FastAPI, SQLAlchemy, WebSockets
- **Voice**: NVIDIA PersonaPlex (Moshi-based)
- **Database**: SQLite (demo) / PostgreSQL (prod)

## License

MIT License - See LICENSE file

## Credits

- [NVIDIA PersonaPlex](https://github.com/NVIDIA/personaplex)
- [Moshi](https://github.com/kyutai-labs/moshi)
