"""Main FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import sessions_router, reservations_router, websocket_router
from app.seed_data import seed_demo_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Restaurant Receptionist API...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Seed demo data
    await seed_demo_data()
    logger.info("Demo data seeded")
    
    yield
    
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="PersonaPlex Restaurant Receptionist API",
    description="Backend API for the AI-powered restaurant reservation system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions_router)
app.include_router(reservations_router)
app.include_router(websocket_router)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "PersonaPlex Restaurant Receptionist API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "sessions": "/sessions",
            "reservations": "/reservations",
            "websocket": "/ws/sessions/{session_id}/audio",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    import httpx
    
    # Actually check if PersonaPlex is reachable
    personaplex_status = False
    personaplex_error = None
    
    if settings.personaplex_host:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Try to connect to PersonaPlex server
                protocol = "https" if settings.personaplex_use_ssl else "http"
                url = f"{protocol}://{settings.personaplex_host}:{settings.personaplex_port}"
                response = await client.get(url, follow_redirects=True)
                personaplex_status = response.status_code < 500
        except Exception as e:
            personaplex_error = str(type(e).__name__)
    
    return {
        "status": "healthy",
        "personaplex_configured": bool(settings.personaplex_host),
        "personaplex_running": personaplex_status,
        "personaplex_error": personaplex_error,
        "twilio_configured": bool(settings.twilio_account_sid),
        "mode": "live" if personaplex_status else "simulation"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
