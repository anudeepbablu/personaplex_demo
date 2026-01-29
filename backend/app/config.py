"""Configuration settings for the restaurant receptionist backend."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # PersonaPlex Server
    personaplex_host: str = "localhost"
    personaplex_port: int = 8998
    personaplex_use_ssl: bool = True
    
    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./restaurant.db"
    
    # Twilio (optional)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    
    # HuggingFace
    hf_token: str = ""
    
    @property
    def personaplex_ws_url(self) -> str:
        protocol = "wss" if self.personaplex_use_ssl else "ws"
        return f"{protocol}://{self.personaplex_host}:{self.personaplex_port}/api/chat"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
