"""API routers package."""
from app.routers.sessions import router as sessions_router
from app.routers.reservations import router as reservations_router
from app.routers.websocket import router as websocket_router
from app.routers.menu import router as menu_router

__all__ = ["sessions_router", "reservations_router", "websocket_router", "menu_router"]
